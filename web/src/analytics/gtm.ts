// Eventos de medición de la SPA. **Solo se envían si hay consentimiento de analítica.**
// Si `gtag` no está disponible (sin consentimiento, o en tests) no se envía nada.

import { analyticsGranted } from "../consent/consent";

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
  }
}

export function pushEvent(event: string, params: Record<string, unknown> = {}): void {
  if (typeof window === "undefined") return;
  if (!analyticsGranted()) return;
  if (typeof window.gtag === "function") {
    window.gtag("event", event, params);
    return;
  }
  window.dataLayer = window.dataLayer ?? [];
  window.dataLayer.push({ event, ...params });
}

/** Marca una vista de página (llamar en cada cambio de ruta). */
export function trackPageView(path: string): void {
  pushEvent("page_view", {
    page_path: path,
    page_location: typeof window !== "undefined" ? window.location.href : path,
    page_title: typeof document !== "undefined" ? document.title : "",
  });
}
