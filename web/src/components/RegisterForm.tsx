import { useState } from "react";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import { useI18n } from "../i18n/I18n";

// Registro de usuario: Web → osap-api → osap-auth. Sin auto-login.
export function RegisterForm({ onDone }: { onDone?: () => void }) {
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ message: string; token: string | null } | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await apiClient.register(email, password, name || undefined);
      // No auto-login: mostrar "verifica tu email". En dev, si hay token, se autoverifica.
      if (res.verification_token) {
        await apiClient.verifyEmail(res.verification_token);
        setDone({ message: t("registro.verified"), token: res.verification_token });
        onDone?.();
      } else {
        setDone({ message: res.message || t("registro.checkYourEmail"), token: null });
        onDone?.();
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("registro.error"));
    } finally {
      setBusy(false);
    }
  };

  if (done !== null) {
    return <p className="text-sm text-osap-muted">{done.message}</p>;
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder={t("registro.email")}
        required
        className="rounded border border-osap-border bg-osap-bg px-2 py-1 text-sm"
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder={t("registro.password")}
        required
        minLength={8}
        className="rounded border border-osap-border bg-osap-bg px-2 py-1 text-sm"
      />
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder={t("registro.name")}
        className="rounded border border-osap-border bg-osap-bg px-2 py-1 text-sm"
      />
      <button disabled={busy} className="rounded bg-osap-accent px-3 py-1 text-sm text-white disabled:opacity-60">
        {busy ? t("registro.working") : t("registro.submit")}
      </button>
      {error !== null && <span className="text-xs text-red-500">{error}</span>}
    </form>
  );
}
