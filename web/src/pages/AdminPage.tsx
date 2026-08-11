import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { AdminOverview, VotesOverview } from "../api/types";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";
import { useAuth } from "../state/auth";

function rankLabel(id: string): string {
  return id.length > 24 ? `${id.slice(0, 12)}…` : id;
}

const REVIEW_KEYS: { key: string; labelKey: TKey }[] = [
  { key: "correct", labelKey: "composers.reviewCorrect" },
  { key: "incorrect", labelKey: "composers.reviewIncorrect" },
  { key: "reviewed", labelKey: "composers.reviewReviewed" },
  { key: "not_reviewed", labelKey: "composers.reviewNotReviewed" },
];

export function AdminPage() {
  const { t } = useI18n();
  const isAdmin = useAuth((s) => s.isAdmin());
  const [overview, setOverview] = useState<VotesOverview | null>(null);
  const [adminOverview, setAdminOverview] = useState<AdminOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAdmin) {
      setOverview(null);
      setAdminOverview(null);
      return;
    }
    apiClient
      .getVotesOverview()
      .then(setOverview)
      .catch((e) => setError(e instanceof ApiError ? e.message : t("admin.error")));
    apiClient
      .getAdminOverview()
      .then(setAdminOverview)
      .catch(() => setAdminOverview(null));
  }, [isAdmin, t]);

  if (!isAdmin) {
    return <p className="text-sm text-osap-muted">{t("admin.accessDenied")}</p>;
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{t("admin.title")}</h1>

      {adminOverview !== null && (
        <div className="rounded border border-osap-border bg-osap-surface p-4">
          <h2 className="mb-2 text-sm font-semibold">{t("admin.composersReview")}</h2>
          <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-5">
            <div>
              <p className="text-osap-muted">{t("admin.total")}</p>
              <p className="text-xl font-bold">{adminOverview.composers.total ?? 0}</p>
            </div>
            {REVIEW_KEYS.map((r) => (
              <div key={r.key}>
                <p className="text-osap-muted">{t(r.labelKey)}</p>
                <p className="text-xl font-bold">{adminOverview.composers[r.key] ?? 0}</p>
              </div>
            ))}
          </div>
          <Link
            to="/admin/source-suggestions"
            className="mt-3 inline-block rounded bg-osap-accent px-3 py-1 text-sm text-white"
          >
            {t("admin.sourceSuggestions")} · {adminOverview.source_suggestions_pending}
          </Link>
        </div>
      )}

      {overview === null ? (
        <p className="text-sm text-osap-muted">{error ?? t("admin.loading")}</p>
      ) : (
        <>
          <div className="rounded border border-osap-border bg-osap-surface p-4">
            <p className="text-sm text-osap-muted">{t("admin.totalVotes")}</p>
            <p className="text-2xl font-bold">{overview.total_votes}</p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <section className="rounded border border-osap-border bg-osap-surface p-4">
              <h2 className="mb-2 text-sm font-semibold">{t("admin.topWorks")}</h2>
              <ul className="space-y-1 text-sm">
                {overview.top_works.map((w) => (
                  <li key={w.work_id} className="flex justify-between">
                    <span className="truncate">{rankLabel(w.work_id)}</span>
                    <span className="text-osap-muted">
                      {w.rating !== null ? `★ ${w.rating.toFixed(2)}` : "—"} · {w.vote_count}
                    </span>
                  </li>
                ))}
              </ul>
            </section>

            <section className="rounded border border-osap-border bg-osap-surface p-4">
              <h2 className="mb-2 text-sm font-semibold">{t("admin.topComposers")}</h2>
              <ul className="space-y-1 text-sm">
                {overview.top_composers.map((c) => (
                  <li key={c.composer_id} className="flex justify-between">
                    <span className="truncate">{rankLabel(c.composer_id)}</span>
                    <span className="text-osap-muted">
                      {c.rating !== null ? `★ ${c.rating.toFixed(2)}` : "—"} · {c.vote_count}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          </div>

          {overview.last_execution !== null && (
            <section className="rounded border border-osap-border bg-osap-surface p-4 text-sm">
              <h2 className="mb-1 font-semibold">{t("admin.lastExecution")}</h2>
              <p className="text-osap-muted">
                {overview.last_execution.kind} · {overview.last_execution.status}
              </p>
            </section>
          )}

          <Link to="/composers" className="inline-block rounded bg-osap-accent px-4 py-1.5 text-sm text-white">
            {t("admin.composers")}
          </Link>
        </>
      )}
    </div>
  );
}
