import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/ApiClient";
import type { RepresentationInfo, SearchResultItem, WorkDetail, WorkInfo } from "../api/types";
import { Spinner } from "./Spinner";
import { WorkDetailTabs } from "./WorkDetailTabs";
import { useI18n } from "../i18n/I18n";

export interface WorksListWork {
  work: SearchResultItem["work"];
  score: number;
  items: SearchResultItem[];
}

function allRepresentations(work: WorksListWork): RepresentationInfo[] {
  return work.items[0]?.representations ?? work.items.map((i) => i.representation);
}

function stars(score: number): string {
  const filled = Math.max(1, Math.min(5, Math.round(score * 5)));
  return "★".repeat(filled) + "☆".repeat(5 - filled);
}

export function groupWorks(results: SearchResultItem[]): WorksListWork[] {
  const byWork = new Map<string, WorksListWork>();
  for (const item of results) {
    const key = item.work.work_id;
    const existing = byWork.get(key);
    if (existing) {
      existing.items.push(item);
      existing.score = Math.max(existing.score, item.score);
    } else {
      byWork.set(key, { work: item.work, score: item.score, items: [item] });
    }
  }
  return [...byWork.values()].sort((a, b) => b.score - a.score);
}

function toWorkInfo(w: WorksListWork, d: WorkDetail): WorkInfo {
  return {
    work_id: String(w.work.work_id ?? d.work.id ?? ""),
    title: d.work.title ?? w.work.title ?? "",
    composer: d.work.composer ?? w.work.composer ?? null,
    catalogue: d.work.catalogue ?? w.work.catalogue ?? null,
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
      available: r.available ?? Boolean(r.url ?? r.file_id != null),
      title: d.work.title ?? undefined,
    }));
}

export function WorksListModule({
  works,
  fallbackWorks,
}: {
  works: WorksListWork[];
  fallbackWorks?: Array<{ work_id: number; title: string | null }>;
}) {
  const { t } = useI18n();
  const [openId, setOpenId] = useState<string | null>(null);
  const [openDetail, setOpenDetail] = useState<WorkDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const toggleWork = useCallback((workId: string) => {
    setOpenId((prev) => (prev === workId ? null : workId));
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

  return (
    <ul className="divide-y divide-osap-border">
      {works.map((w) => {
        const reps = allRepresentations(w);
        const providers = new Set(reps.map((r) => r.provider));
        const isOpen = openId === String(w.work.work_id);
        return (
          <li key={w.work.work_id} className="py-1">
            <button
              type="button"
              onClick={() => toggleWork(String(w.work.work_id))}
              className="flex w-full items-center justify-between rounded px-1 py-2 text-left hover:bg-osap-accent-soft"
            >
              <span>
                <span className="text-osap-accent">{stars(w.score)}</span>{" "}
                <span className="font-medium">
                  {w.work.composer ? `${w.work.composer} — ` : ""}
                  {w.work.title}
                </span>
              </span>
              <span className="flex items-center gap-2">
                <span className="text-xs text-osap-muted">
                  {t("work.repsProviders").replace("{n}", String(reps.length)).replace("{p}", String(providers.size))}
                </span>
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
                  <WorkDetailTabs
                    work={toWorkInfo(w, openDetail)}
                    representations={toRepresentations(openDetail)}
                    score={w.score}
                    evidence={w.items[0]?.evidence}
                  />
                ) : (
                  <WorkDetailTabs
                    work={w.work as WorkInfo}
                    representations={reps}
                    score={w.score}
                    evidence={w.items[0]?.evidence}
                  />
                )}
              </div>
            ) : null}
          </li>
        );
      })}
      {fallbackWorks && fallbackWorks.length > 0 && works.length === 0 ? (
        fallbackWorks.map((w) => (
          <li key={w.work_id} className="py-1">
            <button
              type="button"
              onClick={() => toggleWork(String(w.work_id))}
              className="flex w-full items-center justify-between rounded px-1 py-2 text-left text-sm hover:bg-osap-accent-soft"
            >
              <span className="font-medium">{w.title}</span>
              <span className="text-osap-muted">{openId === String(w.work_id) ? "▲" : "▼"}</span>
            </button>
            {openId === String(w.work_id) ? (
              <div className="mb-2 overflow-hidden rounded bg-osap-surface">
                {loadingDetail ? (
                  <div className="p-4">
                    <Spinner label={t("states.loading")} />
                  </div>
                ) : openDetail ? (
                  <WorkDetailTabs
                    work={toWorkInfo(
                      { work: { work_id: String(w.work_id), title: w.title ?? "" } as WorksListWork["work"], score: 1, items: [] },
                      openDetail,
                    )}
                    representations={toRepresentations(openDetail)}
                    score={1}
                  />
                ) : null}
              </div>
            ) : null}
          </li>
        ))
      ) : null}
    </ul>
  );
}
