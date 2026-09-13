// Identidad en la UI (login real con osap-auth).
//
// - access token: memoria (Zustand). No se persiste.
// - refresh token: localStorage (persiste tras recarga), con rotación.
// - Login/logout/refresh conforme a `_docs/account-login-v1-contract.md`.
//
// La autorización real la aplica osap-api. La UI solo usa `roles`/`email_verified` para
// presentación; nunca como decisión de seguridad. No se inventa `tier`.

import { create } from "zustand";
import { authClient } from "../api/AuthClient";
import { apiClient } from "../api/ApiClient";
import type { FrontendUser } from "../api/types";

const REFRESH_KEY = "osap.refresh_token";

type AuthStatus = "anonymous" | "authenticated" | "refreshing";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: FrontendUser | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<void>;
  completeOidc: (accessToken: string, refreshToken: string) => void;
  devLogin: () => Promise<boolean>;
  logout: () => void;
  refreshSession: () => Promise<boolean>;
  refreshProfile: () => Promise<void>;
  rehydrate: () => Promise<void>;
  isAuthenticated: () => boolean;
  isAdmin: () => boolean; // solo presentación
}

function decodeUser(accessToken: string): FrontendUser {
  try {
    const payload = accessToken.split(".")[1] ?? "";
    const padded = payload + "=".repeat((4 - (payload.length % 4)) % 4);
    const raw = JSON.parse(atob(padded.replace(/-/g, "+").replace(/_/g, "/"))) as {
      sub?: string;
      roles?: string[];
      email_verified?: boolean;
    };
    return {
      user_id: raw.sub ?? "unknown",
      roles: Array.isArray(raw.roles) ? raw.roles : ["user"],
      email_verified: raw.email_verified === true,
    };
  } catch {
    return { user_id: "unknown", roles: ["user"], email_verified: false };
  }
}

let refreshInFlight: Promise<boolean> | null = null;

// El JWT no lleva nombre/email (privacidad); el perfil se pide a /auth/me y se fusiona.
async function loadProfile(accessToken: string): Promise<Partial<FrontendUser>> {
  try {
    const profile = await authClient.me(accessToken);
    return {
      name: profile.name ?? undefined,
      email: profile.email ?? undefined,
      roles: Array.isArray(profile.roles) && profile.roles.length > 0 ? profile.roles : undefined,
    };
  } catch {
    return {};
  }
}

export const useAuth = create<AuthState>((set, get) => ({
  accessToken: null,
  refreshToken: null,
  user: null,
  status: "anonymous",

  login: async (email, password) => {
    set({ status: "refreshing" });
    try {
      const session = await authClient.login(email, password);
      localStorage.setItem(REFRESH_KEY, session.refresh_token);
      const profile = await loadProfile(session.access_token);
      set({
        accessToken: session.access_token,
        refreshToken: session.refresh_token,
        user: { ...decodeUser(session.access_token), ...profile },
        status: "authenticated",
      });
    } catch (error) {
      set({ status: "anonymous" });
      throw error;
    }
  },

  logout: () => {
    localStorage.removeItem(REFRESH_KEY);
    set({ accessToken: null, refreshToken: null, user: null, status: "anonymous" });
  },

  // Sesión admin de desarrollo (solo con OSAP_DEV_AUTH_BYPASS activo en osap-api).
  devLogin: async () => {
    try {
      const session = await apiClient.devSession();
      localStorage.setItem(REFRESH_KEY, session.refresh_token);
      set({
        accessToken: session.access_token,
        refreshToken: session.refresh_token,
        user: decodeUser(session.access_token),
        status: "authenticated",
      });
      return true;
    } catch {
      return false;
    }
  },

  // Sesión obtenida tras el callback OIDC (osap-api devolvió access+refresh a la SPA).
  completeOidc: (accessToken, refreshToken) => {
    localStorage.setItem(REFRESH_KEY, refreshToken);
    set({
      accessToken,
      refreshToken,
      user: decodeUser(accessToken),
      status: "authenticated",
    });
    void get().refreshProfile();
  },

  refreshProfile: async () => {
    const token = get().accessToken;
    if (!token) return;
    const profile = await loadProfile(token);
    const current = get().user;
    if (current && Object.keys(profile).length > 0) {
      set({ user: { ...current, ...profile } });
    }
  },

  refreshSession: async () => {
    // Single-flight: si ya hay un refresh en curso, se reutiliza (evita que la
    // rotación del refresh token genere 401 en llamadas concurrentes y cierre sesión).
    if (refreshInFlight) {
      return refreshInFlight;
    }
    refreshInFlight = (async () => {
      const refreshToken = get().refreshToken;
      if (!refreshToken) {
        get().logout();
        return false;
      }
      set({ status: "refreshing" });
      try {
        const session = await authClient.refresh(refreshToken);
        // Rotación: se guarda SIEMPRE el nuevo refresh (el anterior queda consumido).
        localStorage.setItem(REFRESH_KEY, session.refresh_token);
        set({
          accessToken: session.access_token,
          refreshToken: session.refresh_token,
          user: decodeUser(session.access_token),
          status: "authenticated",
        });
        void get().refreshProfile();
        return true;
      } catch {
        get().logout();
        return false;
      }
    })();
    try {
      return await refreshInFlight;
    } finally {
      refreshInFlight = null;
    }
  },

  rehydrate: async () => {
    const refreshToken = localStorage.getItem(REFRESH_KEY);
    if (!refreshToken) {
      set({ status: "anonymous" });
      return;
    }
    set({ refreshToken });
    await get().refreshSession();
  },

  isAuthenticated: () => get().status === "authenticated",
  isAdmin: () => (get().user?.roles ?? []).includes("admin"),
}));

// ApiClient usa esta sesión para adjuntar el Bearer y para el refresh/retry ante 401.
apiClient.setAuthHandler({
  getToken: () => useAuth.getState().accessToken,
  refresh: () => useAuth.getState().refreshSession(),
  logout: () => useAuth.getState().logout(),
});
