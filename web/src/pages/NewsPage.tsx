import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { apiClient } from "../api/ApiClient";
import { authClient } from "../api/AuthClient";
import type { NewsFeed, NewsTopic } from "../api/types";
import { useOidcLogin } from "../components/useOidcLogin";
import { useI18n } from "../i18n/I18n";
import { useAuth } from "../state/auth";
import { formatEuroDate } from "../utils/dates";

const NEWS_LANGUAGES = [
  ["es", "Español"],
  ["ca", "Català"],
  ["fr", "Français"],
  ["en", "English"],
  ["de", "Deutsch"],
  ["it", "Italiano"],
  ["pt", "Português"],
] as const;

export function NewsPage(): ReactNode {
  const { t } = useI18n();
  const { accessToken, isAuthenticated } = useAuth();
  const { start, error: oidcError } = useOidcLogin();
  const [topicsCatalog, setTopicsCatalog] = useState<NewsTopic[]>([]);
  const [feed, setFeed] = useState<NewsFeed | null>(null);
  const [newsOptIn, setNewsOptIn] = useState(false);
  const [newsLanguage, setNewsLanguage] = useState("es");
  const [newsLanguages, setNewsLanguages] = useState<string[]>(["es"]);
  const [newsTopics, setNewsTopics] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [showPreferences, setShowPreferences] = useState(
    () => localStorage.getItem("osap.news.preferencesCollapsed") !== "1",
  );

  const load = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const [me, topics, nextFeed] = await Promise.all([
        authClient.me(accessToken),
        apiClient.getNewsTopics().catch(() => ({ items: [], count: 0 })),
        apiClient.getNews({ limit: 30, days: 30 }),
      ]);
      setNewsOptIn(Boolean(me.news_opt_in));
      setNewsLanguage(me.news_language ?? "es");
      setNewsLanguages(me.news_languages?.length ? me.news_languages : [me.news_language ?? "es"]);
      setNewsTopics(me.news_topics ?? []);
      setTopicsCatalog(topics.items);
      setFeed(nextFeed);
    } catch {
      setError(t("news.unavailable"));
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    void load();
  }, [load]);

  const savePreferences = async () => {
    if (!accessToken) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await authClient.updateNewsPreferences(accessToken, {
        news_opt_in: newsOptIn,
        news_language: newsLanguages[0] ?? newsLanguage,
        news_languages: newsLanguages.length ? newsLanguages : [newsLanguage],
        news_topics: newsTopics,
      });
      setMessage(t("news.saved"));
      await load();
    } catch {
      setError(t("news.unavailable"));
    } finally {
      setSaving(false);
    }
  };

  const toggleTopic = (code: string) => {
    setNewsTopics((current) =>
      current.includes(code) ? current.filter((item) => item !== code) : [...current, code],
    );
  };

  if (!isAuthenticated()) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <header className="border-b border-osap-border pb-5">
          <h1 className="text-3xl font-semibold text-osap-ink">{t("news.title")}</h1>
          <p className="mt-2 text-sm text-osap-muted">{t("news.loginIntro")}</p>
        </header>
        <section className="rounded-card border border-osap-border bg-osap-surface p-6 shadow-card">
          <p className="text-sm text-osap-ink">{t("news.intro")}</p>
          <div className="mt-5 flex flex-wrap gap-3">
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
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="border-b border-osap-border pb-5">
        <h1 className="text-3xl font-semibold text-osap-ink">{t("news.title")}</h1>
        <p className="mt-2 max-w-3xl text-sm text-osap-muted">{t("news.intro")}</p>
      </header>

      <section className="space-y-4 rounded-card border border-osap-border bg-osap-surface p-5 shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-osap-ink">{t("news.preferences")}</h2>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setShowPreferences((value) => !value)}
              className="rounded-full border border-osap-border px-3 py-1 text-xs text-osap-ink hover:border-osap-accent"
            >
              {showPreferences ? t("news.hidePreferences") : t("news.editPreferences")}
            </button>
            <Link to="/account" className="text-sm text-osap-accent hover:underline">
              {t("nav.sectionYourSpace")}
            </Link>
          </div>
        </div>
        {showPreferences ? (
          <>
        <label className="flex items-start gap-3 text-sm text-osap-ink">
          <input
            type="checkbox"
            className="mt-1"
            checked={newsOptIn}
            onChange={(event) => setNewsOptIn(event.target.checked)}
          />
          <span>
            {t("news.optIn")}
            <span className="mt-1 block text-xs text-osap-muted">{t("news.optInHint")}</span>
          </span>
        </label>
        <div>
          <p className="text-sm text-osap-ink">{t("news.language")}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {NEWS_LANGUAGES.map(([code, label]) => (
              <button
                key={code}
                type="button"
                onClick={() =>
                  setNewsLanguages((current) =>
                    current.includes(code)
                      ? current.filter((language) => language !== code)
                      : [...current, code],
                  )
                }
                className={`rounded-full border px-3 py-1 text-xs ${
                  newsLanguages.includes(code)
                    ? "border-osap-accent bg-osap-accent text-white"
                    : "border-osap-border text-osap-ink hover:border-osap-accent"
                }`}
              >
                {label}
              </button>
            ))}
            <button
              type="button"
              onClick={() => setNewsLanguages(NEWS_LANGUAGES.map(([code]) => code))}
              className="rounded-full border border-osap-border px-3 py-1 text-xs text-osap-ink hover:border-osap-accent"
            >
              {t("news.allLanguages")}
            </button>
          </div>
        </div>
        <div>
          <p className="text-sm text-osap-ink">{t("news.topics")}</p>
          {topicsCatalog.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-2">
              {topicsCatalog.map((topic) => (
                <button
                  key={topic.code}
                  type="button"
                  onClick={() => toggleTopic(topic.code)}
                  className={`rounded-full border px-3 py-1 text-xs ${
                    newsTopics.includes(topic.code)
                      ? "border-osap-accent bg-osap-accent text-white"
                      : "border-osap-border text-osap-ink hover:border-osap-accent"
                  }`}
                  title={topic.description}
                >
                  {topic.name}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setNewsTopics(topicsCatalog.map((topic) => topic.code))}
                className="rounded-full border border-osap-border px-3 py-1 text-xs text-osap-ink hover:border-osap-accent"
              >
                {t("news.allTopics")}
              </button>
            </div>
          ) : (
            <p className="mt-2 text-xs text-osap-muted">{t("news.noTopics")}</p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => void savePreferences()}
            disabled={saving}
            className="rounded-full bg-osap-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {t("news.save")}
          </button>
          {message && <span className="text-sm text-osap-muted">{message}</span>}
          {error && <span className="text-sm text-red-500">{error}</span>}
        </div>
          </>
        ) : null}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-osap-ink">
          {feed?.personalized ? t("news.title") : t("news.general")}
        </h2>
        {loading && <p className="text-sm text-osap-muted">{t("news.loading")}</p>}
        {!loading && feed && feed.items.length === 0 && (
          <div className="rounded-card border border-osap-border bg-osap-surface p-5">
            <p className="text-sm text-osap-ink">{t("news.empty")}</p>
            <p className="mt-1 text-xs text-osap-muted">{t("news.emptyHint")}</p>
          </div>
        )}
        {!loading && feed && feed.items.length > 0 && (
          <ul className="space-y-3">
            {feed.items.map((item) => (
              <li
                key={`${item.news_item_id}-${item.publication_id ?? "none"}`}
                className="rounded-card border border-osap-border bg-osap-surface p-4 shadow-card"
              >
                <h3 className="text-base font-semibold text-osap-ink">{item.title}</h3>
                {item.summary && (
                  <p className="mt-1 text-sm text-osap-muted">{item.summary}</p>
                )}
                <p className="mt-2 text-xs text-osap-muted">
                  {[item.publisher, formatEuroDate(item.published_at)]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
                {item.url && (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 inline-block text-sm text-osap-accent hover:underline"
                  >
                    {t("news.read")} →
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}



