// V1 — Registro (contrato `docs/registro-v1-contract.md`): proxy, anti-enumeración,
// verificación y NO auto-login.

import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "../api/ApiClient";

function ok(data: unknown, status = 200): Response {
  return new Response(JSON.stringify({ success: true, request_id: "r", data }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function err(code: string, message: string, status: number): Response {
  return new Response(
    JSON.stringify({ success: false, request_id: "r", error: { code, message, details: {} } }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function mockFetch(data: unknown, status = 200): void {
  globalThis.fetch = vi.fn(async () => ok(data, status)) as unknown as typeof fetch;
}

afterEach(() => vi.restoreAllMocks());

describe("register", () => {
  it("register posts to /api/v1/auth/register and relays the response (no tokens)", async () => {
    mockFetch({ user_id: "u1", verification_token: null, message: "check your email" });
    const r = await apiClient.register("a@b.c", "password123", "Name");
    expect(r.user_id).toBe("u1");
    expect(r.verification_token).toBeNull();
    expect("access_token" in r).toBe(false); // NO auto-login
  });

  it("email exists returns the generic response (anti-enumeration, not an error)", async () => {
    mockFetch({ user_id: null, verification_token: null, message: "check your email" });
    const r = await apiClient.register("a@b.c", "password123");
    expect(r.user_id).toBeNull();
  });

  it("422 is surfaced", async () => {
    globalThis.fetch = vi.fn(async () => err("VALIDATION_ERROR", "Invalid", 422)) as unknown as typeof fetch;
    await expect(apiClient.register("a@b.c", "short")).rejects.toMatchObject({ code: "VALIDATION_ERROR" });
  });

  it("verify-email posts the token and returns the confirmation", async () => {
    mockFetch({ message: "email verificado" });
    const r = await apiClient.verifyEmail("tok");
    expect(r.message).toBe("email verificado");
  });
});
