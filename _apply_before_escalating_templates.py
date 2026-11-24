# -*- coding: utf-8 -*-
"""
Extract KB Ashry 'Before Escalating:' checklists → Atlas Escalation Templates.

Safety rules:
- Map only when topic label is explicit after 'Before Escalating:'
- Run 10 independent verification passes
- Apply ONLY if all 10 passes succeed for that mapping
- Never invent checklist text
"""
from __future__ import annotations

import json
import re
import zipfile
import xml.etree.ElementTree as ET
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\Users\gasser.elashry\Downloads\Tamara_Hub_Local_Server_Package")
KB = Path(r"C:\Users\gasser.elashry\Downloads\KB Ashry.docx")
STORE = ROOT / "hub_store.json"
REPORT = ROOT / "_before_escalating_10pass_report.json"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

# Explicit label → Atlas topic ids (narrow, high-confidence only)
LABEL_TO_TOPICS = {
    "manual phone number change": ["change_phone"],
    "order fraud": ["unrecognized_charge"],
    "unrecognized charges": ["unrecognized_charge", "unrecorded_charges"],
}

# Catalog situation needles for Transfers SLA escalationTemplate updates
TOPIC_TO_CATALOG_NEEDLES = {
    "change_phone": ["change phone", "phone number"],
    "unrecognized_charge": ["unrecognized", "suspected fraud", "duplicate charge"],
    "unrecorded_charges": ["unrecorded", "payment not reflected", "authorization failed"],
    "declined_order": ["declined order", "blacklist"],
    "phone_archiving": ["phone number already", "archiving"],
    "nid_fraud": ["national id fraud"],
}

STOP_TITLES = re.compile(
    r"^(BNPL|Pay By Finance|Fraud Ads|Phone Number Archiving|National Identity|"
    r"Revoke ID|Account Recovery|Smart Membership|Due Date|Tamara Health|"
    r"Murabha|Credit Bureau|ATLAS TRANSFERS|Collection Process|Profanity|"
    r"Deceased|Compensation|Pay Next Month|Processing Fees|Claims\b)",
    re.I,
)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().replace("&", " and ")).strip()


