import { useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { OsapWorkDetails, PublicWorkRepresentation } from "../api/types";
import { Spinner } from "../components/Spinner";
import { useI18n } from "../i18n/I18n";
import { usePublicWork } from "../state/publicWork";

function canonicalWorkId(raw: string): string {
  return raw.startsWith("index-") ? raw : `index-${raw}`;
}

function viewerHref(rep: PublicWorkRepresentation): string | null {
  if (!rep.downloadable || !rep.id) return null;
  const fmt = rep.format.toLowerCase();
  if (fmt === "midi") return `/viewer?rep=${encodeURIComponent(rep.id)}&format=midi`;
  if (["musicxml", "mxl", "xml", "mei", "pdf"].includes(fmt)) {
    return `/viewer?rep=${encodeURIComponent(rep.id)}`;
  }
  return null;
}

function ExternalIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M14 4h6v6" />
      <path d="M20 4 10 14" />
      <path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5" />
    </svg>
  );
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-osap-muted">{label}</dt>
      <dd className="mt-0.5 break-words text-sm text-osap-ink">{value || "—"}</dd>
    </div>
  );
}

function Fieldset({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="rounded-lg border border-osap-border bg-osap-surface p-4">
      <legend className="px-2 font-display text-base font-semibold text-osap-ink">{title}</legend>
      {children}
    </fieldset>
  );
}

type Tab = "resumen" | "evidencia" | "proveedores";

