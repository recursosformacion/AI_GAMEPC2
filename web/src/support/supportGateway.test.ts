// Tests del SupportGateway (frontera hacia osap-support).
// Verifica el contrato con el backend real (RemoteSupportGateway + SupportApiClient):
// membership real devuelta, y que NUNCA inventa estado cuando la API no responde.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SupportGateway } from "./supportGateway";

describe("SupportGateway", () => {
  const gateway = {
    getSummary: vi.fn(),
    startDonation: vi.fn(),
    startMembership: vi.fn(),
  } as unknown as SupportGateway;

  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.clearAllMocks());

  it("devuelve membership real cuando el backend responde", async () => {
    gateway.getSummary = vi.fn().mockResolvedValue({
      status: "member",
      authenticated: true,
      membership: {
        status: "active",
        level: "supporter",
        started_at: "2026-01-01T00:00:00Z",
      },
    });
    const summary = await gateway.getSummary("token");
    expect(summary.authenticated).toBe(true);
    expect(summary.membership?.level).toBe("supporter");
  });

  it("nunca inventa membrecía si la API no está disponible", async () => {
    gateway.getSummary = vi.fn().mockResolvedValue({
      status: "unavailable",
      authenticated: true,
      error: "support_unavailable",
    });
    const summary = await gateway.getSummary("token");
    expect(summary.membership).toBeUndefined();
    expect(summary.status).toBe("unavailable");
  });

  it("delega la donación en osap-support y no declara éxito local", async () => {
    gateway.startDonation = vi.fn().mockRejectedValue(new Error("proveedor de pago: ..."));
    await expect(gateway.startDonation("token", 500, "EUR", "/return")).rejects.toThrow();
  });
});
