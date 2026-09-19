import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMeritDrop } from "../context/MeritDropContext";
import { EntryRow } from "../components/EntryRow";
import { Campaign as CampaignType, Entry } from "../lib/types";
import { describeError } from "../lib/errors";
import {
  EXPLORER_ADDR,
  MAX_EVIDENCE_ATTEMPTS,
  REPAIR_WINDOW_S,
  SCORE_GRADE_STEP,
  formatDateTime,
  formatGen,
  formatRemaining,
  formatScore,
  shortAddr,
} from "../config";

// Mirrors the contract. Rounds that end without readable evidence are spaced an
// hour apart, a campaign closes after three of them, and a link the validators
// could not read can still be repaired for one day after the deadline.
const EVIDENCE_COOLDOWN_S = 3600;

export function CampaignPage() {
  const { id } = useParams();
  const cid = Number(id);
  const { read, run, busy, wallet, version, lastTx } = useMeritDrop();

  const [campaign, setCampaign] = useState<CampaignType | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [proofUrl, setProofUrl] = useState("");
  const [note, setNote] = useState("");
  const [formMsg, setFormMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!Number.isFinite(cid) || cid < 1) {
      setErr("That campaign id is not valid.");
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [c, list] = await Promise.all([
        read.getCampaign(cid),
        read.listEntries(cid, 0, 200),
      ]);
      setCampaign(c);
      setEntries(list);
      setErr(c ? null : "That campaign does not exist on this contract.");
    } catch (e) {
      setErr(describeError(e));
    } finally {
      setLoading(false);
    }
  }, [cid, read]);

  useEffect(() => {
    load();
  }, [load, version]);

  if (loading && !campaign) {
    return (
      <main className="page">
        <p className="dim pad">Reading the campaign…</p>
      </main>
    );
  }

  if (err && !campaign) {
    return (
      <main className="page">
        <div className="empty">
          <p className="empty-title">{err}</p>
          <p>
            <Link to="/">Back to the ledger</Link>
          </p>
        </div>
      </main>
    );
  }

  if (!campaign) return null;

  const now = Math.floor(Date.now() / 1000);
  const open = campaign.status === "OPEN";
  const inWindow = now >= campaign.opensAt && now <= campaign.closesAt;
  // The window fixes the entry set, so the contract scores only after it shuts,
  // and only a link already reported as unreadable may be repaired afterwards.
  const deadlinePassed = now > campaign.closesAt;
  const repairUntil = campaign.closesAt + REPAIR_WINDOW_S;
  const repairOpen = deadlinePassed && now <= repairUntil;
  const attemptsLeft = Math.max(0, MAX_EVIDENCE_ATTEMPTS - campaign.unreadableRounds);
  const canRepairEntry = (e: Entry) =>
    open &&
    !!wallet.address &&
    e.contributor.toLowerCase() === wallet.address.toLowerCase() &&
    (inWindow ||
      (repairOpen &&
        e.evidenceStatus === "UNREADABLE" &&
        campaign.unreadableRounds > 0 &&
        attemptsLeft > 0));
  const mine = !!wallet.address &&
    wallet.address.toLowerCase() === campaign.sponsor.toLowerCase();
  const alreadyIn = entries.some(
    (e) => e.contributor.toLowerCase() === (wallet.address || "").toLowerCase(),
  );
  const leftover = campaign.escrow - (campaign.allocated - campaign.claimed);
  const canReclaim =
    mine && open === false && !campaign.reclaimed && now >= campaign.closesAt && leftover > 0n;

  // A proof nobody could read decides nothing, so say why the next attempt has
  // to wait instead of letting the button revert.
  const evidenceReadyAt =
    campaign.unreadableRounds > 0 ? campaign.lastAttemptAt + EVIDENCE_COOLDOWN_S : 0;
  const cooling = open && evidenceReadyAt > now;
  const minutesToRetry = cooling
    ? Math.max(1, Math.ceil((evidenceReadyAt - now) / 60))
    : 0;

  const scored = entries.filter((e) => e.status === "SCORED");
  const above = scored.filter((e) => e.allocation > 0n);
  const claimedTotal = campaign.claimed;

  async function onEvaluate() {
    const ok = await run("evaluate", (c) => c.evaluate(cid));
    if (ok) await load();
  }

  async function onReclaim() {
    const ok = await run("reclaim", (c) => c.reclaimUnallocated(cid));
    if (ok) await load();
  }

  async function onClaim(entry: Entry) {
    const ok = await run(`claim-${entry.id}`, (c) => c.claim(entry.id));
    if (ok) await load();
  }

  async function onRevise(
    entry: Entry,
    nextTitle: string,
    nextUrl: string,
    nextNote: string,
  ) {
    const ok = await run(`revise-${entry.id}`, (c) =>
      c.reviseProof(entry.id, nextTitle, nextUrl, nextNote),
    );
    if (ok) {
      setFormMsg("Link updated. The validators fetch this one from now on.");
      await load();
    }
  }

  async function onSubmitProof(ev: FormEvent) {
    ev.preventDefault();
    setFormMsg(null);
    if (!title.trim() || !proofUrl.trim() || !note.trim()) {
      setFormMsg("Title, proof link, and note are all required.");
      return;
    }
    const ok = await run("submit", (c) =>
      c.submitProof(cid, title.trim(), proofUrl.trim(), note.trim()),
    );
    if (ok) {
      setFormMsg("Entry recorded. It waits for the evaluation.");
      setTitle("");
      setProofUrl("");
      setNote("");
      await load();
    }
  }

  return (
    <main className="page">
      <nav className="crumbs">
        <Link to="/">Ledger</Link>
        <span>/</span>
        <span>Campaign #{campaign.id}</span>
      </nav>

      <section className="camp-head">
        <div>
          <p className="eyebrow">
            {open
              ? deadlinePassed
                ? "Closed for entries · ready to score"
                : "Accepting entries"
              : "Scored by the validators"}
          </p>
          <h1>{campaign.title}</h1>
          <p className="meta-line">
            Sponsor{" "}
            <a
              href={EXPLORER_ADDR(campaign.sponsor)}
              target="_blank"
              rel="noreferrer"
            >
              {shortAddr(campaign.sponsor)}
            </a>{" "}
            · closes {formatDateTime(campaign.closesAt)}
          </p>
        </div>
        <div className="camp-head-act">
          {open && campaign.entryCount > 0 && (
            <button
              className="btn"
              onClick={onEvaluate}
              disabled={busy !== null || cooling || !deadlinePassed}
              title={
                deadlinePassed
                  ? "The window is shut, so the entry set is fixed"
                  : "Scoring opens once the deadline passes"
              }
            >
              {busy === "evaluate"
                ? "Scoring…"
                : !deadlinePassed
                  ? `Scoring opens in ${formatRemaining(campaign.closesAt)}`
                  : cooling
                    ? `Retry opens in ${minutesToRetry}m`
                    : "Run the evaluation"}
            </button>
          )}
          {canReclaim && (
            <button className="btn ghost" onClick={onReclaim} disabled={busy !== null}>
              {busy === "reclaim" ? "Reclaiming…" : `Reclaim ${formatGen(leftover)} GEN`}
            </button>
          )}
        </div>
      </section>

      {open && !deadlinePassed && (
        <p className="action-note">
          Scoring is locked while the window is open, so the entry set cannot grow
          after a payout is decided. It opens in {formatRemaining(campaign.closesAt)}.
        </p>
      )}

      {open && campaign.unreadableRounds > 0 && (
        <p className="action-note">
          {campaign.unreadableRounds === 1
            ? "One round"
            : `${campaign.unreadableRounds} rounds`}{" "}
          could not read one or more proof links. A link nobody can read scores
          nothing either way, so nothing moved and the campaign stayed open.{" "}
          {repairOpen && attemptsLeft > 0
            ? `The contributor can still repair it until ${formatDateTime(repairUntil)}.`
            : `${attemptsLeft} more failed round(s) and it closes, at which point an entry whose link stayed unreadable earns nothing.`}
          {cooling && ` The retry window reopens ${formatDateTime(evidenceReadyAt)}.`}
        </p>
      )}

      <section className="panel">
        <header className="panel-head">
          <h2>
            <span className="fig">FIG. 02</span> Criteria
          </h2>
          <p className="panel-note">
            The same text is handed to every validator. Each score is snapped to the
            nearest {SCORE_GRADE_STEP} grade, and both validators have to name the same
            grade before any of it pays out.
          </p>
        </header>
        <p className="criteria">{campaign.criteria}</p>
      </section>

      <section className="figures">
        <div className="figure">
          <span className="figure-label">Budget</span>
          <span className="figure-value">{formatGen(campaign.budget, 3)}</span>
          <span className="figure-unit">GEN</span>
        </div>
        <div className="figure">
          <span className="figure-label">Per claim cap</span>
          <span className="figure-value">{formatGen(campaign.maxPerClaim, 4)}</span>
          <span className="figure-unit">GEN</span>
        </div>
        <div className="figure">
          <span className="figure-label">Still in escrow</span>
          <span className="figure-value">{formatGen(campaign.escrow, 4)}</span>
          <span className="figure-unit">GEN</span>
        </div>
        <div className="figure">
          <span className="figure-label">Allocated</span>
          <span className="figure-value">{formatGen(campaign.allocated, 4)}</span>
          <span className="figure-unit">GEN</span>
        </div>
        <div className="figure">
          <span className="figure-label">Claimed</span>
          <span className="figure-value">{formatGen(claimedTotal, 4)}</span>
          <span className="figure-unit">GEN</span>
        </div>
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>
            <span className="fig">FIG. 03</span> Entry ledger
          </h2>
          <p className="panel-note">
            {campaign.entryCount} entered · {above.length} cleared the merit bar ·{" "}
            {scored.length === 0
              ? "not scored yet"
              : `scores in, mean ${formatScore(
                  Math.round(scored.reduce((s, e) => s + e.scoreBp, 0) / scored.length),
                )}`}
          </p>
        </header>

        {entries.length === 0 ? (
          <p className="dim pad">No entries yet. The first one starts the queue.</p>
        ) : (
          <div className="table-scroll">
            <table className="ledger entries">
              <thead>
                <tr>
                  <th>Ref</th>
                  <th>Entry</th>
                  <th>Who</th>
                  <th>Score</th>
                  <th className="num">Value</th>
                  <th className="num">Share</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <EntryRow
                    key={e.id}
                    entry={e}
                    myAddress={wallet.address}
                    onClaim={onClaim}
                    onRevise={onRevise}
                    canRevise={canRepairEntry(e)}
                    busy={busy === `claim-${e.id}`}
                    reviseBusy={busy === `revise-${e.id}`}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {open && (
        <section className="panel">
          <header className="panel-head">
            <h2>
              <span className="fig">FIG. 04</span> Submit proof
            </h2>
            <p className="panel-note">One entry per wallet per campaign.</p>
          </header>

          {!wallet.address ? (
            <p className="dim pad">Connect a wallet to enter this campaign.</p>
          ) : !inWindow ? (
            <p className="dim pad">
              The submission window has closed, so no new entry can join. If you
              already entered and the validators could not read your link, its row
              above is where you repair it.
            </p>
          ) : alreadyIn ? (
            <p className="dim pad">
              This wallet already entered. Scroll up to find your entry.
            </p>
          ) : (
            <form className="form" onSubmit={onSubmitProof}>
              <label>
                <span>Title</span>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="What you shipped, in one line"
                  maxLength={200}
                />
              </label>
              <label>
                <span>Proof link</span>
                <input
                  value={proofUrl}
                  onChange={(e) => setProofUrl(e.target.value)}
                  placeholder="https://github.com/…/pull/123"
                  maxLength={500}
                />
              </label>
              <label>
                <span>Note</span>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="What the proof shows, and why it satisfies the criteria."
                  rows={4}
                  maxLength={2000}
                />
              </label>
              <div className="form-foot">
                <button className="btn" type="submit" disabled={busy !== null}>
                  {busy === "submit" ? "Submitting…" : "Submit entry"}
                </button>
                {formMsg && <span className="form-msg">{formMsg}</span>}
              </div>
            </form>
          )}
        </section>
      )}

      {lastTx && (
        <p className="dim pad">
          Last transaction:{" "}
          <a href={`https://explorer-studio.genlayer.com/tx/${lastTx}`} target="_blank" rel="noreferrer">
            {lastTx.slice(0, 14)}…
          </a>
        </p>
      )}
    </main>
  );
}
