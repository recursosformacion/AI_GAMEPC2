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

describe("Routing and navigation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders Dashboard at /", () => {
    stubFetch();
    renderAt("/");
    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
  });

  it("renders Searches page at /searches", () => {
    stubFetch();
    renderAt("/searches");
    expect(screen.getByRole("heading", { name: "Searches" })).toBeInTheDocument();
    expect(screen.getByLabelText("query")).toBeInTheDocument();
  });

  it("renders Jobs page at /jobs", () => {
    stubFetch();
    renderAt("/jobs");
    expect(screen.getByRole("heading", { name: "Jobs" })).toBeInTheDocument();
  });

  it("redirects /knowledge to /knowledge/observations", () => {
    stubFetch();
    renderAt("/knowledge/observations");
    expect(screen.getByRole("heading", { name: /Knowledge.*Observations/ })).toBeInTheDocument();
  });

  it("renders Administration/Providers at /providers", () => {
    stubFetch();
    renderAt("/providers");
    expect(screen.getByRole("heading", { name: /Administration.*Providers/ })).toBeInTheDocument();
  });

  it("shows the layout (header, navigation, breadcrumb, footer)", () => {
    stubFetch();
    renderAt("/jobs");
    expect(screen.getByText("OSAP")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: /breadcrumb/ })).toBeInTheDocument();
    expect(screen.getByText(/Open Sheet Music Aggregation Platform/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Searches" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Jobs" })).toBeInTheDocument();
  });
});
