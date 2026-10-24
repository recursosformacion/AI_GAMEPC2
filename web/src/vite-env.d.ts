/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** ID de medición de Google Analytics 4 (p. ej. G-XXXXXXXXXX). */
  readonly VITE_GA_ID?: string;
  /** URL pública del aplicativo de vídeos (por defecto, http://localhost:8400). */
  readonly VITE_VIDEOS_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
