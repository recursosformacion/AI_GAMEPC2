import { describe, expect, it } from "vitest";
import { videosHomeUrl, videosUrl } from "./videos";

describe("videos links", () => {
  it("incluye obra, representación, título, compositor y token", () => {
    const url = videosUrl({
      workId: "index-486795",
      title: "Singing nightingale",
      composer: "JYKN",
      resourceId: "idx-486795-omr-174632-musicxml",
      token: "abc.def",
    });
    expect(url).toContain("/works/index-486795?");
    expect(url).toContain("resource=idx-486795-omr-174632-musicxml");
    expect(url).toContain("title=Singing+nightingale");
    expect(url).toContain("composer=JYKN");
    expect(url).toContain("token=abc.def");
  });

  it("no genera enlace sin obra", () => {
    expect(videosUrl({ title: "Obra" })).toBeNull();
  });

  it("ofrece la portada de búsqueda sin obra", () => {
    expect(videosHomeUrl()).toContain("localhost:8400");
  });
});
