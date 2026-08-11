import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { Card } from "../components/Card";
import { useI18n } from "../i18n/I18n";
import { useComposers } from "../state/composers";
import { useSearches } from "../state/searches";
import { ComposerPage } from "./ComposerPage";

// Detalle público de un compositor: muestra la MISMA pantalla que buscar con ese
// compositor (pipeline completo). Si el pipeline no encuentra obras pero el
// compositor tiene obras enlazadas en storage, se muestran esas como respaldo.
export function ComposerDetailPage() {
  const { composerId = "" } = useParams<{ composerId: string }>();
  const { t } = useI18n();
  const detail = useComposers((s) => s.detail);
  const works = useComposers((s) => s.works);
  const fetchDetail = useComposers((s) => s.fetchDetail);
  const fetchWorks = useComposers((s) => s.fetchWorks);
  const pipeline = useSearches((s) => s.data);

  useEffect(() => {
    void fetchDetail(composerId);
    void fetchWorks(composerId, 100, 0);
  }, [fetchDetail, fetchWorks, composerId]);

  // Igual que una búsqueda con ese compositor.
  useEffect(() => {
    if (detail?.name) {
      void useSearches.getState().create({ query: "", composer: detail.name, limit: 30 });
    }
  }, [detail?.name]);

  const storedWorks = (works?.items ?? []).filter((w) => w.title);
  const pipelineEmpty = (pipeline?.results.length ?? 0) === 0;

  if (pipelineEmpty && storedWorks.length > 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">{detail?.name ?? t("composers.detail")}</h1>
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
      </div>
    );
  }

  return <ComposerPage />;
}
