import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { trackPageView } from "../analytics/gtm";
import { DarkModeToggle } from "../components/DarkModeToggle";
import { GlobalSearch } from "../components/GlobalSearch";
import { LanguageSelect } from "../components/LanguageSelect";
import { LoginForm } from "../components/LoginForm";
import { RegisterForm } from "../components/RegisterForm";
import { useOidcLogin } from "../components/useOidcLogin";
import { useI18n } from "../i18n/I18n";
import type { TKey } from "../i18n/translations";
import { useSeo } from "../seo/useSeo";
import { useAuth } from "../state/auth";
import { useSystem } from "../state/system";

type IconName =
  | "home"
  | "search"
  | "discover"
  | "catalog"
  | "person"
  | "people"
  | "layers"
  | "activity"
  | "clock"
  | "mail"
  | "info"
  | "support";

const ICON_PATHS: Record<IconName, ReactNode> = {
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </>
  ),
  discover: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </>
  ),
  catalog: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18M9 21V9" />
    </>
  ),
  person: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 4-6 8-6s8 2 8 6" />
    </>
  ),
  layers: (
    <>
      <path d="m12 3 9 5-9 5-9-5 9-5Z" />
      <path d="m3 13 9 5 9-5" />
    </>
  ),
  activity: <path d="M3 12h4l2-6 4 12 2-6h6" />,
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </>
  ),
  support: <path d="M12 21s-7-4.5-9-9a5 5 0 0 1 9-4 5 5 0 0 1 9 4c-2 4.5-9 9-9 9Z" />,
  home: (
    <>
      <path d="M3 11.5 12 4l9 7.5" />
      <path d="M5 10v10h14V10" />
    </>
  ),
  people: (
    <>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M2.5 20c0-3.3 2.9-5 6.5-5s6.5 1.7 6.5 5" />
      <path d="M17 8.2a3 3 0 0 1 0 5.6M22 20c0-2.4-1.4-4-3.5-4.6" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  mail: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m4 7 8 6 8-6" />
    </>
  ),
};

function Icon({ name }: { name: IconName }) {
  return (
    <svg
      width="17"
      height="17"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="shrink-0"
    >
      {ICON_PATHS[name]}
    </svg>
  );
}

interface NavItem {
  to: string;
  key: TKey;
  icon: IconName;
}

interface NavGroupItem {
  group: true;
  key: TKey;
  icon: IconName;
  children: readonly { to: string; key: TKey }[];
}

type NavEntry = NavItem | NavGroupItem;

// "Clasificación" es solo un AGRUPADOR del sidebar; las rutas NO se prefijan.
const CLASSIFICATION_CHILDREN = [
  { to: "/epochs", key: "nav.epochs" },
  { to: "/genres", key: "nav.genres" },
  { to: "/catalogues", key: "nav.catalogues" },
  { to: "/instruments", key: "nav.instruments" },
  { to: "/ensembles", key: "nav.ensembles" },
] as const;

// "Contenido": Inicio, Explorar, Compositores, [Clasificación], Colaboradores, Contactos.
// Catálogo y Fuentes viven DENTRO de Explorar (no son ítems de primer nivel).
const CONTENT_ENTRIES: readonly NavEntry[] = [
  { to: "/", key: "nav.home", icon: "home" },
  { to: "/explore", key: "nav.explore", icon: "discover" },
  { to: "/composers", key: "nav.composers", icon: "person" },
  {
    group: true,
    key: "nav.sectionClassification",
    icon: "layers",
    children: CLASSIFICATION_CHILDREN,
  },
  { to: "/collaborators", key: "nav.collaborators", icon: "people" },
  { to: "/corrections?kind=contact", key: "nav.contact", icon: "mail" },
];

const SPACE_NAV: readonly NavItem[] = [{ to: "/activity", key: "nav.activity", icon: "activity" }];

// Fondo del sidebar: exactamente dos entradas, como el diseño.
const BOTTOM_NAV: readonly NavItem[] = [
  { to: "/about", key: "nav.about", icon: "info" },
  { to: "/support", key: "nav.support", icon: "support" },
];

