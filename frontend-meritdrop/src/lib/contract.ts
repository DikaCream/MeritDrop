import { CONTRACT_ADDRESS } from "../config";
import {
  Campaign,
  Entry,
  Stats,
  toCampaign,
  toEntry,
  toStats,
} from "./types";

export class MeritDrop {
  constructor(private client: any, private address: string = CONTRACT_ADDRESS) {}

  private async read(functionName: string, args: unknown[] = []): Promise<any> {
    return this.client.readContract({
      address: this.address as `0x${string}`,
      functionName,
      args,
    });
  }

  private async write(
    functionName: string,
    args: unknown[],
    value: bigint = 0n,
  ): Promise<string> {
    const txHash = await this.client.writeContract({
      address: this.address as `0x${string}`,
      functionName,
      args,
      value,
    });
    return txHash as string;
  }

  async waitForReceipt(txHash: string, retries = 60, interval = 3000): Promise<any> {
    return this.client.waitForTransactionReceipt({
      hash: txHash,
      status: "ACCEPTED" as any,
      retries,
      interval,
    });
  }

  // ---- reads ----------------------------------------------------------
  async getStats(): Promise<Stats> {
    return toStats(await this.read("get_stats"));
  }

  async getCampaign(id: number): Promise<Campaign | null> {
    const v = await this.read("get_campaign", [id]);
    if (v == null) return null;
    return toCampaign(v);
  }

  async listCampaigns(offset = 0, limit = 50): Promise<Campaign[]> {
    const v = await this.read("list_campaigns", [offset, limit]);
    return Array.isArray(v) ? v.map(toCampaign) : [];
  }

  async getEntry(id: number): Promise<Entry | null> {
    const v = await this.read("get_entry", [id]);
    if (v == null) return null;
    return toEntry(v);
  }

  async listEntries(campaignId: number, offset = 0, limit = 50): Promise<Entry[]> {
    const v = await this.read("list_entries", [campaignId, offset, limit]);
    return Array.isArray(v) ? v.map(toEntry) : [];
  }

  // ---- writes ---------------------------------------------------------
  /** Open a campaign; the budget travels with the transaction. */
  async openCampaign(
    title: string,
    criteria: string,
    opensAt: number,
    closesAt: number,
    maxPerClaim: bigint,
    budgetWei: bigint,
  ): Promise<string> {
    return this.write(
      "open_campaign",
      [title, criteria, opensAt, closesAt, maxPerClaim],
      budgetWei,
    );
  }

  async submitProof(
    campaignId: number,
    title: string,
    proofUrl: string,
    note: string,
  ): Promise<string> {
    return this.write("submit_proof", [campaignId, title, proofUrl, note]);
  }

  /** Repair a dead link or a typo, while the campaign is still open. */
  async reviseProof(
    entryId: number,
    title: string,
    proofUrl: string,
    note: string,
  ): Promise<string> {
    return this.write("revise_proof", [entryId, title, proofUrl, note]);
  }

  /** Score a whole campaign through the validator-backed AI path. */
  async evaluate(campaignId: number): Promise<string> {
    return this.write("evaluate", [campaignId]);
  }

  async claim(entryId: number): Promise<string> {
    return this.write("claim", [entryId]);
  }

  async reclaimUnallocated(campaignId: number): Promise<string> {
    return this.write("reclaim_unallocated", [campaignId]);
  }
}
