// URL pública de Chorus. En desarrollo se sirve en `http://chorus-app` (Apache →
// /D:/Proyectos/AI_OSAP/Chorus/web); en producción define
// `VITE_CHORUS_URL=https://chorus.openmusicrepository.com`.
export function chorusBaseUrl(): string {
  const configured = import.meta.env.VITE_CHORUS_URL?.trim();
  if (configured) return configured.replace(/\/$/, "");
  return import.meta.env.PROD
    ? "https://chorus.openmusicrepository.com"
    : "http://chorus-app";
}

export function chorusHomeUrl(): string {
  return `${chorusBaseUrl()}/`;
}
