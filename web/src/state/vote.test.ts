// V1 — Flujo de voto del Web OSAP (contrato `docs/vote-v1-contract.md`).
// Fetch mockeado: login + voto exitoso y errores 401/403/404/409/422.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "../api/ApiClient";
import { useAuth } from "./auth";

function makeToken(claims: Record<string, unknown>): string {
  const enc = (o: object) => btoa(JSON.stringify(o));
  return `${enc({ alg: "none" })}.${enc(claims)}.sig`;
}

function authSession(): Record<string, unknown> {
  return {
    access_token: makeToken({ token_use: "user", sub: "u1", roles: ["user"], email_verified: true }),
    refresh_token: "refresh-1",
    user_id: "u1",
    roles: ["user"],
    email_verified: true,
  };
}

function apiOk(data: unknown): Response {
  return new Response(JSON.stringify({ success: true, request_id: "r", data }), {
    status: 201,
    headers: { "Content-Type": "application/json" },
  });
}

function apiErr(code: string, status: number): Response {
  return new Response(
    JSON.stringify({ success: false, request_id: "r", error: { code, message: code, details: {} } }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function mockFetch(api: () => Response, login = true): void {
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (login && url.includes("/auth/login")) {
      return new Response(JSON.stringify(authSession()), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    return api();
  }) as unknown as typeof fetch;
}

const voteUrl = "/api/v1/works/2/vote";

beforeEach(() => {
  localStorage.clear();
  useAuth.setState({ accessToken: null, refreshToken: null, user: null, status: "anonymous" });
});
afterEach(() => vi.restoreAllMocks());

describe("vote", () => {
  it("authenticated user can vote -> 201", async () => {
    mockFetch(() => apiOk({ work_id: "2", vote: 5, voted_at: "2026-08-10T07:25:16Z", vote_day: "2026-08-10" }));
    await useAuth.getState().login("a@b.c", "pwd");
    expect(useAuth.getState().isAuthenticated()).toBe(true);
    const res = await apiClient.post<{ vote: number }>(voteUrl, { vote: 5 });
    expect(res.vote).toBe(5);
  });

  it("401 -> UNAUTHORIZED", async () => {
    mockFetch(() => apiErr("UNAUTHORIZED", 401));
    await expect(apiClient.post(voteUrl, { vote: 5 })).rejects.toMatchObject({ code: "UNAUTHORIZED" });
  });

  it("403 -> FORBIDDEN", async () => {
    mockFetch(() => apiErr("FORBIDDEN", 403));
    await expect(apiClient.post(voteUrl, { vote: 5 })).rejects.toMatchObject({ code: "FORBIDDEN" });
  });

  it("404 -> NOT_FOUND", async () => {
    mockFetch(() => apiErr("NOT_FOUND", 404));
    await expect(apiClient.post(voteUrl, { vote: 5 })).rejects.toMatchObject({ code: "NOT_FOUND" });
  });

  it("409 -> DUPLICATE_VOTE", async () => {
    mockFetch(() => apiErr("DUPLICATE_VOTE", 409));
    await expect(apiClient.post(voteUrl, { vote: 5 })).rejects.toMatchObject({ code: "DUPLICATE_VOTE" });
  });

  it("422 -> INVALID_VOTE", async () => {
    mockFetch(() => apiErr("INVALID_VOTE", 422));
    await expect(apiClient.post(voteUrl, { vote: 6 })).rejects.toMatchObject({ code: "INVALID_VOTE" });
  });
});
