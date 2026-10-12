import { useEffect, useState } from "react";
import { apiClient } from "../api/ApiClient";
import type { AmigosArticle } from "../api/types";
import { Spinner } from "../components/Spinner";
import { useI18n } from "../i18n/I18n";

// «Artículos»: blog general de OSAP. Cada entrada enlaza a su página pública (SSR) canónica.
export function AmigosBlogPage() {
  const { t } = useI18n();
  const [articles, setArticles] = useState<AmigosArticle[]>([]);
  const [loading, setLoading] = useState(true);

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
