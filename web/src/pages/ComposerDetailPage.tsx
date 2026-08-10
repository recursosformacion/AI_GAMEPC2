import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { ComposerStatistics } from "../api/types";
import { Card } from "../components/Card";
import { RatingView } from "../components/RatingView";
import { useI18n } from "../i18n/I18n";
import { useComposers } from "../state/composers";
import { useSearches } from "../state/searches";
import { ComposerPage } from "./ComposerPage";

// Detalle público de un compositor: información que tenemos (si la hay) y las obras del
// compositor. Se prioriza el pipeline (igual que buscar con ese compositor); si el pipeline
// no encuentra nada pero el compositor tiene obras enlazadas en storage, se muestran esas.
export function ComposerDetailPage() {
  const { composerId = "" } = useParams<{ composerId: string }>();
  const { t } = useI18n();
  const detail = useComposers((s) => s.detail);
  const works = useComposers((s) => s.works);
  const fetchDetail = useComposers((s) => s.fetchDetail);
  const fetchWorks = useComposers((s) => s.fetchWorks);
  const pipelineData = useSearches((s) => s.data);
  const [rating, setRating] = useState<ComposerStatistics | null>(null);

  useEffect(() => {
    void fetchDetail(composerId);
    void fetchWorks(composerId, 100, 0);
    setRating(null);
    apiClient
      .getComposerStatistics(composerId)
      .then(setRating)
      .catch(() => setRating(null));
  }, [fetchDetail, fetchWorks, composerId]);

  // Las obras salen del pipeline, igual que una búsqueda con ese compositor.
  useEffect(() => {
    if (detail?.name) {
      void useSearches.getState().create({ query: "", composer: detail.name, limit: 50 });
    }
  }, [detail?.name]);

  const storedWorks = (works?.items ?? []).filter((w) => w.title);
  const pipelineEmpty = (pipelineData?.results.length ?? 0) === 0;

  return (
    <div className="space-y-4">
      <div className="rounded border border-osap-border bg-osap-surface p-4">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold">{detail?.name ?? t("composers.detail")}</h1>
          {rating !== null && <RatingView rating={rating.rating} voteCount={rating.vote_count} />}
        </div>
        {detail && (
          <p className="mt-1 text-sm text-osap-muted">
            {detail.works_count} {t("composers.works")} · {detail.aliases.length} {t("composers.aliases")}
          </p>
        )}
      </div>

      {pipelineEmpty && storedWorks.length > 0 ? (
        <Card title={t("composers.worksTitle")}>
          <ul className="divide-y divide-osap-border">
            {storedWorks.map((w) => (
              <li key={w.work_id} className="flex items-center justify-between px-1 py-2 text-sm">
                <span className="font-medium">{w.title}</span>
                <span className="text-xs text-osap-muted">#{w.work_id}</span>
              </li>
            ))}
          </ul>
        </Card>
      ) : (
        <ComposerPage />
      )}
    </div>
  );
}
