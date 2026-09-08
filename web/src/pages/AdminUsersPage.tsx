// Listado de usuarios (admin). La identidad vive en osap-auth; osap-api reenvía la
// petición con el token admin. Acciones: ver, editar y deshabilitar (soft delete).

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import { useI18n } from "../i18n/I18n";

export interface AdminUser {
  user_id: string;
  email: string;
  name: string | null;
  roles: string[];
  email_verified: boolean;
  status: string;
  created_at?: string | null;
}

export function AdminUsersPage() {
  const { t } = useI18n();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showDisabled, setShowDisabled] = useState(false);

  const load = () => {
    setError(null);
    void apiClient
      .get<AdminUser[]>("/admin/users")
      .then((data) => setUsers(data))
      .catch((e) => setError(e instanceof Error ? e.message : "admin.error"));
  };

  useEffect(load, []);

  const isActive = (user: AdminUser) => user.status === "active";
  // Por defecto se ocultan los deshabilitados/eliminados (soft delete); el toggle
  // permite verlos para reactivar o auditar.
  const visibleUsers = showDisabled
    ? users
    : users.filter((u) => u.status === "active" || u.status === "pending_verification");

  const disableUser = (user: AdminUser) => {
    if (!window.confirm(t("adminUsers.confirmDisable"))) return;
    void apiClient
      .delete(`/admin/users/${encodeURIComponent(user.user_id)}`)
      .then(load)
      .catch((e) => setError(e instanceof Error ? e.message : "admin.error"));
  };

  const enableUser = (user: AdminUser) => {
    void apiClient
      .patch(`/admin/users/${encodeURIComponent(user.user_id)}`, { status: "active" })
      .then(load)
      .catch((e) => setError(e instanceof Error ? e.message : "admin.error"));
  };

  return (
    <div className="mx-auto max-w-4xl">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">{t("adminUsers.title")}</h1>
        <label className="flex items-center gap-2 text-sm text-osap-muted">
          <input
            type="checkbox"
            checked={showDisabled}
            onChange={(e) => setShowDisabled(e.target.checked)}
          />
          {t("adminUsers.showDisabled")}
        </label>
      </div>
      {error && <p className="mt-2 text-sm text-red-500">{error}</p>}
      <div className="mt-4 overflow-x-auto rounded border border-osap-border bg-osap-surface">
        <table className="w-full text-sm">
          <thead className="border-b border-osap-border text-left">
            <tr>
              <th className="px-3 py-2">{t("adminUsers.name")}</th>
              <th className="px-3 py-2">{t("adminUsers.email")}</th>
              <th className="px-3 py-2">{t("adminUsers.status")}</th>
              <th className="px-3 py-2">{t("adminUsers.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {visibleUsers.map((user) => (
              <tr key={user.user_id} className="border-b border-osap-border last:border-0">
                <td className="px-3 py-2">{user.name ?? "—"}</td>
                <td className="px-3 py-2">{user.email}</td>
                <td className="px-3 py-2">
                  <span
                    className={
                      isActive(user)
                        ? "text-emerald-600"
                        : "rounded bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-600"
                    }
                  >
                    {user.status}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <Link
                    to={`/admin/users/${encodeURIComponent(user.user_id)}?mode=view`}
                    className="mr-3 text-osap-accent hover:underline"
                  >
                    {t("adminUsers.view")}
                  </Link>
                  <Link
                    to={`/admin/users/${encodeURIComponent(user.user_id)}?mode=edit`}
                    className="mr-3 text-osap-accent hover:underline"
                  >
                    {t("adminUsers.edit")}
                  </Link>
                  {isActive(user) ? (
                    <button
                      type="button"
                      onClick={() => disableUser(user)}
                      className="text-red-500 hover:underline"
                    >
                      {t("adminUsers.disable")}
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => enableUser(user)}
                      className="text-emerald-600 hover:underline"
                    >
                      {t("adminUsers.enable")}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {visibleUsers.length === 0 && !error && (
              <tr>
                <td colSpan={4} className="px-3 py-4 text-center text-osap-muted">
                  {t("adminUsers.empty")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
