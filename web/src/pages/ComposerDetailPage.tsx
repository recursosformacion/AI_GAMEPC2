import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { ComposerStatistics } from "../api/types";
import { RatingView } from "../components/RatingView";
import { useI18n } from "../i18n/I18n";
import { useComposers } from "../state/composers";
import { useSearches } from "../state/searches";
import { ComposerPage } from "./ComposerPage";

// Detalle de un compositor: muestra la información que tenemos (si la hay) y la
// lista de obras del compositor pasada por el pipeline (igual que si se buscara
// con ese compositor).
export function ComposerDetailPage() {
  const { composerId = "" } = useParams<{ composerId: string }>();
  const { t } = useI18n();
  const detail = useComposers((s) => s.detail);
  const fetchDetail = useComposers((s) => s.fetchDetail);
  const [rating, setRating] = useState<ComposerStatistics | null>(null);

  useEffect(() => {
    void fetchDetail(composerId);
    setRating(null);
    apiClient
      .getComposerStatistics(composerId)
      .then(setRating)
      .catch(() => setRating(null));
  }, [fetchDetail, composerId]);

  // Las obras salen del pipeline, igual que una búsqueda con ese compositor.
  useEffect(() => {
    if (detail?.name) {
      void useSearches.getState().create({ query: "", composer: detail.name, limit: 50 });
    }
  }, [detail?.name]);

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

      <ComposerPage />
    </div>
  );
}
