// Gestor de consentimiento de cookies de la SPA de OSAP.
//
// Guarda SOLO la decisión mínima (analítica sí/no) en almacenamiento local. No guarda datos
// personales. `necessary` está siempre activo (no se puede desactivar). La versión permite
// pedir de nuevo el consentimiento si cambian las categorías/finalidades.

export interface ConsentCategories {
  necessary: true;
  analytics: boolean;
}

export interface ConsentRecord {
  version: number;
  decided_at: string;
  categories: ConsentCategories;
}

const STORAGE_KEY = "osap.consent.v1";

/** Súbelo cuando cambien categorías o finalidades: invalida decisiones anteriores. */
export const CONSENT_VERSION = 1;

type Listener = (record: ConsentRecord | null) => void;
const listeners = new Set<Listener>();

export function getConsent(): ConsentRecord | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ConsentRecord;
    if (!parsed || parsed.version !== CONSENT_VERSION || !parsed.categories) {
      return null; // versión antigua o inválida → se vuelve a pedir
    }
    return parsed;
  } catch {
    return null;
  }
}

export function saveConsent(categories: ConsentCategories): ConsentRecord {
  const record: ConsentRecord = {
    version: CONSENT_VERSION,
    decided_at: new Date().toISOString(),
    categories: { necessary: true, analytics: Boolean(categories.analytics) },
  };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(record));
  } catch {
    /* almacenamiento no disponible: la decisión no persiste, pero no rompemos la app */
  }
  listeners.forEach((listener) => listener(record));
  return record;
}

export function clearConsent(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
  listeners.forEach((listener) => listener(null));
}

export function onConsentChange(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function analyticsGranted(): boolean {
  return getConsent()?.categories.analytics === true;
}
