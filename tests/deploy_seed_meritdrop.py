"""Deploy a fresh MeritDrop and seed a demo board with real GEN.

Every campaign is opened with one shared, short deadline. Entries land inside
that window, then the run waits the deadline out, because the contract refuses
to score a campaign before its deadline. Two campaigns are then scored (one
with a claimed share), a third is left open with its deadline already behind it
so the steward can press the button and watch the evaluation run on the live
contract, and a fourth records one round against a link that cannot resolve,
which is where the post-deadline repair path shows up on chain.

Evaluation fetches every entry's proof link, so the evidence here is real files
served from the project repository.

Prints the new contract address for the frontend and the README.
Run: .venv/bin/gltest --network studionet tests/deploy_seed_meritdrop.py -v -s
"""

import time

from gltest import get_accounts, get_contract_factory
from gltest.assertions import tx_execution_succeeded

GEN = 10**18

RAW = "https://raw.githubusercontent.com/DikaCream/MeritDrop/main"
EVIDENCE_README = f"{RAW}/README.md"
EVIDENCE_SOURCE = f"{RAW}/contracts/merit_drop.py"
EVIDENCE_DIRECT = f"{RAW}/tests/direct/test_merit_drop.py"
EVIDENCE_INTEGRATION = f"{RAW}/tests/integration/test_merit_drop.py"

CRITERIA_DOCS = (
    "The fetched evidence must be a readable file from the project repository. It "
    "has to name the project and show what the budget pays for. A page that does "
    "not mention the project, or that cannot be read, counts as a failure."
)
CRITERIA_TESTS = (
    "The fetched evidence must be a readable Python test file from the project "
    "repository. Accept it when the file defines test functions that exercise "
    "the contract, which is what real test code looks like. A file that cannot "
    "be read, or that shows no test functions at all, counts as a failure."
)
CRITERIA_DEAD = (
    "The fetched evidence must be a readable file from the project repository "
    "describing the settlement rules. A page that cannot be read counts as a "
    "failure."
)

# A reserved TLD, so this host cannot resolve and the fetch really fails.
DEAD_URL = "https://no-such-proof-link-9f8a7b6c.invalid/work"
CRITERIA_OPEN = (
    "The fetched evidence must be a readable file from the project repository "
    "that documents the contract's rules. A page that cannot be read counts as a "
    "failure."
)


# The window has to stay open long enough for every open and submit below, and
# then the run waits for the deadline because scoring is gated behind it.
WINDOW_LEAD = 200
DEADLINE_PAD = 20


def _window():
    now = int(time.time())
    return now - 86400, now + WINDOW_LEAD


def _wait_for_deadline(closes_at):
    """The chain owns the clock, so wait the deadline out instead of faking it."""
    remaining = closes_at + DEADLINE_PAD - time.time()
    if remaining > 0:
        print(f"waiting {remaining:.0f}s for the deadline to pass...")
        time.sleep(remaining)


def _open(contract, title, criteria, budget, cap, opens_at, closes_at):
    receipt = contract.open_campaign(
        args=[title, criteria, opens_at, closes_at, cap]
    ).transact(value=budget, wait_interval=5000, wait_retries=30)
    assert tx_execution_succeeded(receipt), receipt


def _submit(contract, who, cid, title, url, note):
    receipt = (
        contract.connect(who)
        .submit_proof(args=[cid, title, url, note])
        .transact(wait_interval=5000, wait_retries=30)
    )
    assert tx_execution_succeeded(receipt), receipt


def _evaluate(contract, cid):
    receipt = contract.evaluate(args=[cid]).transact(
        wait_interval=5000, wait_retries=50
    )
    assert tx_execution_succeeded(receipt), receipt
    c = contract.get_campaign(args=[cid]).call()
    assert c["status"] == "SCORED", f"campaign {cid} did not close: {c}"
    return c


