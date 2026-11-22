/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** ID de medición de Google Analytics 4 (p. ej. G-XXXXXXXXXX). */
  readonly VITE_GA_ID?: string;
  /** URL del aplicativo de vídeos en producción. */
  readonly VITE_VIDEOS_URL?: string;
  /** URL del aplicativo de vídeos en desarrollo (por defecto, http://localhost:8400). */
  readonly VITE_VIDEOS_DEV_URL?: string;
  /** URL pública del blog (por defecto, http://osap-blog). */
  readonly VITE_BLOG_URL?: string;
  /** URL del visor/reproductor MuseEncore (Chorus). */
  readonly VITE_MUSEENCORE_VIEWER_URL?: string;
  /** URL pública de Chorus (por defecto, http://chorus-app). */
  readonly VITE_CHORUS_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

