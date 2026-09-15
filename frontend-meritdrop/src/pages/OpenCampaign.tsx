import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMeritDrop } from "../context/MeritDropContext";
import { formatGen, toLocalInput } from "../config";

const DAY = 86400;

function parseGen(input: string): bigint {
  const v = Number(input);
  if (!Number.isFinite(v) || v <= 0) return 0n;
  return BigInt(Math.round(v * 1_000_000)) * 10n ** 12n;
}

function toUnix(local: string): number {
  const t = new Date(local).getTime();
  return Number.isFinite(t) ? Math.floor(t / 1000) : 0;
}

export function OpenCampaign() {
  const { run, busy, wallet } = useMeritDrop();
  const navigate = useNavigate();

  const now = Math.floor(Date.now() / 1000);
  const [title, setTitle] = useState("");
  const [criteria, setCriteria] = useState("");
  const [budget, setBudget] = useState("1");
  const [cap, setCap] = useState("0.4");
  const [opensAt, setOpensAt] = useState(toLocalInput(now));
  const [closesAt, setClosesAt] = useState(toLocalInput(now + 30 * DAY));
  const [msg, setMsg] = useState<string | null>(null);
  const [bad, setBad] = useState(false);

  function fail(text: string) {
    setBad(true);
    setMsg(text);
  }

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault();
    setMsg(null);
    setBad(false);

    if (!wallet.address) return fail("Connect a wallet first.");
    if (!title.trim()) return fail("Give the campaign a title.");
    if (criteria.trim().length < 20)
      return fail("Write criteria the validators can actually apply. At least a sentence.");

    const budgetWei = parseGen(budget);
    const capWei = parseGen(cap);
    const open = toUnix(opensAt);
    const close = toUnix(closesAt);

    if (budgetWei < 10n ** 15n) return fail("The budget has to be at least 0.001 GEN.");
    if (capWei < 10n ** 15n) return fail("The per-claim cap has to be at least 0.001 GEN.");
    if (capWei > budgetWei) return fail("The per-claim cap cannot be larger than the budget.");
    if (close <= open) return fail("The closing time has to come after the opening time.");

    const ok = await run("open", (c) =>
      c.openCampaign(
        title.trim(),
        criteria.trim(),
        open,
        close,
        capWei,
        budgetWei,
      ),
    );
    if (ok) navigate("/");
  }

  return (
    <main className="page page-narrow">
      <nav className="crumbs">
        <Link to="/">Ledger</Link>
        <span>/</span>
        <span>Open a campaign</span>
      </nav>

      <section className="camp-head">
        <div>
          <p className="eyebrow">Sponsor side</p>
          <h1>Open a campaign</h1>
          <p className="meta-line">
            The budget leaves your wallet now and sits in escrow until the evaluation
            splits it. Whatever the evaluators never allocate comes back to you.
          </p>
        </div>
      </section>

      {!wallet.address && (
        <p className="inline-error">Connect a wallet to open a campaign.</p>
      )}

      <form className="form panel" onSubmit={onSubmit}>
        <label>
          <span>Campaign title</span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Documentation translation sprint"
            maxLength={200}
          />
        </label>

        <label>
          <span>Criteria</span>
          <textarea
            value={criteria}
            onChange={(e) => setCriteria(e.target.value)}
            placeholder="What counts as finished work here. Be specific: the only thing the validators see is this text plus each entry."
            rows={6}
            maxLength={2000}
          />
        </label>

        <div className="field-row">
          <label>
            <span>Budget (GEN)</span>
            <input
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              inputMode="decimal"
            />
          </label>
          <label>
            <span>Per claim cap (GEN)</span>
            <input
              value={cap}
              onChange={(e) => setCap(e.target.value)}
              inputMode="decimal"
            />
          </label>
        </div>

        <div className="field-row">
          <label>
            <span>Entries open</span>
            <input
              type="datetime-local"
              value={opensAt}
              onChange={(e) => setOpensAt(e.target.value)}
            />
          </label>
          <label>
            <span>Entries close</span>
            <input
              type="datetime-local"
              value={closesAt}
              onChange={(e) => setClosesAt(e.target.value)}
            />
          </label>
        </div>

        <p className="hint">
          Escrow on submit:{" "}
          <strong className="mono">{formatGen(parseGen(budget), 4)} GEN</strong>. The cap
          is a ceiling per contributor, not a promise: an entry that scores below the
          merit bar receives nothing and the remainder returns to you.
        </p>

        <div className="form-foot">
          <button className="btn" type="submit" disabled={busy !== null}>
            {busy === "open" ? "Opening…" : "Lock the budget and open"}
          </button>
          {msg && <span className={bad ? "form-msg bad" : "form-msg"}>{msg}</span>}
        </div>
      </form>
    </main>
  );
}
