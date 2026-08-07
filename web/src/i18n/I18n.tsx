import { createContext, useContext, type ReactNode } from "react";
import type { Language, TKey } from "./translations";
import { translate } from "./translations";

interface I18nValue {
  lang: Language;
  setLang: (lang: Language) => void;
  t: (key: TKey) => string;
}

export const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({
  lang,
  setLang,
  children,
}: {
  lang: Language;
  setLang: (lang: Language) => void;
  children: ReactNode;
}) {
  const value: I18nValue = {
    lang,
    setLang,
    t: (key) => translate(lang, key),
  };
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (value === null) {
    throw new Error("useI18n must be used within I18nProvider");
  }
  return value;
}
