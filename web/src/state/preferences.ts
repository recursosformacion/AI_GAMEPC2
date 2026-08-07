import { create } from "zustand";
import type { Language } from "../i18n/translations";

const LANG_KEY = "osap.lang";
const THEME_KEY = "osap.theme";

function readLang(): Language {
  const stored = localStorage.getItem(LANG_KEY);
  if (stored === "es" || stored === "ca" || stored === "fr" || stored === "en" || stored === "de") {
    return stored;
  }
  return "en";
}

function readDark(): boolean {
  return localStorage.getItem(THEME_KEY) === "dark";
}

function applyTheme(dark: boolean): void {
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

interface PreferencesState {
  lang: Language;
  dark: boolean;
  setLang: (lang: Language) => void;
  toggleDark: () => void;
}

export const usePreferences = create<PreferencesState>((set) => {
  const dark = readDark();
  if (typeof document !== "undefined") {
    applyTheme(dark);
  }
  return {
    lang: readLang(),
    dark,
    setLang: (lang) => {
      localStorage.setItem(LANG_KEY, lang);
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
