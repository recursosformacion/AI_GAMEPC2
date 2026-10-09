import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { clearConsent, saveConsent } from "../consent/consent";
import { initAnalytics } from "./ga";

function gaScripts(): HTMLScriptElement[] {
  return Array.from(document.querySelectorAll('script[src*="googletagmanager"]'));
}

describe("analytics/ga (carga condicionada al consentimiento)", () => {
  beforeEach(() => {
    localStorage.clear();
    gaScripts().forEach((s) => s.remove());
  });
  afterEach(() => {
    clearConsent();
    gaScripts().forEach((s) => s.remove());
  });

  it("no inyecta la librería de GA sin consentimiento", () => {
    initAnalytics();
    expect(gaScripts()).toHaveLength(0);
  });

  it("inyecta la librería de GA con consentimiento", () => {
    saveConsent({ necessary: true, analytics: true });
    initAnalytics();
    expect(gaScripts().length).toBeGreaterThan(0);
  });
});
