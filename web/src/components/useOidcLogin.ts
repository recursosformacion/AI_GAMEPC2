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

// Abre el login OIDC en una ventana flotante centrada (sin barra de URL) y completa la
// sesión cuando el popup envía el resultado por postMessage. Devuelve `start`, que abre el
// popup o devuelve false si OIDC no está configurado (para usar un respaldo).
export function useOidcLogin(onDone?: () => void) {
  const { t } = useI18n();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      const data = e.data as { type?: string; access_token?: string; refresh_token?: string; message?: string };
      if (data?.type === "osap-oidc" && data.access_token) {
        setError(null);
        setBusy(false);
        useAuth.getState().completeOidc(data.access_token, data.refresh_token ?? "");
        onDone?.();
      } else if (data?.type === "osap-oidc-error") {
        setError(data.message ?? t("auth.error"));
        setBusy(false);
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [onDone, t]);

  const openPopup = (url: string) => {
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
      return false;
    }
    popup.location.assign(url);
    return true;
  };

  const start = async (): Promise<boolean> => {
    setBusy(true);
    setError(null);
    try {
      const result = await apiClient.get<OidcStart>("/auth/oidc/start");
      if (!result.configured || !result.authorize_url) {
        setBusy(false);
        return false;
      }
      openPopup(result.authorize_url);
      return true;
    } catch {
      setBusy(false);
      setError(t("auth.oidcUnavailable"));
      return false;
    }
  };

  return { start, error, busy };
}
