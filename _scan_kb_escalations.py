# -*- coding: utf-8 -*-
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
KB = Path(r"C:\Users\gasser.elashry\Downloads\KB Ashry.docx")
OUT = Path(__file__).resolve().parent / "_kb_escalation_scan.json"


def texts(el):
    return "".join(t.text or "" for t in el.findall(".//w:t", NS)).strip()


def read_paras(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    return [texts(p) for p in root.findall(".//w:p", NS) if texts(p)]


def main():
    paras = read_paras(KB)
    hits = []
    for i, p in enumerate(paras):
        if not re.search(r"escalat", p, re.I):
            continue
        if re.search(r"before\s+escalat", p, re.I):
            kind = "BEFORE"
        elif re.search(r"^escalation\s+steps", p, re.I):
            kind = "STEPS"
        elif re.search(r"escalation\s+scenario", p, re.I):
            kind = "SCENARIO"
        elif re.search(r"escalate\s+to", p, re.I):
            kind = "ESCALATE_TO"
        else:
            kind = "OTHER"
        # lookback title
        title = ""
        for j in range(i - 1, max(-1, i - 40), -1):
            line = paras[j]
            if re.search(r"before\s+escalat|^escalation\s+steps", line, re.I):
                continue
            if 8 <= len(line) <= 120 and not re.search(
                r"^(step|macro|issue type|submit as|sla|q\d|if |case comment|action)", line, re.I
            ):
                title = line
                break
        team = ""
        m = re.search(
            r"escalate(?:d)?\s+to(?:\s+the)?\s+([A-Za-z &/\-]+?)(?:\s+team|\s+by|\s+using|\.|,|$)",
            p,
            re.I,
        )
        if m:
            team = m.group(1).strip()
        hits.append(
            {
                "idx": i,
                "kind": kind,
                "title_guess": title[:140],
                "text": p[:400],
                "team_guess": team,
            }
        )
        print(f"{i}|{kind}|team={team or '-'}|{title[:60]}|{p[:120]}")

    # Also dump refund-related surrounding blocks
    refund_idxs = [i for i, p in enumerate(paras) if re.search(r"refund", p, re.I)]
    print("refund_paras", len(refund_idxs))
    OUT.write_text(
        json.dumps({"hits": hits, "refund_count": len(refund_idxs), "paras": len(paras)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("wrote", OUT, "hits", len(hits))


if __name__ == "__main__":
    main()
