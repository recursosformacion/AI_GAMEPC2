import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { ComposerStatistics, ComposerSummary, WorkDetail } from "../api/types";
import { ComposerMergeForm } from "../components/ComposerMergeForm";
import { Envelope } from "../components/Envelope";
import { RatingView } from "../components/RatingView";
import { useI18n } from "../i18n/I18n";
import { useComposers } from "../state/composers";

export function ComposerDetailPage() {
  const { composerId = "" } = useParams<{ composerId: string }>();
  const { t } = useI18n();
  const { detail, works, loading, error, fetchDetail, fetchWorks } = useComposers();
  const [rating, setRating] = useState<ComposerStatistics | null>(null);
  const [originWork, setOriginWork] = useState<WorkDetail | null>(null);

  useEffect(() => {
    void fetchDetail(composerId);
    void fetchWorks(composerId, 100, 0);
    apiClient
      .getComposerStatistics(composerId)
      .then((s) => setRating(s))
      .catch(() => setRating(null));
  }, [fetchDetail, fetchWorks, composerId]);

  // Carga la obra que originó el compositor (inspección profunda).
  useEffect(() => {
    setOriginWork(null);
    if (!detail || detail.creation_evidence.length === 0) return;
    const first = detail.creation_evidence[0];
    if (!first || first.work_id == null) return;
    apiClient
      .getWork(String(first.work_id))
      .then(setOriginWork)
      .catch(() => setOriginWork(null));
  }, [detail]);

  const originSummary: ComposerSummary | null =
    detail === null
      ? null
      : { id: detail.id, name: detail.name, status: detail.status, aliases_count: detail.aliases.length, works_count: detail.works_count };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{t("composers.detail")}</h1>

      <Envelope loading={loading} error={error} data={detail} emptyMessage={t("states.empty")}>
        {(c) => (
          <div className="rounded border border-osap-border bg-osap-surface p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">{c.name}</h2>
              <span className="rounded-full border border-osap-border px-2 py-0.5 text-xs text-osap-muted">{c.status}</span>
            </div>
            <p className="mt-1 text-sm text-osap-muted">
              {c.works_count} {t("composers.works")} · {c.aliases.length} {t("composers.aliases")}
            </p>
            {rating !== null && (
              <p className="mt-2">
                <RatingView rating={rating.rating} voteCount={rating.vote_count} />
              </p>
            )}
            {c.aliases.length > 0 && (
              <p className="mt-2 text-sm text-osap-muted">
                {t("composers.aliases")}: {c.aliases.join(", ")}
              </p>
            )}
          </div>
        )}
      </Envelope>

      {/* ¿Por qué existe este compositor? */}
      <section className="rounded border border-osap-border bg-osap-surface p-4">
        <h2 className="mb-2 text-base font-semibold">{t("composers.whyExists")}</h2>
        {detail && detail.creation_evidence.length === 0 ? (
          <p className="text-sm text-osap-muted">{t("composers.whyExistsNone")}</p>
        ) : null}
        {detail?.creation_evidence.map((e, i) => (
          <div key={i} className="mb-3 text-sm">
            <p>
              <strong>{t("composers.evidenceExtracted")}:</strong> {e.work_title ?? "—"}
            </p>
            <p>
              <strong>{t("composers.evidenceAuthor")}:</strong> {e.extracted_author ?? "—"}
            </p>
            <p>
              <strong>{t("composers.evidenceProvider")}:</strong> {e.provider ?? "—"}
            </p>
            {e.work_id != null && (
              <p>
                <strong>{t("composers.workId")}:</strong> #{e.work_id}
              </p>
            )}
          </div>
        ))}
        {originWork !== null && (
          <div className="border-t border-osap-border pt-2 text-sm">
            <p>
              <strong>{t("composers.workTitle")}:</strong> {originWork.work.title ?? "—"}
            </p>
            {originWork.work.composer && (
              <p>
                <strong>{t("composers.workComposer")}:</strong> {originWork.work.composer}
              </p>
            )}
            {originWork.resources.length > 0 && (
              <ul className="mt-2 space-y-1">
                {originWork.resources.map((r, j) => (
                  <li key={j} className="flex items-center justify-between text-xs text-osap-muted">
                    <span>{r.format ?? "—"}</span>
                    {r.url ? (
                      <a href={r.url} target="_blank" rel="noreferrer" className="text-osap-accent hover:underline">
                        {t("composers.workOpen")}
                      </a>
                    ) : (
                      <span>{t("composers.workNoFile")}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      {/* Obras relacionadas */}
      <section>
        <h2 className="mb-2 text-base font-semibold">{t("composers.worksTitle")}</h2>
        <ul className="divide-y divide-osap-border rounded border border-osap-border">
          {(works?.items ?? []).map((w) => (
            <li key={w.work_id} className="flex flex-col gap-0.5 px-3 py-2 text-sm">
              <span className="font-medium">{w.title ?? w.work_id}</span>
              <span className="text-xs text-osap-muted">
                {t("composers.origin")}: {w.tags ?? "—"} · #{w.work_id}
              </span>
            </li>
          ))}
        </ul>
      </section>

      {originSummary !== null && <ComposerMergeForm origin={originSummary} />}
    </div>
  );
}
