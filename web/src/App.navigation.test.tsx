import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

function stubFetch(): ReturnType<typeof vi.fn> {
  const fn = vi.fn(async () =>
    new Response(JSON.stringify({ success: false, request_id: "r", error: { code: "NOT_FOUND", message: "x", details: {} } }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    }),
  );
  globalThis.fetch = fn as unknown as typeof fetch;
  return fn;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("Routing and navigation (V3.4)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders Home with the brand at /", () => {
    renderAt("/");
    expect(screen.getAllByText("OpenMusicRepository").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("search")).toBeInTheDocument();
  });

  it("renders Explore (container) at /explore", async () => {
    renderAt("/explore");
    // Las páginas son lazy (code-splitting): se espera a que cargue el chunk.
    expect(await screen.findByRole("heading", { name: "Explore" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Discover" })).toBeInTheDocument();
  });

  it("renders Discover at /discover", async () => {
    stubFetch();
    renderAt("/discover");
    expect(await screen.findByRole("heading", { name: "Discover" })).toBeInTheDocument();
  });

  it("renders Jobs page at /jobs", async () => {
    stubFetch();
    renderAt("/jobs");
    expect(await screen.findByRole("heading", { name: "Jobs" })).toBeInTheDocument();
  });

  it("redirects /knowledge to /knowledge/observations (Observed aliases)", async () => {
    stubFetch();
    renderAt("/knowledge/observations");
    expect(await screen.findByRole("heading", { name: "Observed aliases" })).toBeInTheDocument();
  });

  it("renders Providers under Administration at /providers", async () => {
    stubFetch();
    renderAt("/providers");
    expect(await screen.findByRole("heading", { name: /Administration — Providers/ })).toBeInTheDocument();
  });

  it("shows the brand sidebar, global search and footer", async () => {
    renderAt("/jobs");
    expect(screen.getAllByText("OpenMusicRepository").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("search")).toBeInTheDocument();
    // La línea del shell: borde inferior del header (darkgray, thin, inline).
    expect(screen.getByRole("banner").style.borderBottom).toContain("darkgray");
    expect(screen.getAllByText(/powered by OSAP/).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Home" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Explore" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Collaborators" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "How it works" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Support OSAP" }).length).toBeGreaterThan(0);
  });

  it("agrupa las secciones de Clasificación en el sidebar", async () => {
    renderAt("/jobs");
    fireEvent.click(await screen.findByRole("button", { name: "Classification" }));
    expect(screen.getByRole("link", { name: "Genres" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Catalogues" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Instruments" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ensembles" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Epochs" })).toBeInTheDocument();
  });
});
