import type { ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { DarkModeToggle } from "../components/DarkModeToggle";
import { GlobalSearch } from "../components/GlobalSearch";
import { LanguageSelect } from "../components/LanguageSelect";
import { useI18n } from "../i18n/I18n";
import { useAuth } from "../state/auth";

const MAIN_NAV = [
  { to: "/", key: "nav.home" },
  { to: "/studio", key: "nav.studio" },
  { to: "/discover", key: "nav.discover" },
  { to: "/catalog", key: "nav.sources" },
  { to: "/composers", key: "nav.composers" },
  { to: "/knowledge/observations", key: "nav.knowledge" },
] as const;

const ADMIN_LINKS = [
  { to: "/providers", key: "providers" },
  { to: "/jobs", key: "jobs" },
] as const;

// Semantic labels for the breadcrumb (never routes/URLs).
const SEGMENT_LABELS: Record<string, string> = {
  discover: "Discover",
  searches: "Searches",
  resolution: "Work Resolution",
  knowledge: "Knowledge",
  observations: "Observed aliases",
  facts: "Provider consistency",
  suggestions: "Suggested aliases",
  providers: "Providers",
  jobs: "Jobs",
};

function Breadcrumb() {
  const { t } = useI18n();
  const location = useLocation();
  const parts = location.pathname.split("/").filter(Boolean);
  const crumbs = [{ label: t("nav.home"), to: "/" }];
  let acc = "";
  for (const part of parts) {
    acc += `/${part}`;
    crumbs.push({ label: SEGMENT_LABELS[part] ?? part, to: acc });
  }
  return (
    <nav aria-label="breadcrumb" className="mx-auto w-full max-w-5xl px-4 py-2 text-xs text-osap-muted">
      {crumbs.map((c, i) => (
        <span key={c.to}>
          {i > 0 ? <span className="mx-1">›</span> : null}
          {i === crumbs.length - 1 ? <span>{c.label}</span> : <Link to={c.to}>{c.label}</Link>}
        </span>
      ))}
    </nav>
  );
}

export function Header() {
  const { t } = useI18n();
  const { user, login, logout, isAdmin } = useAuth();
  const onLogin = () => {
    // Dev: pega un JWT (user token) para probar la navegación/acciones. La integración real
    // de login sigue el contrato de osap-auth.
    const token = window.prompt(t("auth.pasteToken"));
    if (token) {
      login(token);
    }
  };
  return (
    <header className="border-b border-osap-border bg-osap-surface">
      <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center gap-3 px-4 py-3">
        <Link to="/" className="flex flex-col leading-tight">
          <span className="text-lg font-bold text-osap-accent">{t("app.name")}</span>
          <span className="text-xs text-osap-muted">{t("app.poweredBy")}</span>
        </Link>
        <div className="flex-1">
          <GlobalSearch />
        </div>
        <div className="flex items-center gap-2">
          <LanguageSelect />
          <DarkModeToggle />
          {user === null ? (
            <button
              onClick={onLogin}
              className="rounded-full border border-osap-border px-3 py-1 text-sm hover:bg-osap-surface"
            >
              {t("auth.login")}
            </button>
          ) : (
            <>
              <span className="rounded-full border border-osap-border px-3 py-1 text-sm">
                {isAdmin() ? t("auth.admin") : "👤"}
              </span>
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

export function Navigation() {
  const { t } = useI18n();
  return (
    <nav className="border-b border-osap-border bg-osap-surface">
      <ul className="mx-auto flex w-full max-w-5xl items-center gap-1 px-4">
        {MAIN_NAV.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) =>
                `block px-3 py-2 text-sm ${isActive ? "text-osap-accent" : "text-osap-muted hover:text-osap-ink"}`
              }
            >
              {t(item.key)}
            </NavLink>
          </li>
        ))}
        <li className="ml-auto">
          <span className="block px-3 py-2 text-xs text-osap-muted">{t("nav.admin")}</span>
        </li>
        {ADMIN_LINKS.map((item) => (
          <li key={item.to}>
            <Link to={item.to} className="block px-2 py-2 text-xs text-osap-muted hover:text-osap-ink">
              {item.key}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function Footer() {
  const { t } = useI18n();
  return (
    <footer className="border-t border-osap-border bg-osap-surface py-4 text-center text-xs text-osap-muted">
      {t("app.name")} · {t("app.subtitle")} — {t("app.poweredBy")}
    </footer>
  );
}

export function Layout(): ReactNode {
  return (
    <div className="flex min-h-screen flex-col bg-osap-bg text-osap-ink">
      <Header />
      <Navigation />
      <Breadcrumb />
      <main className="mx-auto w-full max-w-5xl flex-1 p-4">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
