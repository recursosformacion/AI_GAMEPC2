// Detalle/edición de usuario (admin). La identidad vive en osap-auth; osap-api reenvía.
// Modo "view": solo lectura con todos los datos. Modo "edit": nombre, roles y estado.

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import type { AdminEntity } from "../api/types";
import { Button } from "../components/Button";
import { useI18n } from "../i18n/I18n";
import type { AdminUser } from "./AdminUsersPage";

const ALL_ROLES = ["user", "moderator", "admin"];
const STATUSES = ["active", "pending_verification", "disabled"];
const MEMBERSHIP_STATUS: Record<string, string> = {
  pending: "pendiente",
  approved: "aprobada",
  rejected: "rechazada",
};

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
  const [savingConsent, setSavingConsent] = useState(false);
  const [recognitions, setRecognitions] = useState<AdminRecognition[]>([]);
  const [savingRec, setSavingRec] = useState(false);
  const [entities, setEntities] = useState<AdminEntity[]>([]);
  const [entityId, setEntityId] = useState("");
  const [entityRepresentative, setEntityRepresentative] = useState(false);
  const [savingEntity, setSavingEntity] = useState(false);
  const [entityError, setEntityError] = useState<string | null>(null);
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
        loadRecognitions(user_id);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "admin.error"));
    void apiClient
      .get<AdminEntity[]>("/admin/entities")
      .then(setEntities)
      .catch(() => setEntities([]));
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
      })
      .then(() => {
        window.location.href = "/admin/users";
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "admin.error");
        setSaving(false);
      });
  };

  // Entidades: alta/baja de pertenencia, decisión y representación (admin).
  const addMembership = () => {
    if (!user_id || !entityId) return;
    setSavingEntity(true);
    setEntityError(null);
    void apiClient
      .post<AdminUser>(`/admin/users/${encodeURIComponent(user_id)}/memberships`, {
        entity_id: entityId,
        status: "approved",
        representative: entityRepresentative,
      })
      .then((data) => {
        setUser(data);
        setEntityId("");
        setEntityRepresentative(false);
        setSavingEntity(false);
      })
      .catch((e) => {
        setEntityError(e instanceof Error ? e.message : "admin.error");
        setSavingEntity(false);
      });
  };

  const decideMembership = (membershipId: string, action: "approve" | "reject") => {
    if (!user_id) return;
    setSavingEntity(true);
    setEntityError(null);
    void apiClient
      .post<AdminUser>(
        `/admin/users/${encodeURIComponent(user_id)}/memberships/${encodeURIComponent(membershipId)}/decision`,
        { action },
      )
      .then((data) => {
        setUser(data);
        setSavingEntity(false);
      })
      .catch((e) => {
        setEntityError(e instanceof Error ? e.message : "admin.error");
        setSavingEntity(false);
      });
  };

  const removeMembership = (membershipId: string) => {
    if (!user_id) return;
    setSavingEntity(true);
    setEntityError(null);
    void apiClient
      .delete<AdminUser>(
        `/admin/users/${encodeURIComponent(user_id)}/memberships/${encodeURIComponent(membershipId)}`,
      )
      .then((data) => {
        setUser(data);
        setSavingEntity(false);
      })
      .catch((e) => {
        setEntityError(e instanceof Error ? e.message : "admin.error");
        setSavingEntity(false);
      });
  };

  const makeRepresentative = (membershipEntityId: string) => {
    if (!user_id) return;
    setSavingEntity(true);
    setEntityError(null);
    void apiClient
      .post<AdminUser>(
        `/admin/entities/${encodeURIComponent(membershipEntityId)}/representative`,
        { user_id },
      )
      .then((data) => {
        setUser(data);
        setSavingEntity(false);
      })
      .catch((e) => {
        setEntityError(e instanceof Error ? e.message : "admin.error");
        setSavingEntity(false);
      });
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
          <div className="grid gap-2">
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
          <div className="grid gap-2">
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
          <div className="grid gap-2">
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
        <legend className="px-1 text-sm font-medium">Entidades</legend>
        {user.memberships && user.memberships.length > 0 ? (
          <ul className="space-y-2 text-sm">
            {user.memberships.map((membership) => (
              <li
                key={membership.id}
                className="flex flex-wrap items-center gap-2 border-b border-osap-border pb-2 last:border-0"
              >
                <div className="min-w-0 flex-1">
                  <strong>{membership.entity_name}</strong> ({membership.entity_kind}) —{" "}
                  {MEMBERSHIP_STATUS[membership.status] ?? membership.status}
                  {membership.is_representative ? " · representante" : ""}
                  {membership.entity_email ? (
                    <span className="text-xs text-osap-muted"> · {membership.entity_email}</span>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-1">
                  {membership.status === "pending" ? (
                    <>
                      <Button
                        disabled={savingEntity}
                        onClick={() => decideMembership(membership.id, "approve")}
                      >
                        Aprobar
                      </Button>
                      <Button
                        disabled={savingEntity}
                        onClick={() => decideMembership(membership.id, "reject")}
                      >
                        Rechazar
                      </Button>
                    </>
                  ) : null}
                  {!membership.is_representative ? (
                    <Button
                      disabled={savingEntity}
                      onClick={() => makeRepresentative(membership.entity_id)}
                    >
                      Hacer representante
                    </Button>
                  ) : null}
                  <Button
                    disabled={savingEntity}
                    onClick={() => removeMembership(membership.id)}
                  >
                    Quitar
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-osap-muted">Sin entidades.</p>
        )}
        <div className="flex flex-wrap items-end gap-2 border-t border-osap-border pt-3">
          <label className="text-sm">
            Añadir a entidad
            <select
              className="mt-1 block w-64 max-w-full rounded border border-osap-border bg-osap-surface px-2 py-1"
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
            >
              <option value="">— Elegir entidad —</option>
              {entities
                .filter(
                  (entity) =>
                    !(user.memberships ?? []).some((m) => m.entity_id === entity.id),
                )
                .map((entity) => (
                  <option key={entity.id} value={entity.id}>
                    {entity.name} ({entity.kind})
                  </option>
                ))}
            </select>
          </label>
          <label className="flex items-center gap-1 pb-1 text-sm">
            <input
              type="checkbox"
              checked={entityRepresentative}
              onChange={(e) => setEntityRepresentative(e.target.checked)}
            />
            Representante
          </label>
          <Button disabled={!entityId || savingEntity} onClick={addMembership}>
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

