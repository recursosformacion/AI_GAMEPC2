import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import type { SearchResponse } from "./api/types";
import App from "./App";
import { useSearches } from "./state/searches";

const fixture: SearchResponse = {
  search_id: "s1",
  results: [
    {
      work: { work_id: "w1", title: "Ave Verum Corpus", composer: "Mozart", catalogue: "KV 618" },
      representation: { id: "r1", provider: "imslp", format: "pdf", confidence: 0.9, url: "https://x/file.pdf" },
      score: 0.9,
      evidence: [],
    },
    {
      work: { work_id: "w1", title: "Ave Verum Corpus", composer: "Mozart", catalogue: "KV 618" },
      representation: { id: "r2", provider: "openscore", format: "musicxml", confidence: 0.7, url: "https://x/file.xml" },
      score: 0.9,
      evidence: [],
    },
  ],
};

function renderResolution() {
  return render(
    <MemoryRouter initialEntries={["/resolution"]}>
      <App />
    </MemoryRouter>,
  );
}

describe("Work Resolution (V3.4)", () => {
  beforeEach(() => {
    useSearches.setState({ data: fixture, loading: false, error: null });
  });

  it("shows the resolved work (overview) and representations grouped by provider", () => {
    renderResolution();
    expect(screen.getByText(/Ave Verum Corpus/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Representations" }));
    expect(screen.getByText("imslp")).toBeInTheDocument();
    expect(screen.getByText("openscore")).toBeInTheDocument();
    expect(screen.getAllByText(/pdf/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/musicxml/).length).toBeGreaterThan(0);
  });

  it("shows evidence in the Evidence tab", () => {
    renderResolution();
    fireEvent.click(screen.getByRole("button", { name: "Evidence" }));
    expect(screen.getByText("Matched title")).toBeInTheDocument();
    expect(screen.getByText("Mozart")).toBeInTheDocument();
  });

  it("offers actions for the resolution workspace", () => {
    renderResolution();
    fireEvent.click(screen.getByRole("button", { name: "Representations" }));
    expect(screen.getAllByText("Download").length).toBeGreaterThan(0);
    expect(screen.getAllByText("View").length).toBeGreaterThan(0);
  });
});
