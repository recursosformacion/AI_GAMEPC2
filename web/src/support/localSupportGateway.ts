// IMPLEMENTACIÓN TEMPORAL de SupportGateway.
//
// ⚠️ TEMPORAL / local: todavía NO existe osap-support.
// Solo refleja si hay usuario autenticado (JWT.sub). NO simula membresía ni pagos:
// no inventa importes, niveles, fechas ni suscripciones.
//
// Cuando exista osap-support, se sustituye por un `SupportApiClient` que llame a su API
// (GET /membership/me, etc.). Chorus y osap-app no cambiarán (consumen esta interfaz).

import { useAuth } from "../state/auth";
import type { SupportGateway, SupportSummary } from "./supportGateway";

export class LocalSupportGateway implements SupportGateway {
  getSummary(): Promise<SupportSummary> {
    const user = useAuth.getState().user;
    if (user === null) {
      return Promise.resolve({ status: "anonymous", authenticated: false });
    }
    return Promise.resolve({
      status: "preparing",
      authenticated: true,
      subscriberId: user.user_id, // = JWT.sub
    });
  }
}

/** Instancia de la frontera; swap aquí la implementación cuando exista osap-support. */
export const supportGateway: SupportGateway = new LocalSupportGateway();

/**
 * Hook de UI: expone el estado de apoyo del usuario y reacciona a los cambios de sesión.
 * En el MVP se deriva de `useAuth` (identidad). Cuando exista osap-support se sustituirá
 * la implementación (el hook llamará al gateway real) sin cambiar a osap-app/Chorus.
 */
export function useSupport(): SupportSummary {
  const user = useAuth((s) => s.user);
  if (user === null) {
    return { status: "anonymous", authenticated: false };
  }
  return { status: "preparing", authenticated: true, subscriberId: user.user_id };
}

