// Identidad en la UI (navegación de autenticación).
//
// Refleja el estado de sesión del usuario en el cliente. La autorización real siempre se
// aplica en el backend (osap-api); la UI solo decide qué acciones mostrar. `role=admin`
// decide las acciones administrativas, nunca el `tier`.
//
// La integración de login/logout debe respetar el contrato de osap-auth; aquí solo se
// gestiona el token en el cliente (no un sistema de sesión paralelo).

import { create } from "zustand";
import { apiClient } from "../api/ApiClient";
import type { FrontendUser } from "../api/types";

interface AuthState {
  token: string | null;
  user: FrontendUser | null;
  login: (token: string) => void;
  logout: () => void;
  isAdmin: () => boolean;
}

function decodeUser(token: string): FrontendUser {
  try {
    const payload = token.split(".")[1] ?? "";
    const padded = payload + "=".repeat((4 - (payload.length % 4)) % 4);
    const raw = JSON.parse(atob(padded.replace(/-/g, "+").replace(/_/g, "/"))) as {
      sub?: string;
      roles?: string[];
    };
    return { user_id: raw.sub ?? "unknown", roles: Array.isArray(raw.roles) ? raw.roles : ["user"] };
  } catch {
    return { user_id: "unknown", roles: ["user"] };
  }
}

export const useAuth = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  login: (token: string) => {
    const user = decodeUser(token);
    apiClient.setToken(token);
    set({ token, user });
  },
  logout: () => {
    apiClient.setToken(null);
    set({ token: null, user: null });
  },
  isAdmin: () => (get().user?.roles ?? []).includes("admin"),
}));
