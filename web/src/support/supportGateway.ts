// SupportGateway: frontera (port) del frontend hacia la futura relación de apoyo del
// ecosistema OSAP (osap-support).
//
// FINALIDAD (Fase Técnica 1, modificación mínima):
//   Chorus / osap-app
//         ↓
//   SupportGateway
//         ↓
//   futura Support API (osap-support)
//
// NO contiene lógica de pagos. NO conoce proveedores (Stripe, Patreon, Ko-fi, etc.).
// La interfaz es deliberadamente pequeña: solo expone el estado de apoyo que la UI
// necesita hoy y firmas estables mínimas para el futuro (documentadas, no activas).
//
// IMPORTANTE: Auth (identidad) y Support (relación de apoyo) son fronteras SEPARADAS:
// - AuthClient  → sabe quién eres (JWT.sub).
// - SupportGateway → (futuro) sabrá cómo apoyas. Hoy solo expone si hay sesión.

export type SupportStatus = "anonymous" | "preparing";

export interface SupportSummary {
  status: SupportStatus;
  authenticated: boolean;
  /** = JWT.sub (UUID de Auth). El identificador estable del ecosistema. */
  subscriberId?: string;
}

export interface SupportGateway {
  /** Estado mínimo de la relación de apoyo visible para la UI. */
  getSummary(): Promise<SupportSummary>;
}
