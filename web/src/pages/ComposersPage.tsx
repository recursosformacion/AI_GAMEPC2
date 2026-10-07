import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Envelope } from "../components/Envelope";
import { WorksListModule, groupWorks } from "../components/WorksListModule";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";
import { useAuth } from "../state/auth";
import { useComposers } from "../state/composers";
import { useSearches } from "../state/searches";

const LIMIT = 30;

const REVIEW_OPTIONS: { value: string; key: TKey }[] = [
  { value: "correct", key: "composers.reviewCorrect" },
  { value: "incorrect", key: "composers.reviewIncorrect" },
  { value: "reviewed", key: "composers.reviewReviewed" },
  { value: "not_reviewed", key: "composers.reviewNotReviewed" },
];

// Monograma: iniciales del nombre (primera y última palabra).
function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : "";
  return (first + last).toUpperCase();
}

// "1685–1750" a partir de los años disponibles (puede faltar alguno).
function lifespan(birth?: string | null, death?: string | null): string {
  const b = (birth ?? "").trim();
  const d = (death ?? "").trim();
  if (b && d) return `${b}–${d}`;
  if (b) return `${b}–`;
  if (d) return `–${d}`;
  return "";
}

export function ComposersPage() {
  const { t } = useI18n();
  const { list, loading, error, q, setQuery, fetchList, review, setReview } = useComposers();
  const isAdmin = useAuth((s) => s.isAdmin());
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

  const toggleWorks = (personId: string) => {
    // Cierra si ya está abierto; si no, abre (la búsqueda la lanza ComposerWorksInline).
    setOpenWorks((current) => (current === personId ? null : personId));
  };

  return (
    <div className="space-y-6">
      <header className="border-b border-osap-border pb-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-osap-accent">
          {t("composers.indexLabel")}
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-osap-ink">{t("composers.title")}</h1>
        <p className="mt-2 max-w-2xl text-sm text-osap-muted">{t("composers.subtitle")}</p>
      </header>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="flex flex-1 gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
            placeholder={t("composers.searchPlaceholder")}
            className="w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
          />
          <button onClick={search} className="rounded-md bg-osap-accent px-4 py-2 text-sm text-white">
            {t("search")}
          </button>
        </div>
        {isAdmin && (
          <div className="flex items-center gap-2 text-sm">
            <label htmlFor="review-filter" className="text-xs text-osap-muted">
              {t("composers.reviewFilter")}:
            </label>
            <select
              id="review-filter"
              value={review ?? ""}
              onChange={(e) => onReviewChange(e.target.value)}
              className="rounded-md border border-osap-border bg-osap-surface px-2 py-2 text-sm"
            >
              <option value="">{t("composers.reviewAll")}</option>
              {REVIEW_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {t(o.key)}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <Envelope loading={loading} error={error} data={list} emptyMessage={t("states.empty")}>
        {(data) => (
          <>
            <ul className="divide-y divide-osap-border overflow-hidden rounded-card border border-osap-border bg-osap-surface shadow-card">
              {data.items.map((c) => {
                const meta = [c.biography_nationality, lifespan(c.birth_year, c.death_year)]
                  .filter(Boolean)
                  .join(" · ");
                return (
                <li key={c.id} className="px-4 py-3">
                  <div className="flex items-center gap-4">
                    <span
                      aria-hidden="true"
                      className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-osap-accent-soft font-display text-sm font-semibold text-osap-accent"
                    >
                      {initials(c.name)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <Link
                          to={`/composers/${encodeURIComponent(c.id)}`}
                          className="truncate font-display text-base text-osap-ink transition-colors hover:text-osap-accent"
                        >
                          {c.name}
                        </Link>
                      </div>
                      {meta ? <p className="mt-0.5 text-xs text-osap-muted">{meta}</p> : null}
                    </div>
                    <span className="shrink-0 text-xs text-osap-muted">
                      {c.works_count} {t("composers.works")}
                    </span>
                    <IconButton
                      title={t("composers.viewWorks")}
                      active={openWorks === c.id}
                      onClick={() => toggleWorks(c.id)}
                      path="M5 3h14v18l-7-4-7 4z"
                    />
                    <Link
                      to={`/composers/${encodeURIComponent(c.id)}`}
                      title={t("composers.viewDetail")}
                      className="rounded p-1 text-osap-muted transition-colors hover:text-osap-accent"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                        <path d="m9 6 6 6-6 6" />
                      </svg>
                    </Link>
                  </div>
                  {openWorks === c.id ? <ComposerWorksInline composerName={c.name} /> : null}
                </li>
                );
              })}
            </ul>
            <div className="flex items-center justify-between pt-3 text-sm">
              <button
                disabled={offset === 0}
                onClick={() => setOffset((o) => Math.max(0, o - LIMIT))}
                className="rounded-md px-3 py-1 disabled:opacity-40"
              >
                {t("pagination.previous")}
              </button>
              <span className="text-xs text-osap-muted">{t("composers.total")}: {data.total}</span>
              <button
                disabled={offset + LIMIT >= data.total}
                onClick={() => setOffset((o) => o + LIMIT)}
                className="rounded-md px-3 py-1 disabled:opacity-40"
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
        active ? "bg-osap-accent-soft text-osap-accent" : "text-osap-muted hover:bg-osap-accent-soft hover:text-osap-accent"
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
  const data = useSearches((s) => s.data);
  const loading = useSearches((s) => s.loading);
  const polling = useSearches((s) => s.polling);
  const lastRequest = useSearches((s) => s.lastRequest);

  // Lanza la búsqueda por el MÉTODO NORMAL (POST /searches + polling): igual que el
  // Estudio, pero restringida al ÍNDICE local (rápido, determinista y sin depender de
  // proveedores en vivo): incluye OMR/IMSLP/Mutopia/MusicBrainz ya indexados.
  useEffect(() => {
    void useSearches
      .getState()
      .create({ query: "", composer: composerName, limit: 100, providers: ["index"] });
  }, [composerName]);

  // Solo se pintan resultados del pipeline si la última búsqueda es de ESTE compositor:
  // evita mostrar en vacío/adelantado o resultados de una búsqueda anterior.
  const isCurrent =
    (lastRequest?.composer ?? "").trim().toLowerCase() === composerName.trim().toLowerCase();
  const pipelineWorks = isCurrent && data?.results ? groupWorks(data.results) : [];
  const pending =
    !isCurrent || loading || polling || data?.status === "running" || data?.status === undefined;

  if (pending && pipelineWorks.length === 0) {
    return (
      <div className="mt-2 rounded-md border border-osap-border bg-osap-bg p-3">
        <div className="flex items-center justify-between gap-2 text-sm">
          <span className="flex items-center gap-2 text-osap-muted">
            <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-osap-accent border-t-transparent" />
            {t("search.searching")}
          </span>
          <span className="text-xs text-osap-muted">{data?.progress ?? 0}%</span>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded bg-osap-border">
          <div className="h-full bg-osap-accent transition-all" style={{ width: `${data?.progress ?? 5}%` }} />
        </div>
        {data?.providers && data.providers.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {data.providers.map((p) => (
              <span
                key={p}
                className="inline-flex items-center gap-1 rounded-full border border-osap-border bg-osap-surface px-2 py-0.5 text-xs text-osap-ink"
              >
                <span className="text-green-600">✓</span>
                {p}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    );
  }
  if (pipelineWorks.length === 0) {
    return <p className="py-2 text-sm text-osap-muted">{t("states.empty")}</p>;
  }
  return (
    <div className="mt-2 rounded-md bg-osap-bg p-2">
      <WorksListModule works={pipelineWorks} />
    </div>
  );
}


