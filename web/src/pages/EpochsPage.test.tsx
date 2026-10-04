// Épocas: listado público con nombre, fechas y descripción.

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/ApiClient";
import { I18nProvider } from "../i18n/I18n";
import { useEpochs } from "../state/epochs";
import { EpochsPage } from "./EpochsPage";

beforeEach(() => {
  useEpochs.setState({ data: null, loading: false, error: null });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("EpochsPage", () => {
  it("lista épocas con nombre, fechas y descripción", async () => {
    vi.spyOn(apiClient, "getEpochs").mockResolvedValue([
      { id: 2, title: "Edad Media", year_start: 476, year_end: 1450, description: "Canto gregoriano." },
    ]);

    render(
      <MemoryRouter>
        <I18nProvider lang="en" setLang={() => undefined}>
          <EpochsPage />
        </I18nProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Edad Media")).toBeInTheDocument();
    expect(screen.getByText("476–1450")).toBeInTheDocument();
    expect(screen.getByText("Canto gregoriano.")).toBeInTheDocument();
  });
});
