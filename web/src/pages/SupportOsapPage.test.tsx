// Test de la página "Apoya a OSAP" contra la frontera real de support.
// Verifica: CTA de login (anónimo); estado real (no miembro) con botón de donación real
// cuando el backend responde que NO hay membresía. No simula pagos.

import { render, screen, waitFor } from "@testing-library/react";
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
    const loginButtons = screen.getAllByRole("button", { name: /login|sign in|iniciar/i });
    expect(loginButtons.length).toBeGreaterThan(0);
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

describe("SupportOsapPage · membresía", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function setAuthenticated(membership: unknown): void {
    useAuth.setState({
      accessToken: "token",
      refreshToken: "rt",
      user: { user_id: "uuid-1", roles: ["user"], email_verified: true },
      status: "authenticated",
    });
    vi.spyOn(supportGateway, "getSummary").mockResolvedValue({
      status: membership && (membership as { status?: string | null }).status ? "member" : "no_membership",
      authenticated: true,
      membership,
    } as never);
  }

  function mockLocationAssign(): ReturnType<typeof vi.fn> {
    const assign = vi.fn();
    const stub = {
      assign,
      href: "http://localhost/support",
      origin: "http://localhost",
      pathname: "/support",
    } as unknown as Location;
    vi.spyOn(window, "location", "get").mockReturnValue(stub);
    return assign;
  }

  it("anónimo: muestra el CTA de iniciar sesión, no el checkout", () => {
    renderSupportOsapPage();
    expect(screen.getByText(/log in to become a supporter/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /become supporter \(monthly\)/i })).toBeNull();
  });

  it("sin membresía: muestra los planes mensual y anual junto a la donación", async () => {
    setAuthenticated({ status: null, level: null, is_founder: false });
    renderSupportOsapPage();
    expect(await screen.findByText(/not a member yet/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /become supporter \(monthly\)/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /become supporter \(yearly\)/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /make a donation/i })).toBeTruthy();
  });

  it("mensual: llama a /checkouts/membership y redirige a checkout_url", async () => {
    setAuthenticated({ status: null, level: null, is_founder: false });
    const checkout = {
      checkout_url: "https://www.sandbox.paypal.com/approve?token=x",
      provider_session_id: "I-1",
      mode: "membership" as const,
      return_url: "/support",
    };
    const startMembershipSpy = vi
      .spyOn(supportGateway, "startMembership")
      .mockResolvedValue(checkout);
    const assign = mockLocationAssign();
    renderSupportOsapPage();
    const monthly = await screen.findByRole("button", { name: /become supporter \(monthly\)/i });
    monthly.click();
    expect(startMembershipSpy).toHaveBeenCalledWith(
      "token",
      "supporter",
      "monthly",
      expect.stringContaining("/support"),
    );
    await waitFor(() => expect(assign).toHaveBeenCalledWith(checkout.checkout_url));
  });

  it("anual: llama con periodicity yearly", async () => {
    setAuthenticated({ status: null, level: null, is_founder: false });
    const startMembershipSpy = vi.spyOn(supportGateway, "startMembership").mockResolvedValue({
      checkout_url: "https://paypal.test/yearly",
      provider_session_id: "I-2",
      mode: "membership",
      return_url: "/support",
    });
    mockLocationAssign();
    renderSupportOsapPage();
    const yearly = await screen.findByRole("button", { name: /become supporter \(yearly\)/i });
    yearly.click();
    expect(startMembershipSpy).toHaveBeenCalledWith("token", "supporter", "yearly", expect.any(String));
  });

  it("Supporter activo: muestra estado y NO ofrece contratar otra vez", async () => {
    setAuthenticated({
      status: "active",
      level: "supporter",
      periodicity: "monthly",
      is_founder: false,
    });
    renderSupportOsapPage();
    expect(await screen.findByText(/you are a supporter/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /become supporter \(monthly\)/i })).toBeNull();
  });

  it("otro estado (pending): muestra estado y no ofrece contratar", async () => {
    setAuthenticated({
      status: "pending",
      level: "supporter",
      periodicity: "monthly",
      is_founder: false,
    });
    renderSupportOsapPage();
    expect(await screen.findByText(/activation pending/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /become supporter \(monthly\)/i })).toBeNull();
  });

  it("error del checkout: muestra el mensaje y permite reintentar", async () => {
    setAuthenticated({ status: null, level: null, is_founder: false });
    vi.spyOn(supportGateway, "startMembership").mockRejectedValue(new Error("proveedor de pago caído"));
    mockLocationAssign();
    renderSupportOsapPage();
    const monthly = await screen.findByRole("button", { name: /become supporter \(monthly\)/i });
    monthly.click();
    expect(await screen.findByText(/proveedor de pago caído/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /become supporter \(monthly\)/i })).toBeTruthy();
  });
});
