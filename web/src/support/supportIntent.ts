// Intención de apoyo persistida del visitante anónimo.
//
// Cuando alguien sin cuenta elige una acción en /support, guardamos QUÉ quería hacer para
// reanudarla tras autenticarse (no "quería apoyar", sino el flujo exacto):
//   membership/supporter/monthly | membership/supporter/yearly | donation/one_time
// Se persiste en localStorage (supervive al popup OIDC y a recargas) y se limpia al
// consumirla o al iniciar sesión sin continuar.

const INTENT_KEY = "osap.support_intent";

export type SupportIntent = "donation/one_time" | "membership/supporter/monthly" | "membership/supporter/yearly";

export type SupportIntentKind = "donation" | "membership";

export function parseIntent(value: string | null): SupportIntent | null {
  if (
    value === "donation/one_time" ||
    value === "membership/supporter/monthly" ||
    value === "membership/supporter/yearly"
  ) {
    return value;
  }
  return null;
}

export function storeSupportIntent(intent: SupportIntent): void {
  try {
    localStorage.setItem(INTENT_KEY, intent);
  } catch {
    /* almacenamiento no disponible: se pierde la intención, no es bloqueante */
  }
}

export function readSupportIntent(): SupportIntent | null {
  try {
    return parseIntent(localStorage.getItem(INTENT_KEY));
  } catch {
    return null;
  }
}

export function clearSupportIntent(): void {
  try {
    localStorage.removeItem(INTENT_KEY);
  } catch {
    /* sin almacenamiento: nada que limpiar */
  }
}

export function intentMembershipPeriodicity(
  intent: SupportIntent,
): "monthly" | "yearly" | null {
  if (intent.startsWith("membership/supporter/")) {
    return intent.endsWith("/yearly") ? "yearly" : "monthly";
  }
  return null;
}
