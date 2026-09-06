// Frontera "Support" del frontend: único punto por el que osap-app conoce la relación
// de apoyo. Implementación REAL vía osap-support HTTP (RemoteSupportGateway +
// SupportApiClient), publicado por Apache bajo el mismo origen (/support-api).

import { useEffect, useState } from "react";
import { useAuth } from "../state/auth";
import { supportGateway } from "./remoteSupportGateway";
import type { CheckoutResult, SupportSummary } from "./supportGateway";

export type { SupportGateway, SupportStatus, SupportSummary, MembershipView, CheckoutResult } from "./supportGateway";
export { SupportApiClient, supportApiClient } from "./supportApiClient";
export { RemoteSupportGateway, supportGateway } from "./remoteSupportGateway";

/** Acciones de checkout reales (delegan en osap-support → PayPal). */
export function startDonation(
  accessToken: string,
  amountMinor: number,
  currency: string,
  returnUrl: string,
): Promise<CheckoutResult> {
  return supportGateway.startDonation(accessToken, amountMinor, currency, returnUrl);
}

export function startMembership(
  accessToken: string,
  level: string,
  periodicity: string,
  returnUrl: string,
): Promise<CheckoutResult> {
  return supportGateway.startMembership(accessToken, level, periodicity, returnUrl);
}

/**
 * Hook de UI: estado real de la relación de apoyo consultando osap-support.
 * Solo declara estados que el backend confirmó; errores → unavailable (nunca falso).
 */
export function useSupport(): SupportSummary {
  const token = useAuth((s) => s.accessToken);
  const user = useAuth((s) => s.user);
  const [summary, setSummary] = useState<SupportSummary>({
    status: "anonymous",
    authenticated: false,
  });

  useEffect(() => {
    if (!token) {
      setSummary({ status: "anonymous", authenticated: false });
      return;
    }
    let cancelled = false;
    setSummary({ status: "loading", authenticated: true, subscriberId: user?.user_id });
    void supportGateway.getSummary(token).then((result) => {
      if (!cancelled) setSummary(result);
    });
    return () => {
      cancelled = true;
    };
  }, [token, user?.user_id]);

  return summary;
}
