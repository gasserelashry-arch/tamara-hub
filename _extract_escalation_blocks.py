# -*- coding: utf-8 -*-
"""Extract Before Escalating + Escalation Steps/Scenario blocks with surrounding body."""
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
KB = Path(r"C:\Users\gasser.elashry\Downloads\KB Ashry.docx")
OUT = Path(__file__).resolve().parent / "_kb_escalation_blocks.json"

STOP = re.compile(
    r"^(BNPL|Pay By Finance|ATLAS TRANSFERS|National Identity|Account Recovery|"
    r"Phone Number Archiving|Smart Membership|Due Date|Tamara Health|Murabha|"
    r"Collection Process|Profanity|Deceased|Compensation|Pay Next Month|"
    r"Processing Fees|Claims\b|Open banking|Free Membership|SIMAH Escalation|"
    r"Unrecorded Charges|Payment Technical Issues|Guidance for Handling)",
    re.I,
)


def texts(el):
    return "".join(t.text or "" for t in el.findall(".//w:t", NS)).strip()


def read_paras(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    return [texts(p) for p in root.findall(".//w:p", NS) if texts(p)]


def collect_body(paras, start, end_limit=50):
    body = []
    for j in range(start + 1, min(len(paras), start + end_limit)):
        line = paras[j]
        if re.search(r"before\s+escalat|^escalation\s+steps\b", line, re.I) and body:
            break
        if STOP.match(line) and body:
            break
        body.append(line)
    return body


def main():
    paras = read_paras(KB)
    blocks = []

    for i, p in enumerate(paras):
        label = ""
        kind = None
        m = re.search(r"Before\s+Escalating\s*:\s*(.*)$", p, re.I)
        if m:
            kind = "BEFORE_ESCALATING"
            label = re.sub(r"\s+", " ", m.group(1)).strip(" -–—\t")
        elif re.match(r"^Escalation Steps\b", p, re.I) or p.strip() in ("Escalation Steps", "Escalation Steps:"):
            kind = "ESCALATION_STEPS"
            # title = previous meaningful line
            for j in range(i - 1, max(-1, i - 25), -1):
                if 8 <= len(paras[j]) <= 110 and not re.search(r"escalat|macro|step \d", paras[j], re.I):
                    label = paras[j]
                    break
        elif re.search(r"Edge Cases\s*\(Escalation\)|Escalation scenarios", p, re.I):
            kind = "ESCALATION_SCENARIOS"
            label = p[:120]
        elif re.search(r"escalate(?:d)?\s+to(?:\s+the)?\s+(Tech(?:nical)? Support|Trust\s*&\s*Safety|Credit|AECB|SIMAH|Manager)", p, re.I):
            kind = "ESCALATE_TO_LINE"
            label = ""
            for j in range(i - 1, max(-1, i - 20), -1):
                if 8 <= len(paras[j]) <= 120:
                    label = paras[j]
                    break
        else:
            continue

        body = collect_body(paras, i, 55 if kind != "ESCALATE_TO_LINE" else 12)
        if kind == "ESCALATE_TO_LINE":
            body = [p] + body[:10]

        team = ""
        blob = p + "\n" + "\n".join(body)
        tm = re.search(
            r"(Trust\s*&\s*Safety|Tech(?:nical)? Support|Credit\s*-?\s*Risk|Credit Bureau|AECB|SIMAH|Manager Escalation|Collections|Government Escalation)",
            blob,
            re.I,
        )
        if tm:
            team = tm.group(1)

        blocks.append(
            {
                "idx": i,
                "kind": kind,
                "label": label or "(untitled)",
                "team": team,
                "header": p[:240],
                "body": body,
                "text": (p + "\n" + "\n".join(body)).strip(),
            }
        )

    # Focus dump for refunds
    refund_blocks = [b for b in blocks if re.search(r"refund|murabha|early settlement|cool-off|wallet|cancell", b["text"], re.I)]

    OUT.write_text(
        json.dumps(
            {
                "total_blocks": len(blocks),
                "by_kind": {
                    k: sum(1 for b in blocks if b["kind"] == k)
                    for k in sorted({b["kind"] for b in blocks})
                },
                "blocks": blocks,
                "refund_related": refund_blocks,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("blocks", len(blocks), "refund_related", len(refund_blocks))
    for b in blocks:
        if b["kind"] in ("BEFORE_ESCALATING", "ESCALATION_STEPS", "ESCALATION_SCENARIOS") or re.search(
            r"refund|murabha|early", b["text"], re.I
        ):
            print(
                f"{b['idx']}|{b['kind']}|team={b['team'] or '-'}|{b['label'][:70]}|body={len(b['body'])}"
            )


if __name__ == "__main__":
    main()
