import { describe, expect, it } from "vitest";
import { shareTargets } from "./ShareBar";

describe("shareTargets", () => {
  const url = "https://app.example/amigos/articulo/a1/titulo";
  const title = "Título & más";

  it("construye los enlaces de las redes principales", () => {
    const byKey = Object.fromEntries(shareTargets(url, title).map((t) => [t.key, t.href]));
    expect(byKey.facebook).toContain(encodeURIComponent(url));
    expect(byKey.linkedin).toContain(encodeURIComponent(url));
    expect(byKey.x).toContain(encodeURIComponent(url));
    expect(byKey.x).toContain(encodeURIComponent(title));
    expect(byKey.whatsapp).toContain(encodeURIComponent(url));
    expect(byKey.telegram).toContain(encodeURIComponent(url));
    expect(byKey.email?.startsWith("mailto:")).toBe(true);
  });

  it("no ofrece intención de Instagram (no existe): se cubre con copiar enlace", () => {
    expect(shareTargets(url, title).some((t) => t.key === "instagram")).toBe(false);
  });
});
