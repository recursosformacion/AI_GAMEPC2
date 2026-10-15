import { useEffect, useState } from "react";
import { apiClient } from "../api/ApiClient";
import type { AmigosGroup } from "../api/types";
import { AmigosNote } from "../components/AmigosNote";
import { Spinner } from "../components/Spinner";
import { useI18n } from "../i18n/I18n";

// «Corales»: índice de agrupaciones. Cada tarjeta enlaza a la página pública estable del
// grupo (`/amigos/corales/{id}`, que redirige a su URL canónica con slug), servida por
// osap-api como HTML real (enlazable y compartible).
export function AmigosGroupsPage() {
  const { t } = useI18n();
  const [groups, setGroups] = useState<AmigosGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiClient
      .getAmigosGroups(false, "coral")
      .then((data) => {
        if (!cancelled) setGroups(data);
      })
      .catch(() => {
        if (!cancelled) setError(t("friends.groupsEmpty"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  return (
    <div className="space-y-6">
      <header className="border-b border-osap-border pb-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-osap-accent">
          {t("nav.sectionFriends")}
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-osap-ink">{t("friends.coralesTitle")}</h1>
        <p className="mt-2 max-w-2xl text-sm text-osap-muted">{t("friends.coralesSubtitle")}</p>
        <AmigosNote titleKey="friends.coralesNoteTitle" bodyKey="friends.coralesNoteBody" />
      </header>

      {loading ? (
        <Spinner label={t("states.loading")} />
      ) : error !== null ? (
        <p className="text-sm text-osap-muted">{error}</p>
      ) : groups.length === 0 ? (
        <p className="text-sm text-osap-muted">{t("friends.groupsEmpty")}</p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {groups.map((g) => (
            <li
              key={g.id}
              className="rounded-card border border-osap-border bg-osap-surface p-4 shadow-card"
            >
              <div className="flex items-start gap-3">
                {g.image_url ? (
                  <img
                    src={g.image_url}
                    alt=""
                    className="h-12 w-12 shrink-0 rounded-md object-cover"
                  />
                ) : null}
                <div className="min-w-0 flex-1">
                  {/* Página pública del coral = servida por osap-api (SSR): navegación completa. */}
                  <a
                    href={`/amigos/corales/${encodeURIComponent(g.id)}`}
                    className="font-display text-lg font-semibold text-osap-ink hover:text-osap-accent"
                  >
                    {g.name}
                  </a>
                  {g.description ? (
                    <p className="mt-1 line-clamp-3 text-sm text-osap-muted">{g.description}</p>
                  ) : null}
                  <div className="mt-2 flex items-center gap-2">
                    <span className="rounded bg-osap-accent-soft px-2 py-0.5 text-xs text-osap-accent">
                      {g.editorial_mode === "direct"
                        ? t("friends.modeDirect")
                        : t("friends.modeModerated")}
                    </span>
                    <a
                      href={`/amigos/corales/${encodeURIComponent(g.id)}`}
                      className="text-xs text-osap-accent hover:underline"
                    >
                      {t("friends.openGroup")} →
                    </a>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
