import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { AmigosMediaInput, AmigosMyGroup } from "../api/types";
import { AmigosImageField } from "../components/AmigosImageField";
import { Card } from "../components/Card";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";
import { useAuth } from "../state/auth";
import { htmlToText, textToHtml } from "../utils/richtext";

const STATUS_KEY: Record<string, TKey> = {
  draft: "friends.status.draft",
  pending: "friends.status.pending",
  published: "friends.status.published",
  withdrawn: "friends.status.withdrawn",
};

interface MediaRow {
  kind: "video" | "photo";
  url: string;
  caption: string;
  credit: string;
}

// Editor de artículos. La autorización real la aplica el servidor: aquí solo se permite
// elegir entre los grupos en los que el usuario es miembro activo (`/amigos/my/groups`).
export function AmigosEditorPage() {
  const { t } = useI18n();
  const { articleId } = useParams<{ articleId: string }>();
  const [searchParams] = useSearchParams();
  const preferredGroup = searchParams.get("group");
  const navigate = useNavigate();
  const user = useAuth((s) => s.user);

  const [groups, setGroups] = useState<AmigosMyGroup[]>([]);
  const [editGroup, setEditGroup] = useState<{ id: string; name: string } | null>(null);
  const [groupId, setGroupId] = useState("");
  const [title, setTitle] = useState("");
  const [eventDate, setEventDate] = useState("");
  const [summary, setSummary] = useState("");
  const [body, setBody] = useState("");
  const [bodyMode, setBodyMode] = useState<"text" | "code">("text");
  const [coverUrl, setCoverUrl] = useState("");
  const [media, setMedia] = useState<MediaRow[]>([]);
  const [status, setStatus] = useState<string>("draft");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submittingRef = useRef(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const mine = await apiClient.getAmigosMyGroups();
        setGroups(mine);
        if (articleId === undefined) {
          const preferred =
            preferredGroup !== null && mine.some((g) => g.group.id === preferredGroup)
              ? preferredGroup
              : String(mine[0]?.group.id ?? "");
          if (preferred !== "") setGroupId(preferred);
        }
        if (articleId !== undefined) {
          const article = await apiClient.getAmigosArticle(articleId);
          setGroupId(article.group_id);
          setEditGroup({
            id: article.group_id,
            name:
              article.group_name ??
              (article.group_id === "" ? t("friends.blogTitle") : article.group_id),
          });
          setTitle(article.title);
          setEventDate(article.event_date);
          setSummary(article.summary ?? "");
          setBody(article.body);
          setCoverUrl(article.cover_url ?? "");
          setStatus(article.status);
          setMedia(
            article.media.map((m) => ({
              kind: m.kind === "video" ? "video" : "photo",
              url: m.url,
              caption: m.caption ?? "",
              credit: m.credit ?? "",
            })),
          );
        }
      } catch {
        setError(t("friends.errorSaving"));
      } finally {
        setReady(true);
      }
    })();
  }, [articleId, preferredGroup, t]);

  const generalArticle = groupId === "" || groupId === "None";
  const uploadScope: "blog" | "group" = generalArticle ? "blog" : "group";

  const mediaPayload = (): AmigosMediaInput[] =>
    media
      .filter((m) => m.url.trim() !== "")
      .map((m) => ({
        kind: m.kind,
        url: m.url.trim(),
        caption: m.caption.trim() || null,
        credit: m.credit.trim() || null,
      }));

  const run = async (fn: () => Promise<void>) => {
    // Evita dobles envíos (dos POST simultáneos crearían artículos duplicados).
    if (submittingRef.current) return;
    submittingRef.current = true;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await fn();
    } catch {
      setError(t("friends.errorSaving"));
    } finally {
      submittingRef.current = false;
      setBusy(false);
    }
  };

  const saveDraft = () =>
    run(async () => {
      if (title.trim() === "") {
        setError(t("friends.titleRequired"));
        return;
      }
      if (articleId === undefined) {
        const created = await apiClient.createAmigosArticle(groupId, {
          title,
          event_date: eventDate,
          body,
          summary: summary.trim() || null,
          cover_url: coverUrl.trim() || null,
          media: mediaPayload(),
          action: "draft",
        });
        setStatus(created.status);
        navigate(`/amigos/editor/${encodeURIComponent(created.id)}`);
      } else {
        await apiClient.updateAmigosArticle(articleId, {
          title,
          event_date: eventDate,
          body,
          summary: summary.trim() || null,
          cover_url: coverUrl.trim() || null,
          media: mediaPayload(),
        });
        setMessage(t("friends.saved"));
      }
    });

  const publish = () =>
    run(async () => {
      if (title.trim() === "") {
        setError(t("friends.titleRequired"));
        return;
      }
      if (articleId === undefined) {
        const created = await apiClient.createAmigosArticle(groupId, {
          title,
          event_date: eventDate,
          body,
          summary: summary.trim() || null,
          cover_url: coverUrl.trim() || null,
          media: mediaPayload(),
          action: "publish",
        });
        setStatus(created.status);
        navigate(`/amigos/editor/${encodeURIComponent(created.id)}`);
        setMessage(t("friends.saved"));
      } else {
        await apiClient.updateAmigosArticle(articleId, {
          title,
          event_date: eventDate,
          body,
          summary: summary.trim() || null,
          cover_url: coverUrl.trim() || null,
          media: mediaPayload(),
        });
        const updated = await apiClient.publishAmigosArticle(articleId);
        setStatus(updated.status);
        setMessage(t("friends.saved"));
      }
    });

  const withdraw = () =>
    run(async () => {
      if (articleId === undefined) return;
      const updated = await apiClient.withdrawAmigosArticle(articleId);
      setStatus(updated.status);
      setMessage(t("friends.saved"));
    });

  const addMedia = (kind: "video" | "photo") =>
    setMedia((rows) => [...rows, { kind, url: "", caption: "", credit: "" }]);

  const updateMedia = (index: number, patch: Partial<MediaRow>) =>
    setMedia((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));

  const uploadPhoto = async (index: number, file: File) => {
    try {
      const res = await apiClient.uploadAmigosImage(file, {
        groupId: generalArticle ? undefined : groupId,
        scope: uploadScope,
      });
      updateMedia(index, { url: res.url });
    } catch {
      setError(t("friends.errorSaving"));
    }
  };

  const removeMedia = (index: number) =>
    setMedia((rows) => rows.filter((_, i) => i !== index));

  if (user === null) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">{t("friends.newArticle")}</h1>
        <p className="text-sm text-osap-muted">{t("friends.loginToWrite")}</p>
      </div>
    );
  }

  if (!ready) {
    return <p className="text-sm text-osap-muted">{t("states.loading")}</p>;
  }

  if (groups.length === 0 && editGroup === null) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">{t("friends.newArticle")}</h1>
        <p className="text-sm text-osap-muted">{t("friends.noGroups")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-osap-border pb-4">
        <h1 className="text-2xl font-semibold">
          {articleId === undefined ? t("friends.newArticle") : t("friends.edit")}
        </h1>
        <span className="rounded bg-osap-accent-soft px-2 py-0.5 text-xs text-osap-accent">
          {t(STATUS_KEY[status] ?? "friends.status.draft")}
        </span>
      </header>

      {message ? <p className="text-sm text-osap-success">{message}</p> : null}
      {error ? <p className="text-sm text-osap-danger">{error}</p> : null}

      <Card title={t("friends.group")}>
        <select
          value={groupId}
          disabled={articleId !== undefined}
          onChange={(e) => setGroupId(e.target.value)}
          className="w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm disabled:opacity-60"
        >
          {groups.map((g) => (
            <option key={g.group.id} value={g.group.id}>
              {g.group.name} — {g.role === "admin" ? t("friends.roleAdmin") : t("friends.roleCollaborator")}
            </option>
          ))}
          {editGroup !== null && !groups.some((g) => g.group.id === editGroup.id) ? (
            <option value={editGroup.id}>{editGroup.name}</option>
          ) : null}
        </select>
      </Card>

      <Card title={t("friends.titleField")}>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={t("friends.titleField")}
          className="w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
        />
        <label className="mt-3 block text-xs text-osap-muted">{t("friends.eventDate")}</label>
        <input
          type="date"
          value={eventDate}
          onChange={(e) => setEventDate(e.target.value)}
          className="mt-1 rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
        />
      </Card>

      <Card title={t("friends.summaryField")}>
        <textarea
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          rows={2}
          className="w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
        />
        <div className="mt-3">
          <AmigosImageField
            groupId={generalArticle ? undefined : groupId}
            scope={uploadScope}
            label={t("friends.coverField")}
            value={coverUrl}
            onChange={setCoverUrl}
          />
        </div>
      </Card>

      <Card title={t("friends.bodyField")}>
        <div className="mb-2 flex justify-end">
          <button
            type="button"
            onClick={() => {
              setBody((b) => (bodyMode === "text" ? textToHtml(b) : htmlToText(b)));
              setBodyMode((m) => (m === "text" ? "code" : "text"));
            }}
            className="rounded-md border border-osap-border px-3 py-1 text-xs"
          >
            {bodyMode === "text" ? t("friends.code") : t("friends.text")}
          </button>
        </div>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={10}
          spellCheck={bodyMode === "text"}
          className={`w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm ${
            bodyMode === "code" ? "font-mono" : ""
          }`}
        />
      </Card>

      <Card title={t("friends.mediaField")}>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => addMedia("video")}
            className="rounded-md border border-osap-border px-3 py-1.5 text-sm hover:border-osap-accent"
          >
            + {t("friends.addVideo")}
          </button>
          <button
            type="button"
            onClick={() => addMedia("photo")}
            className="rounded-md border border-osap-border px-3 py-1.5 text-sm hover:border-osap-accent"
          >
            + {t("friends.addPhoto")}
          </button>
        </div>
        <div className="mt-3 space-y-3">
          {media.map((row, index) => (
            <div key={index} className="rounded-md border border-osap-border p-3">
              <p className="text-xs font-semibold text-osap-muted">
                {row.kind === "video" ? t("friends.videoUrl") : t("friends.photoUrl")}
              </p>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <input
                  value={row.url}
                  onChange={(e) => updateMedia(index, { url: e.target.value })}
                  placeholder="https://…"
                  className="min-w-48 flex-1 rounded-md border border-osap-border bg-osap-surface px-3 py-1.5 text-sm"
                />
                {row.kind === "photo" ? (
                  <label className="cursor-pointer rounded-md border border-osap-border px-3 py-1.5 text-sm hover:border-osap-accent">
                    {t("friends.upload")}
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) void uploadPhoto(index, file);
                        e.target.value = "";
                      }}
                    />
                  </label>
                ) : null}
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                <input
                  value={row.caption}
                  onChange={(e) => updateMedia(index, { caption: e.target.value })}
                  placeholder={t("friends.caption")}
                  className="min-w-40 flex-1 rounded-md border border-osap-border bg-osap-surface px-3 py-1.5 text-sm"
                />
                <input
                  value={row.credit}
                  onChange={(e) => updateMedia(index, { credit: e.target.value })}
                  placeholder={t("friends.credit")}
                  className="min-w-40 flex-1 rounded-md border border-osap-border bg-osap-surface px-3 py-1.5 text-sm"
                />
                <button
                  type="button"
                  onClick={() => removeMedia(index)}
                  className="rounded-md border border-osap-border px-3 py-1.5 text-sm text-osap-danger"
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={saveDraft}
          className="rounded-md border border-osap-border px-4 py-2 text-sm disabled:opacity-50"
        >
          {t("friends.saveDraft")}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={publish}
          className="rounded-md bg-osap-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {t("friends.publish")}
        </button>
        {articleId !== undefined ? (
          <>
            <button
              type="button"
              disabled={busy}
              onClick={withdraw}
              className="rounded-md border border-osap-border px-4 py-2 text-sm text-osap-danger disabled:opacity-50"
            >
              {t("friends.withdraw")}
            </button>
            {/* Página pública del artículo = SSR (osap-api): navegación completa. */}
            <a
              href={`/amigos/articulo/${encodeURIComponent(articleId)}`}
              className="text-sm text-osap-accent hover:underline"
            >
              {t("friends.viewPublic")} →
            </a>
          </>
        ) : null}
      </div>
    </div>
  );
}
