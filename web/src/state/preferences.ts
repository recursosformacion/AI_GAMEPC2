import { createSsrStore } from "./createSsrStore";
import type { Language } from "../i18n/translations";

const LANG_KEY = "osap.lang";
const THEME_KEY = "osap.theme";

const LANGUAGES: readonly Language[] = ["es", "ca", "fr", "en", "de"];

function isLanguage(value: string | null | undefined): value is Language {
  return value !== null && value !== undefined && (LANGUAGES as readonly string[]).includes(value);
}

function storage(): Storage | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    return null;
  }
}

// Si el usuario no ha elegido idioma, se usa el del navegador (primer idioma soportado);
// si el navegador no pide ninguno de los soportados, se mantiene el idioma por defecto.
function browserLang(): Language {
  if (typeof navigator === "undefined") return "es";
  const candidates = [navigator.language, ...(navigator.languages ?? [])];
  for (const candidate of candidates) {
    const primary = String(candidate).toLowerCase().split("-")[0];
    if (isLanguage(primary)) return primary;
  }
  return "en";
}

function writeCookie(name: string, value: string): void {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=31536000; SameSite=Lax`;
}

function readLang(): Language {
  // En SSR el idioma viene serializado por el servidor y manda sobre localStorage.
  const ssr = typeof window === "undefined" ? undefined : window.__OSAP_STATE__?.lang;
  if (isLanguage(ssr)) return ssr;
  // ?lang= (hreflang) tiene prioridad y se persiste.
  try {
    const fromUrl = new URLSearchParams(window.location.search).get("lang");
    if (isLanguage(fromUrl)) {
      storage()?.setItem(LANG_KEY, fromUrl);
      writeCookie(LANG_KEY, fromUrl);
      return fromUrl;
    }
  } catch {
    // sin acceso a window/URL: se ignora
  }
  const stored = storage()?.getItem(LANG_KEY) ?? null;
  if (isLanguage(stored)) return stored;
  return browserLang();
}

function readDark(): boolean {
  const ssr = typeof window === "undefined" ? undefined : window.__OSAP_STATE__?.dark;
  if (typeof ssr === "boolean") return ssr;
  return storage()?.getItem(THEME_KEY) === "dark";
}

function applyTheme(dark: boolean): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

function applyLang(lang: Language): void {
  if (typeof document === "undefined") return;
  document.documentElement.lang = lang;
}

interface PreferencesState {
  lang: Language;
  dark: boolean;
  setLang: (lang: Language) => void;
  toggleDark: () => void;
}

export const usePreferences = createSsrStore<PreferencesState>((set) => {
  const lang = readLang();
  const dark = readDark();
  if (typeof document !== "undefined") {
    applyTheme(dark);
    applyLang(lang);
  }
  return {
    lang,
    dark,
    setLang: (lang) => {
      storage()?.setItem(LANG_KEY, lang);
      writeCookie(LANG_KEY, lang);
      applyLang(lang);
      set({ lang });
    },
    toggleDark: () =>
      set((s) => {
        const next = !s.dark;
        storage()?.setItem(THEME_KEY, next ? "dark" : "light");
        writeCookie(THEME_KEY, next ? "dark" : "light");
        applyTheme(next);
        return { dark: next };
      }),
  };
});
