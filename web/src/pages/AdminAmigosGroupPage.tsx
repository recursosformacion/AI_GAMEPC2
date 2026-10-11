import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { AmigosArticle, AmigosGroup, AmigosGroupLink, AmigosMember } from "../api/types";
import { AmigosImageField } from "../components/AmigosImageField";
import { Card } from "../components/Card";
import { Spinner } from "../components/Spinner";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";

const STATUS_KEY: Record<string, TKey> = {
  draft: "friends.status.draft",
  pending: "friends.status.pending",
  published: "friends.status.published",
  withdrawn: "friends.status.withdrawn",
};

const FORMATION_KEYS: Record<string, TKey> = {
  mixed: "friends.formation.mixed",
  equal_voices: "friends.formation.equal_voices",
  children: "friends.formation.children",
  youth: "friends.formation.youth",
  male: "friends.formation.male",
  female: "friends.formation.female",
  other: "friends.formation.other",
};

interface DirectoryUser {
  user_id: string;
  email: string;
  name?: string | null;
}

interface CoralForm {
  foundation_date: string;
  dissolution_date: string;
  locality: string;
  region: string;
  country_code: string;
  venue: string;
  formation_type: string;
  member_count: string;
  website: string;
  public_email: string;
  director_label: string;
  linked_entity: string;
  repertoire: string;
  languages: string;
  places: string;
}

const EMPTY_CORAL: CoralForm = {
  foundation_date: "",
  dissolution_date: "",
  locality: "",
  region: "",
  country_code: "",
  venue: "",
  formation_type: "",
  member_count: "",
  website: "",
  public_email: "",
  director_label: "",
  linked_entity: "",
  repertoire: "",
  languages: "",
  places: "",
};

function splitCsv(value: string): string[] {
  return value.split(",").map((s) => s.trim()).filter((s) => s !== "");
}

