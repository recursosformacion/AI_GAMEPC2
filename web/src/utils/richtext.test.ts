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

  it("convierte URLs sueltas y enlaces markdown en <a>", () => {
    expect(textToHtml("Ver https://osap.example")).toBe(
      '<p>Ver <a href="https://osap.example" rel="nofollow noopener">https://osap.example</a></p>',
    );
    expect(textToHtml("[Guía](https://x.org)")).toBe(
      '<p><a href="https://x.org" rel="nofollow noopener">Guía</a></p>',
    );
    expect(textToHtml("Fin https://x.org.")).toContain("</a>.");
  });

  it("no enlaza esquemas peligrosos", () => {
    expect(textToHtml("[malo](javascript:alert(1))")).toBe(
      "<p>[malo](javascript:alert(1))</p>",
    );
  });

  it("conserva los enlaces al volver a texto plano", () => {
    const html = textToHtml("Ver [Guía](https://x.org) y https://y.org");
    expect(htmlToText(html)).toBe("Ver [Guía](https://x.org) y https://y.org");
  });
});
