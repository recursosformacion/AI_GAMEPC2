import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useI18n } from "../i18n/I18n";
import { useAuth } from "../state/auth";

// Recibe el resultado del callback OIDC:
// - éxito: spa_origin/auth/callback#access_token=...&refresh_token=...
// - error:  spa_origin/auth/callback?error=...
// En el popup, envía el resultado a la ventana que lo abrió (postMessage) y cierra.
// Si se accede directo (sin opener), completa el login o muestra el error aquí.
export function AuthCallbackPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    const err = query.get("error");
    const hash = window.location.hash.replace(/^#/, "");
    const params = new URLSearchParams(hash);
    const access = params.get("access_token");
    const refresh = params.get("refresh_token");

    const send = (data: { type: string; message?: string; access_token?: string; refresh_token?: string }) => {
      if (window.opener) {
        window.opener.postMessage(data, window.location.origin);
        window.close();
        return true;
      }
      return false;
    };

    if (err) {
      if (send({ type: "osap-oidc-error", message: err })) return;
      setError(err);
      return;
    }
    if (access && refresh) {
      if (send({ type: "osap-oidc", access_token: access, refresh_token: refresh })) return;
      useAuth.getState().completeOidc(access, refresh);
      window.history.replaceState(null, "", "/");
      navigate("/", { replace: true });
      return;
    }

    if (send({ type: "osap-oidc-error", message: t("auth.callbackInvalid") })) return;
    setError(t("auth.callbackInvalid"));
  }, [navigate, t]);

  if (error !== null) {
    return <p className="py-16 text-center text-sm text-red-500">{error}</p>;
  }
  return <p className="py-16 text-center text-sm text-osap-muted">{t("auth.completing")}</p>;
}
