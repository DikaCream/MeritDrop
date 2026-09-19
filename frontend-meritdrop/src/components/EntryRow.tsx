import { useState } from "react";
import { Entry } from "../lib/types";
import { formatGen, formatScore, shortAddr } from "../config";
import { ScoreMeter } from "./ScoreMeter";

function hostOf(url: string): string {
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return url;
  }
}

interface Props {
  entry: Entry;
  myAddress: string | null;
  onClaim: (entry: Entry) => void;
  onRevise: (entry: Entry, title: string, proofUrl: string, note: string) => void;
  canRevise: boolean;
  busy: boolean;
  reviseBusy: boolean;
}

/** The repair form. Mounted only for the contributor's own open entry, and
 *  remounted whenever the saved link changes, so it never shows stale text. */
function ReviseForm({
  entry,
  onRevise,
  busy,
}: {
  entry: Entry;
  onRevise: Props["onRevise"];
  busy: boolean;
}) {
  const [title, setTitle] = useState(entry.title);
  const [proofUrl, setProofUrl] = useState(entry.proofUrl);
  const [note, setNote] = useState(entry.note);

  return (
    <div>
      <h4>Fix this entry</h4>
      <p className="hint">
        Inside the window you can change anything. After the deadline only a link the
        validators reported as unreadable can be repaired, and only until the repair
        window closes. Once the campaign is scored the record is final.
      </p>
      <form
        className="form revise"
        onSubmit={(ev) => {
          ev.preventDefault();
          if (!title.trim() || !proofUrl.trim() || !note.trim()) return;
          onRevise(entry, title.trim(), proofUrl.trim(), note.trim());
        }}
      >
        <label>
          <span>Title</span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
          />
        </label>
        <label>
          <span>Proof link</span>
          <input
            value={proofUrl}
            onChange={(e) => setProofUrl(e.target.value)}
            placeholder="https://…"
            maxLength={500}
          />
        </label>
        <label>
          <span>Note</span>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            maxLength={2000}
          />
        </label>
        <div className="form-foot">
          <button className="btn-sm" type="submit" disabled={busy}>
            {busy ? "Saving" : "Save the new link"}
          </button>
        </div>
      </form>
    </div>
  );
}

export function EntryRow({
  entry,
  myAddress,
  onClaim,
  onRevise,
  canRevise,
  busy,
  reviseBusy,
}: Props) {
  const [open, setOpen] = useState(false);
  const scored = entry.status === "SCORED";
  const mine =
    !!myAddress && myAddress.toLowerCase() === entry.contributor.toLowerCase();
  const canClaim = scored && mine && !entry.claimed && entry.allocation > 0n;
  const evidence = entry.evidenceStatus;

  return (
    <>
      <tr className={open ? "entry-row open" : "entry-row"}>
        <td className="col-ref">#{entry.id}</td>
        <td className="col-title">
          <button className="row-toggle" onClick={() => setOpen((v) => !v)}>
            <span className="caret" aria-hidden="true">
              {open ? "▾" : "▸"}
            </span>
            {entry.title}
          </button>
          <span className="proof-row">
            <a className="proof-link" href={entry.proofUrl} target="_blank" rel="noreferrer">
              {hostOf(entry.proofUrl)}
            </a>
            {evidence === "READ" && <span className="stamp read">link read</span>}
            {evidence === "UNREADABLE" && (
              <span className="stamp unreadable">link unreadable</span>
            )}
          </span>
        </td>
        <td className="col-who" title={entry.contributor}>
          {mine ? "you" : shortAddr(entry.contributor)}
        </td>
        <td className="col-gauge">
          {scored ? <ScoreMeter scoreBp={entry.scoreBp} /> : <span className="dim">pending</span>}
        </td>
        <td className="col-num">{scored ? formatScore(entry.scoreBp) : "n/a"}</td>
        <td className="col-num strong">{formatGen(entry.allocation)}</td>
        <td className="col-act">
          {canClaim ? (
            <button className="btn-sm" onClick={() => onClaim(entry)} disabled={busy}>
              {busy ? "Claiming" : "Claim"}
            </button>
          ) : entry.claimed ? (
            <span className="stamp ok">claimed</span>
          ) : scored && entry.allocation === 0n ? (
            <span className="stamp no">below bar</span>
          ) : (
            <span className="dim">waiting</span>
          )}
        </td>
      </tr>
      {open && (
        <tr className="entry-detail">
          <td colSpan={7}>
            <div className="detail-grid">
              <div>
                <h4>What they did</h4>
                <p>{entry.note}</p>
              </div>
              <div>
                <h4>Validator reasoning</h4>
                <p>
                  {entry.reasoning || (
                    <span className="dim">
                      Not scored yet. Run the evaluation and the validators will write
                      their reasoning here.
                    </span>
                  )}
                </p>
                {evidence === "UNREADABLE" && !scored && (
                  <p className="hint">
                    The validators could not read this link on the last attempt. Nothing
                    was scored and no money moved. If the attempts or the repair window
                    run out with the link still dark, the entry earns nothing, so a dead
                    link is worth repairing while it can be.
                  </p>
                )}
              </div>
              {canRevise && (
                <ReviseForm
                  key={entry.proofUrl}
                  entry={entry}
                  onRevise={onRevise}
                  busy={reviseBusy}
                />
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
