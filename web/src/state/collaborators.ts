import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { Collaborator } from "../api/types";
import { initialAsync, type AsyncSlice } from "./async";

interface CollaboratorsState extends AsyncSlice<Collaborator[]> {
  list: (project?: string) => Promise<void>;
}

// Colaboradores públicos: el backend ya agrupa por persona y ordena; aquí no se reordena.
export const useCollaborators = create<CollaboratorsState>((set) => ({
  ...initialAsync,
  list: async (project = "omr") => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.getCollaborators(project);
      set({ data, loading: false, error: null });
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
}));
