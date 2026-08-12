import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useI18n } from "../i18n/I18n";
import { useAuth } from "../state/auth";

// Recibe la sesión que osap-api devolvió tras el callback OIDC (en el fragmento #) y la
// guarda en el store.
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
    useAuth.getState().completeOidc(access, refresh);
    // Limpia el fragmento del historial (no dejar los tokens en la URL).
    window.history.replaceState(null, "", "/");
    navigate("/", { replace: true });
  }, [navigate, t]);

  if (error !== null) {
    return <p className="py-16 text-center text-sm text-red-500">{error}</p>;
  }
  return <p className="py-16 text-center text-sm text-osap-muted">{t("auth.completing")}</p>;
}
