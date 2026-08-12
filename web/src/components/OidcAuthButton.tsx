import { useEffect, useState } from "react";
import { apiClient } from "../api/ApiClient";
import { useI18n } from "../i18n/I18n";
import { useAuth } from "../state/auth";

interface OidcStart {
  authorize_url: string;
  configured: boolean;
}

const POPUP_W = 480;
const POPUP_H = 640;

// Botón de login/registro vía osap-auth (OIDC) en una ventana flotante:
// - popup centrado y sin barra de URL;
// - navega al authorize de osap-auth;
// - AuthCallbackPage (en el popup) envía la sesión por postMessage y cierra.
export function OidcAuthButton({ onDone, label }: { onDone?: () => void; label?: string }) {
  const { t } = useI18n();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Recibe la sesión que el popup envía tras autenticar en osap-auth.
  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      const data = e.data as { type?: string; access_token?: string; refresh_token?: string };
      if (data?.type === "osap-oidc" && data.access_token) {
        useAuth.getState().completeOidc(data.access_token, data.refresh_token ?? "");
        onDone?.();
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [onDone]);

  const open = async () => {
    // Se abre el popup de forma síncrona (gesto de usuario), centrado y sin barra de URL.
    const left = window.screenX + (window.outerWidth - POPUP_W) / 2;
    const top = window.screenY + (window.outerHeight - POPUP_H) / 2;
    const popup = window.open(
      "",
      "osap-auth-login",
      `width=${POPUP_W},height=${POPUP_H},left=${left},top=${top},` +
        "location=no,toolbar=no,menubar=no,status=no,scrollbars=yes,resizable=yes",
    );
    if (!popup) {
      setError(t("auth.popupBlocked"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await apiClient.get<OidcStart>("/auth/oidc/start");
      if (!result.authorize_url) {
        popup.close();
        setError(t("auth.oidcUnavailable"));
        setBusy(false);
        return;
      }
      popup.location.assign(result.authorize_url);
    } catch {
      popup.close();
      setError(t("auth.oidcUnavailable"));
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <button
        disabled={busy}
        onClick={open}
        className="rounded bg-osap-accent px-3 py-2 text-sm text-white disabled:opacity-60"
      >
        {busy ? t("auth.working") : label ?? t("auth.oidc")}
      </button>
      {error !== null && <span className="text-xs text-red-500">{error}</span>}
    </div>
  );
}
