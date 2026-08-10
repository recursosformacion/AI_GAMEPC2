import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { VotesOverview } from "../api/types";
import { useI18n } from "../i18n/I18n";
import { useAuth } from "../state/auth";

function rankLabel(id: string): string {
  return id.length > 24 ? `${id.slice(0, 12)}…` : id;
}

export function AdminPage() {
  const { t } = useI18n();
  const isAdmin = useAuth((s) => s.isAdmin());
  const [overview, setOverview] = useState<VotesOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAdmin) {
      setOverview(null);
      return;
    }
    apiClient
      .getVotesOverview()
      .then(setOverview)
      .catch((e) => setError(e instanceof ApiError ? e.message : t("admin.error")));
  }, [isAdmin, t]);

  if (!isAdmin) {
    return <p className="text-sm text-osap-muted">{t("admin.accessDenied")}</p>;
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{t("admin.title")}</h1>

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
