import { useEffect, useState } from "react";
import { Envelope } from "../components/Envelope";
import { useI18n } from "../i18n/I18n";
import { useEnsembles } from "../state/classification";

export function EnsemblesPage() {
  const { t } = useI18n();
  const { data, loading, error, list } = useEnsembles();
  const [q, setQ] = useState("");

  useEffect(() => {
    void list();
  }, [list]);

  return (
    <div className="space-y-6">
      <header className="border-b border-osap-border pb-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-osap-accent">
          {t("classification.label")}
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-osap-ink">{t("ensembles.title")}</h1>
        <p className="mt-2 max-w-2xl text-sm text-osap-muted">{t("ensembles.subtitle")}</p>
      </header>

      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={t("ensembles.filterPlaceholder")}
        className="w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
      />

      <Envelope loading={loading} error={error} data={data} emptyMessage={t("states.empty")}>
        {(ensembles) => {
          const query = q.trim().toLowerCase();
          const filtered = query
            ? ensembles.filter(
                (e) =>
                  e.name.toLowerCase().includes(query) || e.code.toLowerCase().includes(query),
              )
            : ensembles;
          if (filtered.length === 0) {
            return <p className="text-sm text-osap-muted">{t("states.empty")}</p>;
          }
          return (
            <ul className="divide-y divide-osap-border overflow-hidden rounded-card border border-osap-border bg-osap-surface shadow-card">
              {filtered.map((ensemble) => (
                <li key={ensemble.id} className="px-5 py-3">
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="font-display text-base text-osap-ink">{ensemble.name}</p>
                  </div>
                  {ensemble.description ? (
                    <p className="mt-1 text-sm text-osap-muted">{ensemble.description}</p>
                  ) : (
                    <p className="mt-1 text-xs italic text-osap-muted">{t("ensembles.pending")}</p>
                  )}
                </li>
              ))}
            </ul>
          );
        }}
      </Envelope>
    </div>
  );
}
