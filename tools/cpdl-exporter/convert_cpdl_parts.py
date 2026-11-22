import json
import sys
from pathlib import Path

src = Path(sys.argv[1])
outdir = Path(sys.argv[2])
outdir.mkdir(parents=True, exist_ok=True)
data = json.loads(src.read_text(encoding="utf-8"))
count = 0
for i, part in enumerate(data, 1):
    xml = part.get("*") if isinstance(part, dict) else part
    if not isinstance(xml, str) or "<mediawiki" not in xml:
        continue
    (outdir / f"cpdl-part-{i:03d}.xml").write_text(xml, encoding="utf-8")
    count += 1
print(f"xml_files={count} from {len(data)} parts")
