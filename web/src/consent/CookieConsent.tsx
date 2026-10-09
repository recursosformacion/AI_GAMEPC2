// Aviso y panel de preferencias de cookies. Se muestra en la primera visita y permite
// aceptar todas, rechazar las no necesarias o configurar. El enlace permanente del pie
// ("Configurar cookies") dispara OPEN_CONSENT_EVENT para reabrir las preferencias.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { disableAnalytics, initAnalytics } from "../analytics/ga";
import { getConsent, saveConsent } from "./consent";

export const OPEN_CONSENT_EVENT = "osap:open-cookie-preferences";

/** Reabre el panel de preferencias desde cualquier punto (p. ej. el pie de página). */
export function openCookiePreferences(): void {
  window.dispatchEvent(new Event(OPEN_CONSENT_EVENT));
}

type Mode = "hidden" | "banner" | "prefs";

export function CookieConsent() {
  const [mode, setMode] = useState<Mode>("hidden");
  const [analytics, setAnalytics] = useState(false);

  useEffect(() => {
    // Primera visita (sin decisión vigente) → banner. Tras decidir, no se repite.
    if (getConsent() === null) {
      setMode("banner");
    }
    const onOpen = () => {
      setAnalytics(getConsent()?.categories.analytics ?? false);
      setMode("prefs");
    };
    window.addEventListener(OPEN_CONSENT_EVENT, onOpen);
    return () => window.removeEventListener(OPEN_CONSENT_EVENT, onOpen);
  }, []);

  const decide = (analyticsValue: boolean) => {
    saveConsent({ necessary: true, analytics: analyticsValue });
    if (analyticsValue) {
      initAnalytics();
    } else {
      disableAnalytics();
    }
    setMode("hidden");
  };

  if (mode === "hidden") return null;

  const dialogStyle =
    "fixed inset-x-0 bottom-0 z-50 border-t border-osap-border bg-osap-surface p-4 shadow-lg sm:left-1/2 sm:bottom-4 sm:max-w-xl sm:-translate-x-1/2 sm:rounded-lg sm:border";

  if (mode === "prefs") {
    return (
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Preferencias de cookies"
        className={dialogStyle}
      >
        <h2 className="text-base font-semibold">Preferencias de cookies</h2>
        <p className="mt-1 text-sm text-osap-muted">
          Las cookies necesarias son imprescindibles para el funcionamiento. La analítica solo se
          activa si la aceptas. Puedes consultar el detalle en la{" "}
          <Link to="/cookies" className="text-osap-accent hover:underline">
            política de cookies
          </Link>
          .
        </p>
        <div className="mt-3 space-y-2 text-sm">
          <label className="flex items-start gap-2">
            <input type="checkbox" checked disabled className="mt-0.5" />
            <span>
              <strong>Necesarias</strong> (siempre activas) — funcionamiento y seguridad.
            </span>
          </label>
          <label className="flex items-start gap-2">
            <input
              type="checkbox"
              checked={analytics}
              onChange={(e) => setAnalytics(e.target.checked)}
              className="mt-0.5"
            />
            <span>
              <strong>Analítica</strong> — Google Analytics, para estadísticas de uso.
            </span>
          </label>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => decide(true)}
            className="rounded bg-osap-accent px-4 py-2 text-sm text-white"
          >
            Aceptar todas
          </button>
          <button
            type="button"
            onClick={() => decide(false)}
            className="rounded border border-osap-border px-4 py-2 text-sm hover:bg-osap-bg"
          >
            Rechazar las no necesarias
          </button>
          <button
            type="button"
            onClick={() => decide(analytics)}
            className="rounded border border-osap-border px-4 py-2 text-sm hover:bg-osap-bg"
          >
            Guardar preferencias
          </button>
        </div>
      </div>
    );
  }

  return (
    <div role="dialog" aria-label="Aviso de cookies" className={dialogStyle}>
      <p className="text-sm">
        Usamos cookies necesarias para el funcionamiento del sitio y, si lo aceptas, cookies de
        analítica (Google Analytics) para estadísticas. Puedes aceptar, rechazar las no necesarias
        o configurar tus preferencias.{" "}
        <Link to="/cookies" className="text-osap-accent hover:underline">
          Más información
        </Link>
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => decide(true)}
          className="rounded bg-osap-accent px-4 py-2 text-sm text-white"
        >
          Aceptar todas
        </button>
        <button
          type="button"
          onClick={() => decide(false)}
          className="rounded border border-osap-border px-4 py-2 text-sm hover:bg-osap-bg"
        >
          Rechazar las no necesarias
        </button>
        <button
          type="button"
          onClick={() => {
            setAnalytics(false);
            setMode("prefs");
          }}
          className="rounded border border-osap-border px-4 py-2 text-sm hover:bg-osap-bg"
        >
          Configurar preferencias
        </button>
      </div>
    </div>
  );
}
