import { describe, expect, it } from "vitest";
import { genresToSearch } from "./studioGenre";

const OPTIONS = [
  "Música Clásica / Docta",
  "Música Sacra / Himnología",
  "Jazz y Blues",
  "Rock y Metal",
];

describe("genresToSearch (contrato SearchRequest.genres)", () => {
  it("sin selección = sin filtro (undefined)", () => {
    expect(genresToSearch({}, OPTIONS)).toBeUndefined();
    expect(genresToSearch({ "Jazz y Blues": false, "Rock y Metal": false }, OPTIONS)).toBeUndefined();
  });

  it("todas las familias seleccionadas = sin filtro (undefined)", () => {
    const all = Object.fromEntries(OPTIONS.map((o) => [o, true]));
    expect(genresToSearch(all, OPTIONS)).toBeUndefined();
  });

  it("una familia seleccionada -> [nombre]", () => {
    const selected = { "Música Clásica / Docta": true };
    expect(genresToSearch(selected, OPTIONS)).toEqual(["Música Clásica / Docta"]);
  });

  it("varias familias seleccionadas -> nombres en orden del bloque", () => {
    const selected = { "Jazz y Blues": true, "Música Clásica / Docta": true };
    expect(genresToSearch(selected, OPTIONS)).toEqual([
      "Música Clásica / Docta",
      "Jazz y Blues",
    ]);
  });
});
