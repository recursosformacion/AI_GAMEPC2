// Test del panel de revisión de propuestas de atribución IA.
//
// La SPA no contiene lógica de IA: se simula el backend (osap-api → osap-storage) y se
// verifica el contrato de la pantalla: pestañas por estado, acciones de revisión y mensajes
// de error (IA no configurada / propuesta no asignable).

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/errors";
import type { WorkAiProposal } from "../api/types";
import { AdminWorkPersonAiPage } from "./AdminWorkPersonAiPage";

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  detail: vi.fn(),
  review: vi.fn(),
  storage: vi.fn(),
}));

vi.mock("../api/ApiClient", () => ({
  apiClient: {
    listWorkAttributionProposals: mocks.list,
    getWorkAttributionProposal: mocks.detail,
    reviewWorkAttributionProposal: mocks.review,
    getStorageWebUrl: mocks.storage,
  },
}));

const PROPOSAL: WorkAiProposal = {
  id: 1,
  work_id: 310455,
  resolution: "identified",
  person_match: "matched",
  candidate_person_id: "p1",
  candidate_name: "Louise Farrenc",
  role_name: "Compositor/a",
  status: "pending",
  confidence: 0.96,
  model: "gemini-2.5-flash",
  evidence_json: '[{"type":"source_metadata","text":"PDMX"}]',
};

function renderPage(): void {
  render(
    <MemoryRouter initialEntries={["/admin/work-person-ai"]}>
      <AdminWorkPersonAiPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.list.mockResolvedValue({ items: [PROPOSAL], total: 1 });
  mocks.detail.mockResolvedValue(PROPOSAL);
  mocks.review.mockResolvedValue({ id: 1, status: "accepted" });
  mocks.storage.mockResolvedValue({ url: "https://storage.example/admin?token=x" });
});

describe("AdminWorkPersonAiPage", () => {
  it("carga las propuestas pendientes con su evidencia", async () => {
    renderPage();
    expect((await screen.findAllByText(/Obra #310455/)).length).toBeGreaterThan(0);
    expect(mocks.list).toHaveBeenCalledWith("pending", 50, 0);
    expect(screen.getByText(/Persona: Louise Farrenc/)).toBeTruthy();
    expect(screen.getByText(/source_metadata: PDMX/)).toBeTruthy();
  });

  it("la pestaña Aceptadas filtra por ese estado", async () => {
    renderPage();
    await screen.findAllByText(/Obra #310455/);
    fireEvent.click(screen.getByRole("button", { name: "Aceptadas" }));
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith("accepted", 50, 0));
  });

  it("Aceptar revisa la propuesta con action=accept", async () => {
    renderPage();
    await screen.findAllByText(/Obra #310455/);
    fireEvent.click(screen.getByRole("button", { name: "Aceptar" }));
    await waitFor(() => expect(mocks.review).toHaveBeenCalledWith(1, "accept"));
  });

  it("marca dudosa sin asignar nada", async () => {
    renderPage();
    await screen.findAllByText(/Obra #310455/);
    fireEvent.click(screen.getByRole("button", { name: "Marcar dudosa" }));
    await waitFor(() => expect(mocks.review).toHaveBeenCalledWith(1, "uncertain"));
  });

  it("muestra el detalle de la propuesta al desplegarlo", async () => {
    renderPage();
    await screen.findAllByText(/Obra #310455/);
    fireEvent.click(screen.getByRole("button", { name: "Ver detalle" }));
    await waitFor(() => expect(mocks.detail).toHaveBeenCalledWith(1));
    expect((await screen.findAllByText(/prompt:/)).length).toBeGreaterThan(0);
  });

  it("si la IA no está configurada muestra un mensaje claro", async () => {
    renderPage();
    await screen.findAllByText(/Obra #310455/);
    mocks.review.mockRejectedValue(new ApiError("AI_NOT_CONFIGURED", "IA no configurada"));
    fireEvent.click(screen.getByRole("button", { name: "Aceptar" }));
    expect(await screen.findByText(/IA no configurada en storage/)).toBeTruthy();
  });

  it("aceptar una propuesta sin persona resuelta avisa sin asignar", async () => {
    renderPage();
    await screen.findAllByText(/Obra #310455/);
    mocks.review.mockRejectedValue(new ApiError("PROPOSAL_NOT_ASSIGNABLE", "requires matched"));
    fireEvent.click(screen.getByRole("button", { name: "Aceptar" }));
    expect(await screen.findByText(/no está resuelta/)).toBeTruthy();
  });

  it("el botón Obras → Personas abre la sección de storage", async () => {
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    renderPage();
    await screen.findAllByText(/Obra #310455/);
    fireEvent.click(screen.getByRole("button", { name: "Obras → Personas" }));
    await waitFor(() => expect(mocks.storage).toHaveBeenCalledWith("work-persons"));
    expect(open).toHaveBeenCalled();
    open.mockRestore();
  });
});
