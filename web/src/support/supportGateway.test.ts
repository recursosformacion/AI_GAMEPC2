// Test mínimo del SupportGateway (implementación temporal).
// Garantiza que la frontera devuelve el estado correcto según la sesión de Auth,
// sin inventar membresías ni datos económicos.

import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { useAuth } from "../state/auth";
import { supportGateway } from "./localSupportGateway";

function resetState(): void {
  localStorage.clear();
  useAuth.setState({
    accessToken: null,
    refreshToken: null,
    user: null,
    status: "anonymous",
  });
}

beforeEach(resetState);
afterEach(() => {
  localStorage.clear();
});

describe("SupportGateway (implementación temporal)", () => {
  it("devuelve anonymous sin sesión y no inventa subscriberId", async () => {
    useAuth.setState({ user: null, status: "anonymous" });
    const summary = await supportGateway.getSummary();
    expect(summary.authenticated).toBe(false);
    expect(summary.status).toBe("anonymous");
    expect(summary.subscriberId).toBeUndefined();
  });

  it("devuelve preparing + subscriberId (= JWT.sub) cuando hay usuario identificado", async () => {
    useAuth.setState({
      user: { user_id: "uuid-1", roles: ["user"], email_verified: true },
      status: "authenticated",
    });
    const summary = await supportGateway.getSummary();
    expect(summary.authenticated).toBe(true);
    expect(summary.status).toBe("preparing");
    expect(summary.subscriberId).toBe("uuid-1");
  });
});
