import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { KnowledgeFact, KnowledgeObservation, KnowledgeSuggestion } from "../api/types";
import { initialAsync, type AsyncSlice } from "./async";

interface ObservationsState extends AsyncSlice<KnowledgeObservation[]> {
  load: () => Promise<void>;
}
interface FactsState extends AsyncSlice<KnowledgeFact[]> {
  load: () => Promise<void>;
}
interface SuggestionsState extends AsyncSlice<KnowledgeSuggestion[]> {
  load: () => Promise<void>;
}

export const useObservations = create<ObservationsState>((set) => ({
  ...initialAsync,
  load: async () => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.get<KnowledgeObservation[]>("/knowledge/observations");
      set({ data, loading: false, error: null });
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
}));

export const useFacts = create<FactsState>((set) => ({
  ...initialAsync,
  load: async () => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.get<KnowledgeFact[]>("/knowledge/facts");
      set({ data, loading: false, error: null });
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
}));

export const useSuggestions = create<SuggestionsState>((set) => ({
  ...initialAsync,
  load: async () => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.get<KnowledgeSuggestion[]>("/knowledge/suggestions");
      set({ data, loading: false, error: null });
    } catch (e) {
      set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
    }
  },
}));
