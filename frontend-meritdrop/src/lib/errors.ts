/** Turn any wallet, RPC, or contract error into a sentence a human can act on. */
export function describeError(e: unknown): string {
  if (e == null) return "Something went wrong.";
  const anyE = e as any;

  const raw =
    anyE?.shortMessage ??
    anyE?.message ??
    (typeof e === "string" ? e : undefined) ??
    String(e);

  const lower = String(raw).toLowerCase();

  if (lower.includes("user rejected") || lower.includes("user denied"))
    return "You rejected the request in your wallet.";
  if (lower.includes("unrecognized chain") || lower.includes("4902"))
    return "Add the GenLayer StudioNet network to your wallet, then try again.";
  if (
    lower.includes("insufficient funds") ||
    lower.includes("exceeds") ||
    lower.includes("balance")
  )
    return "Not enough GEN in the connected wallet for this action.";
  if (
    lower.includes("failed to fetch") ||
    lower.includes("network") ||
    lower.includes("connection")
  )
    return "Could not reach GenLayer StudioNet. The network may be busy, try again in a moment.";
  if (lower.includes("timeout") || lower.includes("timed out"))
    return "The transaction took too long to confirm. Check the explorer before retrying.";

  // ---- contract guards, in the order a caller runs into them ----------
  if (lower.includes("send the campaign budget"))
    return "Attach the campaign budget in GEN to the transaction.";
  if (lower.includes("criteria: 1-2000")) return "Criteria must be 1 to 2000 characters.";
  if (lower.includes("title: 1-200")) return "Title must be 1 to 200 characters.";
  if (lower.includes("proof_url: 1-500"))
    return "A proof link is required, up to 500 characters.";
  if (lower.includes("note: 1-2000")) return "The note must be 1 to 2000 characters.";
  if (lower.includes("closes_at must be after"))
    return "The closing time has to come after the opening time.";
  if (lower.includes("below the 0.001 gen floor"))
    return "The per-claim ceiling must be at least 0.001 GEN.";
  if (lower.includes("cannot exceed the budget"))
    return "The per-claim ceiling cannot be larger than the budget.";
  if (lower.includes("campaign not found"))
    return "That campaign does not exist on this contract.";
  if (lower.includes("closed for entries"))
    return "This campaign is closed. Entries stop as soon as it has been scored.";
  if (lower.includes("has not opened yet"))
    return "The submission window has not opened yet.";
  if (lower.includes("window has closed"))
    return "The submission window for this campaign has closed.";
  if (lower.includes("already entered this campaign"))
    return "This wallet has already entered this campaign. One entry per campaign.";
  if (lower.includes("campaign is full"))
    return "This campaign has reached its entry limit.";
  if (lower.includes("already been scored"))
    return "This campaign has already been scored. Scores are written once.";
  if (lower.includes("no entries to score"))
    return "There is nothing to score yet. Wait for the first entries.";
  if (lower.includes("score every entry exactly once"))
    return "The validators did not cover every entry. Nothing moved, try again.";
  if (lower.includes("fell outside 0-1"))
    return "The validators returned a score outside 0 to 1. Nothing moved.";
  if (lower.includes("unreadable output"))
    return "The validators returned output the contract could not read. Nothing moved.";
  if (lower.includes("has not been scored yet"))
    return "This entry has not been scored yet.";
  if (lower.includes("already been claimed"))
    return "This share has already been claimed.";
  if (lower.includes("only the contributor"))
    return "Only the contributor who submitted this entry can claim it.";
  if (lower.includes("not allocated anything"))
    return "This entry fell below the merit bar, so there is nothing to claim.";
  if (lower.includes("escrow cannot cover"))
    return "The escrow cannot cover this claim. Nothing moved.";
  if (lower.includes("only the sponsor"))
    return "Only the sponsor who opened this campaign can reclaim.";
  if (lower.includes("window is still open"))
    return "Wait until the submission window closes before reclaiming.";
  if (lower.includes("already reclaimed"))
    return "The unallocated funds were already reclaimed.";
  if (lower.includes("nothing left to reclaim"))
    return "Everything in this campaign was allocated, so there is nothing to reclaim.";

  return raw.length > 220 ? `${raw.slice(0, 220)}…` : raw;
}
