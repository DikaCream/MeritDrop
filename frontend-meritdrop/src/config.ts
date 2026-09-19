export const NETWORK: "localnet" | "studionet" =
  (import.meta.env.VITE_NETWORK as "localnet" | "studionet") || "studionet";

export const RPC_URL = (import.meta.env.VITE_RPC_URL as string) || "";

/** Deployed MeritDrop contract on GenLayer StudioNet. */
export const CONTRACT_ADDRESS =
  (import.meta.env.VITE_CONTRACT_ADDRESS as string) ||
  "0xc430c7dF330efc7e49664c127a9AdB291ffaB3ae";

export const STUDIONET_CHAIN_ID = 777;
export const STUDIONET_CHAIN_ID_HEX = "0x309";

export const EXPLORER_TX = (hash: string) =>
  `https://explorer-studio.genlayer.com/tx/${hash}`;
export const EXPLORER_ADDR = (address: string) =>
  `https://explorer-studio.genlayer.com/address/${address}`;

export const GEN = 10n ** 18n;

/** Merit bar, mirrored from the contract: 0.30 on a 0 to 10000 scale. */
export const MERIT_BAR_BP = 3000;

/**
 * The five grades, mirrored from the contract. Every score is snapped to the
 * nearest of 0, 0.25, 0.5, 0.75 or 1.0 before the validators have to agree on
 * it, so two answers inside one grade are the same answer and pay the same.
 */
export const SCORE_GRADE_BP = 2500;
export const SCORE_GRADE_STEP = "0.25";

/** Seconds after the deadline during which an unreadable link can be repaired. */
export const REPAIR_WINDOW_S = 86400;

/** Rounds that may end without readable evidence before a campaign closes. */
export const MAX_EVIDENCE_ATTEMPTS = 3;

export function toBigInt(value: bigint | number | string): bigint {
  try {
    return typeof value === "bigint" ? value : BigInt(value ?? 0);
  } catch {
    return 0n;
  }
}

/** GEN amounts stay legible: tiny shares read as "<0.0001", never as a wall of zeros. */
export function formatGen(value: bigint | number | string, maxDecimals = 4): string {
  let wei = toBigInt(value);
  const negative = wei < 0n;
  if (negative) wei = -wei;

  const scale = 10n ** BigInt(maxDecimals);
  const whole = wei / GEN;
  const frac = ((wei % GEN) * scale) / GEN;
  const fracStr = frac.toString().padStart(maxDecimals, "0").replace(/0+$/, "");

  if (whole === 0n) {
    if (fracStr === "") {
      return wei === 0n ? "0" : `<0.${"0".repeat(maxDecimals - 1)}1`;
    }
    return `${negative ? "-" : ""}0.${fracStr}`;
  }
  return `${negative ? "-" : ""}${whole}${fracStr ? `.${fracStr}` : ""}`;
}

export function formatScore(scoreBp: number): string {
  return (scoreBp / 10000).toFixed(2);
}

export function shortAddr(a: string): string {
  if (!a || a.length < 12) return a;
  return `${a.slice(0, 6)}…${a.slice(-4)}`;
}

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function pad(n: number): string {
  return n.toString().padStart(2, "0");
}

export function formatDate(unix: number): string {
  if (!unix) return "n/a";
  const d = new Date(unix * 1000);
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`;
}

export function formatDateTime(unix: number): string {
  if (!unix) return "n/a";
  const d = new Date(unix * 1000);
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()} ${pad(
    d.getUTCHours(),
  )}:${pad(d.getUTCMinutes())} UTC`;
}

/** "3d 4h" or "12m": a bare duration, for button labels. */
export function formatRemaining(closesAt: number): string {
  const diff = closesAt - Math.floor(Date.now() / 1000);
  if (diff <= 0) return "now";
  const days = Math.floor(diff / 86400);
  const hours = Math.floor((diff % 86400) / 3600);
  const minutes = Math.floor((diff % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

/** "3d 4h left" or "closed 2d ago". */
export function formatCountdown(closesAt: number): string {
  const now = Math.floor(Date.now() / 1000);
  const diff = closesAt - now;
  const abs = Math.abs(diff);
  const days = Math.floor(abs / 86400);
  const hours = Math.floor((abs % 86400) / 3600);
  const minutes = Math.floor((abs % 3600) / 60);
  const parts = days > 0 ? `${days}d ${hours}h` : hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
  return diff >= 0 ? `${parts} left` : `closed ${parts} ago`;
}

/** Local datetime string for an <input type="datetime-local"> value. */
export function toLocalInput(unix: number): string {
  const d = new Date(unix * 1000);
  const offset = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - offset).toISOString().slice(0, 16);
}
