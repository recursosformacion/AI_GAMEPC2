import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { AmigosArticle } from "../api/types";
import { Spinner } from "../components/Spinner";
import { useAmigosPermissions } from "../components/useAmigosPermissions";
import { useI18n } from "../i18n/I18n";

// «Artículos»: blog general de OSAP. Cada entrada enlaza a su página pública (SSR) canónica.
export function AmigosBlogPage() {
  const { t } = useI18n();
  const [articles, setArticles] = useState<AmigosArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const perms = useAmigosPermissions();

  useEffect(() => {
    let cancelled = false;
    apiClient
      .getAmigosBlog()
      .then((data) => {
        if (!cancelled) setArticles(data.items);
      })
      .catch(() => {
        if (!cancelled) setArticles([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-5">
      <header className="border-b border-osap-border pb-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-osap-accent">
          {t("nav.sectionFriends")}
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-osap-ink">{t("friends.blogTitle")}</h1>
      </header>

      <div className="rounded-card border border-osap-accent/30 bg-osap-accent-soft p-4">
        <p className="font-semibold text-osap-ink">{t("friends.blogNoteTitle")}</p>
        <p className="mt-1 text-sm text-osap-ink/80">{t("friends.blogNoteBody")}</p>
        <Link
          to="/corrections?kind=contact"
          className="mt-2 inline-block text-sm font-medium text-osap-accent hover:underline"
        >
          {t("nav.contact")} →
        </Link>
      </div>

      {perms?.blog ? (
        <div>
          <Link
            to="/mis/blog"
            className="inline-block rounded-md bg-osap-accent px-4 py-2 text-sm font-medium text-white hover:bg-osap-accent/90"
          >
            {t("friends.manageBlog")}
          </Link>
        </div>
      ) : null}

      {loading ? (
        <Spinner label={t("states.loading")} />
      ) : articles.length === 0 ? (
        <p className="text-sm text-osap-muted">{t("friends.blogEmpty")}</p>
      ) : (
        <ul className="space-y-3">
          {articles.map((a) => (
            <li key={a.id} className="rounded-card border border-osap-border bg-osap-surface p-4 shadow-card">
              <a
                href={`/amigos/articulo/${encodeURIComponent(a.id)}`}
                className="font-display text-lg font-semibold text-osap-ink hover:text-osap-accent"
              >
                {a.title}
              </a>
              <p className="mt-1 text-xs text-osap-muted">{a.event_date}</p>
              {a.summary ? <p className="mt-2 text-sm text-osap-muted">{a.summary}</p> : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
