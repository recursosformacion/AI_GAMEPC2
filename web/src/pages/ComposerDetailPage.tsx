import { useEffect, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { Card } from "../components/Card";
import { Spinner } from "../components/Spinner";
import { SponsorSlot } from "../components/SponsorSlot";
import { WorksListModule, groupWorks } from "../components/WorksListModule";
import { useAuth } from "../state/auth";
import { useComposers } from "../state/composers";
import { useSearches } from "../state/searches";

// Ficha del compositor. Es la misma vista para el público y para el área de admin: aquí
// siempre es de solo lectura; si el usuario es admin se ofrece el acceso a la edición.
// Replica la ficha HTML que servía /compositor/<id>/<slug>.
function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-osap-muted">{label}</dt>
      <dd className="mt-0.5 whitespace-pre-line break-words text-sm text-osap-ink">{value || "—"}</dd>
    </div>
  );
}

export function ComposerDetailPage() {
  const { personId = "" } = useParams<{ personId: string }>();
  const biography = useComposers((s) => s.biography);
  const works = useComposers((s) => s.works);
  const worksFor = useComposers((s) => s.worksFor);
  const fetchBiography = useComposers((s) => s.fetchBiography);
  const fetchWorks = useComposers((s) => s.fetchWorks);
  const indexWorks = useComposers((s) => s.indexWorks);
  const indexWorksFor = useComposers((s) => s.indexWorksFor);
  const fetchIndexWorks = useComposers((s) => s.fetchIndexWorks);
  const isAdmin = useAuth((s) => s.isAdmin());
  const pipeline = useSearches((s) => s.data);
  const searchLoading = useSearches((s) => s.loading);
  const searchPolling = useSearches((s) => s.polling);
  const loading = useComposers((s) => s.loading);

  useEffect(() => {
    if (biography?.id !== personId) void fetchBiography(personId);
  }, [biography?.id, fetchBiography, personId]);

  useEffect(() => {
    if (worksFor !== personId) void fetchWorks(personId, 200, 0);
  }, [fetchWorks, personId, worksFor]);

  useEffect(() => {
    if (indexWorksFor !== personId) void fetchIndexWorks(personId, 300, 0);
  }, [fetchIndexWorks, indexWorksFor, personId]);

  // Igual que una búsqueda con ese compositor (sistema de fusión compartido).
  useEffect(() => {
    if (biography?.name) {
      void useSearches.getState().create({ query: "", composer: biography.name, limit: 100 });
    }
  }, [biography?.name]);

  const indexRows = indexWorks?.items ?? [];
  const normalizeTitle = (value: string) =>
    value
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  const indexByTitle = new Map(indexRows.map((w) => [normalizeTitle(w.title), w.work_id]));
  const asFichaId = (value: string) => (value.startsWith("index-") ? value : `index-${value}`);
  // Las obras que vienen de la búsqueda llevan `work-<uuid>`; la ficha pública usa
  // `index-<n>`. Solo se enlaza cuando hay una obra indexada con el mismo título.
  const fichaIdFor = (workId: string, title: string): string | null => {
    if (workId.startsWith("index-")) return workId;
    const exact = indexByTitle.get(normalizeTitle(title));
    if (exact) return asFichaId(exact);
    const head = title.split(" - ")[0] ?? title;
    const fallback = indexByTitle.get(normalizeTitle(head));
    return fallback ? asFichaId(fallback) : null;
  };
  const pipelineWorks = pipeline?.results ? groupWorks(pipeline.results) : [];
  const showPipeline = pipelineWorks.length > 0;
  const worksLoading =
    loading || searchLoading || searchPolling || (!showPipeline && indexRows.length === 0 && !works);

  if (biography === null) return <Spinner label="Cargando ficha…" />;

  const b = biography;
  const years =
    b.birth_year || b.death_year
      ? `${b.birth_year ?? "?"}–${b.death_year ?? "?"}`
      : null;
  const references = (b.biography_references ?? []).filter(Boolean);

  return (
    <div className="space-y-4">
      <nav className="text-xs text-osap-muted" aria-label="breadcrumb">
        <Link to="/" className="hover:text-osap-accent">Inicio</Link> ›{" "}
        <Link to="/composers" className="hover:text-osap-accent">Compositores</Link> ›{" "}
        <span>{b.name}</span>
      </nav>

      <header className="border-b border-osap-border pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="font-display text-3xl font-semibold text-osap-ink">{b.name}</h1>
          {isAdmin ? (
            <Link
              to={`/admin/composers/${encodeURIComponent(personId)}`}
              className="rounded border border-osap-border px-3 py-1 text-sm text-osap-accent hover:bg-osap-surface"
            >
              Editar
            </Link>
          ) : null}
        </div>
        <div className="mt-2 flex flex-wrap gap-2 text-xs">
          {years ? <span className="rounded bg-osap-accent-soft px-2 py-0.5">{years}</span> : null}
          {b.biography_era ? <span className="rounded bg-osap-accent-soft px-2 py-0.5">{b.biography_era}</span> : null}
          {b.biography_nationality ? (
            <span className="rounded bg-osap-accent-soft px-2 py-0.5">{b.biography_nationality}</span>
          ) : null}
          <span className="rounded bg-osap-accent-soft px-2 py-0.5">{b.works_count ?? works?.total ?? 0} obras</span>
        </div>
      </header>

      <fieldset className="rounded-lg border border-osap-border bg-osap-surface p-5 shadow-sm">
        <legend className="px-2 font-display text-lg font-semibold text-osap-ink">
          Identidad y nombre
        </legend>
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Identificador" value={b.id} />
          <Field label="Nombre completo" value={b.name} />
          <Field label="Nombre de pila" value={b.given_name} />
          <Field label="Apellidos" value={b.family_name} />
          <Field label="Nombre para ordenar" value={b.sort_name} />
          <Field label="Visible" value={b.visible ? "Sí" : "No"} />
        </dl>
      </fieldset>

      <fieldset className="rounded-lg border border-osap-border bg-osap-surface p-5 shadow-sm">
        <legend className="px-2 font-display text-lg font-semibold text-osap-ink">
          Biografía
        </legend>
        <dl className="space-y-4">
          <Field label="Resumen" value={b.biography_summary} />
          <Field label="Época" value={b.biography_era} />
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Nacionalidad" value={b.biography_nationality} />
            <Field label="Año de nacimiento" value={b.birth_year} />
            <Field label="Año de fallecimiento" value={b.death_year} />
          </div>
          <Field label="Dato clave" value={b.biography_key_fact} />
          <Field
            label="Referencias"
            value={
              references.length > 0 ? (
                <ul className="list-inside list-disc">
                  {references.map((ref) => (
                    <li key={ref}>{ref}</li>
                  ))}
                </ul>
              ) : null
            }
          />
        </dl>
      </fieldset>

      <Card title="Obras disponibles">
        {showPipeline ? (
          <WorksListModule works={pipelineWorks} fichaIdFor={fichaIdFor} />
        ) : indexRows.length > 0 ? (
          <WorksListModule
            works={[]}
            fichaIdFor={fichaIdFor}
            fallbackWorks={indexRows.map((w) => ({ work_id: w.work_id, title: w.title, catalogue: w.catalogue ?? null }))}
          />
        ) : worksLoading ? (
          <Spinner label="Buscando obras…" />
        ) : (
          <p className="text-sm text-osap-muted">Todavía no hay obras indexadas para este compositor.</p>
        )}
      </Card>
      <SponsorSlot placement="composer" />
    </div>
  );
}

