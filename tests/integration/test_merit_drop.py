"""Integration tests for MeritDrop on StudioNet.

Run: gltest --network studionet tests/integration/test_merit_drop.py -v -s

These exercise the real consensus pipeline: a sponsor opens a campaign and
locks the budget in escrow, contributors submit proof, and the contract scores
the whole campaign through the validator-backed AI path (evaluate runs the
prompt on the validators and they reach agreement via the comparative
equivalence principle). The deterministic allocation math and every rejection
path are covered by the fast direct-mode tests.
"""

import time

import pytest
from gltest import get_accounts, get_contract_factory
from gltest.assertions import tx_execution_succeeded

GEN = 10**18
BUDGET = 2 * GEN
CAP = GEN // 2

CRITERIA = (
    "Ship a merged pull request that fixes a documented bug. Link the commit "
    "and say in one sentence what changed."
)


def _window():
    now = int(time.time())
    return now - 86400, now + 30 * 86400


def _deploy(account):
    factory = get_contract_factory("MeritDrop")
    contract = factory.deploy(account=account)

    stats = contract.get_stats(args=[]).call()
    assert int(stats["campaigns"]) == 0
    assert int(stats["entries"]) == 0
    assert int(stats["escrow"]) == 0
    return contract


def _open(contract, title):
    opens_at, closes_at = _window()
    receipt = contract.open_campaign(
        args=[title, CRITERIA, opens_at, closes_at, CAP],
    ).transact(value=BUDGET, wait_interval=10000, wait_retries=15)
    assert tx_execution_succeeded(receipt)


@pytest.mark.integration
def test_campaign_lifecycle_end_to_end():
    accounts = get_accounts()
    sponsor, one, two = accounts[0], accounts[1], accounts[2]
    contract = _deploy(account=sponsor)

    _open(contract, "Docs translation sprint")

    campaign = contract.get_campaign(args=[1]).call()
    assert campaign["status"] == "OPEN"
    assert int(campaign["budget"]) == BUDGET
    assert int(campaign["escrow"]) == BUDGET
    assert campaign["sponsor"].lower() == sponsor.address.lower()

    # Two contributors enter before the window closes.
    receipt = (
        contract.connect(one)
        .submit_proof(
            args=[
                1,
                "Translate the validator guide",
                "https://github.com/example/docs/pull/12",
                "Translated the validator guide and the PR is merged.",
            ]
        )
        .transact(wait_interval=10000, wait_retries=15)
    )
    assert tx_execution_succeeded(receipt)

    receipt = (
        contract.connect(two)
        .submit_proof(
            args=[
                1,
                "Fix the retry bug",
                "https://github.com/example/sdk/pull/48",
                "Found an off-by-one in the retry counter and merged the fix with a regression test.",
            ]
        )
        .transact(wait_interval=10000, wait_retries=15)
    )
    assert tx_execution_succeeded(receipt)

    entries = contract.list_entries(args=[1, 0, 10]).call()
    assert len(entries) == 2
    assert all(e["status"] == "OPEN" for e in entries)
    assert [int(e["id"]) for e in entries] == [1001, 1002]

    # Score the whole campaign through the validator-backed AI path.
    receipt = contract.evaluate(args=[1]).transact(
        wait_interval=10000, wait_retries=40
    )
    assert tx_execution_succeeded(receipt)

    scored = contract.list_entries(args=[1, 0, 10]).call()
    assert all(e["status"] == "SCORED" for e in scored)
    total = 0
    for e in scored:
        bp = int(e["score_bp"])
        assert 0 <= bp <= 10000
        assert int(e["allocation"]) <= CAP
        assert len(str(e["reasoning"])) > 0
        total += int(e["allocation"])

    campaign = contract.get_campaign(args=[1]).call()
    assert campaign["status"] == "SCORED"
    assert int(campaign["allocated"]) == total
    assert total <= BUDGET
    assert int(campaign["escrow"]) == BUDGET

    # A contributor withdraws their own share.
    claimable = next((e for e in scored if int(e["allocation"]) > 0), None)
    if claimable is not None:
        who = one if int(claimable["id"]) == 1001 else two
        receipt = (
            contract.connect(who)
            .claim(args=[int(claimable["id"])])
            .transact(wait_interval=10000, wait_retries=15)
        )
        assert tx_execution_succeeded(receipt)

        pulled = contract.get_entry(args=[int(claimable["id"])]).call()
        assert pulled["claimed"] is True
        campaign = contract.get_campaign(args=[1]).call()
        assert int(campaign["claimed"]) == int(claimable["allocation"])
        assert int(campaign["escrow"]) == BUDGET - int(claimable["allocation"])


@pytest.mark.integration
def test_scoring_is_one_time_and_closes_entry():
    accounts = get_accounts()
    sponsor, one = accounts[0], accounts[1]
    contract = _deploy(account=sponsor)

    _open(contract, "Bug fix bounty")

    receipt = (
        contract.connect(one)
        .submit_proof(
            args=[
                1,
                "Patch the parser",
                "https://github.com/example/core/pull/7",
                "Patched the parser and merged it with a test.",
            ]
        )
        .transact(wait_interval=10000, wait_retries=15)
    )
    assert tx_execution_succeeded(receipt)

    receipt = contract.evaluate(args=[1]).transact(
        wait_interval=10000, wait_retries=40
    )
    assert tx_execution_succeeded(receipt)

    # A second evaluation must not double-allocate.
    before = contract.get_campaign(args=[1]).call()
    receipt = contract.evaluate(args=[1]).transact(
        wait_interval=10000, wait_retries=15
    )
    assert not tx_execution_succeeded(receipt)
    after = contract.get_campaign(args=[1]).call()
    assert int(after["allocated"]) == int(before["allocated"])

    # And a scored campaign takes no new entries.
    receipt = (
        contract.connect(one)
        .submit_proof(
            args=[
                1,
                "Late entry",
                "https://github.com/example/core/pull/9",
                "Submitted after the results were published.",
            ]
        )
        .transact(wait_interval=10000, wait_retries=15)
    )
    assert not tx_execution_succeeded(receipt)
    assert len(contract.list_entries(args=[1, 0, 10]).call()) == 1
