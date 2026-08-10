// V1 — Panel administrativo (contrato `docs/administration-v1-contract.md`).

import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "../api/ApiClient";

function ok(data: unknown): Response {
  return new Response(JSON.stringify({ success: true, request_id: "r", data }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => vi.restoreAllMocks());

describe("admin overview", () => {
  it("getVotesOverview returns the contract shape", async () => {
    const payload = {
      total_votes: 1523,
      top_works: [{ work_id: "2", vote_count: 37, rating: 4.32, work_count: 1 }],
      top_composers: [{ composer_id: "comp", vote_count: 1523, rating: 4.41, work_count: 264 }],
      last_execution: { kind: "recompute", status: "ok", started_at: "x", finished_at: "y" },
    };
    globalThis.fetch = vi.fn(async () => ok(payload)) as unknown as typeof fetch;
    const o = await apiClient.getVotesOverview();
    expect(o.total_votes).toBe(1523);
    expect(o.top_works[0]?.work_id).toBe("2");
    expect(o.top_composers[0]?.rating).toBe(4.41);
    expect(o.last_execution?.kind).toBe("recompute");
  });
});
