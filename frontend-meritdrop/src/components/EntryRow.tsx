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
  busy: boolean;
}

export function EntryRow({ entry, myAddress, onClaim, busy }: Props) {
  const [open, setOpen] = useState(false);
  const scored = entry.status === "SCORED";
  const mine =
    !!myAddress && myAddress.toLowerCase() === entry.contributor.toLowerCase();
  const canClaim = scored && mine && !entry.claimed && entry.allocation > 0n;

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
          <a className="proof-link" href={entry.proofUrl} target="_blank" rel="noreferrer">
            {hostOf(entry.proofUrl)}
          </a>
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
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
