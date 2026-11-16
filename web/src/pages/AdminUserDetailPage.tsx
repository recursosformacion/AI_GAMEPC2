// Detalle/edición de usuario (admin). La identidad vive en osap-auth; osap-api reenvía.
// Modo "view": solo lectura con todos los datos. Modo "edit": nombre, roles y estado.

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { AmigosGroup, AmigosGroupCatalog } from "../api/types";
import { Button } from "../components/Button";
import { useI18n } from "../i18n/I18n";
import type { AdminUser } from "./AdminUsersPage";

const ALL_ROLES = ["user", "moderator", "admin"];
const NEWS_LANGUAGES = [
  ["es", "Español"],
  ["ca", "Català"],
  ["fr", "Français"],
  ["en", "English"],
  ["de", "Deutsch"],
] as const;
const NEWS_TOPICS = [
  ["coral", "Música coral y vocal"],
  ["clasica", "Música clásica"],
  ["antigua", "Música antigua"],
  ["opera", "Ópera"],
  ["instrumentos", "Instrumentos y técnica"],
  ["educacion", "Educación y formación"],
  ["patrimonio", "Partituras y patrimonio"],
  ["concursos", "Concursos y convocatorias"],
  ["industria", "Industria y tecnología"],
] as const;

const STATUSES = ["active", "pending_verification", "disabled"];

interface AdminRecognition {
  id: number;
  type: string;
  status: string;
}

// Solo supporter NO se concede manualmente (deriva de una transacción económica); el resto
// (contributor, voice, founder) los otorga el admin. Todos se pueden revocar si están activos.
const RECOGNITION_TYPES = [
  { type: "supporter", icon: "❤️", grantable: false },
  { type: "contributor", icon: "🎼", grantable: true },
  { type: "voice", icon: "📣", grantable: true },
  { type: "founder", icon: "🏛️", grantable: true },
] as const;

