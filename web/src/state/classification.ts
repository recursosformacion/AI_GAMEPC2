import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { Catalogue, Ensemble, Genre, Instrument, InstrumentCategory } from "../api/types";
import { initialAsync, type AsyncSlice } from "./async";

// Stores de Clasificación (listados públicos). El orden lo fija el backend.
type ListSlice<T> = AsyncSlice<T[]> & { list: () => Promise<void> };

function makeListStore<T>(fetcher: () => Promise<T[]>) {
  return create<ListSlice<T>>((set) => ({
    ...initialAsync,
    list: async () => {
      set({ loading: true, error: null });
      try {
        const data = await fetcher();
        set({ data, loading: false, error: null });
      } catch (e) {
        set({ loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) });
      }
    },
  }));
}

export const useGenres = makeListStore<Genre>(() => apiClient.getGenres());
export const useCatalogues = makeListStore<Catalogue>(() => apiClient.getCatalogues());
export const useInstruments = makeListStore<Instrument>(() => apiClient.getInstruments());
export const useEnsembles = makeListStore<Ensemble>(() => apiClient.getEnsembles());

// Categorías de instrumentos: uso interno para agrupar; NO es una sección pública.
export const useInstrumentCategories = makeListStore<InstrumentCategory>(() =>
  apiClient.getInstrumentCategories(),
);
