# MeritDrop: paid for work, not for luck

An airdrop contract on GenLayer. A sponsor locks the budget in escrow and
publishes the criteria next to it. Contributors submit proof of finished work.
Once the deadline passes, AI validators fetch each entry's proof link
themselves, grade the evidence against those criteria, and reach consensus on
that grade before anything is written. The budget then splits by grade, capped
per claim, and each contributor withdraws their own share. Nobody types a number
in by hand, and the sponsor can only take back what was never allocated.

Live app: https://meritdrop.vercel.app

## Why it exists

Most airdrops hand out tokens based on a snapshot, a lottery, or a list
somebody wrote in private. The rule is never published and the reasoning never
explains itself. MeritDrop makes the criteria part of the contract, runs the
scoring through validators instead of an admin, and stores the reasoning next
to every score. The settlement math is plain arithmetic over those scores, so
you can check the payout yourself.

## How it works

1. **Open a campaign.** `open_campaign` takes the title, the criteria, the
   submission window, and the per-claim ceiling, and the budget travels with
   the transaction. From that point the money sits in escrow and the criteria
   cannot be changed.
2. **Submit proof.** `submit_proof` records a title, a link to the work, and a
   note explaining what the link shows. One entry per wallet per campaign, and
   only while the window is open. The link has to be a public http URL, because
   it is what the validators will open.
3. **Evaluate.** `evaluate` is open to any caller, but only after the deadline:
   the window is what fixes the list of entries, so scoring early would settle a
   payout against work that had not arrived yet. The contract is not the judge
   either. Each validator fetches every entry's proof link, grades what the link
   serves against the criteria, and the round only stands when the answers agree
   on the evidence status of every entry and on the grade of every entry. The
   note a contributor writes is a claim, not proof: a page that does not show
   the work fails no matter how confident the note sounds. The grade and the
   reasoning are written to the chain together.
4. **Claim and reclaim.** Every entry at or above the bar takes a share
   proportional to its grade, capped by the per-claim ceiling. Contributors
   call `claim` for their own entry. Whatever the evaluators never allocated
   goes back to the sponsor through `reclaim_unallocated`, and only once the
   window has closed.

### The five grades

The payout is arithmetic over basis points, so agreement has to cover the number
the payout is computed from. Agreeing only that two answers sit on the same side
of the merit bar would leave the payout resting on a figure one validator
reported and the other did not.

So the prompt names five grades (0, 0.25, 0.5, 0.75, 1.0) and asks for one per
entry. Whatever comes back is snapped to the nearest grade, and the equivalence
principle requires both answers to report the same grade for every entry. A
small difference in judgement collapses onto one figure; a real disagreement
lands on two, and then the round fails consensus without moving any money. The
paying grades are 0.5 and up.

### When the evidence cannot be read

A link that cannot be fetched says nothing about the work behind it, so it never
becomes a grade of zero on its own. The round records the attempt, marks which
links failed, and stops: the campaign stays open and not a single GEN moves. An
hour then has to pass before another attempt, which keeps a burst of clicks from
spending the retries while a host is briefly down.

Repairing the link is bounded. Inside the window an entry can be rewritten
freely. After the deadline the only door left is an entry whose link the
validators already reported as unreadable, it can only be repaired by its own
contributor, and only until the repair window closes a day later. Submissions
never reopen, so no new entry can appear once the window shuts and nobody can
swap in a different link after seeing the competition.

Once three rounds have run with the link still dark, or the repair window
expires, the campaign closes and an entry that could never be checked earns
nothing. A dead link must not be a cheaper way into the pool than work somebody
can verify.

Only the first 6000 characters of each page reach the prompt, so a link should
show its relevant part early. A page whose relevant section sits past that mark
is graded on what the validators actually saw.

### What the contract refuses

- An evaluation before the deadline. The window fixes the entry set, so no
  payout can be decided against a list that is still growing.
- A grade typed in by hand. The only scoring path runs through the validators,
  so no caller can set one.
- A payout from grades nobody agreed on. Both validators have to report the same
  grade for every entry before any money moves.
- A second evaluation. A campaign is scored exactly once, so a share cannot be
  allocated twice.
- An entry the validators skipped, or a score referring to an entry that was
  never submitted. Both revert with nothing moved.
- A score outside 0 to 1, or output the contract cannot read.
- A share above the per-claim ceiling, or above what the escrow still holds.
- Claiming a share that belongs to someone else, or claiming it twice.
- A sponsor draining allocated money. `reclaim_unallocated` can only touch the
  part the evaluators never allocated, so a late claim is always payable.
- A proof link that is not a public http URL. It could never be fetched.
- An unreadable link deciding a campaign on its own. It is recorded as an
  attempt and the campaign stays open.
- A second attempt inside the retry window, and a fourth attempt ever.
- Rewriting a readable entry after the deadline, or a dead one once the repair
  window has closed. The post-deadline repair path exists only for a link the
  validators reported as unreadable, and only for its own contributor.
- Rewriting a judged entry. `revise_proof` stops working the moment the campaign
  is scored, so the record a verdict rests on is final.
