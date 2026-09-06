// Implementación TEMPORAL/local del SupportGateway que SOLO se usa cuando osap-support
// NO está disponible (p. ej. en entornos sin proxy /support-api).
//
// ⚠️ No se usa en producción: `index.ts` exporta RemoteSupportGateway (osap-support real).
// Esta implementación NO inventa membresías ni pagos; refleja únicamente identidad.

import type { SupportGateway, SupportSummary } from "./supportGateway";

export class LocalSupportGateway implements SupportGateway {
  async getSummary(): Promise<SupportSummary> {
    return { status: "unavailable", authenticated: false, error: "support_unavailable" };
  }

  async startDonation(): Promise<never> {
    throw new Error("osap-support no está disponible (LocalSupportGateway)");
  }

  async startMembership(): Promise<never> {
    throw new Error("osap-support no está disponible (LocalSupportGateway)");
  }
}