export function WorkPage() {
  const { id = "" } = useParams();
  const { t } = useI18n();
  const sheet = usePublicWork((s) => s.sheet);
  const state = usePublicWork((s) => s.status);
  const loadedId = usePublicWork((s) => s.loadedId);
  const load = usePublicWork((s) => s.load);
  const canonicalId = canonicalWorkId(id);
  const [tab, setTab] = useState<Tab>("resumen");
  const [osap, setOsap] = useState<OsapWorkDetails | null>(null);

  useEffect(() => {
    if (loadedId === canonicalId) return;
    void load(canonicalId);
  }, [canonicalId, loadedId, load]);

  useEffect(() => {
    if (!sheet) return;
    let alive = true;
    apiClient
      .getOsapWorkDetails(canonicalId)
      .then((data) => { if (alive) setOsap(data); })
      .catch(() => { /* la ficha del índice sigue siendo válida */ });
    return () => { alive = false; };
  }, [canonicalId, sheet]);

  if (state === "idle" || state === "loading") return <Spinner label={t("states.loading")} />;
  if (state === "missing" || sheet === null) {
    return (
      <div className="space-y-1 py-16 text-center">
        <p className="text-osap-ink">{t("empty.noWorksFound")}</p>
        <p className="text-sm text-osap-muted">{t("empty.tryAnother")}</p>
      </div>
    );
  }

  const work = sheet.work as typeof sheet.work & {
    attr_type?: string | null;
    attribution_note?: string | null;
    musical_key?: string | null;
    epoch?: string | null;
    description?: string | null;
    duration?: string | null;
    measures?: string | number | null;
    pages?: string | number | null;
    parts?: string | number | null;
    complexity?: string | null;
    license?: string | null;
    genres?: string | null;
    tags?: string | null;
    ensembles?: string | null;
    updated_at?: string | null;
    access_count?: number | null;
    votes?: number | null;
  };
  const providers = Array.from(new Set(sheet.representations.map((r) => r.provider)));
  // Datos ricos pedidos a OSAP al abrir la ficha; el índice queda como respaldo.
  const d = osap;
  const year = d?.year ?? work.year;
  const catalogue = d?.catalogue ?? work.catalogue;
  const musicalKey = d?.musical_key ?? work.musical_key;
  const description = d?.description ?? work.description;
  const attribution = [
    d?.attribution_type ?? work.attr_type,
    d?.attribution_note ?? work.attribution_note,
  ]
    .filter(Boolean)
    .join(" · ");
  const duration = d?.duration ?? work.duration;
  const measures = d?.measures ?? work.measures;
  const pages = d?.pages ?? work.pages;
  const parts = d?.parts ?? work.parts;
  const complexity = d?.complexity ?? work.complexity;
  const license = d?.license ?? work.license;
  const genres = d?.genres?.length ? d.genres.join(", ") : work.genres;
  const tags = d?.tags ?? work.tags;
  const ensembles = d?.instruments?.length
    ? d.instruments.join(", ")
    : d?.parts_names?.length
      ? d.parts_names.join(", ")
      : work.ensembles;
  const updated = d?.updated_at ?? work.updated_at;
  const created = d?.created_at;

  return (
    <div className="space-y-4">
      <nav className="text-xs text-osap-muted" aria-label="breadcrumb">
        <Link to="/" className="hover:text-osap-accent">Inicio</Link> ›{" "}
        <Link to="/explore" className="hover:text-osap-accent">Obras</Link>
      </nav>

      <header className="border-b border-osap-border pb-3">
        <h1 className="font-display text-3xl font-semibold text-osap-ink">{work.title}</h1>
        <p className="mt-1 text-sm text-osap-muted">
          {[work.composer, work.catalogue, attribution].filter(Boolean).join(" · ") || "—"}
        </p>
        <div className="mt-2 flex flex-wrap gap-2 text-xs">
          {year != null ? <span className="rounded bg-osap-accent-soft px-2 py-0.5">{year}</span> : null}
          {musicalKey ? <span className="rounded bg-osap-accent-soft px-2 py-0.5">{musicalKey}</span> : null}
          <span className="rounded bg-osap-accent-soft px-2 py-0.5">
            {sheet.representations.length} representaciones
          </span>
        </div>
      </header>

      <section className="rounded-lg border border-osap-border bg-osap-surface shadow-sm">
        <div className="flex flex-wrap gap-1 border-b border-osap-border p-2" role="tablist">
          {([
            ["resumen", "Resumen"],
            ["evidencia", "Evidencia"],
            ["proveedores", "Proveedores"],
          ] as const).map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={tab === key}
              onClick={() => setTab(key)}
              className={`rounded px-3 py-1.5 text-sm font-semibold ${
                tab === key ? "bg-osap-accent-soft text-osap-accent" : "text-osap-ink hover:bg-osap-accent-soft/60"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="space-y-4 p-4">
          {tab === "resumen" ? (
            <>
              <Fieldset title="Datos de la obra">
                <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <Field label="Compositor" value={d?.composer ?? work.composer} />
                  <Field label="Atribución" value={attribution} />
                  <Field label="Catálogo" value={catalogue} />
                  <Field label="Año" value={year} />
                  <Field label="Tonalidad" value={musicalKey} />
                  <Field label="Época" value={work.epoch} />
                  <Field label="Descripción" value={description} />
                  <Field label="ID de obra" value={work.work_id} />
                </dl>
              </Fieldset>

              <Fieldset title="Características">
                <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <Field label="Duración" value={duration} />
                  <Field label="Compases" value={measures} />
                  <Field label="Páginas" value={pages} />
                  <Field label="Partes" value={parts} />
                  <Field label="Complejidad" value={complexity} />
                  <Field label="Licencia" value={license} />
                  <Field label="Géneros" value={genres} />
                  <Field label="Tags" value={tags} />
                  <Field label="Instrumentación" value={d?.instrumentation ?? work.instrumentation} />
                </dl>
              </Fieldset>

              <Fieldset title="Ensembles">
                <dl className="grid gap-4 sm:grid-cols-2">
                  <Field label="Ensembles" value={ensembles} />
                </dl>
              </Fieldset>

              <Fieldset title="Estadísticas">
                <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <Field label="Creado" value={created} />
                  <Field label="Actualizado" value={updated} />
                  <Field label="Representaciones" value={sheet.representations.length} />
                  <Field label="Proveedores" value={providers.length} />
                  <Field label="Accesos" value={work.access_count} />
                  <Field label="Votos" value={work.votes} />
                </dl>
              </Fieldset>
            </>
          ) : null}

          {tab === "evidencia" ? (
            <p className="text-sm text-osap-muted">—</p>
          ) : null}

          {tab === "proveedores" ? (
            providers.length > 0 ? (
              <ul className="flex flex-wrap gap-2">
                {providers.map((provider) => (
                  <li key={provider} className="rounded bg-osap-accent-soft px-2 py-0.5 text-sm text-osap-ink">
                    {provider}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-osap-muted">—</p>
            )
          ) : null}
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="font-display text-xl font-semibold text-osap-ink">Representaciones</h2>
        {sheet.representations.length === 0 ? (
          <p className="text-sm text-osap-muted">{t("work.noResources")}</p>
        ) : (
          <ul className="space-y-1">
            {sheet.representations.map((rep, index) => {
              const viewer = viewerHref(rep);
              return (
                <li
                  key={rep.id ?? `${rep.provider}-${rep.format}-${index}`}
                  className="flex flex-wrap items-center justify-between gap-2 rounded border border-osap-border bg-osap-surface px-3 py-2 text-sm"
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium text-osap-ink">
                      {rep.title ?? rep.id ?? `${rep.provider} · ${rep.format}`}
                    </span>
                    <span className="text-xs text-osap-muted">
                      {rep.provider} · {rep.format}
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-3">
                    {viewer ? (
                      <Link to={viewer} className="text-osap-accent hover:underline">Ver</Link>
                    ) : null}
                    {rep.downloadable && rep.url ? (
                      <a href={rep.url} target="_blank" rel="noopener noreferrer" className="text-osap-accent hover:underline">
                        Descargar
                      </a>
                    ) : null}
                    {rep.url ? (
                      <a
                        href={rep.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-osap-accent hover:underline"
                        title={`Abrir en ${rep.provider}`}
                      >
                        Web <ExternalIcon />
                      </a>
                    ) : null}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
