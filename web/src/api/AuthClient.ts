// AuthClient: único acceso del Web a osap-auth (login/refresh de usuario).
//
// Los endpoints de osap-auth devuelven sus propios errores ({ detail }) y no usan el
// envelope de osap-api. Aquí se normalizan a ApiError (code/message).

import { ApiError } from "./errors";
import type {
  AuthSession,
  EntityKind,
  EntityListItem,
  EntityMembership,
  EntityRequest,
} from "./types";

// URL base de osap-auth. En dev/prod el Web llama a /auth a través del mismo origen
// (proxy inverso de osap-app → osap-auth), evitando CORS.
export const AUTH_BASE_URL = "";

interface AuthErrorDetail {
  detail?: string | { msg?: string }[];
}

export interface UserProfile {
  user_id: string;
  email: string;
  name: string | null;
  nickname?: string | null;
  phone?: string | null;
  roles: string[];
  email_verified: boolean;
  status: string;
  memberships?: EntityMembership[];
}

export class AuthClient {
  private readonly baseUrl: string;
  private readonly fetcher: typeof fetch | undefined;

  constructor(baseUrl: string = AUTH_BASE_URL, fetcher?: typeof fetch) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.fetcher = fetcher;
  }

  async login(email: string, password: string): Promise<AuthSession> {
    return this.post<AuthSession>("/auth/login", { email, password });
  }

  /** Actualiza el nombre local y, opcionalmente, el nickname. */
  async updateMe(accessToken: string, name: string, nickname?: string): Promise<UserProfile> {
    const fetchImpl = this.fetcher ?? globalThis.fetch;
    let response: Response;
    try {
      response = await fetchImpl.call(globalThis, `${this.baseUrl}/auth/me`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name, ...(nickname ? { nickname } : {}) }),
      });
    } catch (cause) {
      throw new ApiError("NETWORK", "Auth service unreachable", { cause: String(cause) });
    }
    if (!response.ok) {
      throw new ApiError(response.status === 401 ? "UNAUTHORIZED" : "AUTH_ERROR", "Profile unavailable");
    }
    return (await response.json()) as UserProfile;
  }

  async refresh(refreshToken: string): Promise<AuthSession> {
    return this.post<AuthSession>("/auth/refresh", { refresh_token: refreshToken });
  }

  /** Teléfono voluntario para WhatsApp (`null` o vacío lo borra). */
  async updatePhone(accessToken: string, phone: string | null): Promise<UserProfile> {
    return this.send<UserProfile>("PUT", "/auth/me/phone", accessToken, { phone });
  }

  async listEntities(accessToken: string): Promise<EntityListItem[]> {
    return this.send<EntityListItem[]>("GET", "/auth/entities", accessToken);
  }

  async updateMyEntity(
    accessToken: string,
    input: {
      action: "join" | "leave" | "represent";
      entity_id?: string;
      entity_name?: string;
      entity_kind?: EntityKind;
    },
  ): Promise<UserProfile> {
    return this.send<UserProfile>("PUT", "/auth/me/entity", accessToken, input);
  }

  async listEntityRequests(accessToken: string): Promise<EntityRequest[]> {
    return this.send<EntityRequest[]>("GET", "/auth/me/entity-requests", accessToken);
  }

  async decideEntityRequest(
    accessToken: string,
    id: string,
    action: "approve" | "reject",
  ): Promise<{ message: string }> {
    return this.send<{ message: string }>(
      "POST",
      `/auth/me/entity-requests/${encodeURIComponent(id)}/decision`,
      accessToken,
      { action },
    );
  }

  /** Perfil del usuario (nombre/email quedan fuera del JWT por privacidad). */
  async me(accessToken: string): Promise<UserProfile> {
    const fetchImpl = this.fetcher ?? globalThis.fetch;
    let response: Response;
    try {
      response = await fetchImpl.call(globalThis, `${this.baseUrl}/auth/me`, {
        method: "GET",
        headers: { Authorization: `Bearer ${accessToken}` },
      });
    } catch (cause) {
      throw new ApiError("NETWORK", "Auth service unreachable", { cause: String(cause) });
    }
    if (!response.ok) {
      throw new ApiError(response.status === 401 ? "UNAUTHORIZED" : "AUTH_ERROR", "Profile unavailable");
    }
    return (await response.json()) as UserProfile;
  }

  private async send<T>(
    method: string,
    path: string,
    accessToken: string,
    body?: unknown,
  ): Promise<T> {
    const fetchImpl = this.fetcher ?? globalThis.fetch;
    let response: Response;
    try {
      response = await fetchImpl.call(globalThis, `${this.baseUrl}${path}`, {
        method,
        headers: {
          Authorization: `Bearer ${accessToken}`,
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (cause) {
      throw new ApiError("NETWORK", "Auth service unreachable", { cause: String(cause) });
    }
    if (!response.ok) {
      throw new ApiError(
        response.status === 401 ? "UNAUTHORIZED" : "AUTH_ERROR",
        "Auth request failed",
      );
    }
    return (await response.json()) as T;
  }

  private async post<T>(path: string, body: unknown): Promise<T> {
    const fetchImpl = this.fetcher ?? globalThis.fetch;
    let response: Response;
    try {
      response = await fetchImpl.call(globalThis, `${this.baseUrl}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch (cause) {
      throw new ApiError("NETWORK", "Auth service unreachable", { cause: String(cause) });
    }

    let data: AuthErrorDetail | null = null;
    try {
      data = (await response.json()) as AuthErrorDetail;
    } catch {
      data = null;
    }

    if (response.ok) {
      return data as unknown as T;
    }

    const detail = data?.detail;
    let message = "Authentication failed";
    if (typeof detail === "string") {
      message = detail;
    } else if (Array.isArray(detail) && detail[0] && typeof detail[0].msg === "string") {
      message = detail[0].msg;
    } else if (response.status >= 500) {
      message = "Auth service unavailable";
    }
    throw new ApiError(response.status === 401 ? "UNAUTHORIZED" : "AUTH_ERROR", message);
  }
}

export const authClient = new AuthClient();
