import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { RecentWork } from "../api/types";
import { initialAsync, type AsyncSlice } from "./async";

// "Últimas novedades" de la portada: obras incorporadas/actualizadas recientemente en el
// catálogo. Un fallo de red degrada al estado vacío (la portada nunca debe romperse).
interface RecentWorksState {
  list: AsyncSlice<RecentWork[]>;
  load: () => Promise<void>;
}

export const useRecentWorks = create<RecentWorksState>((set) => ({
  list: initialAsync,
  load: async () => {
    set({ list: { data: null, loading: true, error: null } });
    try {
      const data = await apiClient.getRecentWorks(8);
      set({ list: { data: data.items, loading: false, error: null } });
    } catch (e) {
      set({
        list: { data: null, loading: false, error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)) },
      });
    }
  },
}));
