import { useState } from "react";
import type { ComposerSummary } from "../api/types";
import { useI18n } from "../i18n/I18n";
import { useAuth } from "../state/auth";
import { useComposers } from "../state/composers";
import { ComposerSearchSelect } from "./ComposerSearchSelect";

// Formulario de fusión: target y sources seleccionados de compositores EXISTENTES
// (composer_id, nunca texto libre). Muestra evidencia de origen del target cuando existe.
export function ComposerMergeForm() {
  const { t } = useI18n();
  const isAdmin = useAuth((s) => s.isAdmin());
  const { merge, loading, error } = useComposers();
  const [target, setTarget] = useState<ComposerSummary | null>(null);
  const [sources, setSources] = useState<ComposerSummary[]>([]);
  const [result, setResult] = useState<string | null>(null);

  if (!isAdmin) {
    return null;
  }

  const addSource = (c: ComposerSummary) => {
    if (target && c.id === target.id) return;
    if (sources.some((s) => s.id === c.id)) return;
    setSources((prev) => [...prev, c]);
  };

  const onMerge = async () => {
    if (!target || sources.length === 0) return;
    setResult(null);
    try {
      await merge(target.id, sources.map((s) => s.id));
      setResult(t("composers.mergeDone"));
      setSources([]);
    } catch {
      // error se muestra desde el store
    }
  };

  return (
    <section className="rounded border border-osap-border bg-osap-surface p-4">
      <h2 className="mb-3 text-base font-semibold">{t("composers.mergeTitle")}</h2>

      <div className="space-y-3">
        <div>
          <p className="mb-1 text-sm text-osap-muted">{t("composers.mergeTarget")}</p>
          <ComposerSearchSelect
            placeholder={t("composers.mergeTargetPlaceholder")}
            onSelect={setTarget}
            excludeId={(id) => sources.some((s) => s.id === id)}
          />
          {target !== null && (
            <div className="mt-2 rounded border border-osap-border bg-osap-bg p-2 text-sm">
              <p className="font-medium">{target.name}</p>
              <p className="text-xs text-osap-muted">
                {t("composers.works")}: {target.works_count}
              </p>
            </div>
          )}
        </div>

        <div>
          <p className="mb-1 text-sm text-osap-muted">{t("composers.mergeSources")}</p>
          <ComposerSearchSelect
            placeholder={t("composers.mergeSourcesPlaceholder")}
            onSelect={addSource}
            excludeId={(id) => id === target?.id}
          />
          {sources.length > 0 && (
            <ul className="mt-2 space-y-1">
              {sources.map((s) => (
                <li key={s.id} className="flex items-center justify-between text-sm">
                  <span className="truncate">{s.name}</span>
                  <button
                    type="button"
                    onClick={() => setSources((prev) => prev.filter((x) => x.id !== s.id))}
                    className="text-xs text-osap-muted"
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <button
          onClick={onMerge}
          disabled={!target || sources.length === 0 || loading}
          className="rounded bg-osap-accent px-4 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {loading ? t("composers.merging") : t("composers.merge")}
        </button>
        {result !== null && <p className="text-sm text-osap-muted">{result}</p>}
        {error !== null && <p className="text-sm text-red-500">{error.message}</p>}
      </div>
    </section>
  );
}
