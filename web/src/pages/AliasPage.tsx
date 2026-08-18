import { useEffect, useState } from "react";
import { apiClient } from "../api/ApiClient";
import type { Alias, ComposerSummary } from "../api/types";
import { ComposerSearchSelect } from "../components/ComposerSearchSelect";
import { Envelope } from "../components/Envelope";
import { useI18n } from "../i18n/I18n";
import { useComposers } from "../state/composers";

// Pantalla de aliases: buscar por compositor o alias, liberar un alias mal asignado
// (moverlo a otro compositor o promoverlo a su propio Composer) y añadir aliases.
// Los aliases NUNCA se borran: siempre se mueven/promueven.
export function AliasPage() {
  const { t } = useI18n();
  const { list, loading, error, q, setQuery, fetchList, addAlias, moveAlias, promoteAlias } = useComposers();
  const [input, setInput] = useState(q);
  const [aliasesByComposer, setAliasesByComposer] = useState<Record<string, Alias[]>>({});
  const [newAlias, setNewAlias] = useState<Record<string, string>>({});
  const [moveTarget, setMoveTarget] = useState<ComposerSummary | null>(null);
  const [moveFor, setMoveFor] = useState<{ composerId: string; aliasId: number } | null>(null);

  useEffect(() => {
    void fetchList(q, 30, 0, null, "all");
  }, [fetchList, q]);

  // Carga los aliases (con id) de cada compositor del listado.
  useEffect(() => {
    const ids = list?.items.map((c) => c.id) ?? [];
    void Promise.all(
      ids.map(async (id) => {
        try {
          const aliases = await apiClient.listAliases(id);
          setAliasesByComposer((prev) => ({ ...prev, [id]: aliases }));
        } catch {
          /* sin aliases */
        }
      }),
    );
  }, [list]);

  const search = () => {
    setQuery(input);
  };

  const onAdd = (composerId: string) => {
    const alias = (newAlias[composerId] ?? "").trim();
    if (!alias) return;
    void addAlias(composerId, alias).then(() => {
      setNewAlias((prev) => ({ ...prev, [composerId]: "" }));
      apiClient.listAliases(composerId).then((a) => setAliasesByComposer((p) => ({ ...p, [composerId]: a })));
    });
  };

  const onMoveConfirm = () => {
    if (!moveFor || !moveTarget) return;
    void moveAlias(moveFor.composerId, moveFor.aliasId, moveTarget.id).then(() => {
      apiClient.listAliases(moveFor.composerId).then((a) =>
        setAliasesByComposer((p) => ({ ...p, [moveFor.composerId]: a })),
      );
      setMoveFor(null);
      setMoveTarget(null);
    });
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{t("admin.aliases")}</h1>

      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder={t("aliases.searchPlaceholder")}
          className="w-full rounded border border-osap-border bg-osap-surface px-3 py-1 text-sm"
        />
        <button onClick={search} className="rounded bg-osap-accent px-4 py-1 text-sm text-white">
          {t("search")}
        </button>
      </div>

      <Envelope loading={loading} error={error} data={list} emptyMessage={t("states.empty")}>
        {(data) => (
          <ul className="divide-y divide-osap-border rounded border border-osap-border">
            {data.items.map((c) => {
              const aliases = aliasesByComposer[c.id] ?? [];
              return (
                <li key={c.id} className="px-3 py-3">
                  <p className="mb-1 font-medium">{c.name}</p>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {aliases.map((a) => (
                      <span key={a.id} className="inline-flex items-center gap-1 rounded-full border border-osap-border bg-osap-surface px-2 py-0.5 text-xs">
                        {a.alias}
                        <button
                          title={t("aliases.move")}
                          onClick={() => {
                            setMoveFor({ composerId: c.id, aliasId: a.id });
                            setMoveTarget(null);
                          }}
                          className="text-osap-muted hover:text-osap-accent"
                        >
                          ▸
                        </button>
                        <button
                          title={t("aliases.promote")}
                          onClick={() => void promoteAlias(c.id, a.id)}
                          className="text-osap-muted hover:text-osap-accent"
                        >
                          ↑
                        </button>
                      </span>
                    ))}
                    <span className="inline-flex items-center gap-1">
                      <input
                        value={newAlias[c.id] ?? ""}
                        onChange={(e) => setNewAlias((p) => ({ ...p, [c.id]: e.target.value }))}
                        placeholder={t("aliases.add")}
                        className="w-36 rounded border border-osap-border bg-osap-surface px-2 py-0.5 text-xs"
                      />
                      <button onClick={() => onAdd(c.id)} className="rounded bg-osap-accent px-2 py-0.5 text-xs text-white">
                        +
                      </button>
                    </span>
                  </div>
                  {moveFor && moveFor.composerId === c.id && (
                    <div className="mt-2 flex flex-wrap items-end gap-2 rounded border border-osap-accent bg-osap-accent-soft p-2">
                      <div className="flex-1">
                        <p className="mb-1 text-xs text-osap-muted">{t("aliases.moveTarget")}</p>
                        <ComposerSearchSelect placeholder={t("aliases.moveTargetPlaceholder")} onSelect={setMoveTarget} />
                      </div>
                      <button onClick={onMoveConfirm} disabled={moveTarget === null} className="rounded bg-osap-accent px-3 py-1 text-xs text-white disabled:opacity-50">
                        {t("aliases.move")}
                      </button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Envelope>
    </div>
  );
}
