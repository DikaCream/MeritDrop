import { Link } from "react-router-dom";
import { useMeritDrop } from "../context/MeritDropContext";
import { CampaignRow } from "../components/CampaignRow";
import { formatGen } from "../config";

export function Board() {
  const { campaigns, stats, loading, error } = useMeritDrop();

  return (
    <main className="page">
      <section className="masthead">
        <p className="eyebrow">Airdrop settlement on GenLayer</p>
        <h1>
          Paid for work,
          <br />
          not for luck.
        </h1>
        <p className="lede">
          A sponsor locks a budget and publishes the criteria. Contributors submit
          proof of finished work. Validators score every entry against the same
          criteria, reach agreement, and the money is split by those scores. Nobody
          types a number in by hand.
        </p>
        <div className="cta-row">
          <Link className="btn" to="/open">
            Open a campaign
          </Link>
          <Link className="btn ghost" to="/how">
            How the scoring works
          </Link>
        </div>
      </section>

      <section className="stat-strip" aria-label="Contract totals">
        <div className="stat">
          <span className="stat-label">Campaigns</span>
          <span className="stat-value">{stats.campaigns}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Entries</span>
          <span className="stat-value">{stats.entries}</span>
        </div>
        <div className="stat">
          <span className="stat-label">In escrow</span>
          <span className="stat-value">{formatGen(stats.escrow)}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Allocated</span>
          <span className="stat-value">{formatGen(stats.allocated)}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Claimed</span>
          <span className="stat-value">{formatGen(stats.claimed)}</span>
        </div>
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>
            <span className="fig">FIG. 01</span> Campaign ledger
          </h2>
          <p className="panel-note">Newest first. Amounts are in GEN.</p>
        </header>

        {error && <p className="inline-error">{error}</p>}

        {loading && campaigns.length === 0 ? (
          <p className="dim pad">Reading the contract…</p>
        ) : campaigns.length === 0 ? (
          <p className="dim pad">
            No campaigns yet. Open one and it appears here.
          </p>
        ) : (
          <div className="table-scroll">
            <table className="ledger">
              <thead>
                <tr>
                  <th>Ref</th>
                  <th>Campaign</th>
                  <th>Window</th>
                  <th className="num">Budget</th>
                  <th className="num">Escrow</th>
                  <th className="num">Allocated</th>
                  <th className="num">Entries</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c) => (
                  <CampaignRow key={c.id} campaign={c} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
