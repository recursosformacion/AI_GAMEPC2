import type { ReactNode } from "react";
import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { DarkModeToggle } from "../components/DarkModeToggle";
import { GlobalSearch } from "../components/GlobalSearch";
import { LanguageSelect } from "../components/LanguageSelect";
import { LoginForm } from "../components/LoginForm";
import { RegisterForm } from "../components/RegisterForm";
import { useI18n } from "../i18n/I18n";
import { useAuth } from "../state/auth";

const MAIN_NAV = [
  { to: "/", key: "nav.home" },
  { to: "/studio", key: "nav.studio" },
  { to: "/discover", key: "nav.discover" },
  { to: "/catalog", key: "nav.sources" },
  { to: "/composers", key: "nav.composers" },
  { to: "/knowledge/observations", key: "nav.knowledge" },
  { to: "/about", key: "nav.about" },
] as const;

const ADMIN_MENU = [
  { to: "/admin", key: "admin.overview" },
  { to: "/admin/composers", key: "admin.composers" },
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
  const { user, logout, isAdmin } = useAuth();
  const [loginOpen, setLoginOpen] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
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
        <div className="flex flex-wrap items-center gap-2">
          <LanguageSelect />
          <DarkModeToggle />
          {user === null ? (
            <div className="relative">
              <button
                onClick={() => setLoginOpen((o) => !o)}
                aria-label={t("auth.login")}
                className="rounded-full border border-osap-border px-3 py-1 text-lg leading-none hover:bg-osap-surface"
              >
                👤
              </button>
              {loginOpen && (
                <div className="absolute right-0 top-full z-20 mt-2 w-60 rounded border border-osap-border bg-osap-surface p-3 shadow">
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
              <span className="rounded-full border border-osap-border px-3 py-1 text-sm">👤</span>
              {isAdmin() && (
                <div className="relative">
                  <button
                    onClick={() => setAdminOpen((o) => !o)}
                    className="rounded-full border border-osap-border px-3 py-1 text-sm hover:bg-osap-surface"
                  >
                    {t("admin.title")} ▾
                  </button>
                  {adminOpen && (
                    <ul className="absolute right-0 top-full z-20 mt-2 w-44 rounded border border-osap-border bg-osap-surface shadow">
                      {ADMIN_MENU.map((item) => (
                        <li key={item.to}>
                          <Link
                            to={item.to}
                            onClick={() => setAdminOpen(false)}
                            className="block px-3 py-2 text-sm hover:bg-osap-surface"
                          >
                            {t(item.key)}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
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
      </ul>
    </nav>
  );
}

export function Footer() {
  const { t } = useI18n();
  return (
    <footer className="border-t border-osap-border bg-osap-surface py-4 text-center text-xs text-osap-muted">
      {t("app.name")} · {t("app.subtitle")} — {t("app.poweredBy")} ·{" "}
      <Link to="/about" className="text-osap-accent hover:underline">
        {t("nav.about")}
      </Link>
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
