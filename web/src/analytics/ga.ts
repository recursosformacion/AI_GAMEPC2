// Carga de Google Analytics 4 (gtag.js) **condicionada al consentimiento**.
//
// La etiqueta NO se carga hasta que el usuario acepta la categoría "analítica". Al retirar el
// consentimiento se activa el opt-out de GA (`ga-disable-<ID>`) para que no se envíen hits.
// `send_page_view: false`: las vistas las manda la SPA (evita `page_view` duplicados).

import { analyticsGranted } from "../consent/consent";

const GA_ID = (import.meta.env.VITE_GA_ID as string | undefined) ?? "G-8QXVPF8VP0";

let loaded = false;

export function gaId(): string {
  return GA_ID;
}

function setGaDisabled(value: boolean): void {
  if (typeof window === "undefined") return;
  (window as unknown as Record<string, unknown>)[`ga-disable-${GA_ID}`] = value;
}

export function initAnalytics(): void {
  if (typeof window === "undefined") return;
  if (!analyticsGranted()) return;
  setGaDisabled(false);
  if (loaded) return;
  loaded = true;

  const script = document.createElement("script");
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${GA_ID}`;
  document.head.appendChild(script);

  window.dataLayer = window.dataLayer ?? [];
  const gtag = (...args: unknown[]) => {
    window.dataLayer?.push(args);
  };
  window.gtag = gtag as (...args: unknown[]) => void;
  window.gtag("js", new Date());
  window.gtag("config", GA_ID, { send_page_view: false });
}

export function disableAnalytics(): void {
  // Si aún no se cargó, basta con no cargarla; si ya estaba, se opt-out.
  setGaDisabled(true);
}
