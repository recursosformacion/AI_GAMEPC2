// URL pública del blog independiente. En desarrollo se sirve en `http://osap-blog`
// (VirtualHost de Apache → uvicorn 8500); en producción el build define
// `VITE_BLOG_URL=https://blog.openmusicrepository.com`.
export function blogBaseUrl(): string {
  const configured = import.meta.env.VITE_BLOG_URL?.trim();
  if (configured) return configured.replace(/\/$/, "");
  return "http://osap-blog";
}

export function blogHomeUrl(): string {
  return `${blogBaseUrl()}/`;
}

// Entrada con handoff de sesión de OSAP: el blog valida el token contra `/auth/me`
// y deja una cookie HttpOnly antes de redirigir a la portada pública.
export function blogSessionUrl(
  token?: string | null,
  refreshToken?: string | null,
  next = "/",
): string {
  const base = blogBaseUrl();
  // Sin sesión no hay handoff: siempre a la portada pública, nunca a /admin.
  if (!token) return `${base}/`;
  const params = new URLSearchParams({ token, next });
  if (refreshToken) params.set("refresh_token", refreshToken);
  return `${base}/auth/session?${params.toString()}`;
}
