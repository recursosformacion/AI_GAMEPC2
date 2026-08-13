import { useState } from "react";
import type { RepresentationInfo, SearchResultItem } from "../api/types";
import { Card } from "../components/Card";
import { Spinner } from "../components/Spinner";
import { WorkDetailTabs } from "../components/WorkDetailTabs";
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
  // null = todas las colecciones seleccionadas (por defecto). Un Set = filtro activo.
  const [selected, setSelected] = useState<Set<string> | null>(null);

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

  const works = groupWorks(data.results);
  const composer = works[0]?.work.composer ?? "Composer";
  const total = data.total ?? works.length;
  const page = data.page ?? 1;
  const perPage = data.per_page ?? (data.results.length || works.length);
  const totalPages = Math.max(1, Math.ceil(total / perPage));

  // Solo las colecciones presentes en el lote recibido.
  const collections = [...new Set(works.map((w) => w.work.collection).filter((c): c is string => Boolean(c)))];
  const filtered =
    selected === null
      ? works
      : works.filter((w) => !w.work.collection || selected.has(w.work.collection));
  const rangeStart = total === 0 ? 0 : (page - 1) * perPage + 1;
  const rangeEnd = Math.min(page * perPage, total);

  const goPage = (next: number) => {
    const last = useSearches.getState().lastRequest;
    if (last) void useSearches.getState().create({ ...last, page: next });
  };

  const toggleCollection = (c: string) => {
    setSelected((prev) => {
      if (prev === null) {
        // Primera interacción: arranca con todas marcadas y desmarca esta.
        const next = new Set(collections);
        next.delete(c);
        return next;
      }
      const next = new Set(prev);
      if (next.has(c)) next.delete(c);
      else next.add(c);
      return next;
    });
  };

  const toggleWork = (workId: string) => {
    setOpen(open === workId ? null : workId);
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{composer}</h1>
      <p className="text-sm text-osap-muted">
        {rangeStart}–{rangeEnd} of {total} works
      </p>

      {collections.length > 0 && (
        <Card title={t("work.collections")}>
          <div className="flex flex-wrap gap-3">
            {collections.map((c) => (
              <label key={c} className="flex items-center gap-1.5 text-sm">
                <input
                  type="checkbox"
                  checked={selected === null || selected.has(c)}
                  onChange={() => toggleCollection(c)}
                  className="accent-osap-accent"
                />
                {c}
              </label>
            ))}
          </div>
        </Card>
      )}

      <Card title={t("work.works")}>
        <ul className="divide-y divide-osap-border">
          {filtered.map((w) => {
            const reps = allRepresentations(w);
            const providers = new Set(reps.map((r) => r.provider));
            const isOpen = open === w.work.work_id;
            return (
              <li key={w.work.work_id} className="py-1">
                <button
                  type="button"
                  onClick={() => toggleWork(w.work.work_id)}
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
                    <WorkDetailTabs
                      work={w.work}
                      representations={reps}
                      score={w.score}
                      evidence={w.items[0]?.evidence}
                    />
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      </Card>

      <div className="flex items-center justify-between pt-2">
        <button type="button" disabled={page <= 1} onClick={() => goPage(page - 1)} className="rounded border border-osap-border px-3 py-1 text-sm disabled:opacity-40">
          {t("work.prev")}
        </button>
        <span className="text-sm text-osap-muted">
          {t("work.pageOf").replace("{page}", String(page)).replace("{total}", String(totalPages))}
        </span>
        <button type="button" disabled={page >= totalPages} onClick={() => goPage(page + 1)} className="rounded border border-osap-border px-3 py-1 text-sm disabled:opacity-40">
          {t("work.next")}
        </button>
      </div>
    </div>
  );
}
