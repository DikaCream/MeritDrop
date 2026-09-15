"""Direct-mode tests for MeritDrop, the airdrop that pays for work.

Scoring only happens through the validator-backed path: evaluate() runs the
prompt on the validators (mocked here as the model response) and the contract
enforces a single bounded score per entry, a one-time evaluation per campaign,
allocations capped by the per-claim ceiling, and claims restricted to the
contributor. Scores come back as strings in the mocks because the direct-mode
WASI stub encodes model responses through calldata, which does not carry
floats (the real network has no such limit).

The direct VM starts from wall-clock time, so each test pins the block clock
explicitly before touching a submission window.
"""
import datetime
import json

from tests.direct.conftest import to_hex, set_time

GEN = 10 ** 18
BUDGET = 10 * GEN
CAP = 2 * GEN

BASE = "2030-01-01T00:00:00Z"
T_AFTER = "2030-03-01T00:00:00Z"
T_BEFORE = "2029-11-01T00:00:00Z"


def ts(iso):
    return int(datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


OPEN_AT = ts("2029-12-01T00:00:00Z")
CLOSE_AT = ts("2030-02-01T00:00:00Z")

AI_PROMPT = r"You are the evaluator for an airdrop"
CRITERIA = "Ship a merged pull request that fixes a documented bug and link the commit."


def eid(cid, k):
    return cid * 1000 + k


def must_revert(fn):
    try:
        fn()
    except Exception:
        return
    assert False, "expected this call to revert"


def _open(contract, vm, sponsor, budget=BUDGET, cap=CAP, clock=BASE):
    set_time(clock)
    vm.sender = sponsor
    vm.value = budget
    cid = int(contract.open_campaign("Docs sprint", CRITERIA, OPEN_AT, CLOSE_AT, cap))
    vm.value = 0
    return cid


def _enter(contract, vm, who, cid, title="Entry", url="https://example.com/pr/1"):
    vm.sender = who
    return int(
        contract.submit_proof(cid, title, url, "Merged the fix and linked the commit.")
    )


def _score(vm, mapping):
    """AI response object; scores as strings (calldata-safe in direct mode)."""
    vm.mock_llm(AI_PROMPT, json.dumps(mapping))


def _marks(*pairs):
    return {str(i): {"score": s, "reasoning": "looked at the proof"} for i, s in pairs}


# ============================================================= open campaign
def test_open_campaign_locks_the_budget(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    c = contract.get_campaign(cid)
    assert cid == 1
    assert c["status"] == "OPEN"
    assert c["budget"] == BUDGET
    assert c["escrow"] == BUDGET
    assert c["allocated"] == 0
    assert c["entry_count"] == 0
    assert c["sponsor"].lower() == to_hex(direct_alice).lower()
    assert contract.get_stats()["escrow"] == BUDGET


def test_open_campaign_reverts_without_budget(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/merit_drop.py")
    direct_vm.sender = direct_alice
    direct_vm.value = 0
    must_revert(lambda: contract.open_campaign("T", CRITERIA, OPEN_AT, CLOSE_AT, CAP))


def test_open_campaign_reverts_empty_criteria(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/merit_drop.py")
    direct_vm.sender = direct_alice
    direct_vm.value = BUDGET
    must_revert(lambda: contract.open_campaign("T", "", OPEN_AT, CLOSE_AT, CAP))


def test_open_campaign_reverts_window_backwards(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/merit_drop.py")
    direct_vm.sender = direct_alice
    direct_vm.value = BUDGET
    must_revert(lambda: contract.open_campaign("T", CRITERIA, CLOSE_AT, OPEN_AT, CAP))


def test_open_campaign_reverts_cap_above_budget(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/merit_drop.py")
    direct_vm.sender = direct_alice
    direct_vm.value = BUDGET
    must_revert(
        lambda: contract.open_campaign("T", CRITERIA, OPEN_AT, CLOSE_AT, BUDGET * 2)
    )


def test_open_campaign_reverts_cap_below_floor(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/merit_drop.py")
    direct_vm.sender = direct_alice
    direct_vm.value = BUDGET
    must_revert(lambda: contract.open_campaign("T", CRITERIA, OPEN_AT, CLOSE_AT, 1))


# ============================================================== submit proof
def test_submit_proof_creates_entry(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e = _enter(contract, direct_vm, direct_bob, cid)

    assert e == eid(cid, 1)
    entry = contract.get_entry(e)
    assert entry["status"] == "OPEN"
    assert entry["score_bp"] == 0
    assert entry["allocation"] == 0
    assert entry["claimed"] is False
    assert entry["contributor"].lower() == to_hex(direct_bob).lower()
    assert contract.get_campaign(cid)["entry_count"] == 1


def test_submit_reverts_after_the_window_closes(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice, clock=T_AFTER)
    must_revert(lambda: _enter(contract, direct_vm, direct_bob, cid))


def test_submit_reverts_before_the_window_opens(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice, clock=T_BEFORE)
    must_revert(lambda: _enter(contract, direct_vm, direct_bob, cid))


def test_submit_reverts_for_the_same_wallet_twice(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    _enter(contract, direct_vm, direct_bob, cid)
    must_revert(lambda: _enter(contract, direct_vm, direct_bob, cid, url="https://x/2"))
    assert contract.get_campaign(cid)["entry_count"] == 1


def test_submit_reverts_without_a_proof_url(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    must_revert(lambda: _enter(contract, direct_vm, direct_bob, cid, url=""))


def test_submit_reverts_on_a_missing_campaign(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/merit_drop.py")
    must_revert(lambda: _enter(contract, direct_vm, direct_bob, 7))


# ================================================================ evaluation
def test_evaluate_scores_and_allocates(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e = _enter(contract, direct_vm, direct_bob, cid)

    _score(direct_vm, _marks((e, "0.85")))
    contract.evaluate(cid)

    entry = contract.get_entry(e)
    assert entry["status"] == "SCORED"
    assert entry["score_bp"] == 8500
    assert entry["allocation"] > 0
    assert entry["allocation"] <= CAP
    assert len(entry["reasoning"]) > 0
    c = contract.get_campaign(cid)
    assert c["status"] == "SCORED"
    assert c["allocated"] == entry["allocation"]


def test_evaluate_below_the_merit_bar_pays_nothing(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e = _enter(contract, direct_vm, direct_bob, cid)

    _score(direct_vm, _marks((e, "0.2")))
    contract.evaluate(cid)

    entry = contract.get_entry(e)
    assert entry["status"] == "SCORED"
    assert entry["score_bp"] == 2000
    assert entry["allocation"] == 0
    assert contract.get_campaign(cid)["allocated"] == 0


def test_evaluate_splits_in_proportion_to_score(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice, budget=9 * GEN, cap=9 * GEN)
    e1 = _enter(contract, direct_vm, direct_bob, cid, "Strong", "https://example.com/a")
    e2 = _enter(
        contract, direct_vm, direct_charlie, cid, "Weaker", "https://example.com/b"
    )

    _score(direct_vm, _marks((e1, "0.9"), (e2, "0.3")))
    contract.evaluate(cid)

    a1 = contract.get_entry(e1)["allocation"]
    a2 = contract.get_entry(e2)["allocation"]
    assert a1 > a2 > 0
    assert a1 == 9 * GEN * 9000 // 12000
    assert a2 == 9 * GEN * 3000 // 12000


def test_evaluate_by_a_stranger_still_uses_validator_scores(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """Anyone may trigger the evaluation, but the score is the validators',
    so a stranger can neither force a payout nor deny one."""
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e = _enter(contract, direct_vm, direct_bob, cid)

    direct_vm.sender = direct_charlie
    _score(direct_vm, _marks((e, "0.6")))
    contract.evaluate(cid)

    entry = contract.get_entry(e)
    assert entry["score_bp"] == 6000
    assert entry["allocation"] > 0


def test_evaluate_is_one_time(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e = _enter(contract, direct_vm, direct_bob, cid)

    _score(direct_vm, _marks((e, "0.9")))
    contract.evaluate(cid)
    before = contract.get_entry(e)["allocation"]
    assert before > 0

    direct_vm.clear_mocks()
    _score(direct_vm, _marks((e, "0.9")))
    must_revert(lambda: contract.evaluate(cid))

    assert contract.get_entry(e)["allocation"] == before
    assert contract.get_campaign(cid)["allocated"] == before


def test_evaluate_reverts_with_no_entries(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    must_revert(lambda: contract.evaluate(cid))
    assert contract.get_campaign(cid)["status"] == "OPEN"


def test_submit_reverts_once_scored(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e = _enter(contract, direct_vm, direct_bob, cid)
    _score(direct_vm, _marks((e, "0.9")))
    contract.evaluate(cid)
    must_revert(lambda: _enter(contract, direct_vm, direct_charlie, cid))


# ================================================== rejection: bad AI output
def test_evaluate_reverts_on_malformed_output(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e = _enter(contract, direct_vm, direct_bob, cid)

    direct_vm.mock_llm(AI_PROMPT, "the model rambled instead of answering")
    must_revert(lambda: contract.evaluate(cid))

    entry = contract.get_entry(e)
    assert entry["status"] == "OPEN"
    assert entry["allocation"] == 0
    assert contract.get_campaign(cid)["status"] == "OPEN"
    assert contract.get_stats()["escrow"] == BUDGET


def test_evaluate_reverts_on_score_above_one(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e = _enter(contract, direct_vm, direct_bob, cid)

    _score(direct_vm, _marks((e, "1.5")))
    must_revert(lambda: contract.evaluate(cid))

    assert contract.get_entry(e)["status"] == "OPEN"
    assert contract.get_entry(e)["allocation"] == 0
    assert contract.get_campaign(cid)["status"] == "OPEN"


def test_evaluate_reverts_on_negative_score(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e = _enter(contract, direct_vm, direct_bob, cid)

    _score(direct_vm, _marks((e, "-0.1")))
    must_revert(lambda: contract.evaluate(cid))

    assert contract.get_entry(e)["status"] == "OPEN"
    assert contract.get_campaign(cid)["allocated"] == 0


def test_evaluate_reverts_on_a_score_for_an_entry_that_was_not_submitted(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e = _enter(contract, direct_vm, direct_bob, cid)

    _score(direct_vm, _marks((e + 1, "0.9")))
    must_revert(lambda: contract.evaluate(cid))

    assert contract.get_entry(e)["status"] == "OPEN"
    assert contract.get_campaign(cid)["status"] == "OPEN"


def test_evaluate_reverts_when_an_entry_is_skipped(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e1 = _enter(contract, direct_vm, direct_bob, cid, "A", "https://example.com/a")
    e2 = _enter(contract, direct_vm, direct_charlie, cid, "B", "https://example.com/b")

    _score(direct_vm, _marks((e1, "0.9")))
    must_revert(lambda: contract.evaluate(cid))

    assert contract.get_entry(e1)["status"] == "OPEN"
    assert contract.get_entry(e2)["status"] == "OPEN"
    assert contract.get_campaign(cid)["allocated"] == 0


def test_evaluate_reverts_when_an_unsubmitted_entry_rides_along(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e1 = _enter(contract, direct_vm, direct_bob, cid, "A", "https://example.com/a")
    _enter(contract, direct_vm, direct_charlie, cid, "B", "https://example.com/b")

    # e1 + 1 is the second entry; e1 + 5 never existed.
    _score(direct_vm, _marks((e1, "0.9"), (e1 + 5, "0.9")))
    must_revert(lambda: contract.evaluate(cid))

    assert contract.get_campaign(cid)["allocated"] == 0


# ======================================================= there is no manual path
def test_no_manual_scoring_path_exists(direct_vm, direct_deploy, direct_alice):
    """The scoring path cannot be short-circuited: no call sets a score by hand."""
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    must_revert(lambda: contract.score_entries(cid, ["1001"], ["0.99"]))
    must_revert(lambda: contract.set_score(cid, 1001, "0.99"))


# ==================================================================== claims
def test_claim_pays_the_contributor(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e = _enter(contract, direct_vm, direct_bob, cid)

    _score(direct_vm, _marks((e, "0.9")))
    contract.evaluate(cid)

    share = contract.get_entry(e)["allocation"]
    direct_vm.sender = direct_bob
    contract.claim(e)

    entry = contract.get_entry(e)
    assert entry["claimed"] is True
    c = contract.get_campaign(cid)
    assert c["claimed"] == share
    assert c["escrow"] == BUDGET - share
    stats = contract.get_stats()
    assert stats["claimed"] == share
    assert stats["escrow"] == BUDGET - share


def test_claim_reverts_for_a_stranger(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e = _enter(contract, direct_vm, direct_bob, cid)
    _score(direct_vm, _marks((e, "0.9")))
    contract.evaluate(cid)

    direct_vm.sender = direct_charlie
    must_revert(lambda: contract.claim(e))
    assert contract.get_entry(e)["claimed"] is False


def test_claim_reverts_twice(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e = _enter(contract, direct_vm, direct_bob, cid)
    _score(direct_vm, _marks((e, "0.9")))
    contract.evaluate(cid)

    direct_vm.sender = direct_bob
    contract.claim(e)
    paid = contract.get_campaign(cid)["claimed"]
    must_revert(lambda: contract.claim(e))
    assert contract.get_campaign(cid)["claimed"] == paid


def test_claim_reverts_before_scoring(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e = _enter(contract, direct_vm, direct_bob, cid)

    direct_vm.sender = direct_bob
    must_revert(lambda: contract.claim(e))


def test_claim_reverts_with_no_allocation(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e = _enter(contract, direct_vm, direct_bob, cid)

    _score(direct_vm, _marks((e, "0.1")))
    contract.evaluate(cid)

    direct_vm.sender = direct_bob
    must_revert(lambda: contract.claim(e))
    assert contract.get_campaign(cid)["claimed"] == 0


# ==================================================================== ceilings
def test_allocation_is_capped_by_the_per_claim_ceiling(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """A perfect score cannot outrun the campaign's own ceiling."""
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice, budget=10 * GEN, cap=2 * GEN)
    e = _enter(contract, direct_vm, direct_bob, cid)

    _score(direct_vm, _marks((e, "1.0")))
    contract.evaluate(cid)

    assert contract.get_entry(e)["allocation"] == 2 * GEN
    assert contract.get_campaign(cid)["allocated"] == 2 * GEN
    assert contract.get_stats()["escrow"] == 10 * GEN


def test_allocations_together_never_exceed_the_budget(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = direct_deploy("contracts/merit_drop.py")
    budget = 6 * GEN
    cid = _open(contract, direct_vm, direct_alice, budget=budget, cap=budget)
    e1 = _enter(contract, direct_vm, direct_bob, cid, "A", "https://example.com/a")
    e2 = _enter(contract, direct_vm, direct_charlie, cid, "B", "https://example.com/b")

    _score(direct_vm, _marks((e1, "1.0"), (e2, "1.0")))
    contract.evaluate(cid)

    a1 = contract.get_entry(e1)["allocation"]
    a2 = contract.get_entry(e2)["allocation"]
    assert a1 + a2 == budget
    assert a1 <= budget and a2 <= budget
    assert contract.get_stats()["allocated"] == budget


def test_scores_above_the_bar_share_only_among_themselves(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """A below-bar entry takes nothing and does not dilute the others."""
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice, budget=5 * GEN, cap=5 * GEN)
    e1 = _enter(contract, direct_vm, direct_bob, cid, "A", "https://example.com/a")
    e2 = _enter(contract, direct_vm, direct_charlie, cid, "B", "https://example.com/b")

    _score(direct_vm, _marks((e1, "0.8"), (e2, "0.1")))
    contract.evaluate(cid)

    assert contract.get_entry(e1)["allocation"] == 5 * GEN
    assert contract.get_entry(e2)["allocation"] == 0


# ============================================================= reclaim the rest
def test_reclaim_returns_only_what_was_never_allocated(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice, budget=10 * GEN, cap=2 * GEN)
    e1 = _enter(contract, direct_vm, direct_bob, cid, "A", "https://example.com/a")
    e2 = _enter(contract, direct_vm, direct_charlie, cid, "B", "https://example.com/b")

    _score(direct_vm, _marks((e1, "1.0"), (e2, "1.0")))
    contract.evaluate(cid)
    assert contract.get_campaign(cid)["allocated"] == 4 * GEN

    set_time(T_AFTER)
    direct_vm.sender = direct_alice
    contract.reclaim_unallocated(cid)

    c = contract.get_campaign(cid)
    assert c["reclaimed"] is True
    assert c["escrow"] == 4 * GEN          # still reserved for the two contributors
    assert contract.get_stats()["escrow"] == 4 * GEN


def test_a_claim_does_not_change_what_the_sponsor_can_reclaim(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice, budget=10 * GEN, cap=2 * GEN)
    e1 = _enter(contract, direct_vm, direct_bob, cid, "A", "https://example.com/a")
    e2 = _enter(contract, direct_vm, direct_charlie, cid, "B", "https://example.com/b")

    _score(direct_vm, _marks((e1, "1.0"), (e2, "1.0")))
    contract.evaluate(cid)

    direct_vm.sender = direct_bob
    contract.claim(e1)

    set_time(T_AFTER)
    direct_vm.sender = direct_alice
    contract.reclaim_unallocated(cid)

    c = contract.get_campaign(cid)
    assert c["escrow"] == 2 * GEN          # the other contributor can still claim
    direct_vm.sender = direct_charlie
    contract.claim(e2)
    assert contract.get_campaign(cid)["escrow"] == 0


def test_reclaim_reverts_for_a_stranger(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e = _enter(contract, direct_vm, direct_bob, cid)
    _score(direct_vm, _marks((e, "0.1")))
    contract.evaluate(cid)

    set_time(T_AFTER)
    direct_vm.sender = direct_bob
    must_revert(lambda: contract.reclaim_unallocated(cid))


def test_reclaim_reverts_before_scoring(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice, clock=T_AFTER)
    direct_vm.sender = direct_alice
    must_revert(lambda: contract.reclaim_unallocated(cid))


def test_reclaim_reverts_while_the_window_is_open(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e = _enter(contract, direct_vm, direct_bob, cid)
    _score(direct_vm, _marks((e, "1.0")))
    contract.evaluate(cid)

    direct_vm.sender = direct_alice
    must_revert(lambda: contract.reclaim_unallocated(cid))


def test_reclaim_reverts_twice(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice)
    e = _enter(contract, direct_vm, direct_bob, cid)
    _score(direct_vm, _marks((e, "1.0")))
    contract.evaluate(cid)

    set_time(T_AFTER)
    direct_vm.sender = direct_alice
    contract.reclaim_unallocated(cid)
    must_revert(lambda: contract.reclaim_unallocated(cid))


def test_reclaim_reverts_when_exactly_everything_was_allocated(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = direct_deploy("contracts/merit_drop.py")
    budget = 4 * GEN
    cid = _open(contract, direct_vm, direct_alice, budget=budget, cap=budget)
    e1 = _enter(contract, direct_vm, direct_bob, cid, "A", "https://example.com/a")
    e2 = _enter(contract, direct_vm, direct_charlie, cid, "B", "https://example.com/b")

    _score(direct_vm, _marks((e1, "0.5"), (e2, "0.5")))
    contract.evaluate(cid)
    assert contract.get_campaign(cid)["allocated"] == budget

    set_time(T_AFTER)
    direct_vm.sender = direct_alice
    must_revert(lambda: contract.reclaim_unallocated(cid))


# ======================================================================= views
def test_list_campaigns_and_entries(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid1 = _open(contract, direct_vm, direct_alice)
    cid2 = _open(contract, direct_vm, direct_bob)
    _enter(contract, direct_vm, direct_charlie, cid1, "First", "https://example.com/1")
    _enter(contract, direct_vm, direct_alice, cid1, "Second", "https://example.com/2")

    campaigns = contract.list_campaigns(0, 10)
    assert len(campaigns) == 2
    assert campaigns[0]["id"] == cid1
    assert campaigns[1]["id"] == cid2

    entries = contract.list_entries(cid1, 0, 10)
    assert len(entries) == 2
    assert entries[0]["title"] == "First"
    assert entries[1]["title"] == "Second"
    assert entries[0]["id"] == eid(cid1, 1)

    assert contract.list_entries(cid2, 0, 10) == []


def test_stats_track_the_whole_board(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = direct_deploy("contracts/merit_drop.py")
    cid = _open(contract, direct_vm, direct_alice, budget=6 * GEN, cap=3 * GEN)
    e1 = _enter(contract, direct_vm, direct_bob, cid, "A", "https://example.com/a")
    e2 = _enter(contract, direct_vm, direct_charlie, cid, "B", "https://example.com/b")

    _score(direct_vm, _marks((e1, "1.0"), (e2, "1.0")))
    contract.evaluate(cid)

    direct_vm.sender = direct_bob
    contract.claim(e1)

    stats = contract.get_stats()
    assert stats["campaigns"] == 1
    assert stats["entries"] == 2
    assert stats["allocated"] == 6 * GEN
    assert stats["claimed"] == 3 * GEN
    assert stats["escrow"] == 3 * GEN
