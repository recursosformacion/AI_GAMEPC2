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
  const user_id = userId;

  useEffect(() => {
    if (!user_id) return;
    void apiClient
      .get<AdminUser>(`/admin/users/${encodeURIComponent(user_id)}`)
      .then((data) => {
        setUser(data);
        setName(data.name ?? "");
        setRoles(data.roles ?? []);
        setStatus(data.status ?? "");
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
          <Field label={t("adminUsers.email")}>{user.email}</Field>
          <Field label={t("adminUsers.roles")}>{user.roles.join(", ")}</Field>
          <Field label={t("adminUsers.status")}>{user.status}</Field>
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
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex gap-2">
            <Button onClick={save} disabled={saving}>
              {saving ? "…" : t("adminUsers.save")}
            </Button>
            <Link to="/admin/users">{t("adminUsers.cancel")}</Link>
          </div>
        </div>
      )}
    </div>
  );
}
