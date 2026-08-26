import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Envelope } from "../components/Envelope";
import { Spinner } from "../components/Spinner";
import { WorksListModule, groupWorks } from "../components/WorksListModule";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";
import { useComposers } from "../state/composers";
import { useSearches } from "../state/searches";

const LIMIT = 30;

const REVIEW_OPTIONS: { value: string; key: TKey }[] = [
  { value: "correct", key: "composers.reviewCorrect" },
  { value: "incorrect", key: "composers.reviewIncorrect" },
  { value: "reviewed", key: "composers.reviewReviewed" },
  { value: "not_reviewed", key: "composers.reviewNotReviewed" },
];

export function ComposersPage() {
  const { t } = useI18n();
  const { list, loading, error, q, setQuery, fetchList, review, setReview } = useComposers();
  const [input, setInput] = useState(q);
  const [offset, setOffset] = useState(0);
  const [openWorks, setOpenWorks] = useState<string | null>(null);

  useEffect(() => {
    void fetchList(q, LIMIT, offset, review);
  }, [fetchList, q, offset, review]);

  const search = () => {
    setOffset(0);
    setQuery(input);
  };

  const onReviewChange = (value: string) => {
    setOffset(0);
    setReview(value || null);
  };

  const toggleWorks = (composerName: string, composerId: string) => {
    // Cierra si ya está abierto; si no, abre y lanza la búsqueda de ese compositor.
    if (openWorks === composerId) {
      setOpenWorks(null);
      return;
    }
    setOpenWorks(composerId);
    void fetchList(composerName, LIMIT, 0, review);
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{t("composers.title")}</h1>
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder={t("composers.searchPlaceholder")}
          className="w-full rounded border border-osap-border bg-osap-surface px-3 py-1 text-sm"
        />
        <button onClick={search} className="rounded bg-osap-accent px-4 py-1 text-sm text-white">
          {t("search")}
        </button>
      </div>

      <div className="flex items-center gap-2 text-sm">
        <label htmlFor="review-filter" className="text-xs text-osap-muted">
          {t("composers.reviewFilter")}:
        </label>
        <select
          id="review-filter"
          value={review ?? ""}
          onChange={(e) => onReviewChange(e.target.value)}
          className="rounded border border-osap-border bg-osap-surface px-2 py-1 text-sm"
        >
          <option value="">{t("composers.reviewAll")}</option>
          {REVIEW_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {t(o.key)}
            </option>
          ))}
        </select>
      </div>

      <Envelope loading={loading} error={error} data={list} emptyMessage={t("states.empty")}>
        {(data) => (
          <>
            <ul className="divide-y divide-osap-border rounded border border-osap-border">
              {data.items.map((c) => (
                <li key={c.id} className="px-3 py-2">
                  <div className="flex items-center justify-between">
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="truncate font-medium">{c.name}</span>
                      {c.review_status && <ReviewBadge status={c.review_status} />}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-osap-muted">{c.works_count} {t("composers.works")}</span>
                      <IconButton
                        title={t("composers.viewWorks")}
                        active={openWorks === c.id}
                        onClick={() => toggleWorks(c.name, c.id)}
                        path="M5 3h14v18l-7-4-7 4z"
                      />
                      <Link
                        to={`/composers/${encodeURIComponent(c.id)}`}
                        title={t("composers.viewDetail")}
                        className="rounded p-1 text-osap-muted transition-colors hover:bg-osap-surface hover:text-osap-accent"
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M2.5 12S5.5 5.5 12 5.5 21.5 12 21.5 12 18.5 18.5 12 18.5 2.5 12 2.5 12z" />
                          <circle cx="12" cy="12" r="3" />
                        </svg>
                      </Link>
                    </div>
                  </div>
                  {openWorks === c.id ? (
                    <ComposerWorksInline composerName={c.name} />
                  ) : null}
                </li>
              ))}
            </ul>
            <div className="flex items-center justify-between pt-2 text-sm">
              <button
                disabled={offset === 0}
                onClick={() => setOffset((o) => Math.max(0, o - LIMIT))}
                className="rounded px-3 py-1 disabled:opacity-40"
              >
                {t("pagination.previous")}
              </button>
              <span className="text-xs text-osap-muted">{t("composers.total")}: {data.total}</span>
              <button
                disabled={offset + LIMIT >= data.total}
                onClick={() => setOffset((o) => o + LIMIT)}
                className="rounded px-3 py-1 disabled:opacity-40"
              >
                {t("pagination.next")}
              </button>
            </div>
          </>
        )}
      </Envelope>
    </div>
  );
}

function IconButton({ title, onClick, path, active = false }: { title: string; onClick: () => void; path: string; active?: boolean }) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      className={`rounded p-1 transition-colors ${
        active ? "bg-osap-accent-soft text-osap-accent" : "text-osap-muted hover:bg-osap-surface hover:text-osap-accent"
      }`}
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d={path} />
      </svg>
    </button>
  );
}

function ComposerWorksInline({ composerName }: { composerName: string }) {
  const { t } = useI18n();
  const data = useComposers((s) => s.list);
  const loading = useComposers((s) => s.loading);
  const pipeline = useSearches((s) => s.data);

  useEffect(() => {
    if (data && data.items.length > 0 && data.items[0]?.name === composerName) {
      void useSearches.getState().create({ query: "", composer: composerName, limit: 30 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [composerName, data?.items[0]?.name]);

  const pipelineWorks = pipeline?.results ? groupWorks(pipeline.results) : [];

  if (loading) return <Spinner label={t("states.loading")} />;
  if (pipelineWorks.length === 0) {
    return <p className="py-2 text-sm text-osap-muted">{t("states.empty")}</p>;
  }
  return (
    <div className="mt-2 rounded bg-osap-surface p-2">
      <WorksListModule works={pipelineWorks} />
    </div>
  );
}

const REVIEW_LABEL: Record<string, TKey> = {
  correct: "composers.reviewCorrect",
  incorrect: "composers.reviewIncorrect",
  reviewed: "composers.reviewReviewed",
  not_reviewed: "composers.reviewNotReviewed",
};

const REVIEW_STYLE: Record<string, string> = {
  correct: "bg-green-100 text-green-700",
  incorrect: "bg-red-100 text-red-700",
  reviewed: "bg-blue-100 text-blue-700",
  not_reviewed: "bg-osap-surface text-osap-muted",
};

function ReviewBadge({ status }: { status: string }) {
  const { t } = useI18n();
  const labelKey = REVIEW_LABEL[status] ?? "composers.reviewNotReviewed";
  const style = REVIEW_STYLE[status] ?? REVIEW_STYLE.not_reviewed;
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${style}`}>
      {t(labelKey)}
    </span>
  );
}
