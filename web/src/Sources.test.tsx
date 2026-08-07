import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SessionSource } from "./api/types";
import App from "./App";

const session: SessionSource = {
  source_id: "src-1",
  name: "Mi carpeta",
  type: "Local",
  location: "/x",
  status: "USED",
  analysis: { formats: ["MusicXML", "PDF"] },
  created_at: "2026-08-06",
};

function stubFetch() {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.includes("/discover/sources")) {
      return new Response(
        JSON.stringify({
          success: true,
          request_id: "r",
          data: [{ source_id: "imslp", name: "IMSLP", type: "HTTP", origin: "Official", trust: "Verified", quality: 96, url: "" }],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    if (url.endsWith("/sources") && method === "POST") {
      return new Response(JSON.stringify({ success: true, request_id: "r", data: session }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.endsWith("/sources")) {
      return new Response(JSON.stringify({ success: true, request_id: "r", data: [session] }), {
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

  it("lets the user add and see a session source", async () => {
    const fetchMock = stubFetch();
    render(
      <MemoryRouter initialEntries={["/sources"]}>
        <App />
      </MemoryRouter>,
    );

    fireEvent.change(await screen.findByLabelText("name"), { target: { value: "Mi carpeta" } });
    fireEvent.click(screen.getByText("Add"));

    await waitFor(() => expect(screen.getByText("Mi carpeta")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/sources", expect.objectContaining({ method: "POST" }));
  });

  it("Discover shows suggested sources", async () => {
    stubFetch();
    render(
      <MemoryRouter initialEntries={["/discover"]}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByText("IMSLP")).toBeInTheDocument();
  });
});
