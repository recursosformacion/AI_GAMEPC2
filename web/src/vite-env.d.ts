/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** ID de medición de Google Analytics 4 (p. ej. G-XXXXXXXXXX). */
  readonly VITE_GA_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
