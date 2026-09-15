import {
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { createMeritDropClient } from "../lib/client";
import { MeritDrop } from "../lib/contract";
import { Campaign, Stats } from "../lib/types";
import { describeError } from "../lib/errors";
import { useWallet } from "../hooks/useWallet";

const EMPTY_STATS: Stats = {
  campaigns: 0,
  entries: 0,
  escrow: 0n,
  allocated: 0n,
  claimed: 0n,
};

interface MeritDropCtx {
  wallet: ReturnType<typeof useWallet>;
  read: MeritDrop;
  campaigns: Campaign[];
  stats: Stats;
  loading: boolean;
  error: string | null;
  busy: string | null;
  txError: string | null;
  lastTx: string | null;
  version: number;
  refresh: () => void;
  dismissTx: () => void;
  run: (label: string, fn: (c: MeritDrop) => Promise<string>) => Promise<boolean>;
}

const Ctx = createContext<MeritDropCtx | null>(null);

export function MeritDropProvider({ children }: { children: ReactNode }) {
  const wallet = useWallet();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [stats, setStats] = useState<Stats>(EMPTY_STATS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [txError, setTxError] = useState<string | null>(null);
  const [lastTx, setLastTx] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  const readClient = useMemo(() => new MeritDrop(createMeritDropClient()), []);
  const writeClient = useMemo(
    () => new MeritDrop(createMeritDropClient(wallet.address)),
    [wallet.address],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, summary] = await Promise.all([
        readClient.listCampaigns(0, 100),
        readClient.getStats(),
      ]);
      setCampaigns(list.sort((a, b) => b.id - a.id));
      setStats(summary);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }, [readClient]);

  useEffect(() => {
    load();
  }, [load, version]);

  const refresh = useCallback(() => setVersion((v) => v + 1), []);

  const dismissTx = useCallback(() => {
    setTxError(null);
    setLastTx(null);
  }, []);

  const run = useCallback(
    async (label: string, fn: (c: MeritDrop) => Promise<string>) => {
      if (!wallet.address) {
        setTxError("Connect a wallet first.");
        return false;
      }
      setBusy(label);
      setTxError(null);
      setLastTx(null);
      try {
        const hash = await fn(writeClient);
        setLastTx(hash);
        await writeClient.waitForReceipt(hash);
        setVersion((v) => v + 1);
        return true;
      } catch (e) {
        setTxError(describeError(e));
        return false;
      } finally {
        setBusy(null);
      }
    },
    [wallet.address, writeClient],
  );

  const value: MeritDropCtx = {
    wallet,
    read: readClient,
    campaigns,
    stats,
    loading,
    error,
    busy,
    txError,
    lastTx,
    version,
    refresh,
    dismissTx,
    run,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useMeritDrop(): MeritDropCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useMeritDrop must be used inside MeritDropProvider");
  return ctx;
}
