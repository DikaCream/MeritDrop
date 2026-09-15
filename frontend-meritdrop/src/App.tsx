import { Link, NavLink, Route, Routes } from "react-router-dom";
import { MeritDropProvider, useMeritDrop } from "./context/MeritDropContext";
import { WalletButton } from "./components/WalletButton";
import { Board } from "./pages/Board";
import { CampaignPage } from "./pages/Campaign";
import { OpenCampaign } from "./pages/OpenCampaign";
import { Guide } from "./pages/Guide";
import { CONTRACT_ADDRESS, EXPLORER_ADDR, shortAddr } from "./config";

function Spine() {
  return (
    <aside className="spine">
      <Link to="/" className="brand">
        <span className="brand-mark" aria-hidden="true">
          ▲
        </span>
        <span className="brand-text">
          <strong>MeritDrop</strong>
          <em>paid for work</em>
        </span>
      </Link>

      <nav className="spine-nav" aria-label="Main">
        <NavLink to="/" end className={({ isActive }) => (isActive ? "on" : "")}>
          <span className="nav-ref">A</span> Ledger
        </NavLink>
        <NavLink to="/open" className={({ isActive }) => (isActive ? "on" : "")}>
          <span className="nav-ref">B</span> Open a campaign
        </NavLink>
        <NavLink to="/how" className={({ isActive }) => (isActive ? "on" : "")}>
          <span className="nav-ref">C</span> Mechanics
        </NavLink>
      </nav>

      <div className="spine-foot">
        <WalletButton />
      </div>
    </aside>
  );
}

function TxBanner() {
  const { txError, busy, dismissTx, lastTx } = useMeritDrop();
  if (txError) {
    return (
      <div className="banner bad" role="alert">
        <span>{txError}</span>
        <button onClick={dismissTx}>Dismiss</button>
      </div>
    );
  }
  if (busy) {
    return (
      <div className="banner work">
        <span>
          {busy === "evaluate"
            ? "Validators are scoring. This takes a few seconds."
            : "Waiting for the transaction to land…"}
        </span>
      </div>
    );
  }
  if (lastTx) {
    return (
      <div className="banner ok">
        <span>
          Confirmed.{" "}
          <a href={`https://explorer-studio.genlayer.com/tx/${lastTx}`} target="_blank" rel="noreferrer">
            Inspect it
          </a>
        </span>
        <button onClick={dismissTx}>Dismiss</button>
      </div>
    );
  }
  return null;
}

function Footer() {
  return (
    <footer className="site-foot">
      <p>
        MeritDrop runs on GenLayer StudioNet. Contract{" "}
        <a href={EXPLORER_ADDR(CONTRACT_ADDRESS)} target="_blank" rel="noreferrer">
          {shortAddr(CONTRACT_ADDRESS)}
        </a>
        .
      </p>
      <p className="fine">
        Demo network. GEN here holds no value. The settlement logic is the point.
      </p>
    </footer>
  );
}

function NotFound() {
  return (
    <main className="page page-narrow">
      <div className="empty">
        <p className="empty-title">Nothing at this address.</p>
        <p>
          <Link to="/">Back to the ledger</Link>
        </p>
      </div>
    </main>
  );
}

export default function App() {
  return (
    <MeritDropProvider>
      <div className="shell">
        <Spine />
        <div className="body">
          <TxBanner />
          <Routes>
            <Route path="/" element={<Board />} />
            <Route path="/campaigns/:id" element={<CampaignPage />} />
            <Route path="/open" element={<OpenCampaign />} />
            <Route path="/how" element={<Guide />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
          <Footer />
        </div>
      </div>
    </MeritDropProvider>
  );
}
