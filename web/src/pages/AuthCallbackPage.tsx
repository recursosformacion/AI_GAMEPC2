import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useI18n } from "../i18n/I18n";
import { useAuth } from "../state/auth";

// Recibe la sesión que osap-api devolvió tras el callback OIDC (en el fragmento #).
// - En el popup (login OIDC): envía la sesión a la ventana que abrió el popup y cierra.
// - Si se accede directo (sin opener): completa el login en esta misma ventana.
export function AuthCallbackPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const hash = window.location.hash.replace(/^#/, "");
    const params = new URLSearchParams(hash);
    const access = params.get("access_token");
    const refresh = params.get("refresh_token");
    if (!access || !refresh) {
      setError(t("auth.callbackInvalid"));
      return;
    }

    if (window.opener) {
      // Flujo popup: entregar la sesión a la ventana principal y cerrar.
      window.opener.postMessage(
        { type: "osap-oidc", access_token: access, refresh_token: refresh },
        window.location.origin,
      );
      window.close();
      return;
    }

    // Acceso directo: completar aquí.
    useAuth.getState().completeOidc(access, refresh);
    window.history.replaceState(null, "", "/");
    navigate("/", { replace: true });
  }, [navigate, t]);

  if (error !== null) {
    return <p className="py-16 text-center text-sm text-red-500">{error}</p>;
  }
  return <p className="py-16 text-center text-sm text-osap-muted">{t("auth.completing")}</p>;
}