- A proof page writing its own score. The fetched text is quoted as untrusted
  input and its fence markers are stripped before it reaches the prompt.

## On-chain

| | |
|---|---|
| Network | GenLayer StudioNet |
| Contract | [`0xc430c7dF330efc7e49664c127a9AdB291ffaB3ae`](https://explorer-studio.genlayer.com/address/0xc430c7dF330efc7e49664c127a9AdB291ffaB3ae) |
| Contract source | [`contracts/merit_drop.py`](contracts/merit_drop.py) |
| Live state | 4 campaigns, 7 entries, 2 campaigns scored by the validators, 1.8 GEN allocated, 0.4 GEN claimed |

Two campaigns are already scored. Their entries carry real validator grades,
the reasoning behind each one, the evidence status the validators reported, and
the share that grade earned. One of those shares has been claimed, so the escrow
figure has already moved.

The third campaign is open with two entries already in and its deadline behind
it, which is what the evaluation button on the live app is for: press it and the
validators grade both entries for real.

The fourth campaign is the other half of the story. Its only entry points at a
host that cannot resolve, one round has already been recorded against it, and
nothing moved. The deadline has passed and the repair window is still open, so
that entry can still be repaired by its contributor. Open it to see the
post-deadline repair path on a live contract.

## Running locally

The frontend is a Vite + React app that reads and writes StudioNet through
[genlayer-js](https://www.npmjs.com/package/genlayer-js) with any injected
wallet.

```bash
cd frontend-meritdrop
npm install
npm run dev
```

Set `VITE_CONTRACT_ADDRESS` to point the app at a different MeritDrop
deployment; the default is the address above.

### Tests

The contract has two layers:

- **Direct mode** (`tests/direct/test_merit_drop.py`) runs the contract in a
  local VM. It covers opening a campaign and the escrow accounting, the
  submission window and the one-entry-per-wallet rule, the AI evaluation with
  the validators mocked, the proportional split, the per-claim ceiling, claims
  restricted to the contributor, and reclaiming the unallocated remainder. The
  rejection proofs are there too: duplicate, stale, and cancelled states,
  skipped entries, foreign entry ids, malformed output, and scores outside 0 to
  1 all revert with zero GEN moved. 59 tests.
- **The deadline gate** has its own section: scoring is refused anywhere inside
  the window including the final second, one second later it is allowed, and the
  boundary is asserted from both sides. Nothing can be claimed or reclaimed
  inside the window either, because a payout cannot exist yet.
- **The bounded repair path after the close** has one too: submissions stay shut,
  only an unreadable link may be repaired, only by its own contributor, the
  repaired link is what gets fetched, a readable entry cannot be swapped after the
  deadline, and the path expires with the repair window.
- **The five grades** get a section as well: scores snap onto the grade grid
  whatever raw float arrives, three different raw answers inside one grade pay
  exactly the same, a lower grade pays a different number, and a source-level
  check reads the contract to confirm the prompt names the five grades, the
  equivalence principle demands the same grade, and the allocation is computed
  from the grade rather than a raw float.
- **Evidence** is the section to read if you only read one. It proves a finalized
  grade rests on a link that answered, that an unreadable link settles nothing and
  leaves the campaign open, that the retry window blocks a second attempt until
  the hour is up and reopens at the boundary, that the retries ending is what lets
  a campaign close with an unreadable entry earning nothing, and that a hostile
  proof page cannot paste its own grade or smuggle its fence markers into the
  prompt.
- **Integration** (`tests/integration/test_merit_drop.py`) deploys to StudioNet
  and exercises the real consensus path. Each campaign opens with a short window,
  takes its entries inside it, and only then waits the deadline out, because a
  live chain's clock cannot be fast-forwarded. The first test also asserts the
  gate from the live side: the same `evaluate` call the steward would make is
  refused while the window is still open. A third test points an entry at a host
  that cannot resolve, so the validators really fail to fetch it, and asserts the
  campaign stayed open with no GEN allocated and the retry window closed.

```bash
# direct (fast, no network)
python -m pytest tests/direct/test_merit_drop.py -v

# on-chain (StudioNet must be reachable)
gltest --network studionet tests/integration/test_merit_drop.py -v -s

# fresh deploy + demo data
gltest --network studionet tests/deploy_seed_meritdrop.py -v -s
```

## Project layout

```
contracts/merit_drop.py             the MeritDrop contract
tests/direct/                       local VM test suite
tests/integration/                  StudioNet integration tests
tests/deploy_seed_meritdrop.py      fresh deploy + demo data seeder
frontend-meritdrop/                 Vite + React app
```

## Notes

- StudioNet GEN is valueless. The settlement logic is the point.
- Entry ids are composite: campaign 3's first entry is 3001. That keeps a
  campaign's entries addressable without a second index structure.
- Grades are stored as basis points (0, 2500, 5000, 7500, 10000) so the
  allocation math never touches a float. The model's raw score is parsed inside
  the VM for the same reason: floats do not survive the boundary in a way the
  runner can trust. Snapping to a grade happens inside the prompt function, so
  the figure that crosses into the comparison is already the one a payout would
  use.
- Opening a campaign is payable. Every other write reverts if you attach value.
