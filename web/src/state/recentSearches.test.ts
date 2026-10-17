import { beforeEach, describe, expect, it } from "vitest";
import type { SearchRequest } from "../api/types";
import { loadRecentSearches, pushRecentSearch, searchLabel } from "./recentSearches";

const req = (query: string): SearchRequest => ({ query, limit: 30 });

describe("recentSearches", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("guarda la última búsqueda al frente", () => {
    pushRecentSearch(req("bach"));
    pushRecentSearch(req("byrd"));
    expect(loadRecentSearches().map((row) => row.label)).toEqual(["byrd", "bach"]);
  });

  it("no duplica etiquetas (ignorando mayúsculas) y conserva solo 5", () => {
    for (const query of ["a", "b", "c", "d", "e"]) pushRecentSearch(req(query));
    pushRecentSearch(req("A"));
    const labels = loadRecentSearches().map((row) => row.label);
    expect(labels).toHaveLength(5);
    expect(labels[0]).toBe("A");
    expect(labels.filter((label) => label.toLowerCase() === "a")).toHaveLength(1);
  });

  it("compone la etiqueta con los campos estructurados", () => {
    expect(searchLabel({ query: "", limit: 10, title: "Ave verum", composer: "Mozart" })).toBe(
      "Ave verum · Mozart",
    );
    expect(searchLabel({ query: "", limit: 10 })).toBe("");
    pushRecentSearch({ query: "", limit: 10 });
    expect(loadRecentSearches()).toHaveLength(0);
  });
});
