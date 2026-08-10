// V1 — Valoración (contrato `docs/valuation-v1-contract.md`): shapes y proxy.

import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "../api/ApiClient";

function ok(data: unknown): Response {
  return new Response(JSON.stringify({ success: true, request_id: "r", data }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function mockFetch(data: unknown): void {
  globalThis.fetch = vi.fn(async () => ok(data)) as unknown as typeof fetch;
}

afterEach(() => vi.restoreAllMocks());

describe("valuation", () => {
  it("work statistics return the storage proxy shape", async () => {
    mockFetch({
      work_id: "2",
      rating: 4.32,
      adjusted_rating: 4.1,
      vote_count: 37,
      work_count: 1,
      confidence: 0.95,
      calculated_at: "2026-08-10T10:00:00Z",
    });
    const s = await apiClient.getWorkStatistics("2");
    expect(s.work_id).toBe("2");
    expect(s.rating).toBe(4.32);
    expect(s.vote_count).toBe(37);
    expect(s.work_count).toBe(1);
    expect(s.confidence).toBe(0.95);
  });

  it("composer statistics return the storage proxy shape", async () => {
    mockFetch({
      composer_id: "comp",
      rating: 4.41,
      adjusted_rating: 4.3,
      vote_count: 1523,
      work_count: 264,
      confidence: 0.9,
      calculated_at: null,
    });
    const s = await apiClient.getComposerStatistics("comp");
    expect(s.composer_id).toBe("comp");
    expect(s.rating).toBe(4.41);
    expect(s.vote_count).toBe(1523);
  });

  it("rating is null when there are no votes (never 0)", async () => {
    mockFetch({ work_id: "2", rating: null, vote_count: 0, work_count: 1, adjusted_rating: null, confidence: null, calculated_at: null });
    const s = await apiClient.getWorkStatistics("2");
    expect(s.vote_count).toBe(0);
    expect(s.rating).toBeNull();
  });
});
