import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import type { AppNotification } from "../api/types";

// Campana de la app: bandeja del usuario (y avisos globales si es admin). Sin login la API
// devuelve 401 y se deja la bandeja vacía.
interface NotificationsState {
  items: AppNotification[];
  unread: number;
  load: () => Promise<void>;
  markRead: (id: number) => Promise<void>;
  markAll: () => Promise<void>;
}

export const useNotifications = create<NotificationsState>((set, get) => ({
  items: [],
  unread: 0,
  load: async () => {
    try {
      const data = await apiClient.getNotifications();
      set({ items: data.items, unread: data.unread });
    } catch {
      set({ items: [], unread: 0 });
    }
  },
  markRead: async (id) => {
    try {
      await apiClient.markNotificationRead(id);
      set({
        items: get().items.map((item) =>
          item.id === id && item.read_at === null
            ? { ...item, read_at: new Date().toISOString() }
            : item,
        ),
        unread: Math.max(0, get().unread - 1),
      });
    } catch {
      /* sin sesión o sin permiso: se ignora */
    }
  },
  markAll: async () => {
    try {
      await apiClient.markAllNotificationsRead();
      const now = new Date().toISOString();
      set({
        items: get().items.map((item) => ({ ...item, read_at: item.read_at ?? now })),
        unread: 0,
      });
    } catch {
      /* idem */
    }
  },
}));
