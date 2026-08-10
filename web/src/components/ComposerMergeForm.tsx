import { useEffect, useState } from "react";
import { apiClient } from "../api/ApiClient";
import type { ComposerSummary } from "../api/types";
import { useI18n } from "../i18n/I18n";
import { useAuth } from "../state/auth";
import { useComposers } from "../state/composers";
import { ComposerSearchSelect } from "./ComposerSearchSelect";

type Mode = "existing" | "new";

// Fusión dirigida desde el compositor actual: este compositor es el ORIGEN (implícito).
// El destino puede ser un compositor existente o uno nuevo que aún no existe: en ese caso
// se avisa, se pide el nombre y se crea (con los datos de la fusión) antes de fusionar.
export function ComposerMergeForm({ origin }: { origin: ComposerSummary }) {
  const { t } = useI18n();
  const isAdmin = useAuth((s) => s.isAdmin());
  const { merge, createComposer, loading, error } = useComposers();
  const [mode, setMode] = useState<Mode>("existing");
  const [destino, setDestino] = useState<ComposerSummary | null>(null);
  const [newName, setNewName] = useState("");
  const [newMatch, setNewMatch] = useState<ComposerSummary | null>(null);
  const [checked, setChecked] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  // Comprueba si el nombre introducido ya existe como compositor.
  useEffect(() => {
    const name = newName.trim();
    if (name.length < 2) {
      setNewMatch(null);
      setChecked(false);
      return;
    }
    let active = true;
    setChecked(false);
    apiClient
      .getComposers(name, 5, 0)
      .then((r) => {
        if (!active) return;
        const exact = r.items.find((c) => c.name.toLowerCase() === name.toLowerCase());
        setNewMatch(exact ?? null);
        setChecked(true);
      })
      .catch(() => {
        if (active) {
          setNewMatch(null);
          setChecked(true);
        }
      });
    return () => {
      active = false;
    };
  }, [newName]);

  if (!isAdmin) {
    return null;
  }

  const onMergeExisting = async () => {
    if (!destino) return;
    setResult(null);
    try {
      await merge(destino.id, [origin.id]);
      setResult(t("composers.mergeDone"));
      setDestino(null);
    } catch {
      // error se muestra desde el store
    }
  };

  const onMergeNew = async () => {
    const name = newName.trim();
    if (name.length === 0) return;
    setResult(null);
    try {
      if (newMatch) {
        await merge(newMatch.id, [origin.id]);
      } else {
        const created = await createComposer(name);
        await merge(created.id, [origin.id]);
      }
      setResult(t("composers.mergeDone"));
      setNewName("");
      setNewMatch(null);
      setChecked(false);
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

      <div className="mb-3 flex gap-2 text-sm">
        <button
          type="button"
          onClick={() => setMode("existing")}
          className={`rounded px-3 py-1 ${mode === "existing" ? "bg-osap-accent text-white" : "border border-osap-border text-osap-muted"}`}
        >
          {t("composers.mergeExisting")}
        </button>
        <button
          type="button"
          onClick={() => setMode("new")}
          className={`rounded px-3 py-1 ${mode === "new" ? "bg-osap-accent text-white" : "border border-osap-border text-osap-muted"}`}
        >
          {t("composers.mergeNew")}
        </button>
      </div>

      {mode === "existing" ? (
        <>
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
              <button
                onClick={onMergeExisting}
                disabled={loading}
                className="mt-2 rounded bg-osap-accent px-4 py-1.5 text-sm text-white disabled:opacity-50"
              >
                {loading ? t("composers.merging") : t("composers.merge")}
              </button>
            </div>
          )}
        </>
      ) : (
        <div className="space-y-2">
          <p className="mb-1 text-sm text-osap-muted">{t("composers.mergeNewPlaceholder")}</p>
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder={t("composers.mergeNewHint")}
            className="w-full rounded border border-osap-border bg-osap-bg px-3 py-1 text-sm"
          />

          {checked && newName.trim().length >= 2 && (
            <div className="rounded border border-osap-border bg-osap-bg p-2 text-sm">
              {newMatch ? (
                <p className="text-osap-accent">
                  <strong>{t("composers.mergeNewExists")}</strong> {newMatch.name}
                </p>
              ) : (
                <p className="text-amber-700">
                  <strong>{t("composers.mergeNewWarn")}</strong> {newName.trim()}
                </p>
              )}
            </div>
          )}

          <button
            onClick={onMergeNew}
            disabled={loading || newName.trim().length === 0}
            className="rounded bg-osap-accent px-4 py-1.5 text-sm text-white disabled:opacity-50"
          >
            {loading ? t("composers.merging") : newMatch ? t("composers.merge") : t("composers.mergeCreate")}
          </button>
        </div>
      )}

      {result !== null && <p className="mt-2 text-sm text-osap-muted">{result}</p>}
      {error !== null && <p className="mt-2 text-sm text-red-500">{error.message}</p>}
    </section>
  );
}
