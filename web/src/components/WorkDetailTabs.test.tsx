import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RepresentationInfo, RepresentationSelection, WorkInfo } from "../api/types";
import { I18nProvider } from "../i18n/I18n";
import { WorkDetailTabs } from "../components/WorkDetailTabs";

const baseWork: WorkInfo = {
  work_id: "w1",
  title: "Ave Verum Corpus",
  composer: "Mozart",
  catalogue: "KV 618",
};

function reps(available: boolean[]): RepresentationInfo[] {
  return available.map((a, i) => ({
    id: `r${i}`,
    provider: `provider-${i}`,
    format: a ? "musicxml" : "pdf",
    confidence: 0.9,
    available: a,
    title: `Representation ${i}`,
    url: a ? `https://storage.example/download/${i}.mxl` : undefined,
  }));
}

function renderTabs(work: WorkInfo, representations: RepresentationInfo[]) {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <I18nProvider lang="en" setLang={() => {}}>
        <WorkDetailTabs work={work} representations={representations} score={0.9} />
      </I18nProvider>
    </MemoryRouter>,
  );
}

function mockFetch(selectedPayload?: RepresentationSelection) {
  globalThis.fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/representations/selection") && (!init?.method || init.method === "GET")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            success: true,
            data: selectedPayload ?? {
              work_id: "w1",
              representations_known: 0,
              candidates_usable: 0,
              status: "none_selected",
              message: "Sin representación seleccionada.",
              selected: null,
            },
          }),
          { status: 200 },
        ),
      );
    }
    if (url.includes("/representations/select-best")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            success: true,
            data: selectedPayload ?? {
              work_id: "w1",
              representations_known: 1,
              candidates_usable: 1,
              status: "selected",
              message: "Representación seleccionada.",
              selected: {
                provider: "provider-0",
                format: "musicxml",
                url: "https://storage.example/download/0.mxl",
                quality_level: 2,
                reason: "mejor calidad",
              },
            },
          }),
          { status: 200 },
        ),
      );
    }
    return Promise.resolve(new Response(JSON.stringify({ success: true, data: {} }), { status: 200 }));
  }) as unknown as typeof fetch;
}

describe("WorkDetailTabs — select best known representation", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockFetch();
  });

  it("shows the selection action", () => {
    renderTabs(baseWork, reps([true, false]));
    fireEvent.click(screen.getByRole("button", { name: "Representations" }));
    expect(screen.getByRole("button", { name: "Find better representations" })).toBeInTheDocument();
    expect(screen.getByText(/No selected representation/)).toBeInTheDocument();
  });

  it("selects among KNOWN representations via the backend and shows the winner", async () => {
    const payload: RepresentationSelection = {
      work_id: "w1",
      representations_known: 2,
      candidates_usable: 1,
      status: "selected",
      message: "Representación seleccionada.",
      selected: {
        provider: "omr",
        format: "musicxml",
        url: "https://storage.example/download/1.mxl",
        title: "Ave verum corpus",
        quality_level: 2,
        reason: "mayor calidad",
      },
    };
    mockFetch(payload);
    renderTabs(baseWork, reps([true, true]));
    fireEvent.click(screen.getByRole("button", { name: "Representations" }));
    fireEvent.click(screen.getByRole("button", { name: "Find better representations" }));

    await waitFor(() => {
      expect(screen.getByText("Selected representation")).toBeInTheDocument();
    });
    expect(screen.getByText("Ave verum corpus")).toBeInTheDocument();
    const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
    expect(calls.some((u) => u.includes("/representations/select-best"))).toBe(true);
    // No acquisition session is created.
    expect(calls.some((u) => u.includes("/works/resolve"))).toBe(false);
  });

  it("keeps the button available to repeat after a selection", async () => {
    const payload: RepresentationSelection = {
      work_id: "w1",
      representations_known: 1,
      candidates_usable: 1,
      status: "selected",
      message: "Representación seleccionada.",
      selected: { provider: "omr", format: "musicxml", url: "https://x/1.mxl", quality_level: 2 },
    };
    mockFetch(payload);
    renderTabs(baseWork, reps([true]));
    fireEvent.click(screen.getByRole("button", { name: "Representations" }));
    const action = screen.getByRole("button", { name: "Find better representations" });
    fireEvent.click(action);
    await waitFor(() => expect(screen.getByText(/Selected representation/)).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Find better representations" })).toBeInTheDocument();
  });
});
