import { describe, expect, it } from "vitest";
import { htmlToText, textToHtml } from "./richtext";

describe("richText", () => {
  it("convierte texto plano en párrafos HTML", () => {
    expect(textToHtml("Hola\n\nMundo")).toBe("<p>Hola</p>\n<p>Mundo</p>");
  });

  it("escapa el marcado del texto plano", () => {
    expect(textToHtml("<b>x</b>")).toBe("<p>&lt;b&gt;x&lt;/b&gt;</p>");
  });

  it("conserva los bloques <style> al pasar a texto plano", () => {
    expect(htmlToText("<style>.a{color:red}</style><p>Hola</p>")).toBe(
      "<style>.a{color:red}</style>Hola",
    );
  });

  it("conserva los bloques <style> al pasar a HTML", () => {
    const html = textToHtml("<style>.a{color:red}</style>\n\nTexto");
    expect(html).toContain("<style>.a{color:red}</style>");
    expect(html).toContain("<p>Texto</p>");
  });
});
