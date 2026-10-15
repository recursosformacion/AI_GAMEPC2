import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { looksLikeHtml, useBodyMode } from "./useBodyMode";

describe("useBodyMode", () => {
  it("abre en modo Código si el cuerpo ya es HTML", () => {
    const { result } = renderHook(() => useBodyMode("<p>Hola</p>"));
    expect(result.current.mode).toBe("code");
  });

  it("no escapa el HTML al alternar Código → Texto → Código", () => {
    const html = '<style>.a{color:red}</style><div class="articulo-osap"><p>Hola</p></div>';
    const { result } = renderHook(() => useBodyMode(html));

    act(() => result.current.toggle());
    expect(result.current.mode).toBe("text");
    expect(result.current.body).not.toContain("&lt;");
    expect(result.current.body).not.toContain("<div");

    act(() => result.current.toggle());
    expect(result.current.mode).toBe("code");
    expect(result.current.body).toBe(html);
  });

  it("si el texto se edita, no restaura el HTML anterior", () => {
    const { result } = renderHook(() => useBodyMode("<p>Uno</p>"));
    act(() => result.current.toggle());
    act(() => result.current.setBody("Otro"));
    act(() => result.current.toggle());
    expect(result.current.body).toBe("<p>Otro</p>");
  });

  it("no envuelve en <p> un cuerpo que ya es HTML", () => {
    const { result } = renderHook(() => useBodyMode("<p>Hola</p>", "text"));
    act(() => result.current.toggle());
    expect(result.current.body).toBe("<p>Hola</p>");
  });

  it("looksLikeHtml detecta etiquetas HTML", () => {
    expect(looksLikeHtml("Hola\n\nmundo")).toBe(false);
    expect(looksLikeHtml("<p>x</p>")).toBe(true);
  });
});
