# -*- coding: utf-8 -*-
"""
Add pinned Transfers SLA topic + catalog from Transfers SLA.xlsx
Compare KB Ashry.docx escalation SLAs to hub nodes (report only).
"""
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\Users\gasser.elashry\Downloads\Tamara_Hub_Local_Server_Package")
STORE = ROOT / "hub_store.json"
XLSX = Path(r"C:\Users\gasser.elashry\Downloads\Transfers SLA.xlsx")
KB = Path(r"C:\Users\gasser.elashry\Downloads\KB Ashry.docx")
REPORT = ROOT / "_kb_ashry_mismatch_report.json"

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}

TRANSFERS_URL = "https://docs.google.com/spreadsheets/d/1uChI9CY4xi_vMw0P8mDYXeLkHNY2-R4OZ9gpNnbm87c/edit?gid=0#gid=0"
KB_LOCAL = str(KB)


def norm(s):
    s = (s or "").lower().replace("&", " and ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def col_row(ref):
    m = re.match(r"([A-Z]+)(\d+)", ref)
    col = 0
    for ch in m.group(1):
        col = col * 26 + (ord(ch) - 64)
    return col, int(m.group(2))


def read_transfers_xlsx(path):
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", NS):
                texts = [t.text or "" for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")]
                shared.append("".join(texts))
        root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        grid = {}
        max_r = 0
        for c in root.findall(".//a:sheetData/a:row/a:c", NS):
            ref = c.attrib.get("r")
            if not ref:
                continue
            col, row = col_row(ref)
            max_r = max(max_r, row)
            v = c.find("a:v", NS)
            raw = v.text if v is not None else ""
            val = shared[int(raw)] if c.attrib.get("t") == "s" and raw.isdigit() else raw
            grid[(row, col)] = val
        rows = []
        for r in range(2, max_r + 1):
            team = str(grid.get((r, 1), "")).strip()
            lob = str(grid.get((r, 2), "")).strip()
            issue = str(grid.get((r, 3), "")).strip()
            sla = str(grid.get((r, 4), "")).strip()
            if not (team or issue or sla):
                continue
            rows.append({"row": r, "team": team, "lob": lob, "issue": issue, "sla": sla})
        return rows


def category_from_issue(issue):
    first = issue.split("\n")[0].strip(" -•\t")
    if ">" in first:
        return first.split(">")[0].strip()
    if first.lower().startswith("smart"):
        return "Smart"
    if first.lower().startswith("due date"):
        return "Due Date Preference"
    if first.lower().startswith("claims"):
        return "Claims / Trust & Safety"
    if first.lower().startswith("compensation"):
        return "Manager Escalation"
    if first.lower().startswith("according"):
        return "Manager Escalation"
    return first[:80] or "General"


def situations_from_issue(issue):
    """Expand multi-bullet issue cell into selectable situations."""
    lines = [ln.strip(" -•\t") for ln in re.split(r"[\n\r]+", issue) if ln.strip(" -•\t")]
    if not lines:
        return [issue]
    # If only one line, use it
    if len(lines) == 1:
        return lines
    # First line often category header; bullets are situations
    header = lines[0]
    bullets = [ln for ln in lines[1:] if ln]
    if not bullets:
        return [header]
    # Keep header as category context + each bullet
    out = []
    for b in bullets:
        if ">" in b or len(b) > 8:
            out.append(b)
        else:
            out.append(header + " — " + b)
    return out or [header]


def build_catalog(rows):
    catalog = []
    for r in rows:
        cat = category_from_issue(r["issue"])
        sits = situations_from_issue(r["issue"])
        for i, sit in enumerate(sits):
            catalog.append({
                "id": f"TRF_{r['row']}_{i+1}",
                "sheetRow": r["row"],
                "team": r["team"] or "Tech Support",
                "lob": r["lob"] or "Customer Care",
                "category": cat,
                "situation": sit,
                "issueFull": r["issue"],
                "sla": r["sla"],
                "status": "Working",
                "macro": "Ticket Escalated",
                "escalationTemplate": (
                    "PENDING — Escalation template will be shared by admin and linked here.\n"
                    "Until then use: Macro Ticket Escalated + set Team / SLA / Status from this card."
                ),
            })
    return catalog


def read_kb_paras(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        paras = []
        for p in root.findall(".//w:p", NS):
            line = "".join(t.text or "" for t in p.findall(".//w:t", NS)).strip()
            if line:
                paras.append(line)
        return paras


def extract_kb_escalations(paras):
    """Pull escalation records that include Issue type + SLA (+ optional Team/Status/Macro)."""
    records = []

    def parse_window(window, start_i):
        issue = ""
        sla = ""
        team = ""
        status = ""
        macro = ""
        scenario = ""
        for line in window:
            # tolerate concatenated tokens: Macro XIssue type Y
            line2 = re.sub(r"(?i)(Macro[^\n]*?)(Issue type)", r"\1\n\2", line)
            line2 = re.sub(r"(?i)(Issue type[^\n]*?)(Submit as)", r"\1\n\2", line2)
            line2 = re.sub(r"(?i)(Submit as[^\n]*?)(SLA)", r"\1\n\2", line2)
            for part in line2.split("\n"):
                m_issue = re.search(r"(?i)Issue type(?:\s*\((?:CS|CX)\))?\s*[-=:>→]*\s*(.+)$", part)
                if m_issue:
                    issue = m_issue.group(1).strip()
                    # trim trailing Submit/SLA if glued
                    issue = re.split(r"(?i)\bSubmit as\b|\bSLA\b", issue)[0].strip(" -:>→")
                m_sla = re.search(r"(?i)\bSLA\b\s*(?:is\s*)?[-=:>→]?\s*(.+)$", part)
                if m_sla and not sla:
                    sla = m_sla.group(1).strip().rstrip(".")
                    sla = re.split(r"(?i)\bMacro\b|\bIssue type\b", sla)[0].strip()
                m_st = re.search(r"(?i)Submit as\s*[-=:>→]?\s*(.+)$", part)
                if m_st:
                    status = m_st.group(1).strip()
                    status = re.split(r"(?i)\bSLA\b|\bMacro\b|\bIssue type\b", status)[0].strip()
                if re.search(r"(?i)\bMacro\b", part) and not macro:
                    m_mac = re.search(r"(?i)Macro\s*[-=:>→]?\s*(.+)$", part)
                    if m_mac:
                        macro = m_mac.group(1).strip()
                        macro = re.split(r"(?i)\bIssue type\b|\bSubmit as\b|\bSLA\b", macro)[0].strip(" -:>→")
                if re.search(r"(?i)Trust & Safety", part):
                    team = "Trust & Safety"
                elif re.search(r"(?i)Tech(?:nical)? Support", part) and re.search(r"(?i)escalat|team", part):
                    team = "Tech Support"
                elif re.search(r"(?i)Special Operations", part):
                    team = "Special Operations"
                elif re.search(r"(?i)Manager Escalation|escalate.*manager", part):
                    team = "Manager Escalation"
                if re.search(r"(?i)^Scenario", part) and not scenario:
                    scenario = re.sub(r"(?i)^Scenario\s*[-=:>→]?\s*", "", part).strip()
        if issue and sla:
            return {
                "issueType": issue,
                "sla": sla,
                "team": team,
                "status": status,
                "macro": macro,
                "scenario": scenario,
                "paraIndex": start_i,
            }
        return None

    i = 0
    while i < len(paras):
        # sliding windows of different sizes to catch glued paragraphs
        found = None
        for w in (6, 10, 14):
            found = parse_window(paras[i : i + w], i)
            if found:
                break
        if found:
            records.append(found)
            i += 3
        else:
            i += 1

    # Also scan single long lines containing both Issue type and SLA
    for i, line in enumerate(paras):
        if re.search(r"(?i)Issue type", line) and re.search(r"(?i)\bSLA\b", line):
            found = parse_window([line], i)
            if found:
                records.append(found)

    seen = set()
    uniq = []
    for r in records:
        key = (norm(r["issueType"]), norm(r["sla"]), norm(r["scenario"])[:60])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    return uniq


def compare_kb_to_hub(kb_recs, cms):
    mismatches = []
    matched = []
    unmatched_kb = []
    nodes = cms.get("nodes") or {}

    def score(a, b):
        na, nb = norm(a), norm(b)
        if not na or not nb:
            return 0
        if na == nb:
            return 100
        if na in nb or nb in na:
            return 85
        ta, tb = set(na.split()), set(nb.split())
        if not ta or not tb:
            return 0
        return int(100 * len(ta & tb) / len(ta | tb))

    for rec in kb_recs:
        best = None
        best_sc = 0
        for nid, n in nodes.items():
            sc = score(rec["issueType"], n.get("issueType") or "")
            if sc > best_sc:
                best_sc = sc
                best = (nid, n)
        if not best or best_sc < 55:
            unmatched_kb.append(rec)
            continue
        nid, n = best
        diffs = []
        hub_sla = (n.get("sla") or "").strip()
        kb_sla = (rec.get("sla") or "").strip()
        if hub_sla and kb_sla and norm(hub_sla) != norm(kb_sla):
            # allow soft variants like "5 Days" vs "5 business days" only if numbers differ
            hub_nums = re.findall(r"\d+", hub_sla)
            kb_nums = re.findall(r"\d+", kb_sla)
            if hub_nums != kb_nums or ("immediate" in norm(hub_sla)) != ("immediate" in norm(kb_sla)):
                diffs.append({"field": "sla", "hub": hub_sla, "kb": kb_sla})
        if rec.get("team") and n.get("team") and norm(rec["team"]) not in norm(n.get("team")) and norm(n.get("team")) not in norm(rec["team"]):
            # only flag if hub claims a named team and differs
            if "none" not in norm(n.get("team")) and "first contact" not in norm(n.get("team")):
                diffs.append({"field": "team", "hub": n.get("team"), "kb": rec["team"]})
        if rec.get("status") and n.get("sf_status") and norm(rec["status"]) != norm(n.get("sf_status")):
            diffs.append({"field": "status", "hub": n.get("sf_status"), "kb": rec["status"]})
        entry = {
            "node_id": nid,
            "headline": n.get("headline"),
            "hub_issueType": n.get("issueType"),
            "kb_issueType": rec["issueType"],
            "match_score": best_sc,
            "kb_scenario": rec.get("scenario"),
            "diffs": diffs,
        }
        if diffs:
            mismatches.append(entry)
        else:
            matched.append(entry)
    return {"mismatches": mismatches, "matched_ok": matched, "kb_unmatched_to_hub": unmatched_kb}


def main():
    store = json.loads(STORE.read_text(encoding="utf-8"))
    cms = store["cmsData"]

    rows = read_transfers_xlsx(XLSX)
    catalog = build_catalog(rows)
    cms["transfersSlaCatalog"] = catalog

    # Topic always first
    topics = cms.setdefault("topics", [])
    topics = [t for t in topics if t.get("id") != "transfers_sla"]
    topic = {
        "id": "transfers_sla",
        "tag": "Topic 00",
        "name": "Transfers SLA",
        "desc": "Full Transfers SLA matrix — pick category & situation to view Team, SLA, Status, and escalation template.",
        "pinned": True,
        "uniqueType": "transfers_sla_browser",
    }
    cms["topics"] = [topic] + topics

    # Minimal tree placeholder (UI uses special panel)
    cms.setdefault("tree", {})["transfers_sla"] = {
        "step1": {
            "prompt": "Use the Transfers SLA dropdowns above to select a category and situation.",
            "options": [],
        }
    }

    # Policy blurb
    cms.setdefault("policies", {})["transfers_sla"] = (
        "TRANSFERS SLA BROWSER\n"
        "• Select Category, then Situation from the Transfers SLA sheet.\n"
        "• Confirm Team, SLA, and Salesforce Status before escalating.\n"
        "• Escalation template field is reserved — template will be shared and linked.\n"
        "• Source sheet: " + TRANSFERS_URL
    )

    # Link sources
    cms.setdefault("slaSources", {})
    cms["slaSources"].update({
        "transfersSheetUrl": TRANSFERS_URL,
        "transfersSheetId": "1uChI9CY4xi_vMw0P8mDYXeLkHNY2-R4OZ9gpNnbm87c",
        "kbAshryLocalPath": KB_LOCAL,
        "kbAshryLinked": True,
        "lastTransfersCatalogCount": len(catalog),
        "lastTransfersBuiltAt": datetime.now(timezone.utc).isoformat(),
        "note": "Update Transfers SLA.xlsx or KB Ashry.docx in Downloads, then run Sync_SLA_From_Downloads.bat / rebuild script.",
    })

    # KB compare (inform only)
    kb_paras = read_kb_paras(KB)
    kb_recs = extract_kb_escalations(kb_paras)
    cmp = compare_kb_to_hub(kb_recs, cms)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kb_records_extracted": len(kb_recs),
        "transfers_catalog_items": len(catalog),
        "mismatch_count": len(cmp["mismatches"]),
        "matched_ok_count": len(cmp["matched_ok"]),
        "kb_unmatched_count": len(cmp["kb_unmatched_to_hub"]),
        "mismatches": cmp["mismatches"],
        "kb_unmatched_sample": cmp["kb_unmatched_to_hub"][:40],
        "note": "No hub SLAs were auto-changed from KB Ashry. Confirm which mismatches to apply.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    cms["slaSources"]["kbAshryLastCompareAt"] = report["generated_at"]
    cms["slaSources"]["kbAshryMismatchCount"] = report["mismatch_count"]

    store["cmsData"] = cms
    store["revision"] = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    STORE.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")

    print("catalog", len(catalog), "categories", len({c['category'] for c in catalog}))
    print("kb records", len(kb_recs), "mismatches", report["mismatch_count"], "matched_ok", report["matched_ok_count"])
    for m in report["mismatches"][:25]:
        print("DIFF", m["node_id"], m["diffs"], "| hub:", m["hub_issueType"], "| kb:", m["kb_issueType"])


if __name__ == "__main__":
    main()
