// Idioma por defecto: preferencia guardada > idioma del navegador > "en".
// El cambio de idioma también refleja el atributo `lang` del <html>.

import { afterEach, describe, expect, it, vi } from "vitest";

function stubBrowserLang(lang: string): void {
  Object.defineProperty(window.navigator, "language", { value: lang, configurable: true });
  Object.defineProperty(window.navigator, "languages", { value: [lang], configurable: true });
}

async function freshPreferences() {
  vi.resetModules();
  return (await import("./preferences")).usePreferences;
}

describe("preferences · idioma", () => {
  afterEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it("sin preferencia usa el idioma del navegador (con región)", async () => {
    localStorage.clear();
    stubBrowserLang("ca-ES");
    const store = await freshPreferences();
    expect(store.getState().lang).toBe("ca");
    expect(document.documentElement.lang).toBe("ca");
  });

  it("la preferencia guardada manda sobre el navegador", async () => {
    localStorage.setItem("osap.lang", "fr");
    stubBrowserLang("de-DE");
    const store = await freshPreferences();
    expect(store.getState().lang).toBe("fr");
  });

  it("un idioma no soportado cae al por defecto", async () => {
    localStorage.clear();
    stubBrowserLang("pt-BR");
    const store = await freshPreferences();
    expect(store.getState().lang).toBe("en");
  });

  it("setLang persiste y actualiza el html lang", async () => {
    localStorage.clear();
    stubBrowserLang("en-US");
    const store = await freshPreferences();
    store.getState().setLang("de");
    expect(localStorage.getItem("osap.lang")).toBe("de");
    expect(document.documentElement.lang).toBe("de");
  });
});
