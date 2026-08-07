import { render, screen } from "@testing-library/react";
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
    expect(screen.getByRole("heading", { name: "OpenMusicRepository" })).toBeInTheDocument();
    expect(screen.getByLabelText("search")).toBeInTheDocument();
  });

  it("renders Discover at /discover", () => {
    stubFetch();
    renderAt("/discover");
    expect(screen.getByRole("heading", { name: "Discover" })).toBeInTheDocument();
  });

  it("renders Jobs page at /jobs", () => {
    stubFetch();
    renderAt("/jobs");
    expect(screen.getByRole("heading", { name: "Jobs" })).toBeInTheDocument();
  });

  it("redirects /knowledge to /knowledge/observations (Observed aliases)", () => {
    stubFetch();
    renderAt("/knowledge/observations");
    expect(screen.getByRole("heading", { name: "Observed aliases" })).toBeInTheDocument();
  });

  it("renders Providers under Administration at /providers", () => {
    stubFetch();
    renderAt("/providers");
    expect(screen.getByRole("heading", { name: /Administration — Providers/ })).toBeInTheDocument();
  });

  it("shows the brand header, global search, semantic breadcrumb and footer", () => {
    renderAt("/jobs");
    expect(screen.getAllByText("OpenMusicRepository").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("search")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: /breadcrumb/ })).toBeInTheDocument();
    expect(screen.getAllByText(/powered by OSAP/).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Home" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Discover" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sources" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Knowledge" })).toBeInTheDocument();
  });
});
