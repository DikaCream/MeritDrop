"""Deploy a fresh MeritDrop and seed a demo board with real GEN.

Creates three campaigns: two already scored by the validators (one with a
claimed share) and one left open so the steward can press the button and
watch the evaluation run on the live contract.

Prints the new contract address for the frontend and the README.
Run: .venv/bin/gltest --network studionet tests/deploy_seed_meritdrop.py -v -s
"""

import time

from gltest import get_accounts, get_contract_factory
from gltest.assertions import tx_execution_succeeded

GEN = 10**18

CRITERIA_DOCS = (
    "Ship a merged pull request that improves GenLayer documentation or translates "
    "it. Link the pull request and describe in one sentence what a reader can now "
    "do that they could not do before."
)
CRITERIA_FIX = (
    "Ship a merged pull request that fixes a real bug in an open source GenLayer "
    "project. Link the commit and the issue it closes."
)
CRITERIA_SDK = (
    "Publish a runnable example that shows a GenLayer SDK feature together with a "
    "passing test. Link the repository or the pull request."
)


def _window(days=30):
    now = int(time.time())
    return now - 86400, now + days * 86400


def _open(contract, title, criteria, budget, cap):
    opens_at, closes_at = _window()
    receipt = contract.open_campaign(
        args=[title, criteria, opens_at, closes_at, cap]
    ).transact(value=budget, wait_interval=10000, wait_retries=20)
    assert tx_execution_succeeded(receipt), receipt


def _submit(contract, who, cid, title, url, note):
    receipt = (
        contract.connect(who)
        .submit_proof(args=[cid, title, url, note])
        .transact(wait_interval=10000, wait_retries=20)
    )
    assert tx_execution_succeeded(receipt), receipt


def test_deploy_and_seed():
    accounts = get_accounts()
    sponsor, one, two = accounts[0], accounts[1], accounts[2]

    factory = get_contract_factory("MeritDrop")
    contract = factory.deploy(account=sponsor)
    address = contract.address
    print(f"\nNEW CONTRACT ADDRESS: {address}\n")

    # ------------------------------------------------------------ campaign 1
    _open(contract, "Documentation translation sprint", CRITERIA_DOCS, GEN, GEN * 4 // 10)
    _submit(
        contract,
        one,
        1,
        "Translate the validator guide",
        "https://github.com/genlayer/docs/pull/482",
        "Translated the whole validator guide and added a glossary. The pull request is merged.",
    )
    _submit(
        contract,
        two,
        1,
        "Rewrite the settlement walkthrough",
        "https://github.com/genlayer/docs/pull/490",
        "Rewrote the settlement walkthrough around a worked example. Merged.",
    )
    receipt = contract.evaluate(args=[1]).transact(wait_interval=10000, wait_retries=40)
    assert tx_execution_succeeded(receipt), receipt
    print("campaign 1 scored by the validators: OK")

    # ------------------------------------------------------------ campaign 2
    _open(contract, "Bug fix bounty", CRITERIA_FIX, GEN, GEN * 4 // 10)
    _submit(
        contract,
        one,
        2,
        "Fix the retry counter in the JS client",
        "https://github.com/genlayer/sdk-js/pull/41",
        "An off-by-one in the retry counter meant the last attempt never fired. "
        "Added a regression test in the same pull request.",
    )
    _submit(
        contract,
        two,
        2,
        "Patch the address comparison in the explorer",
        "https://github.com/genlayer/explorer/pull/18",
        "The checksum comparison ignored case, so valid addresses were rejected. Fixed and merged.",
    )
    receipt = contract.evaluate(args=[2]).transact(wait_interval=10000, wait_retries=40)
    assert tx_execution_succeeded(receipt), receipt
    print("campaign 2 scored by the validators: OK")

    # ------------------------------------------------------------ campaign 3
    _open(contract, "SDK example repository", CRITERIA_SDK, GEN * 3 // 2, GEN // 2)
    _submit(
        contract,
        one,
        3,
        "Deterministic test harness example",
        "https://github.com/genlayer/examples/pull/23",
        "A runnable example showing how to write and run a deterministic test against "
        "a contract. CI is green.",
    )
    _submit(
        contract,
        two,
        3,
        "Example: reading contract state from a script",
        "https://github.com/genlayer/examples/pull/27",
        "A small script that reads a deployed contract and prints its state, with a test.",
    )

    # ------------------------------------------- claim one already-scored share
    entries = contract.list_entries(args=[1, 0, 10]).call()
    ranked = sorted(entries, key=lambda e: -int(e["allocation"]))
    if ranked and int(ranked[0]["allocation"]) > 0:
        who = one if int(ranked[0]["id"]) == 1001 else two
        receipt = (
            contract.connect(who)
            .claim(args=[int(ranked[0]["id"])])
            .transact(wait_interval=10000, wait_retries=20)
        )
        assert tx_execution_succeeded(receipt), receipt
        print(f"claim on #{int(ranked[0]['id'])}: OK")

    stats = contract.get_stats(args=[]).call()
    print(
        f"\nSTATS: campaigns={stats['campaigns']} entries={stats['entries']} "
        f"escrow={int(stats['escrow']) / GEN:.4f} GEN "
        f"allocated={int(stats['allocated']) / GEN:.4f} GEN "
        f"claimed={int(stats['claimed']) / GEN:.4f} GEN"
    )
    for cid in (1, 2, 3):
        c = contract.get_campaign(args=[cid]).call()
        print(
            f"campaign {cid}: {c['status']} budget={int(c['budget']) / GEN:.2f} "
            f"escrow={int(c['escrow']) / GEN:.4f} entries={int(c['entry_count'])} "
            f"allocated={int(c['allocated']) / GEN:.4f}"
        )
        for e in contract.list_entries(args=[cid, 0, 10]).call():
            print(
                f"   #{int(e['id'])} {e['status']} "
                f"score={int(e['score_bp']) / 10000:.2f} "
                f"alloc={int(e['allocation']) / GEN:.4f} claimed={e['claimed']}"
            )

    print(f"\nUSE THIS ADDRESS: {address}\n")
