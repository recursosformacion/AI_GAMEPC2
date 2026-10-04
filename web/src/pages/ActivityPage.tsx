import { useEffect, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useOidcLogin } from "../components/useOidcLogin";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";
import { useActivityMe } from "../state/activityMe";
import { useAnalyticsMe } from "../state/analyticsMe";
import { useAuth } from "../state/auth";

// Qué encontrará el usuario en su espacio (vista anónima).
const ANON_ITEMS: { icon: string; key: TKey }[] = [
  { icon: "⬇️", key: "activity.anonDownloads" },
  { icon: "➕", key: "activity.anonUploads" },
  { icon: "🤝", key: "activity.anonContributions" },
  { icon: "📚", key: "activity.anonResources" },
  { icon: "📈", key: "activity.anonStats" },
  { icon: "🏅", key: "activity.anonRecognitions" },
];

export function ActivityPage(): ReactNode {
  const { t } = useI18n();
  const isAuthenticated = useAuth((s) => s.isAuthenticated());
  const { data, loading, error, load } = useAnalyticsMe();
  const activity = useActivityMe();
  const { start, error: oidcError } = useOidcLogin();

  useEffect(() => {
    if (isAuthenticated) void load();
  }, [isAuthenticated, load]);

  useEffect(() => {
    if (isAuthenticated) void activity.load();
  }, [isAuthenticated, activity.load]);

  // Vista anónima: explicación + CTA (nunca una pantalla vacía).
  if (!isAuthenticated) {
    return (
      <div className="space-y-8">
        <header className="border-b border-osap-border pb-5">
          <h1 className="text-3xl font-semibold text-osap-ink">{t("activity.title")}</h1>
          <p className="mt-2 max-w-2xl text-sm text-osap-muted">{t("activity.anonymousIntro")}</p>
        </header>

        <section className="rounded-card border border-osap-border bg-osap-surface p-6 shadow-card">
          <h2 className="text-xl text-osap-ink">{t("activity.anonymousWhatTitle")}</h2>
          <ul className="mt-4 grid gap-3 sm:grid-cols-2">
            {ANON_ITEMS.map((item) => (
              <li key={item.key} className="flex items-start gap-3">
                <span aria-hidden="true" className="text-xl">
                  {item.icon}
                </span>
                <span className="text-sm text-osap-ink">{t(item.key)}</span>
              </li>
            ))}
          </ul>
          <div className="mt-6 flex flex-wrap gap-3">
            <button
              onClick={() => void start()}
              className="rounded-full bg-osap-accent px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-osap-accent/90"
            >
              {t("auth.login")}
            </button>
            <button
              onClick={() => void start()}
              className="rounded-full border border-osap-border px-5 py-2 text-sm text-osap-ink hover:border-osap-accent hover:text-osap-accent"
            >
              {t("auth.register")}
            </button>
          </div>
          {oidcError && <p className="mt-2 text-xs text-red-500">{oidcError}</p>}
        </section>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="border-b border-osap-border pb-5">
        <h1 className="text-3xl font-semibold text-osap-ink">{t("activity.title")}</h1>
      </header>

      {loading && <p className="text-sm text-osap-muted">…</p>}
      {error && <p className="text-sm text-osap-danger">{error.message}</p>}

      {data && (
        <div className="grid gap-4 sm:grid-cols-2">
          <section className="rounded-card border border-osap-border bg-osap-surface p-4 shadow-card">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-osap-muted">
              {t("activity.period")}
            </h2>
            <p className="mt-1 text-osap-ink">
              {data.period.from_day} → {data.period.to_day}
            </p>
          </section>

          <section className="rounded-card border border-osap-border bg-osap-surface p-4 shadow-card">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-osap-muted">
              {t("activity.downloads")}
            </h2>
            <p className="mt-1 text-osap-ink">
              {data.downloads.count} · {data.downloads.bytes} {t("activity.bytes")}
            </p>
          </section>

          <section className="rounded-card border border-osap-border bg-osap-surface p-4 shadow-card">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-osap-muted">
              {t("activity.quota")}
            </h2>
            <p className="mt-1 text-osap-ink">
              {data.quota.used} / {data.quota.limit} · {t("activity.remaining")}: {data.quota.remaining}
            </p>
          </section>

          <section className="rounded-card border border-osap-border bg-osap-surface p-4 shadow-card">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-osap-muted">
              {t("activity.stage")}
            </h2>
            <p className="mt-1 text-osap-ink">
              {data.access.stage} · {data.access.tier}
            </p>
          </section>
        </div>
      )}

      {activity.error && <p className="text-sm text-osap-danger">{activity.error.message}</p>}

      {activity.data && (
        <div className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-4">
            <div className="rounded-card border border-osap-border bg-osap-surface p-4 shadow-card">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-osap-muted">Aportaciones</h2>
              <p className="mt-1 text-osap-ink">{activity.data.summary.contributions_total}</p>
            </div>
            <div className="rounded-card border border-osap-border bg-osap-surface p-4 shadow-card">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-osap-muted">Aceptadas</h2>
              <p className="mt-1 text-osap-ink">{activity.data.summary.contributions_accepted}</p>
            </div>
            <div className="rounded-card border border-osap-border bg-osap-surface p-4 shadow-card">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-osap-muted">Pendientes</h2>
              <p className="mt-1 text-osap-ink">{activity.data.summary.contributions_pending}</p>
            </div>
            <div className="rounded-card border border-osap-border bg-osap-surface p-4 shadow-card">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-osap-muted">Obras</h2>
              <p className="mt-1 text-osap-ink">{activity.data.summary.works}</p>
            </div>
          </section>

          <section className="rounded-card border border-osap-border bg-osap-surface p-4 shadow-card">
            <h2 className="text-lg text-osap-ink">Mis aportaciones</h2>
            {activity.data.my_contributions.length === 0 ? (
              <p className="mt-2 text-sm text-osap-muted">Aún no tienes aportaciones.</p>
            ) : (
              <table className="mt-2 w-full text-sm">
                <thead>
                  <tr className="text-left text-osap-muted">
                    <th className="py-1">#</th>
                    <th className="py-1">Operación</th>
                    <th className="py-1">Entidad</th>
                    <th className="py-1">Estado</th>
                    <th className="py-1">Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  {activity.data.my_contributions.map((c) => (
                    <tr key={c.id} className="border-t border-osap-border">
                      <td className="py-1">{c.id}</td>
                      <td className="py-1">{c.operation}</td>
                      <td className="py-1">
                        {c.target_kind} {c.target_id ?? "—"}
                      </td>
                      <td className="py-1">{c.status}</td>
                      <td className="py-1">{c.created_at}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="rounded-card border border-osap-border bg-osap-surface p-4 shadow-card">
            <h2 className="text-lg text-osap-ink">Pendientes</h2>
            {activity.data.pending.length === 0 ? (
              <p className="mt-2 text-sm text-osap-muted">No tienes aportaciones en curso.</p>
            ) : (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-osap-ink">
                {activity.data.pending.map((c) => (
                  <li key={c.id}>
                    #{c.id} · {c.operation} · {c.status}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-card border border-osap-border bg-osap-surface p-4 shadow-card">
            <h2 className="text-lg text-osap-ink">Mis descargas</h2>
            {activity.data.my_downloads.length === 0 ? (
              <p className="mt-2 text-sm text-osap-muted">Sin descargas registradas.</p>
            ) : (
              <table className="mt-2 w-full text-sm">
                <thead>
                  <tr className="text-left text-osap-muted">
                    <th className="py-1">Día</th>
                    <th className="py-1">Obra</th>
                    <th className="py-1">Proveedor</th>
                    <th className="py-1">Formato</th>
                    <th className="py-1">Nº</th>
                  </tr>
                </thead>
                <tbody>
                  {activity.data.my_downloads.map((d, i) => (
                    <tr key={`${d.day}-${d.work_id}-${i}`} className="border-t border-osap-border">
                      <td className="py-1">{d.day}</td>
                      <td className="py-1">{d.work_id}</td>
                      <td className="py-1">{d.provider}</td>
                      <td className="py-1">{d.format}</td>
                      <td className="py-1">{d.quantity}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="rounded-card border border-osap-border bg-osap-surface p-4 shadow-card">
            <h2 className="text-lg text-osap-ink">Impacto</h2>
            <p className="mt-2 text-sm text-osap-ink">
              {activity.data.impact.downloads} descargas generadas por tus aportaciones.
            </p>
            {activity.data.impact.works.length > 0 && (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-osap-ink">
                {activity.data.impact.works.map((w) => (
                  <li key={w.work_id}>
                    Obra {w.work_id}: {w.downloads}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-card border border-osap-border bg-osap-surface p-4 shadow-card">
            <h2 className="text-lg text-osap-ink">Actividad reciente</h2>
            {activity.data.recent.length === 0 ? (
              <p className="mt-2 text-sm text-osap-muted">Sin actividad reciente.</p>
            ) : (
              <ul className="mt-2 space-y-1 text-sm text-osap-ink">
                {activity.data.recent.map((r, i) => (
                  <li key={`${r.at}-${i}`}>
                    {r.at} · {r.kind} · #{r.contribution_id} {r.status}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}

      <p>
        <Link className="text-osap-accent hover:underline" to="/">
          {t("nav.home")}
        </Link>
      </p>
    </div>
  );
}
