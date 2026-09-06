// SupportGateway: frontera (port) del frontend hacia la relación de apoyo del
// ecosistema OSAP (osap-support).
//
// FINALIDAD: osap-app → SupportGateway → osap-support HTTP API.
// NO contiene lógica de pagos ni conoce proveedores.
//
// Auth (identidad) y Support (relación de apoyo) son fronteras SEPARADAS:
// - AuthClient  → sabe quién eres (JWT.sub).
// - SupportGateway → estado real de tu relación de apoyo (via osap-support).

export type SupportStatus =
  | "anonymous"
  | "loading"
  | "unavailable"
  | "no_membership"
  | "member";

export interface MembershipView {
  status?: string | null;
  level?: string | null;
  periodicity?: string | null;
  started_at?: string | null;
  next_renewal_at?: string | null;
  is_founder?: boolean;
}

export interface SupportSummary {
  status: SupportStatus;
  authenticated: boolean;
  /** = JWT.sub (UUID de Auth). El identificador estable del ecosistema. */
  subscriberId?: string;
  /** Estado real de membership si el backend responde (siempre verificado). */
  membership?: MembershipView | null;
  /** Solo si el backend real respondió un error no recuperable. */
  error?: string;
}

export interface CheckoutResult {
  checkout_url: string;
  provider_session_id: string;
  mode: "donation" | "membership";
  return_url: string;
}

export interface SupportGateway {
  /** Estado de la relación de apoyo (identidad + membership real de osap-support). */
  getSummary(accessToken: string): Promise<SupportSummary>;
  /** Inicia un checkout de donación real en osap-support. */
  startDonation(
    accessToken: string,
    amountMinor: number,
    currency: string,
    returnUrl: string,
  ): Promise<CheckoutResult>;
  /** Inicia un checkout de membresía real (nivel+periodicidad; el plan lo resuelve el backend). */
  startMembership(
    accessToken: string,
    level: string,
    periodicity: string,
    returnUrl: string,
  ): Promise<CheckoutResult>;
}
