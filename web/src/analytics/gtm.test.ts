import { beforeEach, describe, expect, it } from "vitest";

import { pushEvent, trackPageView } from "./gtm";

describe("analytics/gtm", () => {
  beforeEach(() => {
    window.dataLayer = [];
  });

  it("envía page_view a dataLayer", () => {
    trackPageView("/composers/mozart");
    expect(window.dataLayer).toHaveLength(1);
    expect(window.dataLayer?.[0]).toMatchObject({ event: "page_view", page_path: "/composers/mozart" });
  });

  it("empuja eventos personalizados", () => {
    pushEvent("search_submit", { query: "ave verum" });
    expect(window.dataLayer?.[0]).toMatchObject({ event: "search_submit", query: "ave verum" });
  });
});
