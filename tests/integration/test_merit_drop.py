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
    "The evidence must be a real, readable file from the project repository. It "
    "has to mention the project name MeritDrop and show what the project does. A "
    "page that does not mention the project, or that cannot be read, counts as a "
    "failure."
)

# Real public files, so the validators fetch the artifact itself rather than a
# description of it. A host that cannot resolve gives the unreadable case.
RAW = "https://raw.githubusercontent.com/DikaCream/MeritDrop/main"
EVIDENCE_README = f"{RAW}/README.md"
EVIDENCE_SOURCE = f"{RAW}/contracts/merit_drop.py"
DEAD_URL = "https://no-such-proof-link-9f8a7b6c.invalid/work"


# Scoring is gated behind the deadline, and a live chain's clock cannot be
# fast-forwarded, so each campaign here opens with a short window, takes its
# entries inside it, and waits the deadline out before asking for a score.
WINDOW_LEAD = 90  # seconds the submission window stays open
DEADLINE_PAD = 15  # how far past the deadline to wait before scoring


def _window(lead=WINDOW_LEAD):
    now = int(time.time())
    return now - 86400, now + lead


def _await_deadline(closes_at):
    """Wait for the chain's deadline to pass rather than assuming it has."""
    remaining = closes_at + DEADLINE_PAD - time.time()
    if remaining > 0:
        time.sleep(remaining)


def _deploy(account):
    factory = get_contract_factory("MeritDrop")
    contract = factory.deploy(account=account)

    stats = contract.get_stats(args=[]).call()
    assert int(stats["campaigns"]) == 0
    assert int(stats["entries"]) == 0
    assert int(stats["escrow"]) == 0
    return contract


def _open(contract, title):
    """Open a campaign and return the deadline it will close at."""
    opens_at, closes_at = _window()
    receipt = contract.open_campaign(
        args=[title, CRITERIA, opens_at, closes_at, CAP],
    ).transact(value=BUDGET, wait_interval=5000, wait_retries=20)
    assert tx_execution_succeeded(receipt)
    return closes_at


@pytest.mark.integration
def test_campaign_lifecycle_end_to_end():
    accounts = get_accounts()
    sponsor, one, two = accounts[0], accounts[1], accounts[2]
    contract = _deploy(account=sponsor)

    closes_at = _open(contract, "Docs translation sprint")

    campaign = contract.get_campaign(args=[1]).call()
    assert campaign["status"] == "OPEN"
    assert int(campaign["budget"]) == BUDGET
    assert int(campaign["escrow"]) == BUDGET
    assert int(campaign["closes_at"]) == closes_at
    assert campaign["sponsor"].lower() == sponsor.address.lower()

    # Two contributors enter before the window closes.
    receipt = (
        contract.connect(one)
        .submit_proof(
            args=[
                1,
                "Project README",
                EVIDENCE_README,
                "The repository README says what MeritDrop does and links the repo.",
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
                "Contract source",
                EVIDENCE_SOURCE,
                "The contract source documents the escrow and allocation rules.",
            ]
        )
        .transact(wait_interval=10000, wait_retries=15)
    )
    assert tx_execution_succeeded(receipt)

    entries = contract.list_entries(args=[1, 0, 10]).call()
    assert len(entries) == 2
    assert all(e["status"] == "OPEN" for e in entries)
    assert [int(e["id"]) for e in entries] == [1001, 1002]

    # The gate is real here, not just in the mocked VM: while the window is
    # still open, the same call the steward would make is refused.
    receipt = contract.evaluate(args=[1]).transact(
        wait_interval=5000, wait_retries=20
    )
    assert not tx_execution_succeeded(receipt)
    campaign = contract.get_campaign(args=[1]).call()
    assert campaign["status"] == "OPEN"
    assert int(campaign["allocated"]) == 0
    entries = contract.list_entries(args=[1, 0, 10]).call()
    assert all(e["status"] == "OPEN" for e in entries)

    _await_deadline(closes_at)

    # Score the whole campaign through the validator-backed AI path.
    receipt = contract.evaluate(args=[1]).transact(
        wait_interval=5000, wait_retries=40
    )
    assert tx_execution_succeeded(receipt)

    scored = contract.list_entries(args=[1, 0, 10]).call()
    assert all(e["status"] == "SCORED" for e in scored)
    assert all(
        e["evidence_status"] == "READ" for e in scored
    ), "a readable link was reported as unreadable"
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

    closes_at = _open(contract, "Bug fix bounty")

    receipt = (
        contract.connect(one)
        .submit_proof(
            args=[
                1,
                "Project README",
                EVIDENCE_README,
                "The repository README says what MeritDrop does and links the repo.",
            ]
        )
        .transact(wait_interval=5000, wait_retries=20)
    )
    assert tx_execution_succeeded(receipt)

    _await_deadline(closes_at)

    receipt = contract.evaluate(args=[1]).transact(
        wait_interval=5000, wait_retries=40
    )
    assert tx_execution_succeeded(receipt)

    # A second evaluation must not double-allocate.
    before = contract.get_campaign(args=[1]).call()
    receipt = contract.evaluate(args=[1]).transact(
        wait_interval=5000, wait_retries=20
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
                EVIDENCE_SOURCE,
                "Submitted after the results were published.",
            ]
        )
        .transact(wait_interval=5000, wait_retries=20)
    )
    assert not tx_execution_succeeded(receipt)
    assert len(contract.list_entries(args=[1, 0, 10]).call()) == 1


@pytest.mark.integration
def test_a_link_nobody_can_read_does_not_close_the_campaign():
    """A proof nobody can fetch must not become a score of zero.

    The validators really attempt this host and really fail, which is the only
    honest way to prove the behaviour end to end: the campaign stays open, the
    attempt is recorded, and not a single GEN moves.
    """
    accounts = get_accounts()
    sponsor, one = accounts[0], accounts[1]
    contract = _deploy(account=sponsor)
    closes_at = _open(contract, "Docs translation sprint")

    receipt = (
        contract.connect(one)
        .submit_proof(
            args=[1, "Gone", DEAD_URL, "The link should be reachable but is not."]
        )
        .transact(wait_interval=5000, wait_retries=20)
    )
    assert tx_execution_succeeded(receipt)

    _await_deadline(closes_at)

    receipt = contract.evaluate(args=[1]).transact(
        wait_interval=5000, wait_retries=40
    )
    assert tx_execution_succeeded(receipt)

    campaign = contract.get_campaign(args=[1]).call()
    assert campaign["status"] == "OPEN", "an unreadable link scored the campaign"
    assert int(campaign["allocated"]) == 0
    assert int(campaign["unreadable_rounds"]) == 1
    assert int(campaign["last_attempt_at"]) > 0

    entry = contract.get_entry(args=[1001]).call()
    assert entry["status"] == "OPEN"
    assert entry["evidence_status"] == "UNREADABLE"
    assert int(entry["allocation"]) == 0

    stats = contract.get_stats(args=[]).call()
    assert int(stats["escrow"]) == BUDGET
    assert int(stats["allocated"]) == 0
    assert int(stats["claimed"]) == 0

    # The retry window is real: the next attempt cannot run immediately.
    receipt = contract.evaluate(args=[1]).transact(
        wait_interval=5000, wait_retries=20
    )
    assert not tx_execution_succeeded(receipt)
    after = contract.get_campaign(args=[1]).call()
    assert int(after["unreadable_rounds"]) == 1
    assert int(contract.get_stats(args=[]).call()["allocated"]) == 0
