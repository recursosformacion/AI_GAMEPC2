import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Envelope } from "../components/Envelope";
import { useI18n } from "../i18n/I18n";
import { useSources } from "../state/repositorySources";
import { useProviders } from "../state/providers";

export function SourceCatalogPage() {
  const { t } = useI18n();
  const { list, detail, loadList, loadDetail } = useSources();
  const providers = useProviders((s) => s.data);
  const listProviders = useProviders((s) => s.list);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    void loadList();
    void listProviders();
  }, [loadList, listProviders]);

  const open = (sourceId: string) => {
    setSelected(sourceId);
    void loadDetail(sourceId);
  };

  const descOf = (p: { description?: Record<string, string> | string | null }): string => {
    const d = p.description;
    if (d && typeof d === "object") return d.en ?? d.es ?? Object.values(d)[0] ?? "";
    if (typeof d === "string") return d;
    return "";
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
          const providerList = providers ?? [];
          // Una sola tarjeta por fuente: fusiona la info del storage (nombre, provider,
          // trust/verified, estrellas, calidad) con la del provider de osap-api
          // (descripción, formatos, website). Clave común: source_id == provider_id.
          const byProvider = new Map(providerList.map((p) => [p.provider_id.toLowerCase(), p]));
          const sourceIds = new Set(wired.map((s) => s.source_id.toLowerCase()));
          const orphanProviders = providerList.filter((p) => !sourceIds.has(p.provider_id.toLowerCase()));
          const merged = wired.map((s) => ({ source: s, provider: byProvider.get(s.source_id.toLowerCase()) }));

          const renderCard = (
            source: (typeof wired)[number],
            provider: (typeof providerList)[number] | undefined,
            key: string,
          ) => {
            const desc = provider ? descOf(provider) : "";
            const formats = provider?.formats.length ? provider.formats : source.type ? [source.type] : [];
            const website = provider?.website;
            const stars = Math.max(1, Math.min(5, Math.round(source.quality / 20)));
            return (
              <li key={key}>
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => open(source.source_id)}
                  onKeyDown={(e) => e.key === "Enter" && open(source.source_id)}
                  className="block h-full w-full cursor-pointer rounded-lg border border-osap-border bg-osap-surface p-4 text-left shadow-sm hover:border-osap-accent"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-osap-accent">{source.name}</span>
                    <span className={`text-sm ${source.status === "Online" ? "text-osap-success" : "text-osap-danger"}`}>
                      {source.status}
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-1 text-xs text-osap-muted">
                    {source.source_id ? <span className="font-mono">{source.source_id}</span> : null}
                    {source.trust ? <span className="rounded bg-osap-surface px-1.5 py-0.5">{source.trust}</span> : null}
                    {source.origin ? <span>{source.origin}</span> : null}
                  </div>
                  <div className="mt-2 text-sm">
                    {"★".repeat(stars)}
                    <span className="ml-1 text-osap-muted">
                      {source.quality}/100 · {source.quality_label}
                    </span>
                  </div>
                  {desc ? <p className="mt-2 text-sm text-osap-muted">{desc}</p> : null}
                  {formats.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {formats.map((f) => (
                        <span key={f} className="rounded bg-osap-accent-soft px-2 py-0.5 text-xs">
                          {f}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {website ? (
                    <a
                      href={website}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="mt-3 inline-flex items-center gap-1 text-xs text-osap-accent hover:underline"
                    >
                      {website.replace(/^https?:\/\//, "")} ↗
                    </a>
                  ) : null}
                </div>
              </li>
            );
          };

          return (
            <ul className="grid gap-4 sm:grid-cols-2">
              {merged.map(({ source, provider }) => renderCard(source, provider, `src-${source.source_id}`))}
              {orphanProviders.map((p) => {
                // Providers sin fuente en el storage (no cableados o nuevos): tarjeta propia.
                const pseudoSource: (typeof wired)[number] = {
                  source_id: p.provider_id,
                  name: p.name,
                  type: p.formats[0] ?? "",
                  origin: "",
                  trust: "",
                  status: p.available ? "Online" : "Offline",
                  quality: 0,
                  quality_label: "",
                  updated_at: "",
                };
                return renderCard(pseudoSource, p, `prov-${p.provider_id}`);
              })}
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
