import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import { ApiError } from "../api/errors";
import type { PopularWorkList } from "../api/types";
import { initialAsync, type AsyncSlice } from "./async";

// «Obras más consultadas» de la portada. El servidor decide la métrica: consultas y, si
// aún no hay, descargas (`basis`). Un fallo de red degrada al estado vacío.
interface PopularWorksState {
  list: AsyncSlice<PopularWorkList>;
  load: () => Promise<void>;
}

export const usePopularWorks = create<PopularWorksState>((set) => ({
  list: initialAsync,
  load: async () => {
    set({ list: { data: null, loading: true, error: null } });
    try {
      const data = await apiClient.getPopularWorks(5);
      set({ list: { data, loading: false, error: null } });
    } catch (e) {
      set({
        list: {
          data: null,
          loading: false,
          error: e instanceof ApiError ? e : new ApiError("UNKNOWN", String(e)),
        },
      });
    }
  },
}));