function NavGroup({ entry, onNavigate }: { entry: NavGroupItem; onNavigate: () => void }) {
  const { t } = useI18n();
  const location = useLocation();
  const childActive = entry.children.some(
    (child) => location.pathname === child.to || location.pathname.startsWith(`${child.to}/`),
  );
  const [open, setOpen] = useState(childActive);
  useEffect(() => {
    if (childActive) setOpen(true);
  }, [childActive]);
  return (
    <li>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-bold ${
          childActive ? "text-osap-accent" : "text-osap-ink hover:bg-osap-accent-soft/60"
        }`}
      >
        <Icon name={entry.icon} />
        <span className="flex-1 text-left">{t(entry.key)}</span>
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`transition-transform ${open ? "rotate-90" : ""}`}
          aria-hidden="true"
        >
          <path d="m9 6 6 6-6 6" />
        </svg>
      </button>
      {open ? (
        <ul className="ml-4 mt-0.5 space-y-0.5 border-l border-osap-border pl-3">
          {entry.children.map((child) => (
            <li key={child.to}>
              <NavLink
                to={child.to}
                onClick={onNavigate}
                className={({ isActive }) =>
                  `block rounded-md px-3 py-1.5 text-sm ${
                    isActive
                      ? "bg-osap-accent-soft font-medium text-osap-accent"
                      : "text-osap-ink hover:bg-osap-accent-soft/60"
                  }`
                }
              >
                {t(child.key)}
              </NavLink>
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function SidebarSection({
  title,
  entries,
  onNavigate,
}: {
  title: string;
  entries: readonly NavEntry[];
  onNavigate: () => void;
}) {
  const { t } = useI18n();
  return (
    <div className="mt-5">
      <p className="px-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-osap-muted">{title}</p>
      <ul className="mt-1.5 space-y-0.5">
        {entries.map((entry) =>
          "group" in entry ? (
            <NavGroup key={entry.key} entry={entry} onNavigate={onNavigate} />
          ) : (
            <li key={entry.to}>
              <NavLink
                to={entry.to}
                end={entry.to === "/"}
                onClick={onNavigate}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-bold ${
                    isActive
                      ? "bg-osap-accent-soft text-osap-accent"
                      : "text-osap-ink hover:bg-osap-accent-soft/60"
                  }`
                }
              >
                <Icon name={entry.icon} />
                {t(entry.key)}
              </NavLink>
            </li>
          ),
        )}
      </ul>
    </div>
  );
}

function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  return (
    <>
      <div
        className={`fixed inset-0 z-30 bg-black/40 lg:hidden ${open ? "" : "hidden"}`}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-osap-border-strong transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="px-5 py-5">
          <Link to="/" onClick={onClose} className="flex items-center gap-3">
            <img
              src="/android-chrome-192x192.png"
              alt=""
              width={36}
              height={36}
              className="h-9 w-9 shrink-0 rounded-md"
            />
            <span className="leading-tight">
              <span className="block font-display text-base font-semibold text-osap-accent">
                {t("app.name")}
              </span>
              <span className="mt-0.5 block text-[10px] uppercase tracking-widest text-osap-muted">
                {t("app.subtitle")}
              </span>
            </span>
          </Link>
        </div>
        <nav aria-label={t("nav.sectionContent")} className="flex-1 overflow-y-auto px-3 pb-4">
          <SidebarSection title={t("nav.sectionContent")} entries={CONTENT_ENTRIES} onNavigate={onClose} />
          <SidebarSection title={t("nav.sectionYourSpace")} entries={SPACE_NAV} onNavigate={onClose} />
        </nav>
        <div className="border-t border-osap-border-strong px-3 py-3">
          <ul className="space-y-0.5">
            {BOTTOM_NAV.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  onClick={onClose}
                  className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-bold text-osap-ink hover:bg-osap-accent-soft/60"
                >
                  <Icon name={item.icon} />
                  {t(item.key)}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </>
  );
}

