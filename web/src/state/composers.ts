// Estado de Compositores (consulta pública + fusión admin).
// Todo pasa por osap-api; la UI nunca accede directamente a osap-storage.

import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { ComposerDetail, ComposerList, ComposerSummary, ComposerWorks, MergeComposersResult } from "../api/types";

interface ComposersState {
  list: ComposerList | null;
  detail: ComposerDetail | null;
  biography: ComposerDetail | null;
  works: ComposerWorks | null;
  loading: boolean;
  error: ApiError | null;
  q: string;
  limit: number;
  offset: number;
  review: string | null;
  visible: string;
  setQuery: (q: string) => void;
  setReview: (review: string | null) => void;
  setVisible: (visible: string) => void;
  fetchList: (q: string, limit: number, offset: number, review: string | null, visible?: string) => Promise<void>;
  fetchDetail: (id: string) => Promise<void>;
  fetchBiography: (id: string) => Promise<void>;
  fetchWorks: (id: string, limit: number, offset: number) => Promise<void>;
  merge: (targetId: string, sourceIds: string[]) => Promise<void>;
  createComposer: (name: string) => Promise<ComposerSummary>;
  reviewComposer: (composerId: string, reviewStatus: string) => Promise<void>;
  addAlias: (composerId: string, alias: string) => Promise<void>;
  moveAlias: (composerId: string, aliasId: number, targetComposerId: string) => Promise<void>;
  promoteAlias: (composerId: string, aliasId: number) => Promise<void>;
  setAttribution: (composerIds: string[], attributionType: string) => Promise<number>;
}

export const useComposers = create<ComposersState>((set, get) => ({
  list: null,
  detail: null,
  biography: null,
  works: null,
  loading: false,
  error: null,
  q: "",
  limit: 50,
  offset: 0,
  review: null,
  visible: "visible",
  setQuery: (q) => set({ q }),
  setReview: (review) => set({ review }),
  setVisible: (visible) => set({ visible }),
  fetchList: async (q, limit, offset, review, visible = "visible") => {
    set({ loading: true, error: null });
    try {
      const list = await apiClient.getComposers(q, limit, offset, review ?? undefined, visible);
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
  fetchBiography: async (id) => {
    set({ loading: true, error: null });
    try {
      const biography = await apiClient.getComposerBiography(id);
      set({ biography, loading: false, error: null });
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
  createComposer: async (name) => {
    return apiClient.createComposer(name);
  },
  reviewComposer: async (composerId, reviewStatus) => {
    set({ loading: true, error: null });
    try {
      await apiClient.reviewComposer(composerId, reviewStatus);
      const { q, limit, offset, review, visible } = get();
      await get().fetchList(q, limit, offset, review, visible);
      set({ loading: false, error: null });
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
  addAlias: async (composerId, alias) => {
    set({ loading: true, error: null });
    try {
      await apiClient.addAlias(composerId, alias);
      await get().fetchDetail(composerId);
      set({ loading: false, error: null });
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
  moveAlias: async (composerId, aliasId, targetComposerId) => {
    set({ loading: true, error: null });
    try {
      await apiClient.moveAlias(composerId, aliasId, targetComposerId);
      await get().fetchDetail(composerId);
      set({ loading: false, error: null });
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
  promoteAlias: async (composerId, aliasId) => {
    set({ loading: true, error: null });
    try {
      await apiClient.promoteAlias(composerId, aliasId);
      await get().fetchDetail(composerId);
      set({ loading: false, error: null });
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
  setAttribution: async (composerIds, attributionType) => {
    set({ loading: true, error: null });
    try {
      const result = await apiClient.setAttribution(composerIds, attributionType);
      const { q, limit, offset, review, visible } = get();
      await get().fetchList(q, limit, offset, review, visible);
      set({ loading: false, error: null });
      return result.works_affected;
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
      return 0;
    }
  },
}));
