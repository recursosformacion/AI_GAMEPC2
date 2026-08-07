import { useState } from "react";
import type { RepresentationInfo, SearchResultItem } from "../api/types";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { useI18n } from "../i18n/I18n";
import { useSearches } from "../state/searches";

interface Work {
  work: SearchResultItem["work"];
  score: number;
  items: SearchResultItem[];
}

function allRepresentations(work: Work): RepresentationInfo[] {
  return work.items[0]?.representations ?? work.items.map((i) => i.representation);
}

function stars(score: number): string {
  const filled = Math.max(1, Math.min(5, Math.round(score * 5)));
  return "★".repeat(filled) + "☆".repeat(5 - filled);
}

function groupWorks(results: SearchResultItem[]): Work[] {
  const byWork = new Map<string, Work>();
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

export function ComposerPage() {
  const { t } = useI18n();
  const data = useSearches((s) => s.data);
  const loading = useSearches((s) => s.loading);
  const error = useSearches((s) => s.error);
  const [open, setOpen] = useState<string | null>(null);

  if (loading) {
    return <EmptyState message={t("states.loading")} />;
  }
  if (error !== null || data === null || data.results.length === 0) {
    return (
      <div className="space-y-1 py-16 text-center">
        <p className="text-osap-ink">{t("empty.noWorksFound")}</p>
        <p className="text-sm text-osap-muted">{t("empty.tryAnother")}</p>
      </div>
    );
  }

  const works = groupWorks(data.results);
  const composer = works[0]?.work.composer ?? "Composer";
  const total = data.total ?? works.length;
  const page = data.page ?? 1;
  const perPage = data.per_page ?? (data.results.length || works.length);
  const totalPages = Math.max(1, Math.ceil(total / perPage));

  const goPage = (next: number) => {
    const last = useSearches.getState().lastRequest;
    if (last) void useSearches.getState().create({ ...last, page: next });
  };

  const openWork = (workId: string) => {
    // Open the Work Resolution in a NEW tab (keeps the works list clickable).
    const searchId = useSearches.getState().data?.search_id ?? "";
    window.open(`/resolution?search_id=${searchId}&work=${workId}`, "_blank", "noopener,noreferrer");
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{composer}</h1>
      <p className="text-sm text-osap-muted">{works.length} works found</p>

      <Card title="Collections">
        <div className="flex flex-wrap gap-2">
          {["Symphonies", "Sacred Music", "Operas", "Chamber", "All works"].map((c) => (
            <span key={c} className="rounded bg-osap-accent-soft px-2 py-0.5 text-xs text-osap-accent">
              {c}
            </span>
          ))}
        </div>
      </Card>

      <Card title="Works">
        <ul className="divide-y divide-osap-border">
          {works.map((w) => {
            const reps = allRepresentations(w);
            return (
              <li key={w.work.work_id} className="py-1">
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => openWork(w.work.work_id)}
                    className="flex flex-1 items-center justify-between rounded px-1 py-2 text-left hover:bg-osap-accent-soft"
                  >
                    <span>
                      <span className="text-osap-accent">{stars(w.score)}</span>{" "}
                      <span className="font-medium">
                        {w.work.composer ? `${w.work.composer} — ` : ""}
                        {w.work.title}
                      </span>
                    </span>
                    <span className="text-xs text-osap-muted">
                      {reps.length} reps · {new Set(reps.map((r) => r.provider)).size} providers
                    </span>
                  </button>
                  <button
                    type="button"
                    aria-label="expand"
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpen(open === w.work.work_id ? null : w.work.work_id);
                    }}
                    className="px-2 text-osap-muted"
                  >
                    {open === w.work.work_id ? "▼" : "▶"}
                  </button>
                </div>
                {open === w.work.work_id ? (
                  <div className="mb-2 rounded bg-osap-surface p-3">
                    <ul className="space-y-1">
                      {reps.map((rep, i) => {
                        const href = `/api/v1/representations/${rep.id}/download`;
                        return (
                          <li key={`${w.work.work_id}-${rep.provider}-${rep.format}-${i}`} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                            <span>
                              <span className="text-osap-muted">{rep.provider}</span> · {rep.title || rep.format} ·{" "}
                              {rep.confidence.toFixed(2)}
                            </span>
                            <a href={href} target="_blank" rel="noopener noreferrer" className="text-osap-accent">
                              View
                            </a>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      </Card>

      <div className="flex items-center justify-between pt-2">
        <button type="button" disabled={page <= 1} onClick={() => goPage(page - 1)} className="rounded border border-osap-border px-3 py-1 text-sm disabled:opacity-40">
          ← Prev
        </button>
        <span className="text-sm text-osap-muted">
          Page {page} of {totalPages}
        </span>
        <button type="button" disabled={page >= totalPages} onClick={() => goPage(page + 1)} className="rounded border border-osap-border px-3 py-1 text-sm disabled:opacity-40">
          Next →
        </button>
      </div>
    </div>
  );
}
