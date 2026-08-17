import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Envelope } from "../components/Envelope";
import { ComposerSearchSelect } from "../components/ComposerSearchSelect";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";
import { useComposers } from "../state/composers";
import { useSystem } from "../state/system";
import type { ComposerSummary } from "../api/types";

const LIMIT = 30;

const REVIEW_OPTIONS: { value: string; key: TKey }[] = [
  { value: "correct", key: "composers.reviewCorrect" },
  { value: "incorrect", key: "composers.reviewIncorrect" },
  { value: "reviewed", key: "composers.reviewReviewed" },
  { value: "not_reviewed", key: "composers.reviewNotReviewed" },
];

const VISIBILITY_OPTIONS: { value: string; key: TKey }[] = [
  { value: "visible", key: "composers.visibilityVisible" },
  { value: "hidden", key: "composers.visibilityHidden" },
  { value: "all", key: "composers.visibilityAll" },
];

export function AdminComposersPage() {
  const { t } = useI18n();
  const { list, loading, error, q, setQuery, fetchList, review, setReview, visible, setVisible, merge, reviewComposer } = useComposers();
  const readOnly = useSystem((s) => s.health?.read_only ?? false);
  const [input, setInput] = useState(q);
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [target, setTarget] = useState<ComposerSummary | null>(null);

  useEffect(() => {
    void fetchList(q, LIMIT, offset, review, visible);
  }, [fetchList, q, offset, review, visible]);

  const search = () => {
    setOffset(0);
    setQuery(input);
  };

  const onReviewChange = (value: string) => {
    setOffset(0);
    setReview(value || null);
  };

  const onVisibilityChange = (value: string) => {
    setOffset(0);
    setVisible(value);
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAllVisible = () => {
    const ids = list?.items.map((c) => c.id) ?? [];
    setSelected((prev) => {
      const allSelected = ids.length > 0 && ids.every((id) => prev.has(id));
      const next = new Set(prev);
      for (const id of ids) {
        if (allSelected) next.delete(id);
        else next.add(id);
      }
      return next;
    });
  };

  const onReviewStatus = (composerId: string, status: string) => {
    void reviewComposer(composerId, status);
  };

  const onMergeSelected = () => {
    if (!target) return;
    const sources = [...selected].filter((id) => id !== target.id);
    if (sources.length === 0) return;
    void merge(target.id, sources);
    setSelected(new Set());
    setTarget(null);
  };

  const selectedCount = selected.size;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{t("admin.composers")}</h1>

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
        <label htmlFor="visibility-filter" className="text-xs text-osap-muted">
          {t("composers.visibilityFilter")}:
        </label>
        <select
          id="visibility-filter"
          value={visible}
          onChange={(e) => onVisibilityChange(e.target.value)}
          className="rounded border border-osap-border bg-osap-surface px-2 py-1 text-sm"
        >
          {VISIBILITY_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {t(o.key)}
            </option>
          ))}
        </select>
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

      {selectedCount > 0 && (
        <div className="rounded border border-osap-accent bg-osap-accent-soft p-3">
          <p className="mb-2 text-sm">
            <strong>{selectedCount}</strong> {t("composers.selected")} · {t("composers.mergeSelectedHint")}
          </p>
          <div className="flex flex-wrap items-end gap-2">
            <div className="flex-1">
              <p className="mb-1 text-xs text-osap-muted">{t("composers.mergeTarget")}</p>
              <ComposerSearchSelect placeholder={t("composers.mergeTargetPlaceholder")} onSelect={setTarget} />
            </div>
            <button
              onClick={onMergeSelected}
              disabled={loading || target === null || readOnly}
              className="rounded bg-osap-accent px-4 py-1.5 text-sm text-white disabled:opacity-50"
            >
              {loading ? t("composers.merging") : `${t("composers.merge")} (${selectedCount - (target ? 1 : 0)})`}
            </button>
          </div>
        </div>
      )}

      <Envelope loading={loading} error={error} data={list} emptyMessage={t("states.empty")}>
        {(data) => (
          <>
            <div className="mb-1 flex items-center gap-2 text-xs text-osap-muted">
              <label className="flex items-center gap-1">
                <input type="checkbox" checked={data.items.length > 0 && data.items.every((c) => selected.has(c.id))} onChange={toggleAllVisible} />
                {t("composers.selectAll")}
              </label>
            </div>
            <ul className="divide-y divide-osap-border rounded border border-osap-border">
              {data.items.map((c) => (
                <li key={c.id} className="flex items-center justify-between gap-2 px-3 py-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <input type="checkbox" checked={selected.has(c.id)} onChange={() => toggleSelect(c.id)} />
                    <Link to={`/admin/composers/${encodeURIComponent(c.id)}`} className="truncate font-medium hover:text-osap-accent">
                      {c.name}
                    </Link>
                    {c.review_status && <ReviewBadge status={c.review_status} />}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="text-xs text-osap-muted">{c.works_count} {t("composers.works")}</span>
                    <select
                      value={c.review_status ?? "not_reviewed"}
                      onChange={(e) => onReviewStatus(c.id, e.target.value)}
                      disabled={readOnly}
                      title={t("composers.reviewFilter")}
                      className="rounded border border-osap-border bg-osap-surface px-1 py-0.5 text-xs disabled:opacity-40"
                    >
                      {REVIEW_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>
                          {t(o.key)}
                        </option>
                      ))}
                    </select>
                  </div>
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
