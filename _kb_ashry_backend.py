# -*- coding: utf-8 -*-
"""Read the local KB Ashry.docx backend document for Atlas Update Hub."""
from __future__ import annotations

import json
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
DEFAULT_KB = Path(r"C:\Users\gasser.elashry\Downloads\KB Ashry.docx")
ROOT = Path(__file__).resolve().parent
CACHE_JSON = ROOT / "_kb_ashry_backend_cache.json"


def kb_path() -> Path:
    env = os.environ.get("KB_ASHRY_PATH", "").strip()
    return Path(env) if env else DEFAULT_KB


def _para_text(p) -> str:
    return "".join(t.text or "" for t in p.findall(".//w:t", NS)).strip()


def _is_heading(p, text: str) -> bool:
    if not text or len(text) > 140 or len(text) < 4:
        return False
    # Skip instruction/body cues that look bold but aren't topics
    skip = re.compile(
        r"^(primary questions|mandatory action|ask the customer|note:|important:|resolution:|"
        r"script:|action:|team:|sla:|status:|macro:|issue type|step\s*\d+\b|option\s*[a-z0-9])",
        re.I,
    )
    if skip.match(text):
        return False
    style = p.find("./w:pPr/w:pStyle", NS)
    if style is not None:
        val = (style.attrib.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val") or "").lower()
        if "heading" in val or val.startswith("title"):
            return True
    # Numbered major SOP blocks: "1- ...", "2. ...", "Topic 12:"
    if re.match(r"^(\d{1,2}[\-\.\)]\s+\S|topic\s*\d+\s*[:.\-])", text, re.I):
        return True
    # Known topic families
    if re.match(
        r"^(national identity|account\s*>|payment\s*>|order\s*>|refunds?|smart membership|"
        r"due date|tamara health|murabha|credit bureau|vulnerable|manager escalation|"
        r"collection|unrecorded|unrecognized|phone number|change phone|claims?\b)",
        text,
        re.I,
    ):
        return True
    # Bold short title-like lines (not ending with period, not a question)
    runs = p.findall("./w:r", NS)
    if runs and 12 <= len(text) <= 80 and not text.endswith((".", "?", ":")):
        bold = any(r.find("./w:rPr/w:b", NS) is not None for r in runs)
        if bold and " " in text:
            return True
    return False


def read_kb_ashry(path: Path | None = None) -> dict:
    path = path or kb_path()
    if not path.is_file():
        return {
            "ok": False,
            "error": f"KB Ashry backend file not found: {path}",
            "path": str(path),
        }

    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))

    paragraphs = []
    sections = []
    current = None
    for p in root.findall(".//w:p", NS):
        text = _para_text(p)
        if not text:
            continue
        paragraphs.append(text)
        if _is_heading(p, text):
            current = {
                "title": text,
                "start": len(paragraphs) - 1,
                "lines": [text],
            }
            sections.append(current)
        elif current is not None:
            current["lines"].append(text)

    for i, sec in enumerate(sections):
        end = sections[i + 1]["start"] if i + 1 < len(sections) else len(paragraphs)
        sec["end"] = end
        sec["text"] = "\n".join(paragraphs[sec["start"]:end])
        sec["id"] = f"sec_{i+1}"
        # trim helper fields for API payload size later
        sec.pop("lines", None)
        sec.pop("start", None)
        sec.pop("end", None)

    # Compact section list for UI dropdown (title + preview)
    section_index = [
        {
            "id": s["id"],
            "title": s["title"],
            "preview": (s["text"][:180] + "…") if len(s["text"]) > 180 else s["text"],
            "chars": len(s["text"]),
        }
        for s in sections
    ]

    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    payload = {
        "ok": True,
        "path": str(path),
        "backend": "KB Ashry.docx",
        "modified_at": mtime,
        "paras_count": len(paragraphs),
        "sections_count": len(sections),
        "full_text": "\n".join(paragraphs),
        "sections": sections,
        "section_index": section_index,
        "loaded_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        CACHE_JSON.write_text(json.dumps({
            "ok": True,
            "path": payload["path"],
            "modified_at": payload["modified_at"],
            "paras_count": payload["paras_count"],
            "sections_count": payload["sections_count"],
            "section_index": section_index,
            "loaded_at": payload["loaded_at"],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
    return payload


if __name__ == "__main__":
    data = read_kb_ashry()
    if not data.get("ok"):
        print("ERROR", data.get("error"))
        raise SystemExit(1)
    print("OK", data["path"])
    print("paras", data["paras_count"], "sections", data["sections_count"], "modified", data["modified_at"])
    for s in data["section_index"][:12]:
        print("-", s["id"], s["title"][:80])
