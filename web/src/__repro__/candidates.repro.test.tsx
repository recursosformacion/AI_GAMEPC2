import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SearchResponse } from "../api/types";
import { I18nProvider } from "../i18n/I18n";
import { CandidatesPage } from "../pages/CandidatesPage";
import { useSearches } from "../state/searches";
import fixture from "./search_fixture.json";

// Reproducción con una respuesta REAL de /searches (búsqueda por catálogo "BWV 1043").
describe("repro CandidatesPage con datos reales", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            success: true,
            data: {
              work_id: "w",
              representations_known: 0,
              candidates_usable: 0,
              status: "none_selected",
              message: "",
              selected: null,
            },
          }),
          { status: 200 },
        ),
      ),
    ) as unknown as typeof fetch;
  });

  it("pinta la lista y despliega la obra sin lanzar", () => {
    useSearches.setState({
      data: fixture as unknown as SearchResponse,
      loading: false,
      error: null,
      polling: false,
    });
    render(
      <MemoryRouter>
        <I18nProvider lang="es" setLang={() => {}}>
          <CandidatesPage />
        </I18nProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText(/Obras coincidentes/i)).toBeInTheDocument();
    const expand = screen.getAllByRole("button", { name: "expand" });
    expect(expand.length).toBeGreaterThan(0);
    for (const button of expand) {
      fireEvent.click(button);
    }
    expect(screen.getByText(/Representa/i)).toBeInTheDocument();
  });
});
