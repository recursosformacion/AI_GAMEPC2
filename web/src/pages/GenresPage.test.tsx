import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/ApiClient";
import { I18nProvider } from "../i18n/I18n";
import { useGenres } from "../state/classification";
import { GenresPage } from "./GenresPage";

beforeEach(() => {
  useGenres.setState({ data: null, loading: false, error: null });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("GenresPage", () => {
  it("lista géneros con nombre y descripción", async () => {
    vi.spyOn(apiClient, "getGenres").mockResolvedValue([
      { id: 4, name: "Jazz y Blues", description: "Ragtime, swing…" },
    ]);

    render(
      <MemoryRouter>
        <I18nProvider lang="en" setLang={() => undefined}>
          <GenresPage />
        </I18nProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Jazz y Blues")).toBeInTheDocument();
    expect(screen.getByText("Ragtime, swing…")).toBeInTheDocument();
  });
});
