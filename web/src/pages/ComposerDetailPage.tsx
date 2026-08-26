import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { Card } from "../components/Card";
import { Spinner } from "../components/Spinner";
import { WorksListModule, groupWorks } from "../components/WorksListModule";
import { useI18n } from "../i18n/I18n";
import { useComposers } from "../state/composers";
import { useSearches } from "../state/searches";

// Detalle de un compositor en pantalla propia (estudio): panel con toda la información
// disponible del compositor + todas sus obras con el MISMO módulo de fusión/resultados
// que la búsqueda.
export function ComposerDetailPage() {
  const { composerId = "" } = useParams<{ composerId: string }>();
  const { t } = useI18n();
  const biography = useComposers((s) => s.biography);
  const works = useComposers((s) => s.works);
  const fetchBiography = useComposers((s) => s.fetchBiography);
  const fetchWorks = useComposers((s) => s.fetchWorks);
  const pipeline = useSearches((s) => s.data);
  const loading = useComposers((s) => s.loading);

  useEffect(() => {
    void fetchBiography(composerId);
    void fetchWorks(composerId, 200, 0);
  }, [fetchBiography, fetchWorks, composerId]);

  // Igual que una búsqueda con ese compositor (sistema de fusión compartido).
  useEffect(() => {
    if (biography?.name) {
      void useSearches.getState().create({ query: "", composer: biography.name, limit: 100 });
    }
  }, [biography?.name]);

  const storedWorks = (works?.items ?? []).filter((w) => w.title);
  const pipelineWorks = pipeline?.results ? groupWorks(pipeline.results) : [];
  const showPipeline = pipelineWorks.length > 0;

  if (loading && !biography) {
    return <Spinner label={t("states.loading")} />;
  }

  const b = biography;
  const reviewLabel = b?.review_status ?? "";
  const periods = [
    b?.birth_year ? `${b.birth_year}–${b.death_year ?? "…"}` : null,
    b?.biography_era ?? null,
    b?.biography_nationality ?? null,
  ].filter(Boolean);

  return (
    <div className="space-y-6">
      {/* Cabecera del compositor */}
      <div className="rounded-lg border border-osap-border bg-osap-surface p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold">{b?.name ?? t("composers.detail")}</h1>
            {periods.length > 0 ? (
              <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-osap-muted">
                {periods.map((p) => (
                  <span key={p} className="rounded bg-osap-accent-soft px-2 py-0.5 text-xs">
                    {p}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
          <div className="flex flex-col items-end gap-1 text-xs">
            {reviewLabel ? (
              <span className="rounded bg-osap-surface px-2 py-0.5 text-osap-muted">
                {t("composers.reviewFilter")}: {reviewLabel}
              </span>
            ) : null}
            {b?.visible === false ? (
              <span className="rounded bg-osap-danger/20 px-2 py-0.5 text-osap-danger">hidden</span>
            ) : null}
            <span className="text-osap-muted">
              {b?.works_count ?? works?.total ?? 0} {t("composers.worksTitle")}
            </span>
          </div>
        </div>

        {b?.aliases && b.aliases.length > 0 ? (
          <div className="mt-3 flex flex-wrap items-center gap-1">
            <span className="text-xs font-semibold uppercase text-osap-muted">{t("composers.aliases")}:</span>
            {b.aliases.map((a) => (
              <span key={a} className="rounded bg-osap-accent-soft px-2 py-0.5 text-xs">
                {a}
              </span>
            ))}
          </div>
        ) : null}

        {b?.identifiers && b.identifiers.length > 0 ? (
          <div className="mt-2 flex flex-wrap items-center gap-1">
            <span className="text-xs font-semibold uppercase text-osap-muted">IDs:</span>
            {b.identifiers.map((idf) => (
              <span key={`${idf.type}-${idf.value}`} className="rounded border border-osap-border px-2 py-0.5 text-xs text-osap-muted">
                {idf.type}: {idf.value}
              </span>
            ))}
          </div>
        ) : null}
      </div>

      {/* Biografía (panel principal del estudio) */}
      {b?.biography_summary ? (
        <Card title={t("composers.biography")}>
          <p className="text-sm leading-relaxed">{b.biography_summary}</p>
          {b.biography_key_fact ? (
            <p className="mt-3 rounded border-l-2 border-osap-accent bg-osap-accent-soft/40 px-3 py-2 text-sm italic text-osap-muted">
              "{b.biography_key_fact}"
            </p>
          ) : null}
          {b.biography_key_works && b.biography_key_works.length > 0 ? (
            <div className="mt-3">
              <h3 className="text-xs font-semibold uppercase text-osap-muted">{t("composers.keyWorks")}</h3>
              <div className="mt-1 flex flex-wrap gap-1">
                {b.biography_key_works.map((k) => (
                  <span key={k} className="rounded bg-osap-accent-soft px-2 py-0.5 text-xs">
                    {k}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
          {b.biography_references && b.biography_references.length > 0 ? (
            <div className="mt-3">
              <h3 className="text-xs font-semibold uppercase text-osap-muted">{t("composers.references")}</h3>
              <ul className="mt-1 list-inside list-disc space-y-0.5 text-xs text-osap-muted">
                {b.biography_references.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </Card>
      ) : null}

      {/* Evidencia de identidad */}
      {b?.evidence && b.evidence.length > 0 ? (
        <Card title={t("composers.evidence")}>
          <ul className="space-y-1 text-sm">
            {b.evidence.map((e, i) => (
              <li key={i} className="flex items-center gap-2">
                <span className="text-osap-accent">{e.source ?? "—"}</span>
                <span className="font-mono text-xs text-osap-muted">{e.code ?? ""}</span>
                {e.score != null ? (
                  <span className="text-xs text-osap-muted">· score {e.score}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {/* Obras del compositor */}
      <Card title={t("composers.worksTitle")}>
        {showPipeline ? (
          <WorksListModule works={pipelineWorks} />
        ) : storedWorks.length > 0 ? (
          <WorksListModule
            works={[]}
            fallbackWorks={storedWorks.map((w) => ({ work_id: w.work_id, title: w.title }))}
          />
        ) : (
          <p className="text-sm text-osap-muted">{t("states.empty")}</p>
        )}
      </Card>
    </div>
  );
}
