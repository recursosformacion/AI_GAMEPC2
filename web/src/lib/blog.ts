// URL pública del blog independiente. En desarrollo se sirve en `http://osap-blog`
// (VirtualHost de Apache → uvicorn 8500); en producción el build define
// `VITE_BLOG_URL=https://blog.openmusicrepository.com`.
export function blogBaseUrl(): string {
  const configured = import.meta.env.VITE_BLOG_URL?.trim();
  if (configured) return configured.replace(/\/$/, "");
  // Un build de producción sin variable no debe apuntar al host de desarrollo.
  return import.meta.env.PROD
    ? "https://blog.openmusicrepository.com"
    : "http://osap-blog";
}

export function blogHomeUrl(): string {
  return `${blogBaseUrl()}/`;
}

export function blogLogoutUrl(next: string): string {
  const params = new URLSearchParams({ next });
  return `${blogBaseUrl()}/logout?${params.toString()}`;
}

// Endpoint de handoff. Los tokens se envían en el cuerpo de un POST desde el
// navegador; nunca se incluyen en la URL, historial ni cabecera Referer.
export function blogSessionUrl(): string {
  return `${blogBaseUrl()}/auth/session`;
}
