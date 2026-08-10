// AuthClient: único acceso del Web a osap-auth (login/refresh de usuario).
//
// Los endpoints de osap-auth devuelven sus propios errores ({ detail }) y no usan el
// envelope de osap-api. Aquí se normalizan a ApiError (code/message).

import { ApiError } from "./errors";
import type { AuthSession } from "./types";

// URL base de osap-auth. En dev apunta al servicio local; en producción debe servirse a
// través de un proxy inverso que exponga /auth/* (CORS o proxy).
export const AUTH_BASE_URL = "http://127.0.0.1:8200";

interface AuthErrorDetail {
  detail?: string | { msg?: string }[];
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

  async refresh(refreshToken: string): Promise<AuthSession> {
    return this.post<AuthSession>("/auth/refresh", { refresh_token: refreshToken });
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
    }
    throw new ApiError(response.status === 401 ? "UNAUTHORIZED" : "AUTH_ERROR", message);
  }
}

export const authClient = new AuthClient();
