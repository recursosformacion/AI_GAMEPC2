import { useRef, useState } from "react";
import { apiClient } from "../api/ApiClient";
import { useI18n } from "../i18n/I18n";

// Campo de imagen de «Los amigos»: permite pegar una URL o subir un fichero (que se
// reenvía a osap-storage vía osap-api y devuelve su URL pública). Reutilizable para
// logo/portada/fotos. Requiere un `groupId` ya existente (destino de la subida).
export function AmigosImageField({
  groupId,
  scope = "group",
  label,
  value,
  onChange,
  disabled = false,
}: {
  groupId?: string;
  scope?: "group" | "events" | "blog";
  label: string;
  value: string;
  onChange: (url: string) => void;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pick = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const res = await apiClient.uploadAmigosImage(file, { groupId, scope });
      onChange(res.url);
    } catch {
      setError(t("friends.errorSaving"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="text-xs text-osap-muted">
      <span>{label}</span>
      <div className="mt-1 flex flex-wrap items-center gap-2">
        {value !== "" ? (
          <img
            src={value}
            alt=""
            className="h-10 w-10 rounded-md border border-osap-border object-cover"
          />
        ) : null}
        <input
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          placeholder="https://…"
          className="min-w-48 flex-1 rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm disabled:opacity-60"
        />
        {disabled ? null : (
          <>
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void pick(file);
                e.target.value = "";
              }}
            />
            <button
              type="button"
              disabled={busy}
              onClick={() => inputRef.current?.click()}
              className="rounded-md border border-osap-border px-3 py-2 text-sm disabled:opacity-50"
            >
              {busy ? t("friends.uploading") : t("friends.upload")}
            </button>
          </>
        )}
      </div>
      {error ? <p className="mt-1 text-osap-danger">{error}</p> : null}
    </div>
  );
}
