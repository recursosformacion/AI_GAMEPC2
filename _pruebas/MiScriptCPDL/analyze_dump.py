import collections
import re
import sys
from xml.etree import ElementTree

PATH = r"G:\ChoralWiki-20260903154414.xml"
NS = "{http://www.mediawiki.org/xml/export-0.11/}"

title_counts = 0
pages = 0
sample_titles = []
ave = []
tmpl = collections.Counter()
firsts = {"ns": 0}
in_page = None
title = None
text = None
last_ns = None

for event, elem in ElementTree.iterparse(PATH, events=("start", "end")):
    tag = elem.tag
    if event == "start" and tag == NS + "page":
        title = None
        text = None
    elif event == "start" and tag == NS + "ns":
        last_ns = None
    elif event == "start" and tag == NS + "title":
        last_ns = "title"
    elif event == "start" and tag == NS + "text":
        last_ns = "text"
    elif event == "start" and tag == NS + "ns":
        last_ns = "ns"
    elif event == "start" and elem.text is None:
        pass
    if event == "end" and tag in (NS + "title", NS + "text", NS + "ns"):
        if last_ns == "title":
            title = (elem.text or "").strip()
        elif last_ns == "text":
            text = elem.text or ""
        elif last_ns == "ns":
            pass
    if event == "end" and tag == NS + "page":
        pages += 1
        if pages <= 40:
            sample_titles.append(title)
        low = (title or "").lower()
        if "ave verum" in low or "aveverum" in low.replace(" ", ""):
            ave.append({"title": title, "text": (text or "")[:12000]})
        for m in re.findall(r"\{\{\s*([A-Za-z_]+)", text or ""):
            tmpl[m[:30]] += 1
        if pages <= 2000:
            title_counts += 1
        elem.clear()

print("total pages:", pages)
print("templates top 20:")
for name, n in tmpl.most_common(20):
    print("  ", name, n)
print("sample titles:")
for t in sample_titles[:25]:
    print("  ", t)
print("AVE VERUM pages:", len(ave))
for a in ave:
    print("=" * 70)
    print("TITLE:", a["title"])
    print(a["text"][:900].replace("\n", " | "))
