import { useEffect, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useI18n } from "../i18n/I18n";
import { useAnalyticsMe } from "../state/analyticsMe";
import { useAuth } from "../state/auth";

export function ActivityPage(): ReactNode {
  const { t } = useI18n();
  const isAuthenticated = useAuth((s) => s.isAuthenticated());
  const { data, loading, error, load } = useAnalyticsMe();

  useEffect(() => {
    if (isAuthenticated) void load();
  }, [isAuthenticated, load]);

  if (!isAuthenticated) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-2xl font-semibold">{t("activity.title")}</h1>
        <p className="mt-4 text-slate-600">{t("activity.loginRequired")}</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-2xl font-semibold">{t("activity.title")}</h1>

      {loading && <p className="mt-4 text-slate-500">…</p>}
      {error && <p className="mt-4 text-red-600">{error.message}</p>}

      {data && (
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <section className="rounded-lg border border-slate-200 p-4">
            <h2 className="text-sm font-medium text-slate-500">{t("activity.period")}</h2>
            <p className="mt-1">
              {data.period.from_day} → {data.period.to_day}
            </p>
          </section>

          <section className="rounded-lg border border-slate-200 p-4">
            <h2 className="text-sm font-medium text-slate-500">{t("activity.downloads")}</h2>
            <p className="mt-1">
              {data.downloads.count} · {data.downloads.bytes} {t("activity.bytes")}
            </p>
          </section>

          <section className="rounded-lg border border-slate-200 p-4">
            <h2 className="text-sm font-medium text-slate-500">{t("activity.quota")}</h2>
            <p className="mt-1">
              {data.quota.used} / {data.quota.limit} · {t("activity.remaining")}:{" "}
              {data.quota.remaining}
            </p>
          </section>

          <section className="rounded-lg border border-slate-200 p-4">
            <h2 className="text-sm font-medium text-slate-500">{t("activity.stage")}</h2>
            <p className="mt-1">
              {data.access.stage} · {data.access.tier}
            </p>
          </section>
        </div>
      )}

      <p className="mt-6">
        <Link className="text-osap-accent hover:underline" to="/">
          {t("nav.home")}
        </Link>
      </p>
    </main>
  );
}
