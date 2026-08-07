import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { RepositorySource, RepositorySourceSummary } from "./api/types";
import App from "./App";

const summary: RepositorySourceSummary = {
  source_id: "imslp",
  name: "IMSLP",
  type: "HTTP",
  origin: "Official",
  trust: "Verified",
  status: "Online",
  quality: 96,
  quality_label: "Excellent",
  updated_at: "2026-08-12",
};

const ficha: RepositorySource = {
  ...summary,
  representations: 128431,
  works: 38912,
  composers: 3281,
  formats: ["MusicXML", "PDF"],
  catalogues: ["BWV", "KV"],
  duplicate_percent: 1.2,
  coverage: ["Baroque"],
  capabilities: ["Search", "Download"],
  description: "Official repository.",
  license: "Public Domain",
  website: "https://imslp.org",
  contact: "",
  notes: "Good Mozart coverage.",
  observations: [{ date: "2026-07-18", text: "Issues with Händel." }],
  tags: ["Baroque", "Choral"],
  community_rating: 4,
  reviews: 27,
  searches: 3214,
  downloads: 9321,
  contributions: 42,
  availability: 99.8,
};

function stubFetch() {
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/repository-sources/imslp")) {
      return new Response(JSON.stringify({ success: true, request_id: "r", data: ficha }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.includes("/repository-sources")) {
      return new Response(JSON.stringify({ success: true, request_id: "r", data: [summary] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(
      JSON.stringify({ success: false, request_id: "r", error: { code: "NOT_FOUND", message: "x", details: {} } }),
      { status: 404, headers: { "Content-Type": "application/json" } },
    );
  });
  globalThis.fetch = fn as unknown as typeof fetch;
  return fn;
}

describe("Source Catalog (V3.6.x)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("lists repository sources", async () => {
    stubFetch();
    render(
      <MemoryRouter initialEntries={["/catalog"]}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByText("IMSLP")).toBeInTheDocument();
    expect(screen.getByText(/96\/100/)).toBeInTheDocument();
  });

  it("opens the ficha on click", async () => {
    stubFetch();
    render(
      <MemoryRouter initialEntries={["/catalog"]}>
        <App />
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByText("IMSLP"));
    expect(await screen.findByText("MusicXML")).toBeInTheDocument();
    expect(screen.getByText("BWV")).toBeInTheDocument();
    expect(screen.getByText(/Public Domain/)).toBeInTheDocument();
    expect(screen.getByText(/128431/)).toBeInTheDocument();
  });
});