export function AdminAmigosGroupPage() {
  const { t } = useI18n();
  const { groupId = "" } = useParams<{ groupId: string }>();
  const [searchParams] = useSearchParams();
  const viewMode = searchParams.get("mode") === "view";

  const [group, setGroup] = useState<AmigosGroup | null>(null);
  const [members, setMembers] = useState<AmigosMember[]>([]);
  const [articles, setArticles] = useState<AmigosArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [website, setWebsite] = useState("");
  const [email, setEmail] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [groupLinks, setGroupLinks] = useState<AmigosGroupLink[]>([]);
  const [mode, setMode] = useState<"direct" | "moderated">("moderated");
  const [status, setStatus] = useState<"active" | "inactive" | "dissolved">("active");
  const [coralForm, setCoralForm] = useState<CoralForm>(EMPTY_CORAL);
  const setCoralField = (patch: Partial<CoralForm>) =>
    setCoralForm((prev) => ({ ...prev, ...patch }));

  const [newUserId, setNewUserId] = useState("");
  const [newRole, setNewRole] = useState<"collaborator" | "admin">("collaborator");
  const [users, setUsers] = useState<DirectoryUser[]>([]);
  const [usersUnavailable, setUsersUnavailable] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const groups = await apiClient.getAmigosGroups(true);
      const found = groups.find((g) => g.id === groupId) ?? null;
      setGroup(found);
      if (found) {
        setName(found.name);
        setDescription(found.description ?? "");
        setImageUrl(found.image_url ?? "");
        setWebsite(found.website ?? "");
        setEmail(found.email ?? "");
        setLogoUrl(found.logo_url ?? "");
        setGroupLinks(found.links ?? []);
        setMode(found.editorial_mode === "direct" ? "direct" : "moderated");
        setStatus(
          found.status === "inactive"
            ? "inactive"
            : found.status === "dissolved"
              ? "dissolved"
              : "active",
        );
        if (found.kind === "coral") {
          try {
            const c = await apiClient.getAmigosCoralDetails(groupId);
            setCoralForm({
              foundation_date: c.foundation_date ?? "",
              dissolution_date: c.dissolution_date ?? "",
              locality: c.locality ?? "",
              region: c.region ?? "",
              country_code: c.country_code ?? "",
              venue: c.venue ?? "",
              formation_type: c.formation_type ?? "",
              member_count: c.member_count != null ? String(c.member_count) : "",
              website: c.website ?? "",
              public_email: c.public_email ?? "",
              director_label: c.director_label ?? "",
              linked_entity: c.linked_entity ?? "",
              repertoire: (c.repertoire ?? []).join(", "),
              languages: (c.languages ?? []).join(", "),
              places: (c.places ?? []).join(", "),
            });
          } catch {
            /* la ficha puede no existir todavía */
          }
        }
      }
      const [memberList, articleList] = await Promise.all([
        apiClient.getAmigosMembers(groupId),
        apiClient.getAmigosGroupArticlesAdmin(groupId),
      ]);
      setMembers(memberList.items);
      setArticles(articleList.items);
      try {
        setUsers(await apiClient.get<DirectoryUser[]>("/admin/users"));
        setUsersUnavailable(false);
      } catch {
        // Sin permiso para listar usuarios (p. ej. admin de grupo no global): se pide id.
        setUsersUnavailable(true);
      }
    } catch {
      setError(t("friends.errorSaving"));
    } finally {
      setLoading(false);
    }
  }, [groupId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const guard = async (fn: () => Promise<void>) => {
    setError(null);
    setMessage(null);
    try {
      await fn();
    } catch {
      setError(t("friends.errorSaving"));
    }
  };

  const saveGroup = () =>
    guard(async () => {
      await apiClient.updateAmigosGroup(groupId, {
        name: name.trim(),
        description: description.trim() || null,
        image_url: imageUrl.trim() || null,
        website: website.trim() || null,
        email: email.trim() || null,
        logo_url: logoUrl.trim() || null,
        links: groupLinks.filter((l) => l.url.trim() !== ""),
        editorial_mode: mode,
        status,
      });
      setMessage(t("friends.saved"));
      await load();
    });

  const saveCoral = () =>
    guard(async () => {
      await apiClient.updateAmigosCoralDetails(groupId, {
        foundation_date: coralForm.foundation_date || null,
        dissolution_date: coralForm.dissolution_date || null,
        locality: coralForm.locality.trim() || null,
        region: coralForm.region.trim() || null,
        country_code: coralForm.country_code.trim() || null,
        venue: coralForm.venue.trim() || null,
        formation_type: coralForm.formation_type || null,
        member_count:
          coralForm.member_count.trim() === "" ? null : Number(coralForm.member_count),
        website: coralForm.website.trim() || null,
        public_email: coralForm.public_email.trim() || null,
        director_label: coralForm.director_label.trim() || null,
        linked_entity: coralForm.linked_entity.trim() || null,
        repertoire: splitCsv(coralForm.repertoire),
        languages: splitCsv(coralForm.languages),
        places: splitCsv(coralForm.places),
      });
      setMessage(t("friends.saved"));
    });

  const toggleBaja = () =>
    guard(async () => {
      await apiClient.updateAmigosGroup(groupId, {
        status: status === "active" ? "inactive" : "active",
      });
      setMessage(t("friends.saved"));
      await load();
    });

  const grantMember = () =>
    guard(async () => {
      if (newUserId.trim() === "") return;
      await apiClient.grantAmigosMember(groupId, newUserId.trim(), newRole);
      setNewUserId("");
      await load();
    });

  const revokeMember = (userId: string) =>
    guard(async () => {
      await apiClient.revokeAmigosMember(groupId, userId);
      await load();
    });

  const approve = (articleId: string) =>
    guard(async () => {
      await apiClient.approveAmigosArticle(articleId);
      await load();
    });

  const sendBack = (articleId: string) =>
    guard(async () => {
      await apiClient.returnAmigosArticle(articleId);
      await load();
    });

  const withdrawPost = (article: AmigosArticle) => {
    if (!window.confirm(t("friends.confirmBaja"))) return;
    void guard(async () => {
      await apiClient.withdrawAmigosArticle(article.id);
      await load();
    });
  };

  const publishPost = (articleId: string) =>
    guard(async () => {
      await apiClient.publishAmigosArticle(articleId);
      await load();
    });

  if (loading) return <Spinner />;
  if (group === null) {
    return <p className="text-sm text-osap-muted">{t("friends.groupsEmpty")}</p>;
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">{group.name}</h1>
        <Link to="/admin/amigos" className="text-sm text-osap-accent hover:underline">
          ← {t("friends.adminGroups")}
        </Link>
      </header>

      {message ? <p className="text-sm text-osap-success">{message}</p> : null}
      {error ? <p className="text-sm text-osap-danger">{error}</p> : null}

      <Card title={t("friends.groupName")}>
        <div className="grid gap-2 sm:grid-cols-2">
          <input
            value={name}
            disabled={viewMode}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("friends.groupName")}
            className="rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm disabled:opacity-60"
          />
          <AmigosImageField groupId={groupId} label={t("friends.imageUrl")} value={imageUrl} onChange={setImageUrl} disabled={viewMode} />
          <input
            value={description}
            disabled={viewMode}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t("friends.description")}
            className="rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm disabled:opacity-60 sm:col-span-2"
          />
          <input
            value={website}
            disabled={viewMode}
            onChange={(e) => setWebsite(e.target.value)}
            placeholder={t("friends.website")}
            className="rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm disabled:opacity-60"
          />
          <input
            value={email}
            disabled={viewMode}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t("friends.publicEmail")}
            className="rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm disabled:opacity-60"
          />
          <div className="sm:col-span-2">
            <AmigosImageField groupId={groupId} label={t("friends.logo")} value={logoUrl} onChange={setLogoUrl} disabled={viewMode} />
          </div>
          <div className="sm:col-span-2">
            <p className="text-xs text-osap-muted">{t("friends.socialLinks")}</p>
            {groupLinks.map((link, i) => (
              <div key={i} className="mt-1 flex flex-wrap items-center gap-2">
                <select
                  value={link.kind}
                  disabled={viewMode}
                  onChange={(e) =>
                    setGroupLinks((rows) =>
                      rows.map((r, j) => (j === i ? { ...r, kind: e.target.value } : r)),
                    )
                  }
                  className="rounded-md border border-osap-border bg-osap-surface px-3 py-1.5 text-sm disabled:opacity-60"
                >
                  <option value="facebook">{t("friends.social.facebook")}</option>
                  <option value="instagram">{t("friends.social.instagram")}</option>
                  <option value="other">{t("friends.social.other")}</option>
                </select>
                {link.kind === "other" ? (
                  <input
                    value={link.label ?? ""}
                    disabled={viewMode}
                    onChange={(e) =>
                      setGroupLinks((rows) =>
                        rows.map((r, j) => (j === i ? { ...r, label: e.target.value } : r)),
                      )
                    }
                    className="w-32 rounded-md border border-osap-border bg-osap-surface px-3 py-1.5 text-sm disabled:opacity-60"
                  />
                ) : null}
                <input
                  value={link.url}
                  disabled={viewMode}
                  onChange={(e) =>
                    setGroupLinks((rows) =>
                      rows.map((r, j) => (j === i ? { ...r, url: e.target.value } : r)),
                    )
                  }
                  placeholder={t("friends.linkUrl")}
                  className="min-w-48 flex-1 rounded-md border border-osap-border bg-osap-surface px-3 py-1.5 text-sm disabled:opacity-60"
                />
                {viewMode ? null : (
                  <button
                    type="button"
                    onClick={() => setGroupLinks((rows) => rows.filter((_, j) => j !== i))}
                    className="rounded-md border border-osap-border px-3 py-1.5 text-sm text-osap-danger"
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
            {viewMode ? null : (
              <button
                type="button"
                onClick={() =>
                  setGroupLinks((rows) => [...rows, { kind: "facebook", url: "", label: "" }])
                }
                className="mt-1 text-sm text-osap-accent hover:underline"
              >
                + {t("friends.addLink")}
              </button>
            )}
          </div>
          <select
            value={mode}
            disabled={viewMode}
            onChange={(e) => setMode(e.target.value === "direct" ? "direct" : "moderated")}
            className="rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm disabled:opacity-60"
          >
            <option value="moderated">{t("friends.modeModerated")}</option>
            <option value="direct">{t("friends.modeDirect")}</option>
          </select>
          <select
            value={status}
            disabled={viewMode}
            onChange={(e) =>
              setStatus(
                e.target.value === "inactive"
                  ? "inactive"
                  : e.target.value === "dissolved"
                    ? "dissolved"
                    : "active",
              )
            }
            className="rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm disabled:opacity-60"
          >
            <option value="active">{t("friends.active")}</option>
            <option value="inactive">{t("friends.inactive")}</option>
            <option value="dissolved">{t("friends.dissolved")}</option>
          </select>
        </div>
        {viewMode ? null : (
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={saveGroup}
              className="rounded-md bg-osap-accent px-4 py-2 text-sm font-medium text-white"
            >
              {t("friends.save")}
            </button>
            <button
              type="button"
              onClick={toggleBaja}
              className={`rounded-md border border-osap-border px-4 py-2 text-sm ${
                status === "active" ? "text-red-500" : "text-emerald-600"
              }`}
            >
              {status === "active" ? t("friends.deactivate") : t("friends.reactivate")}
            </button>
          </div>
        )}
      </Card>

      {group.kind === "coral" ? (
        <Card title={t("friends.coralFicha")}>
          <p className="mb-2 text-xs text-osap-muted">{t("friends.coralFichaHint")}</p>
          <fieldset disabled={viewMode} className="grid gap-2 sm:grid-cols-2">
            <label className="text-xs text-osap-muted">
              {t("friends.formation")}
              <select
                value={coralForm.formation_type}
                onChange={(e) => setCoralField({ formation_type: e.target.value })}
                className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
              >
                <option value="">—</option>
                {Object.entries(FORMATION_KEYS).map(([code, key]) => (
                  <option key={code} value={code}>
                    {t(key)}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-osap-muted">
              {t("friends.memberCount")}
              <input
                type="number"
                value={coralForm.member_count}
                onChange={(e) => setCoralField({ member_count: e.target.value })}
                className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
              />
            </label>
            <label className="text-xs text-osap-muted">
              {t("friends.foundationDate")}
              <input
                type="date"
                value={coralForm.foundation_date}
                onChange={(e) => setCoralField({ foundation_date: e.target.value })}
                className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
              />
            </label>
            <label className="text-xs text-osap-muted">
              {t("friends.dissolutionDate")}
              <input
                type="date"
                value={coralForm.dissolution_date}
                onChange={(e) => setCoralField({ dissolution_date: e.target.value })}
                className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
              />
            </label>
            <label className="text-xs text-osap-muted">
              {t("friends.locality")}
              <input
                value={coralForm.locality}
                onChange={(e) => setCoralField({ locality: e.target.value })}
                className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
              />
            </label>
            <label className="text-xs text-osap-muted">
              {t("friends.region")}
              <input
                value={coralForm.region}
                onChange={(e) => setCoralField({ region: e.target.value })}
                className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
              />
            </label>
            <label className="text-xs text-osap-muted">
              {t("friends.country")}
              <input
                value={coralForm.country_code}
                onChange={(e) => setCoralField({ country_code: e.target.value })}
                maxLength={2}
                className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm uppercase"
              />
            </label>
            <label className="text-xs text-osap-muted">
              {t("friends.venue")}
              <input
                value={coralForm.venue}
                onChange={(e) => setCoralField({ venue: e.target.value })}
                className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
              />
            </label>
            <label className="text-xs text-osap-muted">
              {t("friends.director")}
              <input
                value={coralForm.director_label}
                onChange={(e) => setCoralField({ director_label: e.target.value })}
                className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
              />
            </label>
            <label className="text-xs text-osap-muted">
              {t("friends.linkedEntity")}
              <input
                value={coralForm.linked_entity}
                onChange={(e) => setCoralField({ linked_entity: e.target.value })}
                className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
              />
            </label>
            <label className="text-xs text-osap-muted">
              {t("friends.repertoire")} ({t("friends.multivalueHint")})
              <input
                value={coralForm.repertoire}
                onChange={(e) => setCoralField({ repertoire: e.target.value })}
                className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
              />
            </label>
            <label className="text-xs text-osap-muted">
              {t("friends.languages")} ({t("friends.multivalueHint")})
              <input
                value={coralForm.languages}
                onChange={(e) => setCoralField({ languages: e.target.value })}
                className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
              />
            </label>
            <label className="text-xs text-osap-muted sm:col-span-2">
              {t("friends.places")} ({t("friends.multivalueHint")})
              <input
                value={coralForm.places}
                onChange={(e) => setCoralField({ places: e.target.value })}
                className="mt-1 w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
              />
            </label>
          </fieldset>
          {viewMode ? null : (
            <button
              type="button"
              onClick={saveCoral}
              className="mt-3 rounded-md bg-osap-accent px-4 py-2 text-sm font-medium text-white"
            >
              {t("friends.save")}
            </button>
          )}
        </Card>
      ) : null}

      <Card title={t("friends.members")}>
        {viewMode ? null : (
          <div className="flex flex-wrap gap-2">
            {usersUnavailable ? (
              <input
                value={newUserId}
                onChange={(e) => setNewUserId(e.target.value)}
                placeholder={t("friends.userId")}
                className="min-w-48 flex-1 rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
              />
            ) : (
              <select
                value={newUserId}
                onChange={(e) => setNewUserId(e.target.value)}
                className="min-w-64 flex-1 rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
              >
                <option value="">{t("friends.pickUser")}</option>
                {users
                  .filter(
                    (u) =>
                      !members.some((m) => m.user_id === u.user_id && m.status === "active"),
                  )
                  .map((u) => (
                    <option key={u.user_id} value={u.user_id}>
                      {u.email}
                      {u.name ? ` — ${u.name}` : ""}
                    </option>
                  ))}
              </select>
            )}
            <select
              value={newRole}
              onChange={(e) => setNewRole(e.target.value === "admin" ? "admin" : "collaborator")}
              className="rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
            >
              <option value="collaborator">{t("friends.roleCollaborator")}</option>
              <option value="admin">{t("friends.roleAdmin")}</option>
            </select>
            <button
              type="button"
              onClick={grantMember}
              className="rounded-md bg-osap-accent px-4 py-2 text-sm font-medium text-white"
            >
              {t("friends.grant")}
            </button>
          </div>
        )}
        <ul className="mt-3 divide-y divide-osap-border">
          {members.map((m) => (
            <li key={m.user_id} className="flex items-center justify-between py-2 text-sm">
              <span className="min-w-0 truncate font-mono text-xs">{m.user_id}</span>
              <span className="flex items-center gap-2 text-xs">
                <span className="rounded bg-osap-accent-soft px-2 py-0.5">
                  {m.role === "admin" ? t("friends.roleAdmin") : t("friends.roleCollaborator")}
                </span>
                <span className="text-osap-muted">
                  {m.status === "active" ? t("friends.active") : t("friends.inactive")}
                </span>
                {m.status === "active" && !viewMode ? (
                  <button
                    type="button"
                    onClick={() => void revokeMember(m.user_id)}
                    className="text-osap-danger hover:underline"
                  >
                    {t("friends.revoke")}
                  </button>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      </Card>

      <Card title={t("friends.articlesTitle")}>
        <div className="mb-2 flex justify-end">
          <Link
            to={`/amigos/editor?group=${encodeURIComponent(groupId)}`}
            className="rounded-md bg-osap-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-osap-accent/90"
          >
            {t("friends.newArticle")}
          </Link>
        </div>
        {articles.length === 0 ? (
          <p className="text-sm text-osap-muted">{t("friends.articlesEmpty")}</p>
        ) : (
          <ul className="divide-y divide-osap-border">
            {articles.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className="min-w-0 truncate text-sm">{a.title}</span>
                <span className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="text-osap-muted">{a.event_date}</span>
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
                    <>
                      <button
                        type="button"
                        onClick={() => void approve(a.id)}
                        className="rounded bg-green-600 px-2 py-0.5 text-white"
                      >
                        {t("friends.approve")}
                      </button>
                      <button
                        type="button"
                        onClick={() => void sendBack(a.id)}
                        className="rounded border border-osap-border px-2 py-0.5"
                      >
                        {t("friends.return")}
                      </button>
                    </>
                  ) : null}
                  {a.status === "draft" ? (
                    <button
                      type="button"
                      onClick={() => void publishPost(a.id)}
                      className="rounded border border-osap-border px-2 py-0.5 text-emerald-600"
                    >
                      {t("friends.publish")}
                    </button>
                  ) : null}
                  {a.status === "published" ? (
                    <button
                      type="button"
                      onClick={() => withdrawPost(a)}
                      className="rounded border border-osap-border px-2 py-0.5 text-osap-danger"
                    >
                      {t("friends.deactivate")}
                    </button>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
