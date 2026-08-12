import { useEffect, useState } from "react";
import { apiClient } from "../api/ApiClient";
import { useI18n } from "../i18n/I18n";
import { useAuth } from "../state/auth";

interface OidcStart {
  authorize_url: string;
  configured: boolean;
}

type Mode = "checking" | "oidc" | "password";

// Login vía osap-auth. Si el OIDC está configurado (authorize/token confirmados por
// osap-auth) se muestra "Continuar con cuenta OSAP" (redirect). Si no, se muestra el
// formulario de email/password como respaldo hasta que el OIDC esté activo.
export function LoginForm({ onDone }: { onDone?: () => void }) {
  const { t } = useI18n();
  const login = useAuth((s) => s.login);
  const [mode, setMode] = useState<Mode>("checking");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    let active = true;
    apiClient
      .get<OidcStart>("/auth/oidc/start")
      .then((r) => {
        if (active) setMode(r.authorize_url ? "oidc" : "password");
      })
      .catch(() => {
        if (active) setMode("password");
      });
    return () => {
      active = false;
    };
  }, []);

  const startOidc = async () => {
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

  const submitPassword = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      setEmail("");
      setPassword("");
      onDone?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth.error"));
    } finally {
      setBusy(false);
    }
  };

  if (mode === "checking") {
    return <p className="py-1 text-sm text-osap-muted">{t("auth.working")}</p>;
  }

  if (mode === "oidc") {
    return (
      <div className="flex flex-col gap-2">
        <button
          disabled={busy}
          onClick={startOidc}
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

  return (
    <form onSubmit={submitPassword} className="flex flex-col gap-2">
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder={t("auth.email")}
        required
        autoFocus
        className="rounded border border-osap-border bg-osap-bg px-2 py-1 text-sm"
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder={t("auth.password")}
        required
        className="rounded border border-osap-border bg-osap-bg px-2 py-1 text-sm"
      />
      <button
        disabled={busy}
        className="rounded bg-osap-accent px-3 py-1 text-sm text-white disabled:opacity-60"
      >
        {busy ? t("auth.working") : t("auth.login")}
      </button>
      {error !== null && <span className="text-xs text-red-500">{error}</span>}
    </form>
  );
}
