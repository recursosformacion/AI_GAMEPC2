import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const sources = [
  { source_id: "imslp", name: "IMSLP", type: "HTTP", origin: "Official", trust: "Verified", status: "Online", quality: 96, quality_label: "Excellent", updated_at: "" },
  { source_id: "cpdl", name: "CPDL", type: "Provider", origin: "www.cpdl.org", trust: "Community", status: "Defined", quality: 50, quality_label: "Pending", updated_at: "" },
  { source_id: "omr", name: "Open Music Repository", type: "Provider", origin: "storage.openmusicrepository.com", trust: "Verified", status: "Online", quality: 90, quality_label: "Excellent", updated_at: "" },
];

function stubFetch() {
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/repository-sources")) {
      return new Response(JSON.stringify({ success: true, request_id: "r", data: sources }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(JSON.stringify({ success: true, request_id: "r", data: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
  globalThis.fetch = fn as unknown as typeof fetch;
  return fn;
}

describe("Sources (V3.6.x)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("Sources shows only wired (Online) sources", async () => {
    stubFetch();
    render(
      <MemoryRouter initialEntries={["/sources"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("IMSLP")).toBeInTheDocument());
    expect(screen.getByText("Open Music Repository")).toBeInTheDocument();
    expect(screen.queryByText("CPDL")).not.toBeInTheDocument();
  });

  it("Discover shows only providers to connect (not wired)", async () => {
    stubFetch();
    render(
      <MemoryRouter initialEntries={["/discover"]}>
        <App />
      </MemoryRouter>,
    );
    // CPDL no está cableado → aparece como "providers to connect".
    await waitFor(() => expect(screen.getByText("CPDL")).toBeInTheDocument());
    // IMSLP está cableado (Online) → no debe aparecer en Descubrir.
    expect(screen.queryByText("IMSLP")).not.toBeInTheDocument();
  });
});
