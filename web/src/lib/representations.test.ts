import { describe, expect, it } from "vitest";
import { getRepresentationActions, representationViewHref } from "./representations";

describe("representation actions", () => {
  it("ofrece visor y descarga a OMR aunque la URL sea externa", () => {
    const actions = getRepresentationActions({
      id: "idx-456780-omr-121355-musicxml",
      provider: "omr",
      format: "musicxml",
      url: "https://example.org/external",
      downloadable: false,
      available: true,
    });
    expect(actions.canView).toBe(true);
    expect(actions.canDownload).toBe(true);
    expect(actions.viewHref).toBe("/viewer?rep=idx-456780-omr-121355-musicxml");
    expect(actions.downloadHref).toBe(
      "/api/v1/representations/idx-456780-omr-121355-musicxml/download",
    );
    expect(actions.externalHref).toBe("https://example.org/external");
  });

  it("mantiene los proveedores externos no OMR solo como enlace web", () => {
    const actions = getRepresentationActions({
      id: "idx-100-cpdl-200-pdf",
      provider: "cpdl",
      format: "pdf",
      url: "https://www.cpdl.org/wiki/index.php/File.pdf",
      downloadable: false,
      available: true,
    });
    expect(actions.canView).toBe(false);
    expect(actions.canDownload).toBe(false);
    expect(actions.externalHref).toContain("cpdl.org");
  });

  it("usa la ruta del visor para formatos soportados", () => {
    expect(representationViewHref("idx-1-omr-2-midi", "midi", "Obra")).toBe(
      "/viewer?rep=idx-1-omr-2-midi&format=midi&title=Obra",
    );
  });
});
