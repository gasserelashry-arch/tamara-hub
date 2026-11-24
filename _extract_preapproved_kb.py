# -*- coding: utf-8 -*-
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
KB = Path(r"C:\Users\gasser.elashry\Downloads\KB Ashry.docx")
OUT = Path(__file__).resolve().parent / "_preapproved_kb_extract.json"


def texts(el):
    return "".join(t.text or "" for t in el.findall(".//w:t", NS)).strip()


def main():
    with zipfile.ZipFile(KB) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    paras = [texts(p) for p in root.findall(".//w:p", NS) if texts(p)]

    # Find Pre-Check / Pre-Approved section
    start = next((i for i, p in enumerate(paras) if re.search(r"^Pre-Check Feature\b", p, re.I)), None)
    if start is None:
        start = next((i for i, p in enumerate(paras) if re.search(r"Pre-Approved Amount", p, re.I)), 0)
    end = start + 1
    for j in range(start + 1, min(len(paras), start + 200)):
        if re.match(r"^(Claims|ORDERS|Order Tracking|BNPL|Smart Membership|ATLAS TRANSFERS)\b", paras[j], re.I):
            end = j
            break
        end = j + 1

    section = paras[start:end]

    # Also extract table rows near this region from document tables
    tables = []
    with zipfile.ZipFile(KB) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    for ti, tbl in enumerate(root.findall(".//w:tbl", NS)):
        rows = []
        for tr in tbl.findall("./w:tr", NS):
            cells = [texts(tc) for tc in tr.findall("./w:tc", NS)]
            if any(cells):
                rows.append(cells)
        blob = " ".join(" | ".join(r) for r in rows)
        if re.search(r"pre-?check|pre-?qual|eligib|pre-?approved", blob, re.I):
            tables.append({"index": ti, "rows": rows})

    OUT.write_text(
        json.dumps({"start": start, "end": end, "section": section, "tables": tables}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("section paras", len(section), "from", start, "to", end, "tables", len(tables))
    for i, p in enumerate(section):
        print(f"{start+i}|{p[:200]}")


if __name__ == "__main__":
    main()
