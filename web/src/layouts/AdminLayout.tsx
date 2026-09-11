// Layout de administración a pantalla completa: menú vertical izquierdo permanente
// (solo visible para admins). Los hijos se renderizan en <Outlet/> a ancho completo.

import type { ReactNode } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";
import { useAuth } from "../state/auth";

interface AdminItem {
  to?: string;
  key: TKey;
  end?: boolean;
  action?: "storage-composers" | "storage-works" | "storage-main";
}

interface AdminSection {
  caption?: string;
  items: AdminItem[];
}

const SECTIONS: AdminSection[] = [
  { items: [{ to: "/admin", key: "admin.resumen", end: true }] },
  {
    caption: "Gestión de pagos",
    items: [{ to: "/admin/payments", key: "admin.paymentsTitle" }],
  },
  {
    caption: "Mantenimiento tablas",
    items: [
      { to: "/admin/users", key: "adminUsers.title" },
      { action: "storage-composers", key: "admin.composerMaster" },
      { action: "storage-works", key: "admin.storageWorks" },
      { to: "/admin/providers", key: "admin.providersAdmin" },
    ],
  },
  {
    caption: "Gestión compositores",
    items: [
      { to: "/admin/composers", key: "admin.composersFusion" },
      { to: "/admin/aliases", key: "admin.aliases" },
    ],
  },
  { items: [{ to: "/admin/source-suggestions", key: "admin.sourceSuggestions" }] },
  { items: [{ to: "/admin/corrections", key: "admin.corrections" }] },
  {
    items: [{ action: "storage-main", key: "admin.storageMaint" }],
  },
  { items: [{ to: "/jobs", key: "jobs" }] },
];

export function AdminLayout(): ReactNode {
  const { t } = useI18n();
  const isAdmin = useAuth((s) => s.isAdmin());
  const logout = useAuth((s) => s.logout);
  const navigate = useNavigate();

  const openStorage = (section: string | null) => {
    void (async () => {
      try {
        const r = await apiClient.getStorageWebUrl(section ?? undefined);
        window.open(r.url, "_blank");
      } catch {
        /* storage web no disponible */
      }
    })();
  };

  const onAction = (item: AdminItem) => {
    if (item.action === "storage-composers") openStorage("composers");
    else if (item.action === "storage-works") openStorage("works");
    else if (item.action === "storage-main") openStorage(null);
  };

  if (!isAdmin) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-osap-bg text-osap-ink">
        <p className="text-sm text-osap-muted">{t("admin.accessDenied")}</p>
        <Link to="/" className="text-sm text-osap-accent hover:underline">
          {t("nav.home")}
        </Link>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-osap-bg text-osap-ink">
      <aside className="flex w-64 shrink-0 flex-col border-r border-osap-border bg-osap-surface">
        <div className="flex items-center justify-between border-b border-osap-border px-4 py-3">
          <span className="text-base font-bold text-osap-accent">{t("admin.title")}</span>
          <Link to="/" className="text-xs text-osap-muted hover:text-osap-accent">
            {t("nav.home")} ↗
          </Link>
        </div>
        <nav className="flex-1 overflow-y-auto px-2 py-3">
          {SECTIONS.filter((s) => s.items.length).map((section, i) => (
            <div key={i} className="mb-4">
              {section.caption && (
                <p className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-osap-muted">
                  {section.caption}
                </p>
              )}
              <ul className="space-y-0.5">
                {section.items.map((item) =>
                  item.to ? (
                    <li key={item.to + item.key}>
                      <NavLink
                        to={item.to}
                        end={item.end}
                        className={({ isActive }) =>
                          `block rounded px-3 py-1.5 text-sm ${
                            isActive
                              ? "bg-osap-accent text-white"
                              : "text-osap-muted hover:bg-osap-border hover:text-osap-ink"
                          }`
                        }
                      >
                        {t(item.key)}
                      </NavLink>
                    </li>
                  ) : (
                    <li key={item.key}>
                      <button
                        type="button"
                        onClick={() => onAction(item)}
                        className="block w-full rounded px-3 py-1.5 text-left text-sm text-osap-muted hover:bg-osap-border hover:text-osap-ink"
                      >
                        {t(item.key)}
                      </button>
                    </li>
                  ),
                )}
              </ul>
            </div>
          ))}
        </nav>
        <div className="border-t border-osap-border p-3">
          <button
            type="button"
            onClick={() => {
              logout();
              navigate("/");
            }}
            className="w-full rounded border border-osap-border px-3 py-1.5 text-sm hover:bg-osap-bg"
          >
            {t("auth.logout")}
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-6xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
