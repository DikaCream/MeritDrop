# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""MeritDrop: an airdrop that pays for work instead of luck.

A sponsor opens a campaign with public criteria and locks a GEN budget in
escrow. Contributors submit proof of work before the window closes. Anyone
can then trigger the evaluation: every validator runs the same prompt over
the same entries, and the scores only stand once consensus is reached
through the comparative equivalence principle. The budget is split in
proportion to score, capped by the campaign's per-claim ceiling. Each
contributor claims their own share. The sponsor can only take back the part
the evaluators never allocated.

Entry ids are composite: campaign 3's first entry is 3001. That keeps a
campaign's entries addressable without a second index structure.
"""
from genlayer import *
from dataclasses import dataclass
import datetime
import json

# ---------------------------------------------------------------- statuses
OPEN = "OPEN"
SCORED = "SCORED"

# --------------------------------------------------------------- constants
GEN_ONE = 10 ** 18
MIN_PER_CLAIM = GEN_ONE // 1000      # 0.001 GEN
MERIT_BAR_BP = 3000                  # 0.30 on a 0-10000 basis-point scale
MAX_SCORE_BP = 10000
MAX_REASON_CHARS = 500
MAX_ENTRIES_PER_CAMPAIGN = 50
ENTRY_STRIDE = 1000                  # entry ids are campaign_id * 1000 + index

MAX_TITLE = 200
MAX_CRITERIA = 2000
MAX_NOTE = 2000
MAX_PROOF_URL = 500

# ------------------------------------------------------------- data models
@allow_storage
@dataclass
class Campaign:
    id: u256
    sponsor: Address
    title: str
    criteria: str
    opens_at: u256
    closes_at: u256
    budget: u256
    escrow: u256
    max_per_claim: u256
    allocated: u256
    claimed: u256
    entry_count: u256
    status: str
    reclaimed: bool
    created_at: u256


@allow_storage
@dataclass
class Entry:
    id: u256
    campaign_id: u256
    contributor: Address
    title: str
    proof_url: str
    note: str
    status: str
    score_bp: u256
    reasoning: str
    allocation: u256
    claimed: bool
    created_at: u256


# --------------------------------------------------------------- events
class CampaignOpened(gl.Event):
    def __init__(self, campaign_id: u256, sponsor: Address, budget: u256, /, **blob): ...


class ProofSubmitted(gl.Event):
    def __init__(self, entry_id: u256, campaign_id: u256, contributor: Address, /, **blob): ...


class EntryScored(gl.Event):
    def __init__(self, entry_id: u256, score_bp: u256, allocation: u256, /, **blob): ...


class CampaignScored(gl.Event):
    def __init__(self, campaign_id: u256, allocated: u256, entries: u256, /, **blob): ...


class ShareClaimed(gl.Event):
    def __init__(self, entry_id: u256, contributor: Address, amount: u256, /, **blob): ...


class UnallocatedReclaimed(gl.Event):
    def __init__(self, campaign_id: u256, sponsor: Address, amount: u256, /, **blob): ...


# ---------------------------------------------------------------- payouts
@gl.evm.contract_interface
class _NativeRecipient:
    class View:
        pass

    class Write:
        pass


# =====================================================================
class MeritDrop(gl.Contract):
    campaigns: TreeMap[u256, Campaign]
    entries: TreeMap[u256, Entry]
    next_campaign_id: u256
    next_entry_id: u256
    total_escrow: u256
    total_allocated: u256
    total_claimed: u256

    def __init__(self):
        self.next_campaign_id = u256(1)
        self.next_entry_id = u256(1)
        self.total_escrow = u256(0)
        self.total_allocated = u256(0)
        self.total_claimed = u256(0)

    # ------------------------------------------------------------- clock
    def _now(self) -> int:
        raw = gl.message_raw.get("datetime")
        if raw is None:
            return 0
        try:
            return int(
                datetime.datetime.fromisoformat(
                    raw.replace("Z", "+00:00")
                ).timestamp()
            )
        except Exception:
            return 0

    # -------------------------------------------------------- open a campaign
    @gl.public.write.payable
    def open_campaign(
        self,
        title: str,
        criteria: str,
        opens_at: u256,
        closes_at: u256,
        max_per_claim: u256,
    ) -> u256:
        """Lock the budget in escrow and publish the criteria everyone is judged on."""
        budget = int(gl.message.value)
        if budget <= 0:
            raise gl.vm.UserError("send the campaign budget with the transaction")
        if len(title) == 0 or len(title) > MAX_TITLE:
            raise gl.vm.UserError("title: 1-200 chars")
        if len(criteria) == 0 or len(criteria) > MAX_CRITERIA:
            raise gl.vm.UserError("criteria: 1-2000 chars")
        if int(closes_at) <= int(opens_at):
            raise gl.vm.UserError("closes_at must be after opens_at")
        if int(max_per_claim) < MIN_PER_CLAIM:
            raise gl.vm.UserError("max_per_claim is below the 0.001 GEN floor")
        if int(max_per_claim) > budget:
            raise gl.vm.UserError("max_per_claim cannot exceed the budget")

        cid = u256(int(self.next_campaign_id))
        self.next_campaign_id = u256(int(cid) + 1)
        self.total_escrow = u256(int(self.total_escrow) + budget)
        self.campaigns[cid] = Campaign(
            id=cid,
            sponsor=gl.message.sender_address,
            title=title,
            criteria=criteria,
            opens_at=opens_at,
            closes_at=closes_at,
            budget=u256(budget),
            escrow=u256(budget),
            max_per_claim=max_per_claim,
            allocated=u256(0),
            claimed=u256(0),
            entry_count=u256(0),
            status=OPEN,
            reclaimed=False,
            created_at=u256(self._now()),
        )
        CampaignOpened(cid, gl.message.sender_address, u256(budget)).emit()
        return cid

    # ----------------------------------------------------- submit proof of work
    @gl.public.write
    def submit_proof(
        self, campaign_id: u256, title: str, proof_url: str, note: str
    ) -> u256:
        """Enter the campaign once. The window decides whether you are in time."""
        c = self._campaign(campaign_id)
        if c.status != OPEN:
            raise gl.vm.UserError("this campaign is closed for entries")
        now = self._now()
        if now < int(c.opens_at):
            raise gl.vm.UserError("the submission window has not opened yet")
        if now > int(c.closes_at):
            raise gl.vm.UserError("the submission window has closed")
        if len(title) == 0 or len(title) > MAX_TITLE:
            raise gl.vm.UserError("title: 1-200 chars")
        if len(proof_url) == 0 or len(proof_url) > MAX_PROOF_URL:
            raise gl.vm.UserError("proof_url: 1-500 chars")
        if len(note) == 0 or len(note) > MAX_NOTE:
            raise gl.vm.UserError("note: 1-2000 chars")
        if int(c.entry_count) >= MAX_ENTRIES_PER_CAMPAIGN:
            raise gl.vm.UserError("this campaign is full")

        who = gl.message.sender_address
        cid = int(campaign_id)
        for k in range(1, int(c.entry_count) + 1):
            existing = self.entries[u256(cid * ENTRY_STRIDE + k)]
            if existing.contributor == who:
                raise gl.vm.UserError("this wallet already entered this campaign")

        index = int(c.entry_count) + 1
        eid = u256(cid * ENTRY_STRIDE + index)
        self.entries[eid] = Entry(
            id=eid,
            campaign_id=campaign_id,
            contributor=who,
            title=title,
            proof_url=proof_url,
            note=note,
            status=OPEN,
            score_bp=u256(0),
            reasoning="",
            allocation=u256(0),
            claimed=False,
            created_at=u256(now),
        )
        c.entry_count = u256(index)
        self.next_entry_id = u256(int(self.next_entry_id) + 1)
        ProofSubmitted(eid, campaign_id, who).emit()
        return eid

    # ------------------------------------------------ evaluate (validator-backed)
    @gl.public.write
    def evaluate(self, campaign_id: u256) -> None:
        """Score every entry against the published criteria.

        Any caller may trigger this. The scores come from the validators
        running the same prompt and agreeing through the comparative
        equivalence principle, never from the caller. A campaign is scored
        exactly once, and only the AI produces a score: there is no path in
        this contract that lets a caller set one by hand.
        """
        c = self._campaign(campaign_id)
        if c.status != OPEN:
            raise gl.vm.UserError("this campaign has already been scored")
        count = int(c.entry_count)
        if count == 0:
            raise gl.vm.UserError("this campaign has no entries to score")
        budget = int(c.budget)
        if budget <= 0:
            raise gl.vm.UserError("this campaign has no budget")

        cid = int(campaign_id)
        ids = []
        context_parts = []
        for k in range(1, count + 1):
            eid = cid * ENTRY_STRIDE + k
            e = self.entries[u256(eid)]
            ids.append(eid)
            context_parts.append(
                f"#{eid} | {e.title}\nProof: {e.proof_url}\nWhat they did: {e.note}"
            )
        context = "\n---\n".join(context_parts)

        prompt = (
            "You are the evaluator for an airdrop that pays people for work. "
            "Score every entry from 0 to 1 against the campaign criteria below. "
            "Reward work that is finished, specific, and verifiable from the stated "
            "proof. Give low scores to vague claims, unrelated submissions, and "
            "promises about future work. Return STRICT JSON only, no prose, no "
            "markdown fences: an object mapping every entry id to its score, of the "
            'form {"<id>": {"score": <float 0-1>, "reasoning": "<str>"}}. '
            "One entry per id, every id exactly once. Be strict.\n"
            "Campaign criteria:\n" + c.criteria + "\n"
            "Entries:\n" + context
        )

        def do_score() -> str:
            # Text format on purpose: the raw model text crosses the WASM
            # boundary as a string (calldata-safe). Parsing the JSON here keeps
            # floats inside the VM and re-serialises into the canonical string.
            try:
                raw = gl.nondet.exec_prompt(prompt)
            except Exception:
                raw = None
            if isinstance(raw, str):
                start = raw.find("{")
                end = raw.rfind("}")
                if start >= 0 and end > start:
                    raw = raw[start : end + 1]
                try:
                    data = json.loads(raw)
                except Exception:
                    data = {"error": "unparseable"}
            elif raw is None:
                data = {"error": "unparseable"}
            else:
                data = raw
            return json.dumps(data, sort_keys=True)

        principle = (
            "Both answers score the same entries against the same campaign criteria. "
            "They are equivalent if and only if both cover exactly the same entry ids, "
            "both agree on whether each entry is at or above the merit bar (0.30) or "
            "below it, and neither gives a score outside 0-1. The exact scores and the "
            "reasoning text may differ slightly. Error objects are equivalent only to "
            "other error objects."
        )

        result = gl.eq_principle.prompt_comparative(do_score, principle)
        try:
            evaluations = json.loads(str(result))
        except Exception:
            raise gl.vm.UserError("the evaluators returned unreadable output")

        self._allocate(c, campaign_id, ids, evaluations, budget)

    # ------------------------------------------------------- internal allocate
    def _allocate(
        self,
        c: Campaign,
        campaign_id: u256,
        ids: list,
        evaluations: dict,
        budget: int,
    ) -> None:
        if not isinstance(evaluations, dict) or len(evaluations) != len(ids):
            raise gl.vm.UserError("the evaluators must score every entry exactly once")

        wanted = set(ids)
        scores: dict[int, tuple] = {}
        for key_raw, ev in evaluations.items():
            try:
                eid = int(key_raw)
            except Exception:
                raise gl.vm.UserError("the evaluators returned unreadable output")
            if eid in scores or eid not in wanted:
                raise gl.vm.UserError("the evaluators returned unreadable output")
            if not isinstance(ev, dict):
                raise gl.vm.UserError("the evaluators returned unreadable output")
            try:
                raw = float(ev.get("score"))
            except Exception:
                raise gl.vm.UserError("the evaluators returned unreadable output")
            if raw != raw or raw < 0.0 or raw > 1.0:
                raise gl.vm.UserError("an AI score fell outside 0-1")
            bp = int(round(raw * MAX_SCORE_BP))
            if bp < 0 or bp > MAX_SCORE_BP:
                raise gl.vm.UserError("an AI score fell outside 0-1")
            scores[eid] = (bp, str(ev.get("reasoning", ""))[:MAX_REASON_CHARS])

        total_bp = 0
        for eid in ids:
            bp, _ = scores[eid]
            if bp >= MERIT_BAR_BP:
                total_bp += bp

        cap = int(c.max_per_claim)
        remaining = int(c.escrow)
        allocated_total = 0

        for eid in ids:
            e = self.entries[u256(eid)]
            bp, reasoning = scores[eid]
            allocation = 0
            if total_bp > 0 and bp >= MERIT_BAR_BP:
                share = budget * bp // total_bp
                share = min(share, cap)        # never above the per-claim ceiling
                share = min(share, remaining)  # never above what is still held
                allocation = share
            e.score_bp = u256(bp)
            e.reasoning = reasoning
            e.allocation = u256(allocation)
            e.status = SCORED
            remaining -= allocation
            allocated_total += allocation
            EntryScored(u256(eid), u256(bp), u256(allocation)).emit()

        c.allocated = u256(allocated_total)
        c.status = SCORED
        self.total_allocated = u256(int(self.total_allocated) + allocated_total)
        CampaignScored(campaign_id, u256(allocated_total), u256(len(ids))).emit()

    # ---------------------------------------------------------------- claim
    @gl.public.write
    def claim(self, entry_id: u256) -> None:
        """Contributors withdraw their own share, once."""
        e = self._entry(entry_id)
        if e.status != SCORED:
            raise gl.vm.UserError("this entry has not been scored yet")
        if e.claimed:
            raise gl.vm.UserError("this share has already been claimed")
        if gl.message.sender_address != e.contributor:
            raise gl.vm.UserError("only the contributor can claim this share")
        amount = int(e.allocation)
        if amount <= 0:
            raise gl.vm.UserError("this entry was not allocated anything")

        c = self._campaign(e.campaign_id)
        if amount > int(c.escrow):
            raise gl.vm.UserError("the escrow cannot cover this claim")

        e.claimed = True
        c.escrow = u256(int(c.escrow) - amount)
        c.claimed = u256(int(c.claimed) + amount)
        self.total_escrow = u256(int(self.total_escrow) - amount)
        self.total_claimed = u256(int(self.total_claimed) + amount)
        _NativeRecipient(e.contributor).emit_transfer(value=u256(amount))
        ShareClaimed(entry_id, e.contributor, u256(amount)).emit()

    # ------------------------------------------------- take back the leftovers
    @gl.public.write
    def reclaim_unallocated(self, campaign_id: u256) -> None:
        """The sponsor withdraws only what the evaluators never allocated.

        Money that was allocated stays reserved for its contributor, so a late
        claim can still be paid.
        """
        c = self._campaign(campaign_id)
        if c.status != SCORED:
            raise gl.vm.UserError("this campaign has not been scored")
        if c.reclaimed:
            raise gl.vm.UserError("the unallocated funds were already reclaimed")
        if gl.message.sender_address != c.sponsor:
            raise gl.vm.UserError("only the sponsor can reclaim")
        if self._now() < int(c.closes_at):
            raise gl.vm.UserError("the submission window is still open")

        reserved = int(c.allocated) - int(c.claimed)
        leftover = int(c.escrow) - reserved
        if leftover <= 0:
            raise gl.vm.UserError("there is nothing left to reclaim")

        c.reclaimed = True
        c.escrow = u256(int(c.escrow) - leftover)
        self.total_escrow = u256(int(self.total_escrow) - leftover)
        _NativeRecipient(c.sponsor).emit_transfer(value=u256(leftover))
        UnallocatedReclaimed(campaign_id, c.sponsor, u256(leftover)).emit()

    # ---------------------------------------------------------------- views
    @gl.public.view
    def get_campaign(self, campaign_id: u256) -> dict:
        return self._campaign_dict(self._campaign(campaign_id))

    @gl.public.view
    def list_campaigns(self, offset: u256, limit: u256) -> list:
        out = []
        total = int(self.next_campaign_id) - 1
        start = max(int(offset), 1)
        end = min(start + int(limit), total + 1)
        for i in range(start, end):
            out.append(self._campaign_dict(self.campaigns[u256(i)]))
        return out

    @gl.public.view
    def get_entry(self, entry_id: u256) -> dict:
        return self._entry_dict(self._entry(entry_id))

    @gl.public.view
    def list_entries(self, campaign_id: u256, offset: u256, limit: u256) -> list:
        c = self._campaign(campaign_id)
        count = int(c.entry_count)
        start = max(int(offset), 1)
        end = min(start + int(limit), count + 1)
        out = []
        cid = int(campaign_id)
        for k in range(start, end):
            out.append(self._entry_dict(self.entries[u256(cid * ENTRY_STRIDE + k)]))
        return out

    @gl.public.view
    def get_stats(self) -> dict:
        return {
            "campaigns": int(self.next_campaign_id) - 1,
            "entries": int(self.next_entry_id) - 1,
            "escrow": int(self.total_escrow),
            "allocated": int(self.total_allocated),
            "claimed": int(self.total_claimed),
        }

    # -------------------------------------------------------------- internal
    def _campaign_dict(self, c: Campaign) -> dict:
        return {
            "id": int(c.id),
            "sponsor": c.sponsor.as_hex,
            "title": c.title,
            "criteria": c.criteria,
            "opens_at": int(c.opens_at),
            "closes_at": int(c.closes_at),
            "budget": int(c.budget),
            "escrow": int(c.escrow),
            "max_per_claim": int(c.max_per_claim),
            "allocated": int(c.allocated),
            "claimed": int(c.claimed),
            "entry_count": int(c.entry_count),
            "status": c.status,
            "reclaimed": c.reclaimed,
            "created_at": int(c.created_at),
        }

    def _entry_dict(self, e: Entry) -> dict:
        return {
            "id": int(e.id),
            "campaign_id": int(e.campaign_id),
            "contributor": e.contributor.as_hex,
            "title": e.title,
            "proof_url": e.proof_url,
            "note": e.note,
            "status": e.status,
            "score_bp": int(e.score_bp),
            "reasoning": e.reasoning,
            "allocation": int(e.allocation),
            "claimed": e.claimed,
            "created_at": int(e.created_at),
        }

    def _campaign(self, campaign_id: u256) -> Campaign:
        cid = int(campaign_id)
        if cid < 1 or cid >= int(self.next_campaign_id):
            raise gl.vm.UserError("campaign not found")
        return self.campaigns[campaign_id]

    def _entry(self, entry_id: u256) -> Entry:
        eid = int(entry_id)
        cid, index = eid // ENTRY_STRIDE, eid % ENTRY_STRIDE
        if cid < 1 or index < 1:
            raise gl.vm.UserError("entry not found")
        c = self._campaign(u256(cid))
        if index > int(c.entry_count):
            raise gl.vm.UserError("entry not found")
        return self.entries[entry_id]
