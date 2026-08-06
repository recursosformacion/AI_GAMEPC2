import type { ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard" },
  { to: "/searches", label: "Searches" },
  { to: "/jobs", label: "Jobs" },
  { to: "/knowledge/observations", label: "Knowledge" },
  { to: "/providers", label: "Administration" },
];

export function Header(): ReactNode {
  return (
    <header className="border-b border-osap-border bg-osap-surface">
      <Link to="/" className="block px-6 py-3 text-lg font-bold text-osap-accent">
        OSAP
      </Link>
    </header>
  );
}

export function Navigation(): ReactNode {
  return (
    <nav className="border-b border-osap-border bg-osap-surface">
      <ul className="mx-auto flex max-w-5xl gap-1 px-4">
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) =>
                `block px-3 py-2 text-sm ${isActive ? "text-osap-accent" : "text-osap-muted hover:text-osap-ink"}`
              }
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function Breadcrumb(): ReactNode {
  const location = useLocation();
  const parts = location.pathname.split("/").filter(Boolean);
  return (
    <nav aria-label="breadcrumb" className="mx-auto max-w-5xl px-4 py-2 text-xs text-osap-muted">
      <span>/</span>
      {parts.map((part) => (
        <span key={part}>
          {" "}
          {part}{" "}
        </span>
      ))}
    </nav>
  );
}

export function Footer(): ReactNode {
  return (
    <footer className="border-t border-osap-border bg-osap-surface py-4 text-center text-xs text-osap-muted">
      OSAP — Open Sheet Music Aggregation Platform
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
