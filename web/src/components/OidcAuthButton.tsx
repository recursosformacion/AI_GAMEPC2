import { useI18n } from "../i18n/I18n";
import { useOidcLogin } from "./useOidcLogin";

// Botón de login/registro vía osap-auth (OIDC) en ventana flotante centrada y sin URL.
export function OidcAuthButton({ onDone, label }: { onDone?: () => void; label?: string }) {
  const { t } = useI18n();
  const { start, error, busy } = useOidcLogin(onDone);

  return (
    <div className="flex flex-col gap-2">
      <button
        disabled={busy}
        onClick={() => void start()}
        className="rounded bg-osap-accent px-3 py-2 text-sm text-white disabled:opacity-60"
      >
        {busy ? t("auth.working") : label ?? t("auth.oidc")}
      </button>
      {error !== null && <span className="text-xs text-red-500">{error}</span>}
    </div>
  );
}
