// Envío de eventos a Google Tag Manager (SPA): GTM no recibe "comunicados" por sí solo en
// una SPA porque no hay recargas de página; hay que empujar eventos a `dataLayer`.

declare global {
  interface Window {
    dataLayer?: Record<string, unknown>[];
  }
}

export function pushEvent(event: string, params: Record<string, unknown> = {}): void {
  if (typeof window === "undefined") return;
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
