// V1 — Flujo de login del Web OSAP (contrato `_docs/account-login-v1-contract.md`).
// Tests T1/T2 y casos de login/refresh/logout con fetch mockeado (sin red).

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import { useAuth } from "./auth";

// ---- helpers ---------------------------------------------------------------

function makeToken(claims: Record<string, unknown>): string {
  const enc = (obj: object) => btoa(JSON.stringify(obj));
  return `${enc({ alg: "none" })}.${enc(claims)}.sig`;
}

function authSession(refresh = "refresh-1", sub = "u1"): Record<string, unknown> {
  return {
    access_token: makeToken({ token_use: "user", sub, roles: ["user"], email_verified: true }),
    refresh_token: refresh,
    user_id: sub,
    roles: ["user"],
    email_verified: true,
  };
}

function apiOk(data: unknown, status = 200): Response {
  return new Response(JSON.stringify({ success: true, request_id: "r", data }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function api401(): Response {
  return new Response(
    JSON.stringify({ success: false, request_id: "r", error: { code: "UNAUTHORIZED", message: "expired", details: {} } }),
    { status: 401, headers: { "Content-Type": "application/json" } },
  );
}

function authResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

interface Routes {
  login?: () => Response;
  refresh?: () => Response;
  api?: (call: number) => Response;
}

function mockFetch(routes: Routes): void {
  let apiCall = 0;
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/auth/login")) {
      return routes.login ? routes.login() : authResponse({ detail: "not found" }, 404);
    }
    if (url.includes("/auth/refresh")) {
      return routes.refresh ? routes.refresh() : authResponse({ detail: "invalid" }, 401);
    }
    apiCall += 1;
    return routes.api ? routes.api(apiCall) : authResponse({ detail: "not found" }, 404);
  }) as unknown as typeof fetch;
}

const REFRESH_KEY = "osap.refresh_token";

function resetState(): void {
  localStorage.clear();
  useAuth.setState({ accessToken: null, refreshToken: null, user: null, status: "anonymous" });
}

beforeEach(resetState);
afterEach(() => {
  vi.restoreAllMocks();
});

// ---- T1: flujo de extremo a extremo -----------------------------------------

describe("T1 — login → recarga → refresh → 401 → retry → OK", () => {
  it("completes the full session flow", async () => {
    mockFetch({
      login: () => authResponse(authSession("refresh-1")),
      refresh: () => authResponse(authSession("refresh-2")),
      api: (call) => (call === 1 ? api401() : apiOk({ search_id: "s1", results: [] })),
    });

    // login
    await useAuth.getState().login("a@b.c", "pwd");
    expect(useAuth.getState().accessToken).toBeTruthy();
    expect(localStorage.getItem(REFRESH_KEY)).toBe("refresh-1");

    // "recarga": access en memoria se pierde, refresh persiste en localStorage
    useAuth.setState({ accessToken: null });
    await useAuth.getState().rehydrate();
    // refresh -> nuevo access + nuevo refresh (rotación)
    expect(useAuth.getState().accessToken).toBeTruthy();
    expect(localStorage.getItem(REFRESH_KEY)).toBe("refresh-2");

    // petición a osap-api -> 401 -> refresh automático -> retry único -> OK
    const data = await apiClient.get<{ search_id: string }>("/searches/x");
    expect(data.search_id).toBe("s1");
  });
});

// ---- T2: refresh antiguo reutilizado -> logout ------------------------------

describe("T2 — refresh obsoleto reutilizado -> 401 -> logout -> limpieza", () => {
  it("logs out and cleans the session when refresh is rejected", async () => {
    mockFetch({
      refresh: () => authResponse({ detail: "refresh reutilizado; sesiones revocadas" }, 401),
    });
    localStorage.setItem(REFRESH_KEY, "refresh-antiguo");
    useAuth.setState({ refreshToken: "refresh-antiguo" });

    const ok = await useAuth.getState().refreshSession();
    expect(ok).toBe(false);
    expect(useAuth.getState().status).toBe("anonymous");
    expect(useAuth.getState().accessToken).toBeNull();
    expect(useAuth.getState().refreshToken).toBeNull();
    expect(localStorage.getItem(REFRESH_KEY)).toBeNull();
  });
});

// ---- otros casos ------------------------------------------------------------

describe("login", () => {
  it("stores access in memory and refresh in localStorage, populates user", async () => {
    mockFetch({ login: () => authResponse(authSession("refresh-1")) });
    await useAuth.getState().login("a@b.c", "pwd");
    expect(useAuth.getState().status).toBe("authenticated");
    expect(useAuth.getState().accessToken).toBeTruthy();
    expect(localStorage.getItem(REFRESH_KEY)).toBe("refresh-1");
    expect(useAuth.getState().user?.user_id).toBe("u1");
    expect(useAuth.getState().user?.email_verified).toBe(true);
  });

  it("throws on invalid credentials (401) and leaves no session", async () => {
    mockFetch({ login: () => authResponse({ detail: "credenciales inválidas" }, 401) });
    await expect(useAuth.getState().login("a@b.c", "mala")).rejects.toMatchObject({ code: "UNAUTHORIZED" });
    expect(useAuth.getState().status).toBe("anonymous");
  });

  it("throws on invalid payload (422)", async () => {
    mockFetch({ login: () => authResponse({ detail: [{ type: "missing", loc: ["body", "password"], msg: "Field required" }] }, 422) });
    await expect(useAuth.getState().login("a@b.c", "")).rejects.toBeInstanceOf(ApiError);
  });
});

describe("logout", () => {
  it("removes the refresh token and clears local state", async () => {
    mockFetch({ login: () => authResponse(authSession("refresh-1")) });
    await useAuth.getState().login("a@b.c", "pwd");
    localStorage.setItem(REFRESH_KEY, "refresh-1");
    useAuth.getState().logout();
    expect(useAuth.getState().status).toBe("anonymous");
    expect(useAuth.getState().accessToken).toBeNull();
    expect(localStorage.getItem(REFRESH_KEY)).toBeNull();
  });
});

describe("401 retry único (sin bucle)", () => {
  it("retries once, then logs out on a second 401, without an infinite loop", async () => {
    let refreshCalls = 0;
    mockFetch({
      login: () => authResponse(authSession("refresh-1")),
      refresh: () => {
        refreshCalls += 1;
        return authResponse(authSession("refresh-2"));
      },
      api: () => api401(), // siempre 401
    });
    await useAuth.getState().login("a@b.c", "pwd");
    await expect(apiClient.get("/searches/x")).rejects.toBeInstanceOf(ApiError);
    // un único refresh (no en bucle)
    expect(refreshCalls).toBe(1);
  });
});
