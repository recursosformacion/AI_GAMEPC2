import { useEffect, useRef, useState } from "react";
import { apiClient } from "../api/ApiClient";
import { useI18n } from "../i18n/I18n";
import { useAuth } from "../state/auth";

interface OidcStart {
  authorize_url: string;
  configured: boolean;
}

interface OidcMessage {
  type?: string;
  access_token?: string;
  refresh_token?: string;
  message?: string;
}

const POPUP_W = 480;
const POPUP_H = 640;

// Abre el login OIDC en una ventana flotante centrada y completa la sesión únicamente
// cuando esa misma ventana devuelve el resultado desde el origen de la SPA.
export function useOidcLogin(onDone?: () => void) {
  const { t } = useI18n();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const popupRef = useRef<WindowProxy | null>(null);

  useEffect(() => {
    const onMessage = (e: MessageEvent<OidcMessage>) => {
      const popup = popupRef.current;

      // No aceptar mensajes de otras páginas, pestañas o ventanas, aunque conozcan
      // el formato del mensaje. El callback legítimo vive en el mismo origen de la SPA.
      if (!popup || e.origin !== window.location.origin || e.source !== popup) return;

      const data = e.data;
      if (!data || typeof data !== "object") return;

      if (
        data.type === "osap-oidc" &&
        typeof data.access_token === "string" &&
        data.access_token.length > 0 &&
        typeof data.refresh_token === "string" &&
        data.refresh_token.length > 0
      ) {
        popupRef.current = null;
        setError(null);
        setBusy(false);
        useAuth.getState().completeOidc(data.access_token, data.refresh_token);
        onDone?.();
      } else if (data.type === "osap-oidc-error") {
        popupRef.current = null;
        setError(typeof data.message === "string" ? data.message : t("auth.error"));
        setBusy(false);
      }
    };

    window.addEventListener("message", onMessage);
    return () => {
      window.removeEventListener("message", onMessage);
      popupRef.current = null;
    };
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
    popupRef.current = popup;
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
      if (!openPopup(result.authorize_url)) {
        setBusy(false);
        return false;
      }
      return true;
    } catch {
      setBusy(false);
      setError(t("auth.oidcUnavailable"));
      return false;
    }
  };

  return { start, error, busy };
}
