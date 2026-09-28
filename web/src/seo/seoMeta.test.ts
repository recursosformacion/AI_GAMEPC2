import { describe, expect, it } from "vitest";
import { seoMetaForPath } from "./seoMeta";

describe("seoMetaForPath", () => {
  it("marca noindex las herramientas internas", () => {
    expect(seoMetaForPath("/studio").robots).toBe("noindex, nofollow");
    expect(seoMetaForPath("/admin/users").robots).toBe("noindex, nofollow");
    expect(seoMetaForPath("/viewer").robots).toBe("noindex, nofollow");
    expect(seoMetaForPath("/composer").robots).toBe("noindex, nofollow");
    expect(seoMetaForPath("/candidates", "?q=mozart").robots).toBe("noindex, nofollow");
  });

  it("no confunde /composer (búsqueda) con /composers (listado)", () => {
    expect(seoMetaForPath("/composer").robots).toBe("noindex, nofollow");
    expect(seoMetaForPath("/composers").robots).toBe("index, follow");
    expect(seoMetaForPath("/composers/person-1").robots).toBe("index, follow");
  });

  it("indexa portada y páginas públicas", () => {
    expect(seoMetaForPath("/").robots).toBe("index, follow");
    expect(seoMetaForPath("/about/how-it-works").robots).toBe("index, follow");
  });

  it("da título propio a las rutas conocidas y hereda en subrutas", () => {
    expect(seoMetaForPath("/composers").title).toContain("Compositores");
    expect(seoMetaForPath("/composers/person-1").title).toContain("Compositores");
    expect(seoMetaForPath("/ruta-desconocida").title).toContain("OpenMusicRepository");
  });

  it("canonical sin query ni barra final", () => {
    expect(seoMetaForPath("/composers/").canonicalPath).toBe("/composers");
    expect(seoMetaForPath("/").canonicalPath).toBe("/");
    expect(seoMetaForPath("/explore").canonicalPath).toBe("/explore");
  });
});