export function AdminUserDetailPage() {
  const { t } = useI18n();
  const { userId = "" } = useParams<{ userId: string }>();
  const [params] = useSearchParams();
  const editing = params.get("mode") === "edit";
  const [user, setUser] = useState<AdminUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [nickname, setNickname] = useState("");
  const [phone, setPhone] = useState("");
  const [roles, setRoles] = useState<string[]>([]);
  const [status, setStatus] = useState("");
  const [publicConsent, setPublicConsent] = useState(false);
  const [newsOptIn, setNewsOptIn] = useState(false);
  const [newsLanguage, setNewsLanguage] = useState("es");
  const [newsLanguages, setNewsLanguages] = useState<string[]>(["es"]);
  const [newsTopics, setNewsTopics] = useState<string[]>([]);
  const [savingConsent, setSavingConsent] = useState(false);
  const [recognitions, setRecognitions] = useState<AdminRecognition[]>([]);
  const [savingRec, setSavingRec] = useState(false);
  const [savingEntity, setSavingEntity] = useState(false);
  const [entityError, setEntityError] = useState<string | null>(null);
  const [amigosGroups, setAmigosGroups] = useState<AmigosGroup[]>([]);
  const [friendsGroups, setFriendsGroups] = useState<Array<{ group_id: string; name: string; kind: string; role: string; status: string }>>([]);
  const [friendsGroupId, setFriendsGroupId] = useState("");
  const [friendsRole, setFriendsRole] = useState<"collaborator" | "admin">("collaborator");
  const [friendCatalog, setFriendCatalog] = useState<AmigosGroupCatalog>({ admin: [], musical: [], section: [] });
  const [friendAdminRole, setFriendAdminRole] = useState("");
  const [friendMusicalRole, setFriendMusicalRole] = useState("");
  const [friendSection, setFriendSection] = useState("");
  const user_id = userId;

  const loadRecognitions = (id: string) => {
    void apiClient
      .get<AdminRecognition[]>(`/admin/users/${encodeURIComponent(id)}/recognitions`)
      .then(setRecognitions)
      .catch(() => setRecognitions([]));
  };

  useEffect(() => {
    if (!user_id) return;
    void apiClient
      .get<AdminUser>(`/admin/users/${encodeURIComponent(user_id)}`)
      .then((data) => {
        setUser(data);
        setName(data.name ?? "");
        setNickname(data.nickname ?? "");
        setPhone(data.phone ?? "");
        setRoles(data.roles ?? []);
        setStatus(data.status ?? "");
        setPublicConsent(Boolean(data.nickname_public_consent));
        setNewsOptIn(Boolean(data.news_opt_in));
        setNewsLanguage(data.news_language ?? "es");
        setNewsLanguages(data.news_languages?.length ? data.news_languages : [data.news_language ?? "es"]);
        setNewsTopics(data.news_topics ?? []);
        loadRecognitions(user_id);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "admin.error"));
    void apiClient
      .getAmigosGroups(true)
      .then(setAmigosGroups)
      .catch((e) => {
        setAmigosGroups([]);
        setEntityError(e instanceof Error ? e.message : "admin.error");
      });
    void apiClient
      .getAmigosUserGroups(user_id)
      .then(setFriendsGroups)
      .catch((e) => {
        setFriendsGroups([]);
        setEntityError(e instanceof Error ? e.message : "admin.error");
      });
  }, [user_id]);

  const save = () => {
    if (!user_id) return;
    const cleanedPhone = phone.replace(/[\s().\-/]/g, "");
    if (cleanedPhone && !/^\+?[0-9]{7,15}$/.test(cleanedPhone)) {
      setError("Teléfono inválido: usa 7-15 dígitos con + opcional.");
      return;
    }
    setSaving(true);
    setError(null);
    void apiClient
      .patch(`/admin/users/${encodeURIComponent(user_id)}`, {
        name: name || null,
        nickname: nickname.trim() || null,
        phone: phone.trim(),
        roles,
        status,
        news_opt_in: newsOptIn,
        news_language: newsLanguages[0] ?? newsLanguage,
        news_languages: newsLanguages.length ? newsLanguages : [newsLanguage],
        news_topics: newsTopics,
      })
      .then(() => {
        window.location.href = "/admin/users";
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "admin.error");
        setSaving(false);
      });
  };

  useEffect(() => {
    if (!friendsGroupId) return;
    void apiClient
      .getAmigosGroupCatalog(friendsGroupId)
      .then(setFriendCatalog)
      .catch(() => setFriendCatalog({ admin: [], musical: [], section: [] }));
  }, [friendsGroupId]);

  const addFriendGroup = () => {
    if (!user_id || !friendsGroupId) return;
    setSavingEntity(true);
    setEntityError(null);
    void apiClient
      .grantAmigosMember(friendsGroupId, user_id, friendsRole, {
        admin_role_id: friendAdminRole || null,
        musical_role_id: friendMusicalRole || null,
        section_id: friendSection || null,
      })
      .then(() => apiClient.getAmigosUserGroups(user_id))
      .then((rows) => {
        setFriendsGroups(rows);
        setFriendsGroupId("");
      })
      .catch((e) => setEntityError(e instanceof Error ? e.message : "admin.error"))
      .finally(() => setSavingEntity(false));
  };

  const setConsent = (value: boolean) => {
    if (!user_id) return;
    setSavingConsent(true);
    setError(null);
    void apiClient
      .put<AdminUser>(`/admin/users/${encodeURIComponent(user_id)}/public-consent`, { value })
      .then((data) => {
        setUser(data);
        setPublicConsent(Boolean(data.nickname_public_consent));
        setSavingConsent(false);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "admin.error");
        setSavingConsent(false);
      });
  };

  const activeRecognition = (type: string) =>
    recognitions.find((r) => r.type === type && r.status === "active");
  // Conceder/revocar reconocimiento: operación INDEPENDIENTE (osap-support, auditada aparte).
  const toggleRecognition = (type: string) => {
    if (!user_id) return;
    const active = activeRecognition(type);
    setSavingRec(true);
    setError(null);
    const request = active
      ? apiClient.post(`/admin/users/${encodeURIComponent(user_id)}/recognitions/${active.id}/revoke`, {})
      : apiClient.post(`/admin/users/${encodeURIComponent(user_id)}/recognitions`, {
          project: "omr",
          type,
        });
    void request
      .then(() => loadRecognitions(user_id))
      .catch((e) => setError(e instanceof Error ? e.message : "admin.error"))
      .finally(() => setSavingRec(false));
  };

  if (error) {
    return (
      <div className="mx-auto max-w-2xl">
        <p className="text-sm text-red-500">{error}</p>
        <Link to="/admin/users" className="text-sm text-osap-accent hover:underline">
          {t("adminUsers.back")}
        </Link>
      </div>
    );
  }
  if (!user) {
    return <p className="text-sm text-osap-muted">…</p>;
  }

  const Field = ({ label, children }: { label: string; children: ReactNode }) => (
    <div className="sm:grid sm:grid-cols-3 sm:gap-3">
      <dt className="text-sm text-osap-muted">{label}</dt>
      <dd className="text-sm sm:col-span-2">{children}</dd>
    </div>
  );

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">
          {editing ? t("adminUsers.edit") : t("adminUsers.view")} · {user.name ?? user.email}
        </h1>
        <Link to="/admin/users" className="text-sm text-osap-accent hover:underline">
          {t("adminUsers.back")}
        </Link>
      </div>

      {!editing ? (
        <dl className="space-y-2 rounded border border-osap-border bg-osap-surface p-4">
          <Field label={t("adminUsers.name")}>{user.name ?? "—"}</Field>
          <Field label={t("adminUsers.nickname")}>{user.nickname ?? "—"}</Field>
          <Field label="Teléfono">{user.phone ?? "—"}</Field>
          <Field label={t("adminUsers.email")}>{user.email}</Field>
          <Field label={t("adminUsers.roles")}>{user.roles.join(", ")}</Field>
          <Field label={t("adminUsers.status")}>{user.status}</Field>
          <Field label={t("adminUsers.publicTitle")}>
            {publicConsent ? t("adminUsers.publicOn") : t("adminUsers.publicOff")}
          </Field>
          <Field label={t("adminUsers.emailVerified")}>{String(user.email_verified)}</Field>
          <Field label={t("adminUsers.createdAt")}>{user.created_at ?? "—"}</Field>
          <Link to={`/admin/users/${encodeURIComponent(user.user_id)}?mode=edit`}>
            <Button>{t("adminUsers.edit")}</Button>
          </Link>
        </dl>
      ) : (
        <div className="space-y-4 rounded border border-osap-border bg-osap-surface p-4">
          <div className="grid gap-3">
            <label className="text-sm font-medium">{t("adminUsers.name")}</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="rounded border border-osap-border bg-osap-bg px-3 py-2"
            />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <label className="text-sm font-medium" htmlFor="admin-nickname">
              {t("adminUsers.nickname")}
            </label>
            <input
              id="admin-nickname"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              placeholder="3–30, empieza por letra"
              className="rounded border border-osap-border bg-osap-bg px-3 py-2"
            />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium" htmlFor="admin-phone">
              Teléfono
            </label>
            <input
              id="admin-phone"
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+34 600 123 456"
              maxLength={32}
              className="rounded border border-osap-border bg-osap-bg px-3 py-2"
            />
          </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm font-medium">{t("adminUsers.roles")}</span>
            {ALL_ROLES.map((role) => (
              <label key={role} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={roles.includes(role)}
                  onChange={(e) =>
                    setRoles((prev) =>
                      e.target.checked ? [...prev, role] : prev.filter((r) => r !== role),
                    )
                  }
                />
                {role}
              </label>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-sm font-medium">{t("adminUsers.status")}</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="rounded border border-osap-border bg-osap-bg px-3 py-2"
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm font-medium">{t("adminUsers.publicTitle")}</span>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={publicConsent}
                disabled={savingConsent}
                onChange={(e) => setConsent(e.target.checked)}
              />
              {t("adminUsers.publicOn")}
            </label>
          </div>
          <fieldset className="space-y-3 rounded border border-osap-border bg-osap-surface p-4">
            <legend className="px-1 text-sm font-medium">Noticias</legend>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={newsOptIn}
                onChange={(e) => setNewsOptIn(e.target.checked)}
              />
              Quiere recibir noticias
            </label>
            {newsOptIn ? (
              <>
                <div>
                  <p className="text-sm">Idiomas</p>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {NEWS_LANGUAGES.map(([value, label]) => (
                      <label key={value} className="flex items-center gap-1 rounded border border-osap-border px-2 py-1 text-xs">
                        <input
                          type="checkbox"
                          checked={newsLanguages.includes(value)}
                          onChange={(e) =>
                            setNewsLanguages(
                              e.target.checked
                                ? [...newsLanguages, value]
                                : newsLanguages.filter((language) => language !== value),
                            )
                          }
                        />
                        {label}
                      </label>
                    ))}
                    <button
                      type="button"
                      className="rounded bg-osap-accent px-3 py-1 text-xs font-medium text-white hover:bg-osap-accent/90"
                      onClick={() => setNewsLanguages(NEWS_LANGUAGES.map(([value]) => value))}
                    >
                      Todos
                    </button>
                  </div>
                </div>
                <div>
                  <p className="text-sm">Temas</p>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {NEWS_TOPICS.map(([code, label]) => (
                      <label key={code} className="flex items-center gap-1 rounded border border-osap-border px-2 py-1 text-xs">
                        <input
                          type="checkbox"
                          checked={newsTopics.includes(code)}
                          onChange={(e) =>
                            setNewsTopics(
                              e.target.checked
                                ? [...newsTopics, code]
                                : newsTopics.filter((topic) => topic !== code),
                            )
                          }
                        />
                        {label}
                      </label>
                    ))}
                    <button
                      type="button"
                      className="rounded bg-osap-accent px-3 py-1 text-xs font-medium text-white hover:bg-osap-accent/90"
                      onClick={() => setNewsTopics(NEWS_TOPICS.map(([code]) => code))}
                    >
                      Marcar todos los temas
                    </button>
                  </div>
                </div>
              </>
            ) : null}
          </fieldset>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex gap-2">
            <Button onClick={save} disabled={saving}>
              {saving ? "…" : t("adminUsers.save")}
            </Button>
            <Link to="/admin/users">{t("adminUsers.cancel")}</Link>
          </div>
        </div>
      )}

      <fieldset className="space-y-3 rounded border border-osap-border bg-osap-surface p-4">
        <legend className="px-1 text-sm font-medium">Grupos de Amigos</legend>
        {friendsGroups.filter((item) => item.status === "active").length > 0 ? (
          <ul className="space-y-1 text-sm">
            {friendsGroups.filter((item) => item.status === "active").map((item) => (
              <li key={item.group_id}>
                <a
                  href={`/admin/amigos/${encodeURIComponent(item.group_id)}?mode=edit`}
                  className="text-osap-accent hover:underline"
                >
                  {item.name}
                </a>{" "}
                <span className="text-osap-muted">
                  ({item.kind}) · {item.role === "admin" ? "administrador" : "colaborador"} ·{" "}
                  {item.status}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-osap-muted">Sin grupos de Amigos.</p>
        )}
        <div className="flex flex-wrap items-end gap-2 border-t border-osap-border pt-3">
          <label className="text-sm">
            Añadir a grupo
            <select
              className="mt-1 block w-64 max-w-full rounded border border-osap-border bg-osap-surface px-2 py-1"
              value={friendsGroupId}
              onChange={(e) => setFriendsGroupId(e.target.value)}
            >
              <option value="">— Elegir grupo —</option>
              {amigosGroups
                .filter((group) => !friendsGroups.some((item) => item.group_id === group.id && item.status === "active"))
                .map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name} ({group.kind})
                  </option>
                ))}
            </select>
          </label>
          <label className="text-sm">
            Rol
            <select
              className="mt-1 block rounded border border-osap-border bg-osap-surface px-2 py-1"
              value={friendsRole}
              onChange={(e) =>
                setFriendsRole(e.target.value === "admin" ? "admin" : "collaborator")
              }
            >
              <option value="collaborator">Colaborador</option>
              <option value="admin">Administrador</option>
            </select>
          </label>
          <select value={friendAdminRole} onChange={(e) => setFriendAdminRole(e.target.value)} className="mt-1 block rounded border border-osap-border bg-osap-surface px-2 py-1 text-sm">
            <option value="">Cargo administrativo</option>
            {friendCatalog.admin.map((item) => <option key={item.id ?? item.name} value={item.id ?? ""}>{item.name}</option>)}
          </select>
          <select value={friendMusicalRole} onChange={(e) => setFriendMusicalRole(e.target.value)} className="mt-1 block rounded border border-osap-border bg-osap-surface px-2 py-1 text-sm">
            <option value="">Rol musical</option>
            {friendCatalog.musical.map((item) => <option key={item.id ?? item.name} value={item.id ?? ""}>{item.name}</option>)}
          </select>
          <select value={friendSection} onChange={(e) => setFriendSection(e.target.value)} className="mt-1 block rounded border border-osap-border bg-osap-surface px-2 py-1 text-sm">
            <option value="">Sección</option>
            {friendCatalog.section.map((item) => <option key={item.id ?? item.name} value={item.id ?? ""}>{item.name}</option>)}
          </select>
          <Button disabled={!friendsGroupId || savingEntity} onClick={addFriendGroup}>
            Añadir
          </Button>
        </div>
        {entityError && <p className="text-sm text-red-500">{entityError}</p>}
      </fieldset>

      <fieldset className="space-y-3 rounded border border-osap-border bg-osap-surface p-4">
        <legend className="px-1 text-sm font-medium">{t("adminUsers.recognitions")}</legend>
        <p className="text-xs text-osap-muted">
          Conceder o revocar reconocimientos (osap-support). Solo supporter no se concede
          manualmente (deriva de una transacción económica); el resto sí.
        </p>
        <div className="flex flex-wrap gap-3">
          {RECOGNITION_TYPES.map(({ type, icon, grantable }) => {
            const active = Boolean(activeRecognition(type));
            const disabled = savingRec || (!active && !grantable);
            return (
              <label
                key={type}
                className={`flex items-center gap-1 text-sm ${disabled ? "opacity-50" : ""}`}
                title={!active && !grantable ? "Supporter no se concede manualmente (transacción económica)" : undefined}
              >
                <input
                  type="checkbox"
                  checked={active}
                  disabled={disabled}
                  onChange={() => toggleRecognition(type)}
                />
                <span aria-hidden="true">{icon}</span>
                {type}
              </label>
            );
          })}
        </div>
      </fieldset>
    </div>
  );
}


