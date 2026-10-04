import { useEffect, useMemo } from "react";
import type { Instrument, InstrumentCategory } from "../api/types";
import { Envelope } from "../components/Envelope";
import { useI18n } from "../i18n/I18n";
import { useInstrumentCategories, useInstruments } from "../state/classification";

// Instrumentos presentados por familias comprensibles. `category_id` se usa SOLO para
// agrupar: no se expone la taxonomía técnica ni el id de categoría al usuario.
export function InstrumentsPage() {
  const { t } = useI18n();
  const instruments = useInstruments();
  const categories = useInstrumentCategories();

  useEffect(() => {
    void instruments.list();
    void categories.list();
  }, [instruments.list, categories.list]);

  const grupos = useMemo(() => {
    const byId = new Map<number, InstrumentCategory>(categories.data?.map((c) => [c.id, c]) ?? []);
    const rootOf = (id: number): InstrumentCategory | undefined => {
      let current = byId.get(id);
      while (current?.parent_id != null) {
        const parent = byId.get(current.parent_id);
        if (!parent) break;
        current = parent;
      }
      return current;
    };
    const map = new Map<string, { sort: number; items: Instrument[] }>();
    for (const instrument of instruments.data ?? []) {
      const root = rootOf(instrument.category_id);
      const key = root?.name ?? t("instruments.other");
      const entry = map.get(key) ?? { sort: root?.sort ?? 999, items: [] };
      entry.items.push(instrument);
      map.set(key, entry);
    }
    return [...map.entries()]
      .sort((a, b) => a[1].sort - b[1].sort || a[0].localeCompare(b[0]))
      .map(([name, entry]) => ({
        name,
        items: entry.items.sort((x, y) => x.sort - y.sort || x.name_es.localeCompare(y.name_es)),
      }));
  }, [instruments.data, categories.data, t]);

  const loading = instruments.loading || categories.loading;
  const error = instruments.error ?? categories.error;

  return (
    <div className="space-y-6">
      <header className="border-b border-osap-border pb-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-osap-accent">
          {t("classification.label")}
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-osap-ink">{t("instruments.title")}</h1>
        <p className="mt-2 max-w-2xl text-sm text-osap-muted">{t("instruments.subtitle")}</p>
      </header>

      <Envelope loading={loading} error={error} data={grupos} emptyMessage={t("states.empty")}>
        {(groups) => (
          <div className="space-y-8">
            {groups.map((group) => (
              <section key={group.name}>
                <h2 className="text-xl text-osap-ink">{group.name}</h2>
                <ul className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {group.items.map((instrument) => (
                    <li
                      key={instrument.id}
                      className="rounded-card border border-osap-border bg-osap-surface px-4 py-3 shadow-card"
                    >
                      <p className="text-sm text-osap-ink">{instrument.name_es}</p>
                      {instrument.name_en && instrument.name_en !== instrument.name_es ? (
                        <p className="text-xs text-osap-muted">{instrument.name_en}</p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
      </Envelope>
    </div>
  );
}
