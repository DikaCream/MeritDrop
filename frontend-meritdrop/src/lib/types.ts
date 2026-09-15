export interface Campaign {
  id: number;
  sponsor: string;
  title: string;
  criteria: string;
  opensAt: number;
  closesAt: number;
  budget: bigint;
  escrow: bigint;
  maxPerClaim: bigint;
  allocated: bigint;
  claimed: bigint;
  entryCount: number;
  status: string;
  reclaimed: boolean;
  unreadableRounds: number;
  lastAttemptAt: number;
  createdAt: number;
}

export interface Entry {
  id: number;
  campaignId: number;
  contributor: string;
  title: string;
  proofUrl: string;
  note: string;
  status: string;
  evidenceStatus: string;
  scoreBp: number;
  reasoning: string;
  allocation: bigint;
  claimed: boolean;
  createdAt: number;
}

export interface Stats {
  campaigns: number;
  entries: number;
  escrow: bigint;
  allocated: bigint;
  claimed: bigint;
}

export function toInt(v: unknown, fallback = 0): number {
  if (v == null) return fallback;
  try {
    return Number(v as number);
  } catch {
    return fallback;
  }
}

export function toBig(v: unknown): bigint {
  if (v == null) return 0n;
  try {
    return typeof v === "bigint" ? v : BigInt(v as string);
  } catch {
    return 0n;
  }
}

export function toStr(v: unknown, fallback = ""): string {
  return v == null ? fallback : String(v);
}

export function toCampaign(raw: any): Campaign {
  return {
    id: toInt(raw?.id),
    sponsor: toStr(raw?.sponsor),
    title: toStr(raw?.title),
    criteria: toStr(raw?.criteria),
    opensAt: toInt(raw?.opens_at),
    closesAt: toInt(raw?.closes_at),
    budget: toBig(raw?.budget),
    escrow: toBig(raw?.escrow),
    maxPerClaim: toBig(raw?.max_per_claim),
    allocated: toBig(raw?.allocated),
    claimed: toBig(raw?.claimed),
    entryCount: toInt(raw?.entry_count),
    status: toStr(raw?.status, "OPEN"),
    unreadableRounds: toInt(raw?.unreadable_rounds),
    lastAttemptAt: toInt(raw?.last_attempt_at),
    reclaimed: Boolean(raw?.reclaimed),
    createdAt: toInt(raw?.created_at),
  };
}

export function toEntry(raw: any): Entry {
  return {
    id: toInt(raw?.id),
    campaignId: toInt(raw?.campaign_id),
    contributor: toStr(raw?.contributor),
    title: toStr(raw?.title),
    proofUrl: toStr(raw?.proof_url),
    note: toStr(raw?.note),
    status: toStr(raw?.status, "OPEN"),
    evidenceStatus: toStr(raw?.evidence_status),
    scoreBp: toInt(raw?.score_bp),
    reasoning: toStr(raw?.reasoning),
    allocation: toBig(raw?.allocation),
    claimed: Boolean(raw?.claimed),
    createdAt: toInt(raw?.created_at),
  };
}

export function toStats(raw: any): Stats {
  return {
    campaigns: toInt(raw?.campaigns),
    entries: toInt(raw?.entries),
    escrow: toBig(raw?.escrow),
    allocated: toBig(raw?.allocated),
    claimed: toBig(raw?.claimed),
  };
}
