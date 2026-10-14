import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { AmigosArticle } from "../api/types";
import { Spinner } from "../components/Spinner";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";
import { useAuth } from "../state/auth";
import { formatEuroDate } from "../utils/dates";

const STATUS_KEY: Record<string, TKey> = {
  draft: "friends.status.draft",
  pending: "friends.status.pending",
  published: "friends.status.published",
  withdrawn: "friends.status.withdrawn",
};

/** URL pública canónica (osap-api la sirve como HTML; el id resuelve el slug por 301). */
function publicUrl(article: AmigosArticle): string {
  return `${window.location.origin}/amigos/articulo/${encodeURIComponent(article.id)}`;
}

export function AmigosMyArticlesPage() {
  const { t } = useI18n();
  const user = useAuth((s) => s.user);
  const [articles, setArticles] = useState<AmigosArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.getAmigosMyArticles();
      setArticles(data.items);
    } catch {
      setArticles([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user !== null) void load();
    else setLoading(false);
  }, [load, user]);

  const copy = async (article: AmigosArticle) => {
    const url = publicUrl(article);
    try {
      if (navigator.share) {
        await navigator.share({ title: article.title, url });
        return;
      }
      await navigator.clipboard.writeText(url);
      setCopied(article.id);
    } catch {
      setCopied(null);
    }
  };

  if (user === null) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">{t("nav.myArticles")}</h1>
        <p className="text-sm text-osap-muted">{t("friends.loginToWrite")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-osap-border pb-4">
        <h1 className="text-2xl font-semibold">{t("nav.myArticles")}</h1>
        <Link
          to="/amigos/editor"
          className="rounded-md bg-osap-accent px-4 py-2 text-sm font-medium text-white hover:bg-osap-accent/90"
        >
          {t("friends.newArticle")}
        </Link>
      </header>

      {loading ? (
        <Spinner label={t("states.loading")} />
      ) : articles.length === 0 ? (
        <p className="text-sm text-osap-muted">{t("friends.articlesEmpty")}</p>
      ) : (
        <ul className="divide-y divide-osap-border overflow-hidden rounded-card border border-osap-border bg-osap-surface shadow-card">
          {articles.map((a) => (
            <li key={a.id} className="px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate font-display text-base text-osap-ink">{a.title}</p>
                  <p className="mt-0.5 text-xs text-osap-muted">
                    {a.group_name ?? a.group_id} · {t("friends.eventDate")}: {formatEuroDate(a.event_date)}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded bg-osap-accent-soft px-2 py-0.5 text-xs text-osap-accent">
                    {t(STATUS_KEY[a.status] ?? "friends.status.draft")}
                  </span>
                  <Link
                    to={`/amigos/editor/${encodeURIComponent(a.id)}`}
                    className="text-xs text-osap-accent hover:underline"
                  >
                    {t("friends.edit")}
                  </Link>
                  <button
                    type="button"
                    onClick={() => void copy(a)}
                    className="text-xs text-osap-accent hover:underline"
                  >
                    {copied === a.id ? t("friends.copied") : t("friends.copyLink")}
                  </button>
                  {a.status === "published" ? (
                    <a
                      href={`/amigos/articulo/${encodeURIComponent(a.id)}`}
                      className="text-xs text-osap-accent hover:underline"
                    >
                      {t("friends.viewPublic")} ↗
                    </a>
                  ) : null}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