function TopBar({ onMenu }: { onMenu: () => void }) {
  const { t } = useI18n();
  const { user, logout, isAdmin, updateName } = useAuth();
  const [loginOpen, setLoginOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const { start: startOidc, error: oidcError } = useOidcLogin();

  // Sin sesión: pulsa "Iniciar sesión" → popup OIDC; si no se puede, panel de respaldo.
  const openAuth = () => {
    void (async () => {
      const opened = await startOidc();
      if (!opened) setLoginOpen(true);
    })();
  };

  return (
    <header className="sticky top-0 z-20 border-b border-osap-border-strong">
      <div className="flex items-center gap-3 px-4 py-3 lg:px-6">
        <button
          type="button"
          onClick={onMenu}
          aria-label={t("nav.menu")}
          className="rounded-md border border-osap-border p-2 lg:hidden"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
        </button>
        <div className="min-w-0 flex-1">
          <GlobalSearch />
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/about/how-it-works"
            aria-label={t("nav.help")}
            className="hidden rounded-full border border-osap-border px-2.5 py-1 text-sm text-osap-muted hover:text-osap-accent sm:block"
          >
            ?
          </Link>
          <LanguageSelect />
          <DarkModeToggle />
          {user === null ? (
            <div className="relative">
              <button
                onClick={openAuth}
                className="rounded-full bg-osap-accent px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-osap-accent/90"
              >
                {t("auth.login")}
              </button>
              {oidcError && (
                <p className="absolute right-0 top-full z-20 mt-1 w-60 text-right text-xs text-red-500">{oidcError}</p>
              )}
              {loginOpen && (
                <div className="absolute right-0 top-full z-20 mt-2 w-60 rounded-md border border-osap-border bg-osap-surface p-3 shadow-card">
                  <div className="mb-2 flex gap-2 text-sm">
                    <button
                      type="button"
                      onClick={() => setAuthMode("login")}
                      className={authMode === "login" ? "font-semibold text-osap-accent" : "text-osap-muted"}
                    >
                      {t("auth.login")}
                    </button>
                    <button
                      type="button"
                      onClick={() => setAuthMode("register")}
                      className={authMode === "register" ? "font-semibold text-osap-accent" : "text-osap-muted"}
                    >
                      {t("auth.register")}
                    </button>
                  </div>
                  {authMode === "login" ? (
                    <LoginForm onDone={() => setLoginOpen(false)} />
                  ) : (
                    <RegisterForm onDone={() => setLoginOpen(false)} />
                  )}
                </div>
              )}
            </div>
          ) : (
            <>
              <button
                type="button"
                className="max-w-[12rem] truncate rounded-full border border-osap-border px-3 py-1 text-sm hover:border-osap-accent hover:text-osap-accent"
                title={t("account.editName")}
                onClick={() => {
                  const next = window.prompt(t("account.namePrompt"), user.name ?? "");
                  if (next && next.trim()) void updateName(next.trim());
                }}
              >
                {user.name || user.email || "…"}
              </button>
              {isAdmin() && (
                <Link
                  to="/admin"
                  className="rounded-full border border-osap-border px-3 py-1 text-sm text-osap-accent hover:bg-osap-surface"
                >
                  {t("admin.title")}
                </Link>
              )}
              <button
                onClick={logout}
                className="rounded-full border border-osap-border px-3 py-1 text-sm hover:bg-osap-surface"
              >
                {t("auth.logout")}
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

export function Footer() {
  const { t } = useI18n();
  return (
    <footer className="border-t border-osap-border py-4 text-center text-xs text-osap-muted">
      {t("app.name")} · {t("app.subtitle")} — {t("app.poweredBy")} ·{" "}
      <Link to="/about/how-it-works" className="text-osap-accent hover:underline">
        {t("nav.howItWorks")}
      </Link>
      {" · "}
      <Link to="/collaborators" className="text-osap-accent hover:underline">
        {t("nav.collaborators")}
      </Link>
      {" · "}
      <Link to="/support" className="text-osap-accent hover:underline">
        {t("nav.support")}
      </Link>
    </footer>
  );
}

export function StorageBanner() {
  const { t } = useI18n();
  const health = useSystem((s) => s.health);
  const load = useSystem((s) => s.load);
  useEffect(() => {
    void load();
  }, [load]);
  // Solo hay aviso cuando osap-api en desarrollo está conectado a un storage real
  // (read_only). El resto del tiempo no se muestra ningún aviso.
  if (!health || !health.read_only) return null;
  return (
    <div
      data-testid="storage-banner"
      className="bg-amber-300 px-4 py-1 text-center text-xs font-medium text-amber-900"
    >
      {t("system.readOnlyRemote")}
    </div>
  );
}

export function Layout(): ReactNode {
  useSeo();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // GTM en SPA: cada cambio de ruta debe enviar un page_view a dataLayer.
  useEffect(() => {
    trackPageView(location.pathname);
  }, [location.pathname]);
  // Cierra el drawer al navegar (móvil).
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  return (
    <div className="min-h-screen text-osap-ink">
      <StorageBanner />
      <div className="flex min-h-screen">
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <div className="osap-score-bg flex min-w-0 flex-1 flex-col">
          <TopBar onMenu={() => setSidebarOpen(true)} />
          <main className="mx-auto my-4 w-full max-w-5xl flex-1 px-4 py-6 sm:my-6 sm:px-6 lg:px-8">
            <Outlet />
          </main>
          <Footer />
        </div>
      </div>
    </div>
  );
}
