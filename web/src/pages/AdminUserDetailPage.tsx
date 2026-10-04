// Detalle/edición de usuario (admin). La identidad vive en osap-auth; osap-api reenvía.
// Modo "view": solo lectura con todos los datos. Modo "edit": nombre, roles y estado.

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import { Button } from "../components/Button";
import { useI18n } from "../i18n/I18n";
import type { AdminUser } from "./AdminUsersPage";

const ALL_ROLES = ["user", "moderator", "admin"];
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
  const [roles, setRoles] = useState<string[]>([]);
  const [status, setStatus] = useState("");
  const [publicConsent, setPublicConsent] = useState(false);
  const [savingConsent, setSavingConsent] = useState(false);
  const [recognitions, setRecognitions] = useState<AdminRecognition[]>([]);
  const [savingRec, setSavingRec] = useState(false);
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
        setRoles(data.roles ?? []);
        setStatus(data.status ?? "");
        setPublicConsent(Boolean(data.nickname_public_consent));
        loadRecognitions(user_id);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "admin.error"));
  }, [user_id]);

  const save = () => {
    if (!user_id) return;
    setSaving(true);
    setError(null);
    void apiClient
      .patch(`/admin/users/${encodeURIComponent(user_id)}`, {
        name: name || null,
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

  // Autorización pública del nickname: operación INDEPENDIENTE (auditada por separado).
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
            <span className="text-sm font-medium">{t("adminUsers.nickname")}</span>
            <p className="text-sm text-osap-muted">{user.nickname ?? "—"}</p>
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
