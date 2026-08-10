// Estado de Compositores (consulta pública + fusión admin).
// Todo pasa por osap-api; la UI nunca accede directamente a osap-storage.

import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { ComposerDetail, ComposerList, ComposerWorks, MergeComposersResult } from "../api/types";

interface ComposersState {
  list: ComposerList | null;
  detail: ComposerDetail | null;
  works: ComposerWorks | null;
  loading: boolean;
  error: ApiError | null;
  q: string;
  limit: number;
  offset: number;
  review: string | null;
  setQuery: (q: string) => void;
  setReview: (review: string | null) => void;
  fetchList: (q: string, limit: number, offset: number, review: string | null) => Promise<void>;
  fetchDetail: (id: string) => Promise<void>;
  fetchWorks: (id: string, limit: number, offset: number) => Promise<void>;
  merge: (targetId: string, sourceIds: string[]) => Promise<void>;
}

export const useComposers = create<ComposersState>((set, get) => ({
  list: null,
  detail: null,
  works: null,
  loading: false,
  error: null,
  q: "",
  limit: 50,
  offset: 0,
  review: null,
  setQuery: (q) => set({ q }),
  setReview: (review) => set({ review }),
  fetchList: async (q, limit, offset, review) => {
    set({ loading: true, error: null });
    try {
      const list = await apiClient.getComposers(q, limit, offset, review ?? undefined);
      set({ list, loading: false, error: null });
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
  fetchDetail: async (id) => {
    set({ loading: true, error: null });
    try {
      const detail = await apiClient.getComposer(id);
      set({ detail, loading: false, error: null });
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
  fetchWorks: async (id, limit, offset) => {
    try {
      const works = await apiClient.getComposerWorks(id, limit, offset);
      set({ works });
    } catch (e) {
      set({ error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
  merge: async (targetId, sourceIds) => {
    set({ loading: true, error: null });
    try {
      const result: MergeComposersResult = await apiClient.mergeComposers(targetId, sourceIds);
      // Tras una fusión, refresca el detalle y el listado.
      await get().fetchDetail(targetId);
      set({ loading: false, error: null, detail: get().detail ?? null });
      void result;
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
}));
