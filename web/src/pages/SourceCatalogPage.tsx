import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Envelope } from "../components/Envelope";
import { useI18n } from "../i18n/I18n";
import { useSources } from "../state/repositorySources";

export function SourceCatalogPage() {
  const { t } = useI18n();
  const { list, detail, loadList, loadDetail } = useSources();
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  const open = (sourceId: string) => {
    setSelected(sourceId);
    void loadDetail(sourceId);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{t("nav.sources")}</h1>
          <p className="text-sm text-osap-muted">
            {t("sources.connected").replace("{n}", String((list.data ?? []).filter((s) => s.status === "Online").length))}
          </p>
        </div>
        <Link to="/sources" className="rounded bg-osap-accent px-4 py-1.5 text-sm text-white">
          {t("sources.add")}
        </Link>
      </div>

      <Envelope loading={list.loading} error={list.error} data={list.data} emptyMessage={t("states.empty")}>
        {(sources) => {
          const wired = sources.filter((s) => s.status === "Online");
          return (
            <ul className="grid gap-4 sm:grid-cols-2">
              {wired.map((s) => (
              <li key={s.source_id}>
                <button
                  type="button"
                  onClick={() => open(s.source_id)}
                  className="block w-full rounded-lg border border-osap-border bg-osap-surface p-4 text-left shadow-sm hover:border-osap-accent"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-osap-accent">{s.name}</span>
                    <span className={`text-sm ${s.status === "Online" ? "text-osap-success" : "text-osap-danger"}`}>
                      {s.status}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-osap-muted">
                    {s.type} · {s.origin} · {s.trust}
                  </div>
                  <div className="mt-2 text-sm">
                    {"★".repeat(Math.max(1, Math.min(5, Math.round(s.quality / 20))))}
                    <span className="ml-1 text-osap-muted">
                      {s.quality}/100 · {s.quality_label}
                    </span>
                  </div>
                </button>
              </li>
            ))}
            </ul>
          );
        }}
      </Envelope>

      {selected !== null ? (
        <Envelope loading={detail.loading} error={detail.error} data={detail.data} isEmpty={(d) => d === null}>
          {(source) => (
            <section className="rounded-lg border border-osap-border bg-osap-surface p-4 shadow-sm">
              <h2 className="text-lg font-semibold">{source.name}</h2>
              <p className="text-xs text-osap-muted">
                {source.type} · {source.origin} · {source.trust} · {source.status}
              </p>

              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div>
                  <h3 className="text-xs font-semibold uppercase text-osap-muted">Automatic</h3>
                  <dl className="mt-2 space-y-1 text-sm">
                    <Field label="Quality" value={`${source.quality}/100 (${source.quality_label})`} />
                    <Field label="Representations" value={String(source.representations)} />
                    <Field label="Works" value={String(source.works)} />
                    <Field label="Composers" value={String(source.composers)} />
                    <Field label="Duplicates" value={`${source.duplicate_percent}%`} />
                    <Field label="Updated" value={source.updated_at} />
                  </dl>
                </div>
                <div>
                  <h3 className="text-xs font-semibold uppercase text-osap-muted">Documentation</h3>
                  <p className="mt-2 text-sm">{source.description}</p>
                  <p className="mt-1 text-xs text-osap-muted">
                    License: {source.license} · <a href={source.website} className="text-osap-accent">{source.website}</a>
                  </p>
                  {source.notes ? <p className="mt-1 text-sm italic text-osap-muted">"{source.notes}"</p> : null}
                </div>
              </div>

              <div className="mt-4">
                <h3 className="text-xs font-semibold uppercase text-osap-muted">Formats</h3>
                <div className="mt-1 flex flex-wrap gap-1">
                  {source.formats.map((f) => (
                    <span key={f} className="rounded bg-osap-accent-soft px-2 py-0.5 text-xs">
                      {f}
                    </span>
                  ))}
                </div>
              </div>

              <div className="mt-4">
                <h3 className="text-xs font-semibold uppercase text-osap-muted">Catalogues</h3>
                <div className="mt-1 flex flex-wrap gap-1">
                  {source.catalogues.map((c) => (
                    <span key={c} className="rounded border border-osap-border px-2 py-0.5 text-xs">
                      {c}
                    </span>
                  ))}
                </div>
              </div>

              {source.tags.length > 0 ? (
                <div className="mt-4">
                  <h3 className="text-xs font-semibold uppercase text-osap-muted">Tags</h3>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {source.tags.map((tag) => (
                      <span key={tag} className="rounded bg-osap-accent-soft px-2 py-0.5 text-xs text-osap-accent">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="mt-4">
                <h3 className="text-xs font-semibold uppercase text-osap-muted">Community</h3>
                <p className="mt-1 text-sm">
                  {"★".repeat(source.community_rating)}
                  {"☆".repeat(5 - source.community_rating)} · {source.reviews} reviews
                </p>
                <p className="text-xs text-osap-muted">
                  Searches {source.searches} · Downloads {source.downloads} · Contributions {source.contributions} ·
                  Availability {source.availability}%
                </p>
              </div>

              {source.observations.length > 0 ? (
                <div className="mt-4">
                  <h3 className="text-xs font-semibold uppercase text-osap-muted">Observations</h3>
                  <ul className="mt-1 space-y-1 text-sm">
                    {source.observations.map((o) => (
                      <li key={o.date}>
                        <span className="text-osap-muted">{o.date}</span>: {o.text}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </section>
          )}
        </Envelope>
      ) : null}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-osap-muted">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
