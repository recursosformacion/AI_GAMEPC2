import { useState } from "react";
import type { ComposerSummary } from "../api/types";
import { useI18n } from "../i18n/I18n";
import { useAuth } from "../state/auth";
import { useComposers } from "../state/composers";
import { ComposerSearchSelect } from "./ComposerSearchSelect";

// Fusión dirigida desde el compositor actual: este compositor es el ORIGEN (implícito);
// se selecciona el DESTINO entre todos los compositores existentes. Confirmación explícita.
export function ComposerMergeForm({ origin }: { origin: ComposerSummary }) {
  const { t } = useI18n();
  const isAdmin = useAuth((s) => s.isAdmin());
  const { merge, loading, error } = useComposers();
  const [destino, setDestino] = useState<ComposerSummary | null>(null);
  const [result, setResult] = useState<string | null>(null);

  if (!isAdmin) {
    return null;
  }

  const onMerge = async () => {
    if (!destino) return;
    setResult(null);
    try {
      await merge(destino.id, [origin.id]); // destino = target, origen = source
      setResult(t("composers.mergeDone"));
      setDestino(null);
    } catch {
      // error se muestra desde el store
    }
  };

  return (
    <section className="rounded border border-osap-border bg-osap-surface p-4">
      <h2 className="mb-3 text-base font-semibold">{t("composers.mergeTitle")}</h2>

      <div className="mb-2 rounded border border-osap-border bg-osap-bg p-2">
        <p className="text-xs text-osap-muted">{t("composers.currentComposer")}</p>
        <p className="font-medium">{origin.name}</p>
        <p className="text-xs text-osap-muted">
          {origin.works_count} {t("composers.works")}
        </p>
      </div>

      <p className="mb-1 text-sm text-osap-muted">{t("composers.mergeTarget")}</p>
      <ComposerSearchSelect
        placeholder={t("composers.mergeTargetPlaceholder")}
        onSelect={setDestino}
        excludeId={(id) => id === origin.id}
      />

      {destino !== null && (
        <div className="mt-3 rounded border border-osap-border bg-osap-bg p-2 text-sm">
          <p className="mb-1 text-xs font-semibold uppercase text-osap-muted">{t("composers.mergeConfirm")}</p>
          <p>
            <strong>{t("composers.mergeSource")}:</strong> {origin.name}
          </p>
          <p>
            <strong>{t("composers.mergeDestino")}:</strong> {destino.name}
          </p>
          <p className="mt-1 text-xs text-osap-muted">{t("composers.mergeTransfer")}</p>
          <button
            onClick={onMerge}
            disabled={loading}
            className="mt-2 rounded bg-osap-accent px-4 py-1.5 text-sm text-white disabled:opacity-50"
          >
            {loading ? t("composers.merging") : t("composers.merge")}
          </button>
        </div>
      )}

      {result !== null && <p className="mt-2 text-sm text-osap-muted">{result}</p>}
      {error !== null && <p className="mt-2 text-sm text-red-500">{error.message}</p>}
    </section>
  );
}
