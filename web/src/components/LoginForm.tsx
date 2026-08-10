import { useState } from "react";
import { useI18n } from "../i18n/I18n";
import { useAuth } from "../state/auth";

export function LoginForm() {
  const { t } = useI18n();
  const login = useAuth((s) => s.login);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      setEmail("");
      setPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth.error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex items-center gap-2">
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder={t("auth.email")}
        required
        className="w-40 rounded border border-osap-border bg-osap-bg px-2 py-1 text-sm"
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder={t("auth.password")}
        required
        className="w-32 rounded border border-osap-border bg-osap-bg px-2 py-1 text-sm"
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
