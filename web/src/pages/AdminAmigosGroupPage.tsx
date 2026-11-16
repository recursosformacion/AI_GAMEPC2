import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type {
  AmigosArticle,
  AmigosCatalogItem,
  AmigosGroup,
  AmigosGroupCatalog,
  AmigosGroupLink,
  AmigosMember,
} from "../api/types";
import { AmigosImageField } from "../components/AmigosImageField";
import { Card } from "../components/Card";
import { Spinner } from "../components/Spinner";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";
import { formatEuroDate } from "../utils/dates";

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
  nickname?: string | null;
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
  const [catalog, setCatalog] = useState<AmigosGroupCatalog>({ admin: [], musical: [], section: [] });
  const [requests, setRequests] = useState<AmigosMember[]>([]);
  const [catalogMessage, setCatalogMessage] = useState<string | null>(null);
  const [history, setHistory] = useState<Array<{
    id: string; event_type: string; member_user_id?: string | null; role?: string | null;
    start_date?: string | null; end_date?: string | null; notes?: string | null;
  }>>([]);
  const [articles, setArticles] = useState<AmigosArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [kind, setKind] = useState("coral");
  const [description, setDescription] = useState("");
  const [technicalDescription, setTechnicalDescription] = useState("");
  const [adminRoles, setAdminRoles] = useState("");
  const [musicalRoles, setMusicalRoles] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [website, setWebsite] = useState("");
  const [email, setEmail] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [groupLinks, setGroupLinks] = useState<AmigosGroupLink[]>([]);
  const [mode, setMode] = useState<"direct" | "moderated">("moderated");
  const [status, setStatus] = useState<"active" | "inactive" | "dissolved">("active");
  const [status0, setStatus0] = useState<"active" | "inactive" | "dissolved">("active");
  const [coralForm, setCoralForm] = useState<CoralForm>(EMPTY_CORAL);
  const setCoralField = (patch: Partial<CoralForm>) =>
    setCoralForm((prev) => ({ ...prev, ...patch }));

  const [newUserId, setNewUserId] = useState("");
  const [newRole, setNewRole] = useState<"collaborator" | "admin">("collaborator");
  const [newAdminRole, setNewAdminRole] = useState("");
  const [newMusicalRole, setNewMusicalRole] = useState("");
  const [newSection, setNewSection] = useState("");
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
        setKind(found.kind || "coral");
        setDescription(found.description ?? "");
        setTechnicalDescription(found.technical_description ?? "");
        setAdminRoles((found.admin_roles ?? []).join(", "));
        setMusicalRoles((found.musical_roles ?? []).join(", "));
        setImageUrl(found.image_url ?? "");
        setWebsite(found.website ?? "");
        setEmail(found.email ?? "");
        setLogoUrl(found.logo_url ?? "");
        setGroupLinks(found.links ?? []);
        setMode(found.editorial_mode === "direct" ? "direct" : "moderated");
        const resolvedStatus =
          found.status === "inactive"
            ? "inactive"
            : found.status === "dissolved"
              ? "dissolved"
              : "active";
        setStatus(resolvedStatus);
        setStatus0(resolvedStatus);
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
      const [memberList, historyList, articleList, catalogData, requestList] = await Promise.all([
        apiClient.getAmigosMembers(groupId),
        apiClient.getAmigosGroupHistory(groupId),
        apiClient.getAmigosGroupArticlesAdmin(groupId),
        apiClient.getAmigosGroupCatalog(groupId),
        apiClient.getAmigosGroupRequests(groupId),
      ]);
      setMembers(memberList.items);
      setHistory(historyList);
      setCatalog(catalogData);
      setRequests(requestList.items);
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
        kind,
        description: description.trim() || null,
        technical_description: technicalDescription.trim() || null,
        admin_roles: splitCsv(adminRoles),
        musical_roles: splitCsv(musicalRoles),
        image_url: imageUrl.trim() || null,
        website: website.trim() || null,
        email: email.trim() || null,
        logo_url: logoUrl.trim() || null,
        links: groupLinks.filter((l) => l.url.trim() !== ""),
        editorial_mode: mode,
        ...(status !== status0 ? { status } : {}),
      });
      setMessage(t("friends.saved"));
      await load();
    });

  const saveCatalog = () =>
    guard(async () => {
      const items: AmigosCatalogItem[] = [
        ...catalog.admin.map((item, index) => ({ ...item, scope: "admin" as const, sort_order: index })),
        ...catalog.musical.map((item, index) => ({ ...item, scope: "musical" as const, sort_order: index })),
        ...catalog.section.map((item, index) => ({ ...item, scope: "section" as const, sort_order: index })),
      ];
      setCatalog(await apiClient.updateAmigosGroupCatalog(groupId, items));
      setCatalogMessage("Cargos guardados.");
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

  const resolveUser = (query: string): DirectoryUser | null => {
    const q = query.trim().toLowerCase();
    if (q === "") return null;
    return (
      users.find((u) => u.email.toLowerCase() === q) ??
      users.find((u) => u.user_id === query.trim()) ??
      null
    );
  };

  const userLabel = (userId: string): string => {
    const u = users.find((x) => x.user_id === userId);
    if (u === undefined) return userId;
    const nick = u.nickname ? ` (${u.nickname})` : "";
    const name = u.name ? `${u.name} · ` : "";
    return `${name}${u.email}${nick}`;
  };

  const grantMember = () =>
    guard(async () => {
      const query = newUserId.trim();
      if (query === "") return;
      // Se admite el email (buscado en el directorio) o el propio user_id.
      const resolved = resolveUser(query);
      const userId = resolved !== null ? resolved.user_id : query;
      await apiClient.grantAmigosMember(groupId, userId, newRole, {
        admin_role_id: newAdminRole || null,
        musical_role_id: newMusicalRole || null,
        section_id: newSection || null,
      });
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
    if (!window.confirm(t("friends.confirmWithdraw"))) return;
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
        <div className="flex items-center gap-2"><h1 className="text-xl font-semibold">{group.name}</h1><span className="rounded bg-osap-accent-soft px-2 py-0.5 text-xs text-osap-accent">{kind === "coral" ? "Coral" : kind}</span></div>
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
          <label className="text-xs text-osap-muted">
            Tipo de grupo/entidad
            <select
              value={kind}
              disabled={viewMode}
              onChange={(e) => setKind(e.target.value)}
              className="mt-1 block w-full rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm disabled:opacity-60"
            >
              {["coral","grupo","banda","orquesta","ensemble","escuela","iglesia"].map((value) => (
                <option key={value} value={value}>{value.charAt(0).toUpperCase() + value.slice(1)}</option>
              ))}
            </select>
          </label>
          <AmigosImageField groupId={groupId} label={t("friends.imageUrl")} value={imageUrl} onChange={setImageUrl} disabled={viewMode} />
          <input
            value={description}
            disabled={viewMode}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t("friends.description")}
            className="rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm disabled:opacity-60 sm:col-span-2"
          />
          <textarea
            value={technicalDescription}
            disabled={viewMode}
            maxLength={1000}
            onChange={(e) => setTechnicalDescription(e.target.value)}
            placeholder="Descripción técnica (formación, secciones, plantilla…)"
            rows={4}
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
            {kind === "coral" ? (
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
            ) : null}
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
            <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-osap-muted sm:col-span-2">Dirección</p>
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
            {/* La dirección musical es un rol del catálogo del grupo. */}
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

      <Card title="Cargos, roles musicales y secciones">
        <div className="grid gap-4 md:grid-cols-3">
          {([
            ["admin", "Cargos administrativos"],
            ["musical", "Roles musicales"],
            ["section", "Secciones / cuerdas"],
          ] as const).map(([scope, title]) => (
            <div key={scope} className="space-y-2">
              <h3 className="text-sm font-semibold text-osap-ink">{title}</h3>
              {catalog[scope].map((item, index) => (
                <div key={item.id ?? `${scope}-${index}`} className="flex items-center gap-1">
                  <input
                    value={item.name}
                    disabled={viewMode}
                    onChange={(e) =>
                      setCatalog((current) => ({
                        ...current,
                        [scope]: current[scope].map((row, i) =>
                          i === index ? { ...row, name: e.target.value } : row,
                        ),
                      }))
                    }
                    className="min-w-0 flex-1 rounded border border-osap-border bg-osap-surface px-2 py-1 text-sm disabled:opacity-60"
                  />
                  {viewMode ? null : (
                    <button
                      type="button"
                      title="Quitar"
                      onClick={() =>
                        setCatalog((current) => ({
                          ...current,
                          [scope]: current[scope].filter((_, i) => i !== index),
                        }))
                      }
                      className="rounded border border-osap-border px-2 py-1 text-xs text-osap-danger"
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
              {viewMode ? null : (
                <button
                  type="button"
                  onClick={() =>
                    setCatalog((current) => ({
                      ...current,
                      [scope]: [
                        ...current[scope],
                        { scope, name: "Nuevo", code: null, parent_id: null },
                      ],
                    }))
                  }
                  className="rounded border border-osap-border px-2 py-1 text-xs text-osap-accent"
                >
                  + Añadir
                </button>
              )}
            </div>
          ))}
        </div>
        {viewMode ? null : (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={saveCatalog}
              className="rounded-md bg-osap-accent px-4 py-2 text-sm font-medium text-white"
            >
              Guardar cargos
            </button>
            {catalogMessage ? <span className="text-sm text-osap-muted">{catalogMessage}</span> : null}
          </div>
        )}
      </Card>

      <Card title="Historial de altas y bajas">
        {history.length === 0 ? (
          <p className="text-sm text-osap-muted">
            Sin entradas todavía. Se registran al dar de alta o de baja a un componente.
          </p>
        ) : (
          <ul className="divide-y divide-osap-border text-sm">
            {history.map((item) => (
              <li key={item.id} className="flex flex-wrap justify-between gap-2 py-2">
                <span>
                  {item.event_type === "director_join" ? "Alta de dirección" : "Alta de componente"}
                  {item.role === "admin" ? " (dirección)" : ""}
                </span>
                <span className="text-osap-muted">
                  {formatEuroDate(item.start_date) || "—"} → {item.end_date ? formatEuroDate(item.end_date) : "actualidad"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Solicitudes pendientes">
        {requests.length === 0 ? (
          <p className="text-sm text-osap-muted">No hay solicitudes pendientes.</p>
        ) : (
          <ul className="divide-y divide-osap-border text-sm">
            {requests.map((request) => (
              <li key={request.user_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className="text-xs">{request.user_id}</span>
                <span className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => void guard(async () => {
                      await apiClient.grantAmigosMember(groupId, request.user_id, "collaborator", {
                        admin_role_id: request.admin_role_id,
                        musical_role_id: request.musical_role_id,
                        section_id: request.section_id,
                      });
                      await load();
                    })}
                    className="rounded bg-osap-accent px-2 py-1 text-xs text-white"
                  >
                    Aprobar
                  </button>
                  <button
                    type="button"
                    onClick={() => void revokeMember(request.user_id)}
                    className="rounded border border-osap-border px-2 py-1 text-xs"
                  >
                    Rechazar
                  </button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title={t("friends.members")}>
        {viewMode ? null : (
          <div className="flex flex-wrap gap-2">
            <input
              list="amigos-users"
              value={newUserId}
              onChange={(e) => setNewUserId(e.target.value)}
              placeholder={usersUnavailable ? t("friends.userId") : t("friends.emailOrUser")}
              className="min-w-64 flex-1 rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
            />
            {usersUnavailable ? null : (
              <datalist id="amigos-users">
                {users
                  .filter(
                    (u) =>
                      !members.some((m) => m.user_id === u.user_id && m.status === "active"),
                  )
                  .map((u) => (
                    <option key={u.user_id} value={u.email}>
                      {u.name ?? ""}
                      {u.nickname ? ` (${u.nickname})` : ""}
                    </option>
                  ))}
              </datalist>
            )}
            <select
              value={newRole}
              onChange={(e) => setNewRole(e.target.value === "admin" ? "admin" : "collaborator")}
              className="rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm"
            >
              <option value="collaborator">{t("friends.roleCollaborator")}</option>
              <option value="admin">{t("friends.roleAdmin")}</option>
            </select>
            <select value={newAdminRole} onChange={(e) => setNewAdminRole(e.target.value)} className="rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm">
              <option value="">Cargo administrativo</option>
              {catalog.admin.map((item) => <option key={item.id ?? item.name} value={item.id ?? ""}>{item.name}</option>)}
            </select>
            <select value={newMusicalRole} onChange={(e) => setNewMusicalRole(e.target.value)} className="rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm">
              <option value="">Rol musical</option>
              {catalog.musical.map((item) => <option key={item.id ?? item.name} value={item.id ?? ""}>{item.name}</option>)}
            </select>
            <select value={newSection} onChange={(e) => setNewSection(e.target.value)} className="rounded-md border border-osap-border bg-osap-surface px-3 py-2 text-sm">
              <option value="">Sección</option>
              {catalog.section.map((item) => <option key={item.id ?? item.name} value={item.id ?? ""}>{item.name}</option>)}
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
              <span className="min-w-0 truncate text-xs" title={m.user_id}>
                {userLabel(m.user_id)}
              </span>
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
                  <span className="text-osap-muted">{formatEuroDate(a.event_date)}</span>
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