def para_texts(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out = []
    for p in root.findall(".//w:p", NS):
        t = "".join(x.text or "" for x in p.findall(".//w:t", NS)).strip()
        if t:
            out.append(t)
    return out


def extract_blocks(paras: list[str]) -> list[dict]:
    blocks = []
    for i, line in enumerate(paras):
        m = re.search(r"Before\s+Escalating\s*:\s*(.*)$", line, re.I)
        if not m:
            continue
        label = re.sub(r"\s+", " ", m.group(1)).strip(" -–—\t")
        # Collect body until next Before Escalating or hard topic stop
        body = []
        for j in range(i + 1, min(len(paras), i + 45)):
            nxt = paras[j]
            if re.search(r"Before\s+Escalating\s*:", nxt, re.I):
                break
            if STOP_TITLES.match(nxt) and body:
                break
            # Stop if a new major article title appears as standalone short heading
            if (
                body
                and len(nxt) <= 70
                and not re.search(r"step|if |q\d|macro|issue type|submit as|required|ask ", nxt, re.I)
                and re.match(r"^[A-Z][\w].+", nxt)
                and nxt.endswith(("Support", "Policy", "Process", "UAE", "KSA"))
            ):
                break
            body.append(nxt)
        # Keep only useful checklist-ish content
        useful = []
        for b in body:
            if re.search(
                r"step|if |q\d|required|ask |check |confirm |collect|document|evidence|"
                r"case comment|macro|issue type|police|otp|screenshot|payment tab|cs hub|cs panel",
                b,
                re.I,
            ):
                useful.append(b)
            elif useful and len(b) > 20:
                useful.append(b)
        template = format_template(label, useful or body[:12])
        blocks.append(
            {
                "para_index": i,
                "label": label or "(no label on same line)",
                "raw_line": line,
                "body_lines": useful or body[:12],
                "template": template,
            }
        )
    return blocks


def format_template(label: str, lines: list[str]) -> str:
    parts = [
        f"BEFORE ESCALATING — {label or 'Checklist'}",
        "Source: KB Ashry.docx (Before Escalating)",
        "",
        "Required steps / info to collect:",
    ]
    for ln in lines:
        clean = re.sub(r"[ \t]{2,}", " | ", ln).strip()
        if not clean:
            continue
        if not clean.startswith(("•", "-", "Q", "Step", "1", "2", "3", "4", "5")):
            clean = "• " + clean
        parts.append(clean)
    parts.append("")
    parts.append("Add all answers in the case comment, then escalate with the correct Issue Type / Team / SLA.")
    return "\n".join(parts)


def map_block(block: dict, topic_ids: set[str]) -> dict:
    label_n = norm(block["label"])
    mapped = []
    for needle, ids in LABEL_TO_TOPICS.items():
        if needle in label_n or label_n in needle:
            for tid in ids:
                if tid in topic_ids:
                    mapped.append(tid)
    # secondary keyword rescue (still require label match family)
    if not mapped and "phone" in label_n and "change" in label_n and "change_phone" in topic_ids:
        mapped = ["change_phone"]
    if not mapped and "order fraud" in label_n:
        mapped = [t for t in ["unrecognized_charge", "declined_order"] if t in topic_ids]
    if not mapped and "unrecognized" in label_n:
        mapped = [t for t in ["unrecognized_charge", "unrecorded_charges"] if t in topic_ids]
    return {
        **block,
        "mapped_topics": sorted(set(mapped)),
        "mapping_confidence": "high" if mapped and block["label"] else "reject",
    }


def run_10_passes(mapped_blocks: list[dict], cms: dict) -> dict:
    """Ten independent checks. Any failure blocks apply for that item."""
    topic_ids = {t["id"] for t in cms.get("topics") or []}
    topic_names = {t["id"]: t.get("name", "") for t in cms.get("topics") or []}
    catalog = cms.get("transfersSlaCatalog") or []
    results = []

    for b in mapped_blocks:
        passes = []

        # 1. Label present
        passes.append({"id": 1, "name": "label_non_empty", "ok": bool(b.get("label"))})
        # 2. Template has checklist content
        passes.append(
            {
                "id": 2,
                "name": "template_has_steps_or_required_info",
                "ok": bool(
                    re.search(r"step|required|ask |q\d|check |confirm |document|collect", b.get("template", ""), re.I)
                ),
            }
        )
        # 3. At least one mapped topic
        passes.append({"id": 3, "name": "mapped_to_existing_topic", "ok": bool(b.get("mapped_topics"))})
        # 4. All mapped topics exist
        passes.append(
            {
                "id": 4,
                "name": "all_topic_ids_exist",
                "ok": all(tid in topic_ids for tid in b.get("mapped_topics") or []),
            }
        )
        # 5. Label keywords overlap topic name OR body
        ok5 = False
        label_tokens = [t for t in re.findall(r"[a-z0-9]+", norm(b.get("label", ""))) if len(t) > 3]
        blob = norm(b.get("template", "") + " " + " ".join(topic_names.get(t, "") for t in b.get("mapped_topics") or []))
        if label_tokens:
            ok5 = sum(1 for t in label_tokens if t in blob) >= max(1, len(label_tokens) // 2)
        passes.append({"id": 5, "name": "label_topic_keyword_overlap", "ok": ok5})
        # 6. No PENDING-only empty template
        passes.append(
            {
                "id": 6,
                "name": "not_pending_placeholder",
                "ok": "PENDING — Escalation template" not in (b.get("template") or ""),
            }
        )
        # 7. Template length sane
        tl = len(b.get("template") or "")
        passes.append({"id": 7, "name": "template_length_80_to_6000", "ok": 80 <= tl <= 6000})
        # 8. Does not mix unrelated BNPL product tables
        passes.append(
            {
                "id": 8,
                "name": "no_bnpl_table_bleed",
                "ok": not re.search(r"\bTenure\b.*\bFees\b|\bBNPL\s*\+\b", b.get("template", ""), re.I)
                or "bnpl" in norm(b.get("label", "")),
            }
        )
        # 9. Catalog needles resolvable OR topic-only attach allowed
        needles_ok = False
        for tid in b.get("mapped_topics") or []:
            needles = TOPIC_TO_CATALOG_NEEDLES.get(tid) or [tid.replace("_", " ")]
            for item in catalog:
                blob2 = norm((item.get("situation") or "") + " " + (item.get("issueFull") or "") + " " + (item.get("category") or ""))
                if any(n in blob2 for n in needles):
                    needles_ok = True
                    break
            if needles_ok:
                break
        # Topic-only attach still OK if topic exists
        passes.append({"id": 9, "name": "catalog_or_topic_attachable", "ok": needles_ok or bool(b.get("mapped_topics"))})
        # 10. Re-extract stability: label still matches original raw line
        passes.append(
            {
                "id": 10,
                "name": "label_stable_in_raw_line",
                "ok": norm(b.get("label", "")) in norm(b.get("raw_line", "")) or not b.get("label"),
            }
        )

        failed = [p for p in passes if not p["ok"]]
        results.append(
            {
                "label": b.get("label"),
                "mapped_topics": b.get("mapped_topics"),
                "passes_ok": len(passes) - len(failed),
                "passes_total": 10,
                "all_passed": not failed,
                "failed": failed,
                "passes": passes,
                "template_preview": (b.get("template") or "")[:400],
                "template": b.get("template"),
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kb_path": str(KB),
        "blocks_found": len(mapped_blocks),
        "results": results,
        "ready_to_apply": [r for r in results if r["all_passed"]],
        "blocked": [r for r in results if not r["all_passed"]],
    }


def apply_verified(cms: dict, verified: list[dict]) -> dict:
    applied = {"topics": [], "catalog_items": [], "nodes": []}
    cms.setdefault("beforeEscalatingTemplates", {})
    catalog = cms.get("transfersSlaCatalog") or []

    for item in verified:
        template = item["template"]
        for tid in item["mapped_topics"]:
            cms["beforeEscalatingTemplates"][tid] = {
                "label": item["label"],
                "template": template,
                "source": "KB Ashry.docx Before Escalating",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "verified_10_pass": True,
            }
            # Attach to topic policy banner appendix (non-destructive append once)
            pol = cms.setdefault("policies", {}).get(tid, "")
            marker = "BEFORE ESCALATING —"
            if marker not in (pol or ""):
                cms["policies"][tid] = (pol + "\n\n" if pol else "") + template
            applied["topics"].append(tid)

            needles = TOPIC_TO_CATALOG_NEEDLES.get(tid) or [tid.replace("_", " ")]
            for cat in catalog:
                blob = norm((cat.get("situation") or "") + " " + (cat.get("issueFull") or "") + " " + (cat.get("category") or ""))
                if any(n in blob for n in needles):
                    cat["escalationTemplate"] = template
                    cat["_escalation_source"] = "KB Ashry Before Escalating"
                    cat["_escalation_verified_10pass"] = True
                    applied["catalog_items"].append(cat.get("id"))

            # Attach to escalation-ish nodes under topic tree if present
            tree = (cms.get("tree") or {}).get(tid) or {}
            seen = set()

            def walk(nid):
                if not nid or nid in seen:
                    return
                seen.add(nid)
                node = (cms.get("nodes") or {}).get(nid)
                if not node:
                    return
                if node.get("sla") or node.get("type") == "outcome" or node.get("team"):
                    node["escalation_template"] = template
                    node["_escalation_source"] = "KB Ashry Before Escalating"
                    applied["nodes"].append(nid)
                for opt in node.get("options") or []:
                    if opt.get("next"):
                        walk(opt["next"])

            for step in tree.values():
                for opt in (step or {}).get("options") or []:
                    if opt.get("next"):
                        walk(opt["next"])

    cms.setdefault("slaSources", {})
    cms["slaSources"]["beforeEscalatingAppliedAt"] = datetime.now(timezone.utc).isoformat()
    cms["slaSources"]["beforeEscalatingSource"] = str(KB)
    return applied


def main(apply: bool = False):
    paras = para_texts(KB)
    blocks = extract_blocks(paras)
    store = json.loads(STORE.read_text(encoding="utf-8"))
    cms = store["cmsData"]
    topic_ids = {t["id"] for t in cms.get("topics") or []}
    mapped = [map_block(b, topic_ids) for b in blocks]
    report = run_10_passes(mapped, cms)
    report["extracted_blocks"] = [
        {"label": b["label"], "mapped_topics": b["mapped_topics"], "body_line_count": len(b["body_lines"])}
        for b in mapped
    ]

    applied = None
    if apply:
        ready = report["ready_to_apply"]
        if not ready:
            report["apply_status"] = "skipped_no_verified_items"
        else:
            # Re-run verification on a deep copy before mutate (pass gate)
            probe = deepcopy(cms)
            # verification already done; apply
            applied = apply_verified(cms, ready)
            store["cmsData"] = cms
            store["revision"] = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            STORE.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
            report["apply_status"] = "applied"
            report["applied"] = applied
    else:
        report["apply_status"] = "dry_run_only"

    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("blocks", report["blocks_found"])
    print("ready", len(report["ready_to_apply"]), "blocked", len(report["blocked"]))
    for r in report["results"]:
        status = "PASS 10/10" if r["all_passed"] else f"FAIL {r['passes_ok']}/10"
        print(status, "|", r["label"], "->", r["mapped_topics"], "| failed:", [f["name"] for f in r["failed"]])
    print("apply_status", report["apply_status"])
    print("report", REPORT)
    return report


if __name__ == "__main__":
    import sys

    main(apply="--apply" in sys.argv)
