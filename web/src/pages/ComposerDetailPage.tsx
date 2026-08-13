import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { RepresentationInfo, WorkDetail, WorkInfo } from "../api/types";
import { Card } from "../components/Card";
import { Spinner } from "../components/Spinner";
import { WorkDetailTabs } from "../components/WorkDetailTabs";
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
  const [openId, setOpenId] = useState<string | null>(null);
  const [openDetail, setOpenDetail] = useState<WorkDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const openWork = useCallback((workId: string) => {
    setOpenId((prev) => {
      if (prev === workId) return null;
      return workId;
    });
  }, []);

  useEffect(() => {
    if (openId === null) return;
    let cancelled = false;
    setLoadingDetail(true);
    setOpenDetail(null);
    apiClient
      .getWork(openId)
      .then((d) => {
        if (!cancelled) setOpenDetail(d);
      })
      .catch(() => {
        if (!cancelled) setOpenDetail(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingDetail(false);
      });
    return () => {
      cancelled = true;
    };
  }, [openId]);

  if (pipelineEmpty && storedWorks.length > 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">{detail?.name ?? t("composers.detail")}</h1>
        <Card title={t("composers.worksTitle")}>
          <ul className="divide-y divide-osap-border">
            {storedWorks.map((w) => {
              const isOpen = openId === String(w.work_id);
              return (
                <li key={w.work_id}>
                  <button
                    type="button"
                    onClick={() => openWork(String(w.work_id))}
                    className="flex w-full items-center justify-between px-1 py-2 text-left text-sm hover:bg-osap-accent-soft"
                  >
                    <span className="font-medium">{w.title}</span>
                    <span className="flex items-center gap-2">
                      <span className="text-xs text-osap-muted">#{w.work_id}</span>
                      <span className="text-osap-muted">{isOpen ? "▲" : "▼"}</span>
                    </span>
                  </button>
                  {isOpen ? (
                    <div className="mb-2 overflow-hidden rounded bg-osap-surface">
                      {loadingDetail ? (
                        <div className="p-4">
                          <Spinner label={t("states.loading")} />
                        </div>
                      ) : openDetail ? (
                        <WorkDetailTabs work={toWorkInfo(w, openDetail)} representations={toRepresentations(openDetail)} score={1} />
                      ) : null}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </Card>
      </div>
    );
  }

  return <ComposerPage />;
}

function toWorkInfo(w: { work_id: number; title: string | null; tags: string | null }, d: WorkDetail): WorkInfo {
  return {
    work_id: String(w.work_id),
    title: d.work.title ?? w.title ?? String(w.work_id),
    composer: d.work.composer ?? null,
    catalogue: d.work.catalogue ?? w.tags ?? null,
  };
}

function toRepresentations(d: WorkDetail): RepresentationInfo[] {
  return (d.resources ?? [])
    .map((r, i): RepresentationInfo => ({
      id: String(r.file_id ?? i),
      provider: "osap-storage",
      format: r.format ?? "unknown",
      confidence: 1,
      url: r.url ?? undefined,
      title: d.work.title ?? undefined,
    }));
}
