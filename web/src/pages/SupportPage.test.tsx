// Test mínimo de la página /support (a través del SupportGateway).
// Verifica que mantiene el comportamiento actual: CTA de login (anónimo) vs CTA de
// "empezar a apoyar" (identificado), sin romper la autenticación.

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { I18nProvider } from "../i18n/I18n";
import { useAuth } from "../state/auth";
import { SupportPage } from "./SupportPage";

function renderSupportPage(): void {
  render(
    <MemoryRouter initialEntries={["/support"]}>
      <I18nProvider lang="en" setLang={() => undefined}>
        <SupportPage />
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

beforeEach(resetAuth);
afterEach(() => {
  localStorage.clear();
  resetAuth();
});

describe("SupportPage", () => {
  it("muestra el CTA de iniciar sesión cuando no hay usuario", () => {
    renderSupportPage();
    // Botón de identificación (login) para no autenticado.
    expect(screen.getByRole("button", { name: /login|sign in|iniciar/i })).toBeTruthy();
  });

  it("muestra el CTA de empezar a apoyar cuando hay usuario identificado", () => {
    useAuth.setState({
      user: { user_id: "uuid-1", roles: ["user"], email_verified: true },
      status: "authenticated",
    });
    renderSupportPage();
    // CTA de apoyo (autenticado), sin simular pago.
    expect(screen.getByRole("button", { name: /start supporting|empezar a apoyar/i })).toBeTruthy();
  });
});
