// Implementación REAL de SupportGateway: llama a osap-support a través de
// SupportApiClient. Sustituye al LocalSupportGateway (datos locales).
//
// - getSummary: consulta /membership/me SOLO si hay token. Ante error de red o 401 se
//   devuelve `unavailable` (no se muestra estado falso). Un backend que responde 200 con
//   membership null → `no_membership`.
// - startDonation / startMembership: delegan en osap-support; devuelven la URL real de
//   PayPal o propagan el error (la UI nunca dice "pago realizado" por su cuenta).

import type { SupportApiClient } from "./supportApiClient";
import { supportApiClient } from "./supportApiClient";
import type { CheckoutResult, SupportGateway, SupportSummary } from "./supportGateway";

export class RemoteSupportGateway implements SupportGateway {
  constructor(private readonly client: SupportApiClient = supportApiClient) {}

  async getSummary(accessToken: string): Promise<SupportSummary> {
    try {
      const membership = await this.client.getMyMembership(accessToken);
      return {
        status: membership?.status ? "member" : "no_membership",
        authenticated: true,
        membership,
      };
    } catch (error) {
      const code = (error as { code?: string })?.code;
      return {
        status: "unavailable",
        authenticated: true,
        error: code === "UNAUTHORIZED" ? "session_expired" : "support_unavailable",
      };
    }
  }

  async startDonation(
    accessToken: string,
    amountMinor: number,
    currency: string,
    returnUrl: string,
  ): Promise<CheckoutResult> {
    return this.client.startDonation(accessToken, {
      amount_minor: amountMinor,
      currency,
      return_url: returnUrl,
    });
  }

  async startMembership(
    accessToken: string,
    level: string,
    periodicity: string,
    returnUrl: string,
  ): Promise<CheckoutResult> {
    return this.client.startMembership(accessToken, { level, periodicity, return_url: returnUrl });
  }
}

export const supportGateway: SupportGateway = new RemoteSupportGateway();
