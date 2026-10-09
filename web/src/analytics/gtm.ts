// Envío de eventos a Google Analytics 4 (gtag.js) desde una SPA: como no hay recargas de
// página, cada cambio de ruta empuja un `page_view`. Si `gtag` no está disponible (p. ej. en
// tests), se cae al `dataLayer` "clásico".

declare global {
  interface Window {
    dataLayer?: Record<string, unknown>[];
    gtag?: (...args: unknown[]) => void;
  }
}

export function pushEvent(event: string, params: Record<string, unknown> = {}): void {
  if (typeof window === "undefined") return;
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
