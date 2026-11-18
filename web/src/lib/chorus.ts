// URL pública de Chorus. En desarrollo se sirve en `http://chorus-app` (Apache →
// /D:/Proyectos/AI_OSAP/Chorus/web); en producción define
// `VITE_CHORUS_URL=https://chorus.openmusicrepository.com`.
export function chorusBaseUrl(): string {
  const configured = import.meta.env.VITE_CHORUS_URL?.trim();
  if (configured) return configured.replace(/\/$/, "");
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host === "osap-app" || host === "localhost" || host === "127.0.0.1") {
      return "http://chorus-app";
    }
  }
  return import.meta.env.PROD
    ? "https://chorus.openmusicrepository.com"
    : "http://chorus-app";
}

export function chorusHomeUrl(): string {
  return `${chorusBaseUrl()}/`;
}

export function chorusSessionUrl(
  token?: string | null,
  refreshToken?: string | null,
): string {
  const base = chorusBaseUrl();
  if (!token) return `${base}/`;
  const params = new URLSearchParams({ token });
  if (refreshToken) params.set("refresh_token", refreshToken);
  return `${base}/?${params.toString()}`;
}



