import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiClient } from "./ApiClient";
import { ApiError } from "./errors";
import type { JobResponse } from "./types";

function okResponse<T>(data: T, status = 200): Response {
  return new Response(JSON.stringify({ success: true, request_id: "r1", data }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function errorResponse(code: string, message: string, status = 400): Response {
  return new Response(
    JSON.stringify({ success: false, request_id: "r1", error: { code, message, details: { field: "x" } } }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

describe("ApiClient", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("GET calls /api/v1 and returns data from the envelope", async () => {
    const fetcher = vi.fn(async () => okResponse<JobResponse[]>([{ job_id: "j1", type: "t", state: "completed", progress: 100, result: {} }]));
    const client = new ApiClient("/api/v1", fetcher as unknown as typeof fetch);
    const jobs = await client.get<JobResponse[]>("/jobs");
    expect(jobs).toEqual([expect.objectContaining({ job_id: "j1" })]);
    expect(fetcher).toHaveBeenCalledWith("/api/v1/jobs", expect.objectContaining({ method: "GET" }));
  });

  it("POST serializes the body as JSON", async () => {
    const fetcher = vi.fn(async () => okResponse({ search_id: "s1", results: [] }));
    const client = new ApiClient("/api/v1", fetcher as unknown as typeof fetch);
    await client.post("/searches", { query: "Ave Verum", limit: 10 });
    const [, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.body).toBe(JSON.stringify({ query: "Ave Verum", limit: 10 }));
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("throws ApiError with code/message/details on error envelope", async () => {
    const fetcher = vi.fn(async () => errorResponse("INVALID_QUERY", "Query cannot be empty"));
    const client = new ApiClient("/api/v1", fetcher as unknown as typeof fetch);
    await expect(client.get("/searches/x")).rejects.toMatchObject({ code: "INVALID_QUERY", message: "Query cannot be empty" });
  });

  it("throws ApiError on network failure", async () => {
    const fetcher = vi.fn(async () => {
      throw new TypeError("failed");
    });
    const client = new ApiClient("/api/v1", fetcher as unknown as typeof fetch);
    await expect(client.get("/system/health")).rejects.toBeInstanceOf(ApiError);
  });

  it("throws ApiError on invalid response body", async () => {
    const fetcher = vi.fn(async () => new Response("<html>", { status: 200 }));
    const client = new ApiClient("/api/v1", fetcher as unknown as typeof fetch);
    await expect(client.get("/system/health")).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  });

  it("binds the fetcher to globalThis (prevents Illegal invocation in browsers)", async () => {
    let captured: unknown = null;
    const fetcher = function (this: unknown) {
      captured = this;
      return Promise.resolve(
        new Response(JSON.stringify({ success: true, request_id: "r", data: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    } as unknown as typeof fetch;
    const client = new ApiClient("/api/v1", fetcher);
    await client.get("/jobs");
    expect(captured).toBe(globalThis);
  });

  it("treats a non-envelope JSON body as an invalid response", async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 }));
    const client = new ApiClient("/api/v1", fetcher as unknown as typeof fetch);
    await expect(client.get("/api/v1/system/health")).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  });
});
