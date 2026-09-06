// Test de la página "Apoya a OSAP" contra la frontera real de support.
// Verifica: CTA de login (anónimo); estado real (no miembro) con botón de donación real
// cuando el backend responde que NO hay membresía. No simula pagos.

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18n";
import { useAuth } from "../state/auth";
import { SupportOsapPage } from "./SupportOsapPage";
import { supportGateway } from "../support/remoteSupportGateway";

function renderSupportOsapPage(): void {
  render(
    <MemoryRouter initialEntries={["/support"]}>
      <I18nProvider lang="en" setLang={() => undefined}>
        <SupportOsapPage />
      </I18nProvider>
    </MemoryRouter>,
  );
}

function resetAuth(): void {
  useAuth.setState({
    accessToken: null,
    refreshToken: null,
    user: null,
    status: "anonymous",
  });
}

beforeEach(() => {
  resetAuth();
  vi.clearAllMocks();
});

afterEach(() => {
  localStorage.clear();
  resetAuth();
  vi.restoreAllMocks();
});

describe("SupportOsapPage", () => {
  it("muestra el CTA de iniciar sesión cuando no hay usuario", () => {
    renderSupportOsapPage();
    expect(screen.getByRole("button", { name: /login|sign in|iniciar/i })).toBeTruthy();
  });

  it("muestra estado real 'no miembro' y el botón de donación cuando el backend responde", async () => {
    useAuth.setState({
      accessToken: "token",
      refreshToken: "rt",
      user: { user_id: "uuid-1", roles: ["user"], email_verified: true },
      status: "authenticated",
    });
    // Frontera real mockeada: osap-support responde que no hay membresía.
    vi.spyOn(supportGateway, "getSummary").mockResolvedValue({
      status: "no_membership",
      authenticated: true,
      membership: { status: null, level: null, is_founder: false },
    });
    renderSupportOsapPage();
    expect(await screen.findByText(/not a member yet/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /make a donation/i })).toBeTruthy();
  });

  it("no muestra 'miembro' por defecto cuando el servicio no está disponible", async () => {
    useAuth.setState({
      accessToken: "token",
      refreshToken: "rt",
      user: { user_id: "uuid-1", roles: ["user"], email_verified: true },
      status: "authenticated",
    });
    vi.spyOn(supportGateway, "getSummary").mockResolvedValue({
      status: "unavailable",
      authenticated: true,
      error: "support_unavailable",
    });
    renderSupportOsapPage();
    expect(await screen.findByText(/temporarily unavailable/i)).toBeTruthy();
    expect(screen.queryByText("Member")).toBeNull();
  });
});
