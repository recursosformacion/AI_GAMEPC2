import { afterEach, beforeAll, describe, expect, it } from "vitest";

import {
  VOICING_STORAGE_KEY,
  loadVoicingSelection,
  saveVoicingSelection,
  voicingToSearch,
} from "./studioVoicing";

const storage = new Map<string, string>();

beforeAll(() => {
  Object.defineProperty(globalThis, "localStorage", {
    value: {
      getItem: (k: string) => storage.get(k) ?? null,
      setItem: (k: string, v: string) => void storage.set(k, v),
      removeItem: (k: string) => void storage.delete(k),
    },
  });
});

afterEach(() => storage.clear());

describe("voicingToSearch (contrato SearchRequest.voices)", () => {
  it("ALL no añade filtro", () => {
    expect(voicingToSearch("ALL")).toBeUndefined();
    expect(voicingToSearch("")).toBeUndefined();
    expect(voicingToSearch(undefined)).toBeUndefined();
  });

  it.each(["SATB", "STTB", "AATB", "ATTB"])("%s genera el valor esperado", (v) => {
    expect(voicingToSearch(v)).toEqual([v]);
  });

  it("trimming y espacios", () => {
    expect(voicingToSearch("  SATB ")).toEqual(["SATB"]);
  });
});

describe("persistencia en localStorage", () => {
  it("guarda y restaura la selección", () => {
    saveVoicingSelection("SATB");
    expect(loadVoicingSelection()).toBe("SATB");
    expect(storage.get(VOICING_STORAGE_KEY)).toBe("SATB");
  });

  it("ALL se guarda como ausencia de filtro al restaurar (vacío devuelve '')", () => {
    saveVoicingSelection("ALL");
    expect(loadVoicingSelection()).toBe("ALL");
  });

  it("sin valor previo devuelve ''", () => {
    expect(loadVoicingSelection()).toBe("");
  });
});
