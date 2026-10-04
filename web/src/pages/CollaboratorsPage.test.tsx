// Test de la página pública "Colaboradores": estados loading / lista / vacío / error.
// La página solo consume osap-api (apiClient); no conoce user_id ni auth/support.

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import { I18nProvider } from "../i18n/I18n";
import { useCollaborators } from "../state/collaborators";
import { CollaboratorsPage } from "./CollaboratorsPage";

function renderPage(): void {
  render(
    <MemoryRouter initialEntries={["/collaborators"]}>
      <I18nProvider lang="en" setLang={() => undefined}>
        <CollaboratorsPage />
      </I18nProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  useCollaborators.setState({ data: null, loading: false, error: null });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("CollaboratorsPage", () => {
  it("ready: muestra una entrada por persona con sus badges", async () => {
    vi.spyOn(apiClient, "getCollaborators").mockResolvedValue([
      {
        nickname: "ana",
        recognitions: [
          { type: "supporter", granted_at: "2026-01-01" },
          { type: "contributor", granted_at: "2026-02-01" },
        ],
      },
      { nickname: "bob", recognitions: [{ type: "voice", granted_at: "2026-03-01" }] },
    ]);

    renderPage();

    expect(await screen.findByText("ana")).toBeTruthy();
    expect(screen.getByText("bob")).toBeTruthy();
    expect(screen.getByText("Supporter")).toBeTruthy();
    expect(screen.getByText("Contributor")).toBeTruthy();
    expect(screen.getByText("Voice")).toBeTruthy();
  });

  it("vacío: mensaje específico de colaboradores públicos (no error)", async () => {
    vi.spyOn(apiClient, "getCollaborators").mockResolvedValue([]);

    renderPage();

    expect(
      await screen.findByText("No public collaborators to show yet."),
    ).toBeTruthy();
    expect(screen.queryByTestId("error")).toBeNull();
  });

  it("error: muestra el envelope de error", async () => {
    vi.spyOn(apiClient, "getCollaborators").mockRejectedValue(
      new ApiError("UPSTREAM_UNAVAILABLE", "auth caido", {}),
    );

    renderPage();

    expect(await screen.findByTestId("error")).toBeTruthy();
    expect(screen.getByText(/UPSTREAM_UNAVAILABLE/)).toBeTruthy();
  });
});
