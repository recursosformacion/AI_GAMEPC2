// Layout de administración a pantalla completa: menú vertical izquierdo permanente
// (solo visible para admins). Los hijos se renderizan en <Outlet/> a ancho completo.
//
// La navegación agrupa por función administrativa (no por implementación de BD). Los
// ítems de storage abren la capa web de osap-storage con un service token `storage:admin`:
// páginas curadas (/admin/maestros, /admin/obras) y el SPA de mantenimiento
// (/admin/representations, /admin/t/<tabla>, /admin/ multimantenimiento).

import type { ReactNode } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { apiClient } from "../api/ApiClient";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";
import { useAuth } from "../state/auth";

interface AdminItem {
  to?: string;
  key?: TKey;
  label?: string;
  end?: boolean;
  title?: string;
  /** Sección de la web de storage a abrir con service token (composers|works|tables|
   *  representations|mantenimiento|multimantenimiento|table:<tabla>). */
  storage?: string;
  children?: AdminItem[];
}

interface AdminSection {
  caption?: string;
  items: AdminItem[];
}

const SECTIONS: AdminSection[] = [
  {
    caption: "Administración",
    items: [
      { to: "/admin", key: "admin.resumen", end: true },
      { to: "/admin/funnel", label: "Estadísticas" },
    ],
  },
  {
    caption: "Gestión de pagos",
    items: [
      { to: "/admin/payments", key: "admin.paymentsTitle" },
      { to: "/admin/quota", key: "admin.quota" },
    ],
  },
  {
    caption: "Mantenimiento de datos",
    items: [
      { to: "/admin/users", key: "adminUsers.title" },
      { to: "/admin/providers", key: "admin.providersAdmin" },
    ],
  },
  {
    caption: "Mantenimiento storage",
    items: [
      {
        label: "Personas",
        children: [
          { storage: "composers", label: "Maestro personas" },
          { to: "/admin/composers", key: "admin.composersFusion" },
          { to: "/admin/aliases", key: "admin.aliases" },
        ],
      },
      {
        label: "Obras",
        children: [
          { storage: "works", label: "Works" },
          { storage: "representations", label: "Representaciones" },
          { storage: "work-persons", label: "Obras → Personas" },
        ],
      },
      {
        label: "Servicios",
        children: [
          { storage: "table:instruments", label: "Instrumentos" },
          { storage: "table:instrument_categories", label: "Tipos de instrumentos" },
          { storage: "table:catalog", label: "Catálogos" },
          { storage: "table:category", label: "Categoría" },
          { storage: "table:ensembles", label: "Ensembles" },
          { storage: "table:epochs", label: "Épocas" },
          { storage: "table:genres", label: "Géneros" },
          { storage: "table:genre_mappings", label: "Mapeado de géneros" },
          { storage: "table:languages", label: "Lenguas" },
        ],
      },
    ],
  },
  {
    caption: "Seguimiento del producto",
    items: [
      { to: "/admin/source-suggestions", key: "admin.sourceSuggestions" },
      { to: "/admin/corrections", key: "admin.corrections" },
      { to: "/jobs", key: "jobs" },
    ],
  },
  { items: [{ storage: "multimantenimiento", key: "admin.storageMaint" }] },
];

export function AdminLayout(): ReactNode {
  const { t } = useI18n();
  const isAdmin = useAuth((s) => s.isAdmin());
  const logout = useAuth((s) => s.logout);
  const navigate = useNavigate();

  const openStorage = (section: string) => {
    void (async () => {
      try {
        const r = await apiClient.getStorageWebUrl(section);
        window.open(r.url, "_blank");
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error);
        window.alert(`osap-storage admin no disponible · not available: ${detail}`);
      }
    })();
  };

  const label = (item: AdminItem): string => item.label ?? (item.key ? t(item.key) : "");
  const itemKey = (item: AdminItem): string => (item.to ?? item.storage ?? "") + label(item);

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

  function renderLeaf(item: AdminItem): ReactNode {
    if (item.to) {
      return (
        <NavLink
          to={item.to}
          end={item.end}
          title={item.title}
          className={({ isActive }) =>
            `block rounded px-3 py-1.5 text-sm ${
              isActive
                ? "bg-osap-accent text-white"
                : "text-osap-muted hover:bg-osap-border hover:text-osap-ink"
            }`
          }
        >
          {label(item)}
        </NavLink>
      );
    }
    return (
      <button
        type="button"
        onClick={() => openStorage(item.storage ?? "multimantenimiento")}
        title={item.title}
        className="block w-full rounded px-3 py-1.5 text-left text-sm text-osap-muted hover:bg-osap-border hover:text-osap-ink"
      >
        {label(item)}
      </button>
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
                {section.items.map((item) => (
                  <li key={itemKey(item)}>
                    {item.children ? (
                      <div>
                        <p className="px-3 pb-0.5 pt-2 text-[11px] font-semibold uppercase tracking-wide text-osap-muted">
                          {label(item)}
                        </p>
                        <ul className="space-y-0.5 pl-2">
                          {item.children.map((child) => (
                            <li key={itemKey(child)}>{renderLeaf(child)}</li>
                          ))}
                        </ul>
                      </div>
                    ) : (
                      renderLeaf(item)
                    )}
                  </li>
                ))}
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
