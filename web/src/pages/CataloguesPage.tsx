import { useEffect } from "react";
import { Envelope } from "../components/Envelope";
import { useI18n } from "../i18n/I18n";
import { useCatalogues } from "../state/classification";

export function CataloguesPage() {
  const { t } = useI18n();
  const { data, loading, error, list } = useCatalogues();
  useEffect(() => {
    void list();
  }, [list]);

  return (
    <div className="space-y-6">
      <header className="border-b border-osap-border pb-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-osap-accent">
          {t("classification.label")}
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-osap-ink">{t("catalogues.title")}</h1>
        <p className="mt-2 max-w-2xl text-sm text-osap-muted">{t("catalogues.subtitle")}</p>
      </header>

      <Envelope loading={loading} error={error} data={data} emptyMessage={t("states.empty")}>
        {(catalogues) => (
          <ul className="divide-y divide-osap-border overflow-hidden rounded-card border border-osap-border bg-osap-surface shadow-card">
            {catalogues.map((cat) => (
              <li key={cat.id} className="px-5 py-4">
                <div className="flex items-baseline gap-2">
                  <span className="rounded bg-osap-accent-soft px-2 py-0.5 text-xs font-semibold text-osap-accent">
                    {cat.prefix}
                  </span>
                  <h2 className="text-lg text-osap-ink">{cat.catalogue_name}</h2>
                </div>
                {cat.description ? (
                  <p className="mt-1 text-sm leading-relaxed text-osap-ink">{cat.description}</p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Envelope>
    </div>
  );
}
