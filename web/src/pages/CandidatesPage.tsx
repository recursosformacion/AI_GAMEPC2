import { useState } from "react";
import type { RepresentationInfo, SearchResultItem } from "../api/types";
import { Spinner } from "../components/Spinner";
import { WorkDetailTabs } from "../components/WorkDetailTabs";
import { useI18n } from "../i18n/I18n";
import { useSearches } from "../state/searches";

interface Candidate {
  work: SearchResultItem["work"];
  score: number;
  items: SearchResultItem[];
}

function allRepresentations(candidate: Candidate): RepresentationInfo[] {
  return candidate.items[0]?.representations ?? candidate.items.map((i) => i.representation);
}

function stars(score: number): string {
  const filled = Math.max(1, Math.min(5, Math.round(score * 5)));
  return "★".repeat(filled) + "☆".repeat(5 - filled);
}

function groupCandidates(results: SearchResultItem[]): Candidate[] {
  const byWork = new Map<string, Candidate>();
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

export function CandidatesPage() {
  const { t } = useI18n();
  const data = useSearches((s) => s.data);
  const loading = useSearches((s) => s.loading);
  const error = useSearches((s) => s.error);
  const [open, setOpen] = useState<string | null>(null);

  if (loading) {
    return <Spinner label={t("states.loading")} />;
  }
  if (error !== null || data === null || data.results.length === 0) {
    return (
      <div className="space-y-1 py-16 text-center">
        <p className="text-osap-ink">{t("empty.noWorksFound")}</p>
        <p className="text-sm text-osap-muted">{t("empty.tryAnother")}</p>
      </div>
    );
  }

  const candidates = groupCandidates(data.results);
  const total = data.total ?? candidates.length;
  const page = data.page ?? 1;
  const perPage = data.per_page ?? (data.results.length || candidates.length);
  const totalPages = Math.max(1, Math.ceil(total / perPage));
  const rangeStart = total === 0 ? 0 : (page - 1) * perPage + 1;
  const rangeEnd = Math.min(page * perPage, total);

  const goPage = (next: number) => {
    const last = useSearches.getState().lastRequest;
    if (last) void useSearches.getState().create({ ...last, page: next });
  };

  // Toggle the inline expandable panel in the same window. Opening one work
  // closes any other that was open, and pushes the rest of the list down.
  const toggleWork = (workId: string) => {
    setOpen(open === workId ? null : workId);
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Matching Works</h1>
      <p className="text-sm text-osap-muted">
        {rangeStart}–{rangeEnd} of {total} works
      </p>
      <ul className="space-y-2">
        {candidates.map((c) => {
          const reps = allRepresentations(c);
          const providers = new Set(reps.map((r) => r.provider));
          const isOpen = open === c.work.work_id;
          return (
            <li key={c.work.work_id}>
              <div className="flex items-center rounded-lg border border-osap-border bg-osap-surface">
                <button
                  type="button"
                  onClick={() => toggleWork(c.work.work_id)}
                  className="flex flex-1 items-center justify-between p-3 text-left hover:bg-osap-accent-soft"
                >
                  <span>
                    <span className="text-osap-accent">{stars(c.score)}</span>{" "}
                    <span className="font-medium">
                      {c.work.composer ? `${c.work.composer} — ` : ""}
                      {c.work.title}
                    </span>
                  </span>
                  <span className="text-xs text-osap-muted">
                    {reps.length} representations · {providers.size} providers
                  </span>
                </button>
                <button
                  type="button"
                  aria-label="expand"
                  onClick={() => toggleWork(c.work.work_id)}
                  className="px-3 text-osap-muted"
                >
                  {isOpen ? "▲" : "▼"}
                </button>
              </div>
              {isOpen ? (
                <div className="overflow-hidden rounded-b-lg border border-t-0 border-osap-border bg-osap-surface">
                  <WorkDetailTabs
                    work={c.work}
                    representations={reps}
                    score={c.score}
                    evidence={c.items[0]?.evidence}
                    relationships={c.items[0]?.relationships}
                  />
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>

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