def test_deploy_and_seed():
    accounts = get_accounts()
    sponsor, one, two = accounts[0], accounts[1], accounts[2]

    factory = get_contract_factory("MeritDrop")
    contract = factory.deploy(account=sponsor)
    address = contract.address
    print(f"\nNEW CONTRACT ADDRESS: {address}\n")

    # One shared window for every campaign, so the run waits the deadline out
    # exactly once. The contract refuses to score until it has passed.
    opens_at, closes_at = _window()

    # ------------------------------------------------------------ campaign 1
    _open(
        contract,
        "Documentation translation sprint",
        CRITERIA_DOCS,
        GEN,
        GEN * 4 // 10,
        opens_at,
        closes_at,
    )
    _submit(
        contract,
        one,
        1,
        "Project README",
        EVIDENCE_README,
        "The README states what the project does and links the repository. It is the "
        "page a new contributor reads first.",
    )
    _submit(
        contract,
        two,
        1,
        "Contract source with the allocation rules",
        EVIDENCE_SOURCE,
        "The contract source documents how the budget is held in escrow and split by "
        "score, including the per-claim ceiling.",
    )

    # ------------------------------------------------------------ campaign 2
    _open(
        contract,
        "Test coverage evidence",
        CRITERIA_TESTS,
        GEN * 3 // 2,
        GEN // 2,
        opens_at,
        closes_at,
    )
    _submit(
        contract,
        one,
        2,
        "Direct test suite",
        EVIDENCE_DIRECT,
        "The local VM suite asserts the window guards, the one-time evaluation, and "
        "the payout ceiling.",
    )
    _submit(
        contract,
        two,
        2,
        "StudioNet integration suite",
        EVIDENCE_INTEGRATION,
        "The integration suite asserts the same guards against the real consensus "
        "path on StudioNet.",
    )
    # ------------------------------------------------------------ campaign 3
    _open(
        contract,
        "Cross-VM contract patterns",
        CRITERIA_OPEN,
        GEN,
        GEN // 2,
        opens_at,
        closes_at,
    )
    _submit(
        contract,
        one,
        3,
        "Pattern: hold a budget in escrow",
        EVIDENCE_SOURCE,
        "The source shows the escrow accounting and the guarded withdrawal path.",
    )
    _submit(
        contract,
        two,
        3,
        "Pattern: published criteria before entries",
        EVIDENCE_README,
        "The README explains why the criteria are frozen in the same transaction "
        "that funds the campaign.",
    )

    # ------------------------------------------------------------ campaign 4
    # A link that cannot resolve. The round has to record the attempt, move no
    # money, and leave the campaign open inside its repair window.
    _open(
        contract,
        "Docs mirror",
        CRITERIA_DEAD,
        GEN,
        GEN * 4 // 10,
        opens_at,
        closes_at,
    )
    _submit(
        contract,
        one,
        4,
        "Mirrored copy of the rules",
        DEAD_URL,
        "A mirror of the settlement rules that should be reachable but is not.",
    )

    # The gate is on the live contract too: scoring before the deadline fails.
    receipt = contract.evaluate(args=[1]).transact(
        wait_interval=5000, wait_retries=20
    )
    assert not tx_execution_succeeded(receipt), (
        "a campaign was scored before its deadline"
    )
    assert contract.get_campaign(args=[1]).call()["status"] == "OPEN"
    print("campaign 1: scoring refused while the window was still open")

    _wait_for_deadline(closes_at)

    _evaluate(contract, 1)
    print("campaign 1 scored by the validators: OK")
    _evaluate(contract, 2)
    print("campaign 2 scored by the validators: OK")

    receipt = contract.evaluate(args=[4]).transact(
        wait_interval=5000, wait_retries=50
    )
    assert tx_execution_succeeded(receipt), receipt
    c4 = contract.get_campaign(args=[4]).call()
    assert c4["status"] == "OPEN", "an unreadable link scored the campaign"
    assert int(c4["unreadable_rounds"]) == 1
    print("campaign 4: evidence unreadable, recorded an attempt and stayed open")

    # ------------------------------------------- claim one already-scored share
    entries = contract.list_entries(args=[1, 0, 10]).call()
    ranked = sorted(entries, key=lambda e: -int(e["allocation"]))
    if ranked and int(ranked[0]["allocation"]) > 0:
        who = one if int(ranked[0]["id"]) == 1001 else two
        receipt = (
            contract.connect(who)
            .claim(args=[int(ranked[0]["id"])])
            .transact(wait_interval=5000, wait_retries=30)
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
    for cid in (1, 2, 3, 4):
        c = contract.get_campaign(args=[cid]).call()
        print(
            f"campaign {cid}: {c['status']} budget={int(c['budget']) / GEN:.2f} "
            f"escrow={int(c['escrow']) / GEN:.4f} entries={int(c['entry_count'])} "
            f"allocated={int(c['allocated']) / GEN:.4f} "
            f"unreadable_rounds={int(c['unreadable_rounds'])}"
        )
        for e in contract.list_entries(args=[cid, 0, 10]).call():
            print(
                f"   #{int(e['id'])} {e['status']} evidence={e['evidence_status']} "
                f"score={int(e['score_bp']) / 10000:.2f} "
                f"alloc={int(e['allocation']) / GEN:.4f} claimed={e['claimed']}"
            )

    print(f"\nUSE THIS ADDRESS: {address}\n")
