// Listado de usuarios (admin). La identidad vive en osap-auth; osap-api reenvía la petición
// con el token admin. La gestión fina (rol, nickname, visibilidad, reconocimientos, baja)
// vive en el detalle; aquí el listado es compacto: estado on/off, iconos de acción y columnas
// de rol más alto + visibilidad.

import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import { useI18n } from "../i18n/I18n";

export interface AdminUser {
  user_id: string;
  email: string;
  name: string | null;
  nickname?: string | null;
  roles: string[];
  email_verified: boolean;
  status: string;
  created_at?: string | null;
  nickname_public_consent?: boolean;
}

const ROLE_RANK: Record<string, number> = { admin: 3, moderator: 2, user: 1 };
const ROLE_LABEL: Record<string, string> = { admin: "Admin", moderator: "Moderador", user: "Usuario" };

function highestRole(roles: string[]): string {
  return roles.slice().sort((a, b) => (ROLE_RANK[b] ?? 0) - (ROLE_RANK[a] ?? 0))[0] ?? "user";
}

function Icon({ children, title }: { children: ReactNode; title: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
      role="img"
      aria-label={title}
    >
      {children}
    </svg>
  );
}

export function AdminUsersPage() {
  const { t } = useI18n();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showDisabled, setShowDisabled] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = () => {
    setError(null);
    void apiClient
      .get<AdminUser[]>("/admin/users")
      .then((data) => setUsers(data))
      .catch((e) => setError(e instanceof Error ? e.message : "admin.error"));
  };

  useEffect(load, []);

  const isActive = (user: AdminUser) => user.status === "active";
  // Por defecto se ocultan los deshabilitados/eliminados (soft delete); el toggle permite
  // verlos para reactivar o auditar.
  const visibleUsers = showDisabled
    ? users
    : users.filter((u) => u.status === "active" || u.status === "pending_verification");

  const deleteUser = (user: AdminUser) => {
    if (!window.confirm(t("adminUsers.confirmDelete"))) return;
    setBusyId(user.user_id);
    void apiClient
      .delete(`/admin/users/${encodeURIComponent(user.user_id)}`)
      .then(load)
      .catch((e) => setError(e instanceof Error ? e.message : "admin.error"))
      .finally(() => setBusyId(null));
  };

  // Interruptor de estado on/off: activa/desactiva la cuenta (no para pendientes de verificar).
  const toggleStatus = (user: AdminUser) => {
    if (user.status === "pending_verification") return;
    const next = isActive(user) ? "disabled" : "active";
    setBusyId(user.user_id);
    void apiClient
      .patch(`/admin/users/${encodeURIComponent(user.user_id)}`, { status: next })
      .then(load)
      .catch((e) => setError(e instanceof Error ? e.message : "admin.error"))
      .finally(() => setBusyId(null));
  };

  const StatusToggle = ({ user }: { user: AdminUser }) => {
    if (user.status === "pending_verification") {
      return (
        <button
          type="button"
          disabled
          title="Pendiente de verificar el email"
          className="text-amber-500"
        >
          <Icon title="Pendiente">
            <circle cx="12" cy="12" r="9" />
            <path d="M12 7v5l3 2" />
          </Icon>
        </button>
      );
    }
    const active = isActive(user);
    return (
      <button
        type="button"
        disabled={busyId === user.user_id}
        onClick={() => toggleStatus(user)}
        title={active ? "Activo (clic para desactivar)" : "Inactivo (clic para activar)"}
        className={active ? "text-emerald-600" : "text-osap-muted"}
      >
        <Icon title={active ? "Activo" : "Inactivo"}>
          {active ? (
            <>
              <circle cx="12" cy="12" r="9" />
              <path d="M8 12l3 3 5-6" />
            </>
          ) : (
            <>
              <circle cx="12" cy="12" r="9" />
              <path d="M9 12h6" />
            </>
          )}
        </Icon>
      </button>
    );
  };

  const iconBtn = "rounded p-1.5 hover:bg-osap-surface";

  return (
    <div className="mx-auto max-w-5xl">
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
              <th className="px-3 py-2">Rol</th>
              <th className="px-3 py-2 text-center">{t("adminUsers.status")}</th>
              <th className="px-3 py-2 text-center">Visibilidad</th>
              <th className="px-3 py-2 text-right">{t("adminUsers.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {visibleUsers.map((user) => (
              <tr key={user.user_id} className="border-b border-osap-border last:border-0">
                <td className="px-3 py-2">
                  {user.name ?? "—"}
                  {user.nickname ? (
                    <span className="ml-2 text-xs text-osap-muted">@{user.nickname}</span>
                  ) : null}
                </td>
                <td className="px-3 py-2">{user.email}</td>
                <td className="px-3 py-2">
                  <span className="rounded bg-osap-accent-soft px-2 py-0.5 text-xs">
                    {ROLE_LABEL[highestRole(user.roles)] ?? highestRole(user.roles)}
                  </span>
                </td>
                <td className="px-3 py-2 text-center">
                  <div className="flex justify-center">
                    <StatusToggle user={user} />
                  </div>
                </td>
                <td className="px-3 py-2 text-center">
                  <span
                    title={
                      user.nickname_public_consent ? "Nickname público" : "Nickname privado"
                    }
                    className={
                      user.nickname_public_consent ? "text-emerald-600" : "text-osap-muted"
                    }
                  >
                    <Icon title="Visibilidad">
                      {user.nickname_public_consent ? (
                        <>
                          <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z" />
                          <circle cx="12" cy="12" r="3" />
                        </>
                      ) : (
                        <>
                          <path d="M3 3l18 18" />
                          <path d="M10.6 5.2A11 11 0 0 1 12 5c7 0 11 7 11 7a18 18 0 0 1-3.2 4" />
                          <path d="M6.6 6.6A18 18 0 0 0 1 12s4 7 11 7a11 11 0 0 0 4.4-.9" />
                        </>
                      )}
                    </Icon>
                  </span>
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center justify-end gap-1 text-osap-accent">
                    <Link
                      to={`/admin/users/${encodeURIComponent(user.user_id)}?mode=view`}
                      title={t("adminUsers.view")}
                      className={iconBtn}
                    >
                      <Icon title={t("adminUsers.view")}>
                        <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z" />
                        <circle cx="12" cy="12" r="3" />
                      </Icon>
                    </Link>
                    <Link
                      to={`/admin/users/${encodeURIComponent(user.user_id)}?mode=edit`}
                      title={t("adminUsers.edit")}
                      className={iconBtn}
                    >
                      <Icon title={t("adminUsers.edit")}>
                        <path d="M12 20h9" />
                        <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" />
                      </Icon>
                    </Link>
                    <Link
                      to={`/admin/users/${encodeURIComponent(user.user_id)}?mode=view`}
                      title="Reconocimientos"
                      className={iconBtn}
                    >
                      <Icon title="Reconocimientos">
                        <circle cx="12" cy="8" r="5" />
                        <path d="M8.5 12.5L7 22l5-3 5 3-1.5-9.5" />
                      </Icon>
                    </Link>
                    <button
                      type="button"
                      onClick={() => deleteUser(user)}
                      disabled={busyId === user.user_id}
                      title={t("adminUsers.delete")}
                      className={`${iconBtn} text-red-500`}
                    >
                      <Icon title={t("adminUsers.delete")}>
                        <path d="M3 6h18" />
                        <path d="M8 6V4h8v2" />
                        <path d="M19 6l-1 14H6L5 6" />
                        <path d="M10 11v6M14 11v6" />
                      </Icon>
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {visibleUsers.length === 0 && !error && (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-center text-osap-muted">
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
