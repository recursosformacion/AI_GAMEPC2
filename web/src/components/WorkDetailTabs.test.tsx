import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RepresentationInfo, WorkInfo } from "../api/types";
import { I18nProvider } from "../i18n/I18n";
import { WorkDetailTabs } from "../components/WorkDetailTabs";
import { useResolution } from "../state/resolution";

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
    title: "Representation",
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

describe("WorkDetailTabs — resolve button", () => {
  beforeEach(() => {
    useResolution.setState({ session: null, loading: false, polling: false, error: null });
    vi.resetAllMocks();
  });

  it("shows acquire CTA when no usable representation exists", () => {
    renderTabs(baseWork, reps([false]));
    fireEvent.click(screen.getByRole("button", { name: "Representations" }));
    expect(screen.getByText("No usable file found")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resolve work" })).toBeInTheDocument();
  });

  it("shows find-better CTA when at least one usable representation exists", () => {
    renderTabs(baseWork, reps([true]));
    fireEvent.click(screen.getByRole("button", { name: "Representations" }));
    const texts = screen.getAllByText("Find better representations");
    expect(texts.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByRole("button", { name: "Find better representations" })).toBeInTheDocument();
  });

  it("starts a resolution session when CTA is clicked", async () => {
    const fakeSession = {
      session_id: "ses_test",
      status: "acquiring",
      query: "Ave Verum Corpus — Mozart",
      providers: ["imslp"],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 1800000).toISOString(),
    };

    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 202,
        json: () => Promise.resolve({ success: true, data: fakeSession }),
      } as Response),
    );

    renderTabs(baseWork, reps([false]));
    fireEvent.click(screen.getByRole("button", { name: "Representations" }));
    fireEvent.click(screen.getByRole("button", { name: "Resolve work" }));

    await waitFor(() => {
      const state = useResolution.getState();
      expect(state.session).not.toBeNull();
      expect(state.session?.status).toBe("acquiring");
    });
  });
});
