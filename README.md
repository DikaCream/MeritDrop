# MeritDrop: paid for work, not for luck

An airdrop contract on GenLayer. A sponsor locks the budget in escrow and
publishes the criteria next to it. Contributors submit proof of finished work.
AI validators score every entry against those criteria and reach consensus
before anything is written. The budget then splits by score, capped per claim,
and each contributor withdraws their own share. Nobody types a number in by
hand, and the sponsor can only take back what was never allocated.

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
   only while the window is open. The note is what the validators read, so
   vague entries score badly.
3. **Evaluate.** `evaluate` is open to any caller, but the contract is not the
   judge. Each validator runs the same scoring prompt over the same entries and
   the round only stands when the answers agree on which entries clear the
   merit bar. The score and the reasoning are written to the chain together.
4. **Claim and reclaim.** Every entry at or above the bar takes a share
   proportional to its score, capped by the per-claim ceiling. Contributors
   call `claim` for their own entry. Whatever the evaluators never allocated
   goes back to the sponsor through `reclaim_unallocated`, and only once the
   window has closed.

### What the contract refuses

- A score typed in by hand. The only scoring path runs through the validators,
  so no caller can set one.
- A second evaluation. A campaign is scored exactly once, so a share cannot be
  allocated twice.
- An entry the validators skipped, or a score referring to an entry that was
  never submitted. Both revert with nothing moved.
- A score outside 0 to 1, or output the contract cannot read.
- A share above the per-claim ceiling, or above what the escrow still holds.
- Claiming a share that belongs to someone else, or claiming it twice.
- A sponsor draining allocated money. `reclaim_unallocated` can only touch the
  part the evaluators never allocated, so a late claim is always payable.

## On-chain

| | |
|---|---|
| Network | GenLayer StudioNet |
| Contract | [`0xcb56f0D3D801664f940cA2380B42cfd22B426689`](https://explorer-studio.genlayer.com/address/0xcb56f0D3D801664f940cA2380B42cfd22B426689) |
| Contract source | [`contracts/merit_drop.py`](contracts/merit_drop.py) |
| Live state | 4 campaigns, 8 entries, 3 campaigns scored by the validators, 2.6 GEN allocated, 0.9 GEN claimed |

Three campaigns are already scored. Their entries carry real validator scores,
the reasoning behind each one, and the share that score earned. Two of those
shares have been claimed, so the escrow figure has already moved. The fourth
campaign is open with two entries waiting, which is what the evaluation button
on the live app is for.

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
  1 all revert with zero GEN moved. 43 tests.
- **Integration** (`tests/integration/test_merit_drop.py`) deploys to StudioNet
  and exercises the real consensus path: open, two entries, validator-backed
  evaluation, claim, plus the one-time evaluation revert and the frozen entry
  list afterwards.

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
- Scores are stored as basis points (0 to 10000) so the allocation math never
  touches a float. The model's raw score is parsed inside the VM for the same
  reason: floats do not survive the boundary in a way the runner can trust.
- Opening a campaign is payable. Every other write reverts if you attach value.
