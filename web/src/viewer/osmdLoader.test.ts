import { describe, expect, it } from "vitest";

import { looksLikeZip, musicXmlFromMxl, type JSZipLike } from "./osmdLoader";

function fakeZip(files: Record<string, string>): JSZipLike {
  return {
    loadAsync: async () => ({
      files: Object.fromEntries(
        Object.entries(files).map(([name, content]) => [
          name,
          { name, async: async () => content },
        ])
      ),
    }),
  };
}

describe("viewer/osmdLoader", () => {
  it("detects zip signature (.mxl)", () => {
    expect(looksLikeZip(new Uint8Array([0x50, 0x4b, 0x03, 0x04, 0x00]))).toBe(true);
    expect(looksLikeZip(new Uint8Array([0x3c, 0x3f, 0x78, 0x6d, 0x6c]))).toBe(false);
  });

  it("extracts MusicXML through META-INF/container.xml", async () => {
    const zip = fakeZip({
      "META-INF/container.xml": '<container><rootfile full-path="score.xml"/></container>',
      "score.xml": "<score-partwise/>",
    });
    await expect(musicXmlFromMxl(zip, new ArrayBuffer(0))).resolves.toBe("<score-partwise/>");
  });

  it("falls back to the first xml entry", async () => {
    const zip = fakeZip({ "other/piece.musicxml": "<score-partwise/>" });
    await expect(musicXmlFromMxl(zip, new ArrayBuffer(0))).resolves.toBe("<score-partwise/>");
  });

  it("fails when there is no MusicXML", async () => {
    const zip = fakeZip({ "readme.txt": "nope" });
    await expect(musicXmlFromMxl(zip, new ArrayBuffer(0))).rejects.toThrow("MusicXML");
  });
});
