import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { clearConsent, saveConsent } from "../consent/consent";
import { pushEvent, trackPageView } from "./gtm";

describe("analytics/gtm (gated por consentimiento)", () => {
  beforeEach(() => {
    window.dataLayer = [];
    localStorage.clear();
  });
  afterEach(() => {
    clearConsent();
  });

  it("no envía nada sin consentimiento de analítica", () => {
    trackPageView("/");
    pushEvent("search_submit", { query: "x" });
    expect(window.dataLayer).toHaveLength(0);
  });

  it("envía page_view con consentimiento", () => {
    saveConsent({ necessary: true, analytics: true });
    trackPageView("/composers/mozart");
    expect(window.dataLayer).toHaveLength(1);
    expect(window.dataLayer?.[0]).toMatchObject({ event: "page_view", page_path: "/composers/mozart" });
  });

  it("empuja eventos personalizados con consentimiento", () => {
    saveConsent({ necessary: true, analytics: true });
    pushEvent("search_submit", { query: "ave verum" });
    expect(window.dataLayer?.[0]).toMatchObject({ event: "search_submit", query: "ave verum" });
  });
});
