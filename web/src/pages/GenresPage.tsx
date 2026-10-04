import { useEffect } from "react";
import { Envelope } from "../components/Envelope";
import { useI18n } from "../i18n/I18n";
import { useGenres } from "../state/classification";

export function GenresPage() {
  const { t } = useI18n();
  const { data, loading, error, list } = useGenres();
  useEffect(() => {
    void list();
  }, [list]);

  return (
    <div className="space-y-6">
      <header className="border-b border-osap-border pb-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-osap-accent">
          {t("classification.label")}
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-osap-ink">{t("genres.title")}</h1>
        <p className="mt-2 max-w-2xl text-sm text-osap-muted">{t("genres.subtitle")}</p>
      </header>

      <Envelope loading={loading} error={error} data={data} emptyMessage={t("states.empty")}>
        {(genres) => (
          <ul className="divide-y divide-osap-border overflow-hidden rounded-card border border-osap-border bg-osap-surface shadow-card">
            {genres.map((genre) => (
              <li key={genre.id} className="px-5 py-4">
                <h2 className="text-lg text-osap-ink">{genre.name}</h2>
                {genre.description ? (
                  <p className="mt-1 text-sm leading-relaxed text-osap-muted">{genre.description}</p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Envelope>
    </div>
  );
}
