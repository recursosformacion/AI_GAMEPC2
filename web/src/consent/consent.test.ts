import { afterEach, describe, expect, it } from "vitest";

import { analyticsGranted, clearConsent, getConsent, saveConsent } from "./consent";

describe("consent", () => {
  afterEach(() => {
    clearConsent();
    localStorage.clear();
  });

  it("sin decisión no hay consentimiento", () => {
    clearConsent();
    expect(getConsent()).toBeNull();
    expect(analyticsGranted()).toBe(false);
  });

  it("guarda y lee la decisión (necesarias siempre activas)", () => {
    const granted = saveConsent({ necessary: true, analytics: true });
    expect(granted.categories.necessary).toBe(true);
    expect(analyticsGranted()).toBe(true);

    saveConsent({ necessary: true, analytics: false });
    expect(analyticsGranted()).toBe(false);
  });

  it("una versión antigua se considera sin decisión", () => {
    localStorage.setItem(
      "osap.consent.v1",
      JSON.stringify({ version: 0, decided_at: "x", categories: { necessary: true, analytics: true } }),
    );
    expect(getConsent()).toBeNull();
  });
});
