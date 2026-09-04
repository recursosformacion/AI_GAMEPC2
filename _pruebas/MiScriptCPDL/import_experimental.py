"""Importador EXPERIMENTAL de CPDL (dump MediaWiki local). NO toca works.

Produce registros normalizados a partir de la plantillas wiki de cada página:
  {source, source_id, title, composer, voicing, instrumentation, genre,
   language, license, catalogue_hint, editions:[{cpdlno, files:[...], editor}],
   arrangement_hint, categories[]}

Uso: python import_experimental.py --limit 14  (filtra páginas Ave verum)
"""

import argparse
import json
import re
from pathlib import Path
from xml.etree import ElementTree

PATH = Path(r"G:\ChoralWiki-20260903154414.xml")
NS = "{http://www.mediawiki.org/xml/export-0.11/}"


def clean(s: str) -> str:
    s = re.sub(r"\[\[Media:[^|\]]*\|[^]]*\]\]", "", s)
    s = re.sub(r"\[\[[^|\]]*\|([^]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^]]*)\]\]", r"\1", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"''+", "", s)
    s = re.sub(r"\{\{#?\w+:?[^}]*\}\}", "", s)
    return s.replace("&nbsp;", " ").strip()


def tmpl(text: str, name: str) -> str:
    m = re.search(r"\{\{\s*%s\|([^}]*)\}\}" % name, text)
    if not m:
        return ""
    parts = [p for p in m.group(1).split("|")]
    value = clean(parts[0])
    return value


def tmpl_multi(text: str, name: str) -> list[str]:
    m = re.search(r"\{\{\s*%s\|([^}]*)\}\}" % name, text)
    if not m:
        return []
    return [clean(p) for p in m.group(1).split("|") if clean(p)]


def composer_and_catalogue(title: str, text: str) -> tuple[str, str]:
    m = re.search(r"\((.*?)\)\s*$", title)
    composer = m.group(1) if m else ""
    catalogue = ""
    cm = re.search(r"\{\{\s*Composer\|([^}|]*)", text)
    if cm:
        composer = clean(cm.group(1))
    for pat in (r"KV\s*\d+", r"K\.\s*\d+", r"Op\.\s*[\dNo. ,]+", r"CG\s*\d+", r"D\.\s*\d+", r"BWV\s*\d+"):
        c = re.search(pat, title)
        if c:
            catalogue = c.group(0)
            break
    return composer, catalogue


def parse_page(title: str, text: str) -> dict:
    composer, catalogue = composer_and_catalogue(title, text)
    editions = []
    # Bloques de edición separados por ' * ' o '*' al inicio de línea.
    chunks = re.split(r"\n\s*\*\s*", text)
    for chunk in chunks[1:]:
        m = re.search(r"\{\{\s*CPDLno\|(\d+)\}\}", chunk)
        if not m:
            continue
        files = re.findall(r"\[\[Media:([^\]|]+\.(?:pdf|mxl|mid|xml|mp3|mscz|capx|sib|mus))", chunk, re.I)
        ed = re.search(r"\{\{\s*Editor\|([^}|]+)", chunk)
        copy = re.search(r"\{\{\s*Copy(?:CC)?\|([^}|]+)", chunk)
        editions.append(
            {
                "cpdlno": m.group(1),
                "files": sorted(set(f.lower() for f in files)),
                "editor": clean(ed.group(1)) if ed else "",
                "license": clean(copy.group(1)) if copy else "",
            }
        )
    low = (text + title).lower()
    arrangement = bool(
        re.search(r"arr(?:anged)?|reformat|reduction|transcr|piano acc", low)
    )
    return {
        "source": "cpdl",
        "source_id": f"cpdl:{title}",
        "title": clean(tmpl(text, "Title")) or clean(title),
        "composer": composer,
        "voicing": tmpl_multi(text, "Voicing"),
        "instrumentation": tmpl_multi(text, "Instruments"),
        "genre": tmpl_multi(text, "Genre"),
        "language": tmpl_multi(text, "Language"),
        "license": editions[0]["license"] if editions else "",
        "catalogue_hint": catalogue,
        "arrangement_hint": arrangement,
        "n_editions": len(editions),
        "editions": editions[:3],
        "imslp": re.findall(r"\{\{\s*IMSLPWork\|([^}]+)\}\}", text)[:2],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=14)
    args = ap.parse_args()
    out: list[dict] = []
    for event, elem in ElementTree.iterparse(PATH, events=("end",)):
        if elem.tag != NS + "page":
            continue
        t = elem.findtext(NS + "title") or ""
        if "ave verum" in t.lower() or "aveverum" in t.lower().replace(" ", ""):
            text = elem.findtext(".//" + NS + "text") or ""
            out.append(parse_page(t, text))
        if len(out) >= args.limit:
            break
        elem.clear()
    (Path(__file__).parent / "cpdl_ave_verum_records.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"registros: {len(out)}")
    for r in out:
        print("----", r["source_id"])
        print("   title:", r["title"], "| composer:", r["composer"], "| catalogue:", r["catalogue_hint"], "| arr:", r["arrangement_hint"])
        print("   voicing:", r["voicing"], "| instr:", r["instrumentation"], "| genre:", r["genre"], "| editions:", r["n_editions"])


if __name__ == "__main__":
    main()
