import { useState } from "react";
import { apiClient } from "../api/ApiClient";
import { useI18n } from "../i18n/I18n";

interface OidcStart {
  authorize_url: string;
  configured: boolean;
}

// Login vía osap-auth como IdP (OIDC Authorization Code + PKCE): se redirige al
// navegador a la pantalla de authorize de osap-auth. El callback (backend) devuelve
// la sesión a la SPA en /auth/callback.
export function LoginForm({ onDone }: { onDone?: () => void }) {
  const { t } = useI18n();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await apiClient.get<OidcStart>("/auth/oidc/start");
      if (!result.authorize_url) {
        setError(t("auth.oidcUnavailable"));
        setBusy(false);
        return;
      }
      window.location.assign(result.authorize_url);
    } catch {
      setError(t("auth.oidcUnavailable"));
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <button
        disabled={busy}
        onClick={start}
        className="rounded bg-osap-accent px-3 py-2 text-sm text-white disabled:opacity-60"
      >
        {busy ? t("auth.working") : t("auth.oidc")}
      </button>
      {onDone ? (
        <button onClick={onDone} className="rounded px-3 py-1 text-xs text-osap-muted">
          {t("auth.skip")}
        </button>
      ) : null}
      {error !== null && <span className="text-xs text-red-500">{error}</span>}
    </div>
  );
}
