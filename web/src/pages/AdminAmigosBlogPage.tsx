import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { AmigosArticle, AmigosArticleCreateInput, AmigosArticleList } from "../api/types";
import { AmigosImageField } from "../components/AmigosImageField";
import { Card } from "../components/Card";
import { useBodyMode } from "../components/useBodyMode";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";
import { formatEuroDate } from "../utils/dates";

const STATUS_KEY: Record<string, TKey> = {
  draft: "friends.status.draft",
  pending: "friends.status.pending",
  published: "friends.status.published",
  withdrawn: "friends.status.withdrawn",
};

// Blog general «Artículos»: crear y aprobar publicaciones (autor autorizado o admin).
export function AdminAmigosBlogPage({ mine = false }: { mine?: boolean } = {}) {
  const { t } = useI18n();
  const [articles, setArticles] = useState<AmigosArticle[]>([]);
  const [title, setTitle] = useState("");
  const [eventDate, setEventDate] = useState("");
  const [summary, setSummary] = useState("");
  const [cover, setCover] = useState("");
  const { body, setBody, mode: bodyMode, toggle: toggleBody } = useBodyMode("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = mine
        ? await apiClient.getAmigosMyBlog()
        : await apiClient.get<AmigosArticleList>("/admin/amigos/blog");
      setArticles(data.items);
    } catch {
      setArticles([]);
    }
  }, [mine]);

  useEffect(() => {
    void load();
  }, [load]);

  const create = async (action: "draft" | "publish") => {
    setError(null);
    if (title.trim() === "" || body.trim() === "" || eventDate === "") {
      setError(t("friends.titleRequired"));
      return;
    }
    const payload: AmigosArticleCreateInput = {
      title: title.trim(),
      event_date: eventDate,
      body,
      summary: summary.trim() || null,
      cover_url: cover.trim() || null,
      action,
    };
    try {
      await apiClient.createAmigosBlogArticle(payload);
      setTitle("");
      setEventDate("");
      setSummary("");
      setCover("");
      setBody("");
      await load();
    } catch {
      setError(t("friends.errorSaving"));
    }
  };

  const approve = async (id: string) => {
    try {
      await apiClient.approveAmigosBlogArticle(id);
      await load();
    } catch {
      setError(t("friends.errorSaving"));
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <h1 className="text-xl font-semibold">
        {t("nav.sectionFriends")} · {t("friends.blogTitle")}
      </h1>

      <Card title={t("friends.newArticle")}>
        {error ? <p className="mb-2 text-sm text-osap-danger">{error}</p> : null}
        <div className="grid gap-2 sm:grid-cols-3">
          <label className="text-xs text-osap-muted sm:col-span-2">
            {t("friends.titleField")} *
            <input value={title} onChange={(e) => setTitle(e.target.value)} className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm" />
          </label>
          <label className="text-xs text-osap-muted">
            {t("friends.eventDate")} *
            <input type="date" value={eventDate} onChange={(e) => setEventDate(e.target.value)} className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm" />
          </label>
          <label className="text-xs text-osap-muted sm:col-span-3">
            {t("friends.summaryField")}
            <input value={summary} onChange={(e) => setSummary(e.target.value)} className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm" />
          </label>
          <div className="sm:col-span-3">
            <AmigosImageField
              label={t("friends.coverField")}
              scope="blog"
              value={cover}
              onChange={setCover}
            />
          </div>
          <div className="text-xs text-osap-muted sm:col-span-3">
            <div className="flex items-center justify-between">
              <span>{t("friends.bodyField")} *</span>
              <button
                type="button"
                onClick={toggleBody}
                className="rounded-md border border-osap-border px-3 py-1 text-xs"
              >
                {bodyMode === "text" ? t("friends.code") : t("friends.text")}
              </button>
            </div>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={6}
              spellCheck={bodyMode === "text"}
              className={`mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm ${
                bodyMode === "code" ? "font-mono" : ""
              }`}
            />
          </div>
        </div>
        <div className="mt-3 flex gap-2">
          <button type="button" onClick={() => void create("draft")} className="rounded-md border border-osap-border px-4 py-2 text-sm">
            {t("friends.saveDraft")}
          </button>
          <button type="button" onClick={() => void create("publish")} className="rounded-md bg-osap-accent px-4 py-2 text-sm font-medium text-white">
            {t("friends.publish")}
          </button>
        </div>
      </Card>

      <ul className="divide-y divide-osap-border overflow-hidden rounded-card border border-osap-border bg-osap-surface">
        {articles.map((a) => (
          <li key={a.id} className="flex items-center justify-between px-4 py-3">
            <div className="min-w-0">
              <p className="truncate text-sm">{a.title}</p>
              <p className="text-xs text-osap-muted">{formatEuroDate(a.event_date)}</p>
            </div>
            <span className="flex items-center gap-2 text-xs">
              <span className="rounded bg-osap-accent-soft px-2 py-0.5">
                {t(STATUS_KEY[a.status] ?? "friends.status.draft")}
              </span>
              <Link
                to={`/amigos/editor/${encodeURIComponent(a.id)}`}
                className="text-osap-accent hover:underline"
              >
                {t("friends.edit")}
              </Link>
              {a.status === "pending" ? (
                <button type="button" onClick={() => void approve(a.id)} className="text-osap-success hover:underline">
                  {t("friends.approve")}
                </button>
              ) : null}
            </span>
          </li>
        ))}
        {articles.length === 0 ? (
          <li className="px-4 py-4 text-sm text-osap-muted">{t("friends.blogEmpty")}</li>
        ) : null}
      </ul>
    </div>
  );
}
