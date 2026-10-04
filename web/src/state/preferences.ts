import { create } from "zustand";
import type { Language } from "../i18n/translations";

const LANG_KEY = "osap.lang";
const THEME_KEY = "osap.theme";

const LANGUAGES: readonly Language[] = ["es", "ca", "fr", "en", "de"];

function isLanguage(value: string | null | undefined): value is Language {
  return value !== null && value !== undefined && (LANGUAGES as readonly string[]).includes(value);
}

// Si el usuario no ha elegido idioma, se usa el del navegador (primer idioma soportado);
// si el navegador no pide ninguno de los soportados, se mantiene el idioma por defecto.
function browserLang(): Language {
  if (typeof navigator === "undefined") return "en";
  const candidates = [navigator.language, ...(navigator.languages ?? [])];
  for (const candidate of candidates) {
    const primary = String(candidate).toLowerCase().split("-")[0];
    if (isLanguage(primary)) return primary;
  }
  return "en";
}

function readLang(): Language {
  const stored = localStorage.getItem(LANG_KEY);
  if (isLanguage(stored)) return stored;
  return browserLang();
}

function readDark(): boolean {
  return localStorage.getItem(THEME_KEY) === "dark";
}

function applyTheme(dark: boolean): void {
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

function applyLang(lang: Language): void {
  document.documentElement.lang = lang;
}

interface PreferencesState {
  lang: Language;
  dark: boolean;
  setLang: (lang: Language) => void;
  toggleDark: () => void;
}

export const usePreferences = create<PreferencesState>((set) => {
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
      localStorage.setItem(LANG_KEY, lang);
      applyLang(lang);
      set({ lang });
    },
    toggleDark: () =>
      set((s) => {
        const next = !s.dark;
        localStorage.setItem(THEME_KEY, next ? "dark" : "light");
        applyTheme(next);
        return { dark: next };
      }),
  };
});
