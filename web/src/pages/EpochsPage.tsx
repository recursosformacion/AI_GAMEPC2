import { useEffect } from "react";
import { Envelope } from "../components/Envelope";
import { useI18n } from "../i18n/I18n";
import { useEpochs } from "../state/epochs";

// "476–1450" | "desde X" | "hasta Y" | "" según los años disponibles.
function formatRange(
  start: number | null,
  end: number | null,
  since: string,
  until: string,
): string {
  if (start != null && end != null) return `${start}–${end}`;
  if (start != null) return `${since} ${start}`;
  if (end != null) return `${until} ${end}`;
  return "";
}

export function EpochsPage() {
  const { t } = useI18n();
  const { data, loading, error, list } = useEpochs();
  useEffect(() => {
    void list();
  }, [list]);

  return (
    <div className="space-y-6">
      <header className="border-b border-osap-border pb-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-osap-accent">
          {t("epochs.label")}
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-osap-ink">{t("epochs.title")}</h1>
        <p className="mt-2 max-w-2xl text-sm text-osap-muted">{t("epochs.subtitle")}</p>
      </header>

      <Envelope loading={loading} error={error} data={data} emptyMessage={t("states.empty")}>
        {(epochs) => (
          <ul className="space-y-3">
            {epochs.map((epoch) => {
              const range = formatRange(
                epoch.year_start,
                epoch.year_end,
                t("epochs.since"),
                t("epochs.until"),
              );
              return (
                <li
                  key={epoch.id}
                  className="rounded-card border border-osap-border bg-osap-surface p-5 shadow-card"
                >
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <h2 className="text-xl text-osap-ink">{epoch.title}</h2>
                    {range ? <span className="text-sm text-osap-muted">{range}</span> : null}
                  </div>
                  {epoch.description ? (
                    <p className="mt-2 text-sm leading-relaxed text-osap-ink">{epoch.description}</p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </Envelope>
    </div>
  );
}
