// Mi Actividad: anónimo (explicación + CTA) y autenticado (actividad real).

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { I18nProvider } from "../i18n/I18n";
import { useAnalyticsMe } from "../state/analyticsMe";
import { useAuth } from "../state/auth";
import { ActivityPage } from "./ActivityPage";

function renderPage(): void {
  render(
    <MemoryRouter>
      <I18nProvider lang="en" setLang={() => undefined}>
        <ActivityPage />
      </I18nProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  useAuth.setState({ status: "anonymous", user: null });
  useAnalyticsMe.setState({ data: null, loading: false, error: null });
});

describe("ActivityPage", () => {
  it("anónimo: muestra explicación y CTA, no una pantalla vacía", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "My activity" })).toBeInTheDocument();
    expect(screen.getByText(/Sign in to see what you have downloaded/)).toBeInTheDocument();
    expect(screen.getByText("What you will find")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Login" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Register" })).toBeInTheDocument();
  });

  it("autenticado: muestra la actividad del usuario", () => {
    useAuth.setState({
      status: "authenticated",
      user: { user_id: "u1", roles: ["user"], email_verified: true, name: "Test" },
    });
    useAnalyticsMe.setState({
      data: {
        period: { from_day: "2026-01-01", to_day: "2026-01-31" },
        downloads: { count: 3, bytes: 100, providers: [] },
        quota: { used: 1, limit: 10, remaining: 9 },
        access: { stage: "free", tier: "basic" },
      },
      loading: false,
      error: null,
      load: async () => undefined,
    });

    renderPage();

    expect(screen.getByRole("heading", { name: "My activity" })).toBeInTheDocument();
    expect(screen.getByText(/2026-01-01/)).toBeInTheDocument();
  });
});
