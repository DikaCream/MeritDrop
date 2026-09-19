import { Link } from "react-router-dom";
import { SCORE_GRADE_STEP } from "../config";

export function Guide() {
  return (
    <main className="page page-narrow">
      <nav className="crumbs">
        <Link to="/">Ledger</Link>
        <span>/</span>
        <span>How the scoring works</span>
      </nav>

      <section className="masthead">
        <p className="eyebrow">Mechanics</p>
        <h1>Four steps, no adjusters.</h1>
        <p className="lede">
          An airdrop usually asks you to trust a list. This one publishes the rule,
          runs the rule through validators, and lets the arithmetic decide who gets
          paid.
        </p>
      </section>

      <section className="steps">
        <article className="step">
          <span className="step-num">01</span>
          <h3>The sponsor locks the budget</h3>
          <p>
            Opening a campaign sends the whole budget into the contract and publishes
            the criteria next to it. The money is out of reach until the evaluation
            runs, and the criteria cannot be edited afterwards.
          </p>
        </article>

        <article className="step">
          <span className="step-num">02</span>
          <h3>Contributors submit proof</h3>
          <p>
            One entry per wallet per campaign, inside the window. An entry is a title,
            a link to the work, and a note explaining what the link shows. The
            validators fetch that link themselves and judge the artifact, not the
            description of it. The note is a claim: a link that cannot be read earns
            nothing, and a confident note over thin evidence scores badly.
          </p>
        </article>

        <article className="step">
          <span className="step-num">03</span>
          <h3>Validators score every entry</h3>
          <p>
            The button only works once the deadline has passed, because the window is
            what fixes the list of entries. The contract is not the judge: each
            validator runs the same prompt over the same entries, and the round only
            stands when the answers land on the same grade for every entry. The grades
            are 0, {SCORE_GRADE_STEP}, 0.5, 0.75 and 1.0, and every score is snapped to
            the nearest one before it is compared, so a small difference in judgement
            collapses onto one figure while a real disagreement fails the round. The
            reasoning is written to the chain next to the grade.
          </p>
        </article>

        <article className="step">
          <span className="step-num">04</span>
          <h3>The budget splits by score</h3>
          <p>
            Each entry at or above the 0.30 bar takes a share proportional to its grade,
            capped by the per-claim ceiling. On this scale the paying grades are 0.5 and
            up. Contributors then claim their own share, and anything the evaluators
            never allocated goes back to the sponsor.
          </p>
        </article>
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>
            <span className="fig">FIG. 05</span> What the contract refuses
          </h2>
          <p className="panel-note">
            These are enforced on chain, not in this page.
          </p>
        </header>
        <ul className="refusals">
          <li>
            A score typed in by hand. The only scoring path runs through the
            validators, so no caller can set one.
          </li>
          <li>
            Scoring before the deadline, or a second scoring pass. The window fixes
            the entry set and a campaign is scored once, so a share cannot be decided
            early or allocated twice.
          </li>
          <li>
            A payout from scores nobody agreed on. Both validators have to report the
            same grade for every entry before any money moves.
          </li>
          <li>
            Swapping in a different link after the deadline. Only an entry whose link
            the validators reported as unreadable may be repaired, and only until the
            repair window closes.
          </li>
          <li>
            An entry the validators skipped, or a score for an entry that was never
            submitted.
          </li>
          <li>A score outside 0 to 1, or output the contract cannot read.</li>
          <li>A share larger than the per-claim cap, or larger than what the escrow holds.</li>
          <li>Claiming a share that belongs to someone else, or claiming it twice.</li>
          <li>
            A sponsor draining allocated money. Reclaiming can only touch what was never
            allocated.
          </li>
        </ul>
      </section>

      <div className="cta-row">
        <Link className="btn" to="/">
          Back to the ledger
        </Link>
      </div>
    </main>
  );
}
