# -*- coding: utf-8 -*-
"""
Treat Transfers SLA.xlsx as source of truth:
1) Refresh Transfers SLA catalog/topic
2) Apply curated escalation node SLAs from the sheet
3) Patch KB Ashry.docx with Transfers SLA appendix + update known SLA lines
4) Report missing Atlas topics vs sheet coverage
"""
import json
import re
import zipfile
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(r"C:\Users\gasser.elashry\Downloads\Tamara_Hub_Local_Server_Package")
STORE = ROOT / "hub_store.json"
XLSX = Path(r"C:\Users\gasser.elashry\Downloads\Transfers SLA.xlsx")
KB = Path(r"C:\Users\gasser.elashry\Downloads\KB Ashry.docx")
KB_BACKUP = Path(r"C:\Users\gasser.elashry\Downloads\KB Ashry.BACKUP_before_transfers_sync.docx")
REPORT = ROOT / "_transfers_authority_report.json"

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

TRANSFERS_URL = "https://docs.google.com/spreadsheets/d/1uChI9CY4xi_vMw0P8mDYXeLkHNY2-R4OZ9gpNnbm87c/edit?gid=0#gid=0"


def norm(s):
    s = (s or "").lower().replace("&", " and ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def col_row(ref):
    m = re.match(r"([A-Z]+)(\d+)", ref)
    col = 0
    for ch in m.group(1):
        col = col * 26 + (ord(ch) - 64)
    return col, int(m.group(2))


def read_transfers(path):
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", NS):
                shared.append("".join(t.text or "" for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))
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
            if team or issue or sla:
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
    if first.lower().startswith("compensation") or first.lower().startswith("according"):
        return "Manager Escalation"
    return first[:80] or "General"


def situations_from_issue(issue):
    lines = [ln.strip(" -•\t") for ln in re.split(r"[\n\r]+", issue) if ln.strip(" -•\t")]
    if len(lines) <= 1:
        return lines or [issue]
    header, bullets = lines[0], lines[1:]
    out = []
    for b in bullets:
        out.append(b if (">" in b or len(b) > 8) else f"{header} — {b}")
    return out or [header]


def build_catalog(rows):
    catalog = []
    for r in rows:
        cat = category_from_issue(r["issue"])
        for i, sit in enumerate(situations_from_issue(r["issue"])):
            catalog.append({
                "id": f"TRF_{r['row']}_{i+1}",
                "sheetRow": r["row"],
                "team": r["team"] or "Tech Support",
                "lob": r["lob"] or "Customer Care",
                "category": cat,
                "situation": sit,
                "issueFull": r["issue"],
                "sla": r["sla"] or "See sheet / supervisor",
                "status": "Working" if r["team"] else "N/A",
                "macro": "Ticket Escalated",
                "escalationTemplate": (
                    "PENDING — Escalation template will be shared by admin and linked here.\n"
                    "Until then use: Macro Ticket Escalated + set Team / SLA / Status from this card.\n"
                    f"Source: Transfers SLA sheet row {r['row']}"
                ),
            })
    return catalog


# Curated node updates from Transfers SLA (escalation outcomes only)
# (sheet_row, node_id, sla, team)
# Exact sheet wording preferred via apply_node_updates (row SLA wins when present).
CURATED_NODE_UPDATES = [
    # Tech Support
    (2, "REV_LEGAL_ESCALATE", "5 business days", "Tech Support"),  # ID verification / Tahaqaq
    (10, "UNREC_STATUS_CAPTURED_ESC", "5 business days", "Tech Support"),
    (10, "UNREC_SYSTEM_ERROR", "5 business days", "Tech Support"),
    (10, "LINK_RECONCILE", "5 business days", "Tech Support"),
    (14, "ORD_STUCK_ESC", "5 days", "Tech Support"),
    (19, "IVR_CALL_RETRY", "3 days from the engineering team", "Tech Support"),
    (25, "OTP_TROUBLESHOOT", "3 business days / 5 business days for app issues", "Tech Support"),
    (27, "NODE_BRANCH_889157_581_MAIN", "7 business days", "Tech Support"),  # Card not accepted
    (27, "NODE_BRANCH_377157_293_MAIN", "7 business days", "Tech Support"),
    (28, "DEC_CUST_DUES_ESCALATE", "10 business days", "Tech Support"),
    (28, "DEC_CUST_ZERO_DUES_CLOSE", "10 business days", "Tech Support"),
    (28, "DEC_CUST_PENDING_DOCS", "10 business days", "Tech Support"),
    (28, "VUL_DECEASED", "10 business days", "Tech Support"),
    (29, "VUL_PHYSICAL_ESCALATE", "10 business days", "Tech Support"),
    # Due Date Preference — sheet row 9 points to Due Date Preference doc;
    # keep situation-specific SLAs (do NOT replace with the combined sheet cell).
    # Mark with sheet_row 0 so apply_node_updates keeps curated exact wording.
    (0, "DUE_ESC_OPT_OUT_STILL_APPLIED", "7 Days", "Tech Support"),
    (0, "DUE_ESC_PREF_DISAPPEARED", "4 Days", "Tech Support"),
    (0, "DUE_ESC_DUPLICATE_STATE", "5 Days", "Tech Support"),
    # Trust & Safety
    (35, "MFR_ESCALATE", "5 days", "Trust & Safety"),  # Refund blocked by merchant
    (36, "UNREG_DUES_ID_FRAUD", "5 calendar days", "Trust & Safety"),
    (36, "NID_COLL_AGENCY", "5 calendar days", "Trust & Safety"),
    (37, "UNREG_DUES_PHONE_ARCHIVE", "5 calendar days", "Trust & Safety"),
    (37, "PHN_ARCH_ESCALATE", "5 calendar days", "Trust & Safety"),
    (38, "CRD_CARD_DISPUTE", "5 calendar days", "Trust & Safety"),  # Payment fraud complaints
    (40, "NID_TNS_ESCALATE", "5 calendar days", "Trust & Safety"),
    (40, "NID_TAKEOVER_ACT", "5 calendar days", "Trust & Safety"),
    # Credit / Manager / Collections
    (45, "AECB_DISPUTE_ESCALATE", "5 business days", "Credit - Risk"),
    (46, "AECB_CLEARANCE_LETTER", "24 hours", "Government Escalation"),
    (43, "MGR_WARM_TRANSFER", "24 hours", "Manager Escalation"),
    (47, "COLL_HOLD_REQUEST", "48 business hours", "Collections"),
]

# Missing product topics to create so sheet coverage is complete (SLA-only shells).
MISSING_TOPICS_TO_CREATE = [
    {
        "id": "about_tamara_general",
        "tag": "Topic NEW",
        "name": "About Tamara (General) — App Issues",
        "desc": "Other > About Tamara (General) — app issues. Transfers SLA: 3 business days / 5 business days for app issues (Tech Support).",
        "sheet_row": 5,
        "sla": "3 business days / 5 business days for app issues",
        "team": "Tech Support",
        "node_id": "ABOUT_TAMARA_APP_ESC",
    },
    {
        "id": "feedback_jailbroken",
        "tag": "Topic NEW",
        "name": "Feedback — Jailbroken / Rooted Device",
        "desc": "Other > Feedback about Tamara — Jailbroken / Rooted Device. Transfers SLA: 5 business days (Tech Support).",
        "sheet_row": 6,
        "sla": "5 business days",
        "team": "Tech Support",
        "node_id": "FEEDBACK_JAILBREAK_ESC",
    },
    {
        "id": "account_passcode",
        "tag": "Topic NEW",
        "name": "Account Passcode",
        "desc": "Account > Passcode. Transfers SLA: 5 business days (Tech Support).",
        "sheet_row": 13,
        "sla": "5 business days",
        "team": "Tech Support",
        "node_id": "PASSCODE_ESC",
    },
    {
        "id": "murabha_early_settlement",
        "tag": "Topic NEW",
        "name": "Murabha — Early Settlement",
        "desc": "Payment > Murabha - Pay By Finance > Early Settlement. Transfers SLA: 7-10 days (Tech Support).",
        "sheet_row": 30,
        "sla": "7-10 days",
        "team": "Tech Support",
        "node_id": "MURABHA_EARLY_SETTLE_ESC",
    },
]

# Map sheet themes -> Atlas topic ids (existing + newly created)
SHEET_THEME_TO_TOPICS = {
    "id verification": ["revoke_id", "nid_fraud"],
    "registration": ["phone_archiving"],
    "login": ["phone_archiving"],
    "otp": ["no_order_otp"],
    "unrecorded": ["unrecorded_charges"],
    "stuck order": ["stuck_order"],
    "expired order": ["expired_order"],
    "ivr": ["order_ivr"],
    "card is not accepted": ["payment_methods"],
    "deceased": ["deceased_customer"],
    "disability": ["vulnerable_customer"],
    "due date": ["due_date"],
    "smart": ["smart_membership"],
    "cashback": ["promo_cashback"],
    "discount": ["promo_cashback"],
    "murabha": ["murabha_bnpl_plus", "murabha_early_settlement"],
    "early settlement": ["murabha_early_settlement"],
    "national id fraud": ["nid_fraud", "unregistered_dues"],
    "phone number already": ["phone_archiving"],
    "suspected fraud": ["unrecognized_charge"],
    "refund blocked": ["refunds_cancellations", "merchant_fraud"],
    "declined order": ["declined_order"],
    "change phone": ["change_phone"],
    "credit bureau": ["aecb_support", "credit_bureau"],
    "collection agency": ["collection_process"],
    "contact from": ["contact_merchant"],
    "manager": ["manager_escalation"],
    "compensation": ["compensation_policy", "manager_escalation"],
    "passcode": ["account_passcode"],
    "lavender": ["lavender_membership", "smart_membership"],
    "tamara health": ["tamara_health"],
    "claims fraud": ["dispute", "merchant_fraud"],
    "wallet refund": ["tamaras_wallet", "refunds_cancellations"],
    "duplicate charge": ["unrecognized_charge"],
    "incorrect refund": ["incorrect_refund", "refunds_cancellations"],
    "late refund": ["refunds_cancellations"],
    "about tamara": ["about_tamara_general"],
    "app issues": ["about_tamara_general"],
    "jailbroken": ["feedback_jailbroken"],
    "feedback": ["feedback_jailbroken"],
}


def missing_topics_report(rows, cms):
    topic_ids = {t["id"] for t in cms.get("topics") or []}
    topic_names = {norm(t.get("name", "")): t["id"] for t in cms.get("topics") or []}
    missing = []
    covered = []
    for r in rows:
        issue_n = norm(r["issue"])
        matched_ids = set()
        for needle, ids in SHEET_THEME_TO_TOPICS.items():
            if needle in issue_n:
                for tid in ids:
                    if tid in topic_ids:
                        matched_ids.add(tid)
        # also fuzzy name contains
        for name, tid in topic_names.items():
            if name and name in issue_n:
                matched_ids.add(tid)
        entry = {
            "sheet_row": r["row"],
            "team": r["team"],
            "sla": r["sla"],
            "issue": r["issue"][:180].replace("\n", " | "),
            "matched_topics": sorted(matched_ids),
        }
        if matched_ids:
            covered.append(entry)
        else:
            missing.append(entry)
    return covered, missing


def ensure_missing_topics(cms, rows_by):
    """Create SLA shell topics + escalation nodes for sheet rows with no Atlas topic."""
    created = []
    existing_ids = {t["id"] for t in cms.get("topics") or []}
    cms.setdefault("nodes", {})
    cms.setdefault("tree", {})
    cms.setdefault("policies", {})
    for spec in MISSING_TOPICS_TO_CREATE:
        row = rows_by.get(spec["sheet_row"])
        sla = (row["sla"] if row and row.get("sla") else spec["sla"])
        sla = re.sub(r"[ \t]{2,}", " / ", (sla or "").strip()).strip()
        team = spec["team"]
        node_id = spec["node_id"]
        cms["nodes"][node_id] = {
            "type": "outcome",
            "title": spec["name"],
            "prompt": f"Escalate per Transfers SLA. Issue: {spec['desc']}",
            "sla": sla,
            "team": team,
            "system_action": f"Escalate to {team}. Use Transfers SLA row {spec['sheet_row']}.",
            "_sla_source": TRANSFERS_URL,
            "_sla_authority": "Transfers SLA.xlsx",
            "_sla_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if spec["id"] not in existing_ids:
            cms["topics"].append({
                "id": spec["id"],
                "tag": spec["tag"],
                "name": spec["name"],
                "desc": spec["desc"],
            })
            existing_ids.add(spec["id"])
            created.append({"topic_id": spec["id"], "node_id": node_id, "sheet_row": spec["sheet_row"], "sla": sla})
        else:
            # refresh desc/sla on existing shell
            for t in cms["topics"]:
                if t["id"] == spec["id"]:
                    t["desc"] = spec["desc"]
                    break
            created.append({"topic_id": spec["id"], "node_id": node_id, "sheet_row": spec["sheet_row"], "sla": sla, "refreshed": True})
        cms["tree"][spec["id"]] = {
            "step1": {
                "prompt": f"{spec['name']} — escalate using Transfers SLA ({sla}).",
                "options": [{"text": f"Escalate to {team} — SLA {sla}", "next": node_id}],
            }
        }
        cms["policies"][spec["id"]] = (
            f"TRANSFERS SLA AUTHORITY\n• Team: {team}\n• SLA: {sla}\n"
            f"• Sheet row: {spec['sheet_row']}\n• Source: {TRANSFERS_URL}"
        )
    return created


def apply_node_updates(cms, rows_by):
    applied = []
    skipped = []
    seen = {}
    for sheet_row, node_id, sla, team in CURATED_NODE_UPDATES:
        seen[node_id] = (sheet_row, sla, team)

    for node_id, (sheet_row, sla, team) in seen.items():
        node = cms["nodes"].get(node_id)
        if not node:
            skipped.append({"node_id": node_id, "reason": "missing node"})
            continue
        row = rows_by.get(sheet_row) if sheet_row else None
        # Prefer exact sheet SLA text; sheet_row 0 = curated exact (Due Date Preference exceptions)
        if row and row.get("sla"):
            new_sla = re.sub(r"[ \t]{2,}", " / ", row["sla"].strip()).strip()
        else:
            new_sla = sla
        old = node.get("sla")
        node["sla"] = new_sla
        if team:
            node["team"] = team
        node["_sla_source"] = TRANSFERS_URL
        node["_sla_authority"] = "Transfers SLA.xlsx"
        node["_sla_sheet_row"] = sheet_row
        node["_sla_updated_at"] = datetime.now(timezone.utc).isoformat()
        applied.append({"node_id": node_id, "sheet_row": sheet_row, "old_sla": old, "new_sla": new_sla, "team": team})
    return applied, skipped


def make_w_p(text, bold=False):
    p = ET.Element(f"{W}p")
    r = ET.SubElement(p, f"{W}r")
    if bold:
        rPr = ET.SubElement(r, f"{W}rPr")
        ET.SubElement(rPr, f"{W}b")
    t = ET.SubElement(r, f"{W}t")
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    return p


def update_kb_ashry(rows, catalog_count):
    if not KB.exists():
        return {"ok": False, "reason": "KB file missing"}
    if not KB_BACKUP.exists():
        shutil.copy2(KB, KB_BACKUP)

    tmp = ROOT / "_kb_ashry_edit.docx"
    shutil.copy2(KB, tmp)

    with zipfile.ZipFile(tmp, "r") as zin:
        namelist = zin.namelist()
        doc_xml = zin.read("word/document.xml")
        others = {n: zin.read(n) for n in namelist if n != "word/document.xml"}

    # Register namespaces to preserve prefixes better
    ET.register_namespace("w", "http://schemas.openxmlformats.org/wordprocessingml/2006/main")
    ET.register_namespace("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")
    ET.register_namespace("wp", "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing")
    ET.register_namespace("a", "http://schemas.openxmlformats.org/drawingml/2006/main")
    ET.register_namespace("pic", "http://schemas.openxmlformats.org/drawingml/2006/picture")

    root = ET.fromstring(doc_xml)
    body = root.find(f"{W}body")
    if body is None:
        return {"ok": False, "reason": "no body"}

    # Remove previous generated appendix if present
    children = list(body)
    # sectPr is usually last
    sect = None
    if children and children[-1].tag == f"{W}sectPr":
        sect = children[-1]
        body.remove(sect)

    # Delete existing marker paragraphs block
    texts = []
    for p in body.findall(f"{W}p"):
        txt = "".join(t.text or "" for t in p.findall(f".//{W}t"))
        texts.append((p, txt))
    start_idx = None
    end_idx = None
    for i, (p, txt) in enumerate(texts):
        if "ATLAS TRANSFERS SLA AUTHORITY" in txt:
            start_idx = i
        if start_idx is not None and "END ATLAS TRANSFERS SLA AUTHORITY" in txt:
            end_idx = i
            break
    if start_idx is not None and end_idx is not None:
        for p, _ in texts[start_idx : end_idx + 1]:
            body.remove(p)

    # Also rewrite known conflicting SLA lines for National ID Fraud / ID verification where safe
    replacements = 0
    for p in body.findall(f"{W}p"):
        full = "".join(t.text or "" for t in p.findall(f".//{W}t"))
        new_full = full
        # Align KB NID fraud escalation SLA mentions toward Transfers (5 calendar days)
        if re.search(r"(?i)National ID Fraud", full) and re.search(r"(?i)SLA", full):
            new_full = re.sub(r"(?i)SLA\s*[-=:>→]?\s*7\s*business days", "SLA → 5 calendar days (Transfers SLA authority)", new_full)
        # Standalone SLA 7 business days immediately after National ID Fraud issue type blocks is handled via appendix; keep ID verification technical SLA if clearly ID verification typo path
        if new_full != full:
            # rewrite all w:t into one
            for t in p.findall(f".//{W}t"):
                t.text = ""
            ts = p.findall(f".//{W}t")
            if ts:
                ts[0].text = new_full
                replacements += 1
            else:
                # create run
                r = ET.SubElement(p, f"{W}r")
                t = ET.SubElement(r, f"{W}t")
                t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                t.text = new_full
                replacements += 1

    # Append authority appendix
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    appendix_paras = [
        make_w_p("ATLAS TRANSFERS SLA AUTHORITY", bold=True),
        make_w_p(f"Updated from Transfers SLA.xlsx on {stamp}. This matrix is the source of truth for escalation Team + SLA."),
        make_w_p(f"Source link: {TRANSFERS_URL}"),
        make_w_p(f"Catalog situations in Atlas Transfers SLA topic: {catalog_count}"),
        make_w_p(""),
        make_w_p("Team | SLA | Issue / Situation", bold=True),
    ]
    for r in rows:
        issue_one = " / ".join([ln.strip(" -•\t") for ln in r["issue"].splitlines() if ln.strip()][:3])
        line = f"{r['team']} | {r['sla'] or '-'} | {issue_one}"
        appendix_paras.append(make_w_p(line))
    appendix_paras.append(make_w_p(""))
    appendix_paras.append(make_w_p("Note: Where this appendix conflicts with older SLA lines in this KB, follow Transfers SLA."))
    appendix_paras.append(make_w_p("END ATLAS TRANSFERS SLA AUTHORITY", bold=True))

    for p in appendix_paras:
        body.append(p)
    if sect is not None:
        body.append(sect)

    new_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    out_path = KB
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in others.items():
            zout.writestr(name, data)
        zout.writestr("word/document.xml", new_xml)
    tmp.unlink(missing_ok=True)
    return {"ok": True, "replacements": replacements, "backup": str(KB_BACKUP), "appendix_rows": len(rows)}


def main():
    store = json.loads(STORE.read_text(encoding="utf-8"))
    cms = store["cmsData"]
    rows = read_transfers(XLSX)
    rows_by = {r["row"]: r for r in rows}
    catalog = build_catalog(rows)
    cms["transfersSlaCatalog"] = catalog

    # Ensure pinned topic first
    topics = [t for t in cms.get("topics", []) if t.get("id") != "transfers_sla"]
    topic = {
        "id": "transfers_sla",
        "tag": "Topic 00",
        "name": "Transfers SLA",
        "desc": "Full Transfers SLA matrix (source of truth) — pick category & situation for Team, SLA, Status, template.",
        "pinned": True,
        "uniqueType": "transfers_sla_browser",
    }
    cms["topics"] = [topic] + topics
    # Keep / rebuild category decision tree when present; always ensure Claims SLA entry
    tree = cms.setdefault("tree", {})
    tr = tree.get("transfers_sla")
    if not isinstance(tr, dict) or not ((tr.get("step1") or {}).get("options")):
        tree["transfers_sla"] = {
            "step1": {
                "prompt": "Transfers SLA — SOURCE OF TRUTH. Pick category first, then situation (use Claims SLA for Tier + Buyer Protection matrix):",
                "options": [],
            }
        }
        tr = tree["transfers_sla"]
    step1 = tr.setdefault("step1", {"prompt": "", "options": []})
    opts = step1.setdefault("options", [])
    opts[:] = [
        o
        for o in opts
        if not (
            isinstance(o, dict)
            and (
                o.get("next") == "step_trf_CLAIMS_SLA_TIER"
                or str(o.get("text", "")).strip() == "Claims SLA"
            )
        )
    ]
    opts.insert(0, {"text": "Claims SLA", "next": "step_trf_CLAIMS_SLA_TIER"})
    tr["step_trf_CLAIMS_SLA_TIER"] = {
        "prompt": "Claims SLA — Step 1: What is the Merchant Tier?",
        "options": [
            {"text": "T0", "next": "step_trf_CLAIMS_SLA_BP_T0"},
            {"text": "T1", "next": "step_trf_CLAIMS_SLA_BP_T1"},
            {"text": "T2", "next": "step_trf_CLAIMS_SLA_BP_T2"},
            {"text": "T3", "next": "step_trf_CLAIMS_SLA_BP_T3"},
        ],
    }
    for tier, yes_leaf, no_leaf in [
        ("T0", "CLAIM_SLA_T0_T2_BP", "CLAIM_SLA_T0_T2_NO_BP"),
        ("T1", "CLAIM_SLA_T0_T2_BP", "CLAIM_SLA_T0_T2_NO_BP"),
        ("T2", "CLAIM_SLA_T0_T2_BP", "CLAIM_SLA_T0_T2_NO_BP"),
        ("T3", "CLAIM_SLA_T3_BP", "CLAIM_SLA_T3_NO_BP"),
    ]:
        tr[f"step_trf_CLAIMS_SLA_BP_{tier}"] = {
            "prompt": f"Claims SLA — Step 2 (Tier {tier}): Is the customer Buyer Protection eligible?",
            "options": [
                {"text": "Yes — Buyer Protection Eligible (✅)", "next": yes_leaf},
                {"text": "No — Buyer Protection Ineligible (❌)", "next": no_leaf},
            ],
        }
    cms.setdefault("policies", {})["transfers_sla"] = (
        "TRANSFERS SLA — SOURCE OF TRUTH\n"
        "• This topic mirrors Transfers SLA.xlsx.\n"
        "• Select Category then Situation — or choose Claims SLA for Tier + Buyer Protection.\n"
        "• Use Team / SLA / Status shown before escalating.\n"
        "• Never communicate Action SLA to the customer.\n"
        f"• Sheet: {TRANSFERS_URL}"
    )

    created_topics = ensure_missing_topics(cms, rows_by)
    applied, skipped = apply_node_updates(cms, rows_by)
    covered, missing = missing_topics_report(rows, cms)

    # Row-by-row audit (sheet → topics/nodes)
    node_by_row = {}
    for a in applied:
        node_by_row.setdefault(a["sheet_row"], []).append(a["node_id"])
    for c in created_topics:
        node_by_row.setdefault(c["sheet_row"], []).append(c["node_id"])
    row_audit = []
    for r in rows:
        matched = next((x for x in covered if x["sheet_row"] == r["row"]), None)
        miss = next((x for x in missing if x["sheet_row"] == r["row"]), None)
        row_audit.append({
            "row": r["row"],
            "team": r["team"],
            "sla": r["sla"],
            "issue": r["issue"][:160].replace("\n", " | "),
            "matched_topics": (matched or miss or {}).get("matched_topics", []),
            "mapped_nodes": node_by_row.get(r["row"], []),
            "coverage": "covered" if matched else ("missing_topic" if miss else "unknown"),
        })

    cms.setdefault("slaSources", {})
    cms["slaSources"].update({
        "transfersSheetUrl": TRANSFERS_URL,
        "transfersSheetId": "1uChI9CY4xi_vMw0P8mDYXeLkHNY2-R4OZ9gpNnbm87c",
        "authority": "Transfers SLA.xlsx",
        "kbAshryLocalPath": str(KB),
        "kbAshrySyncedFromTransfersAt": datetime.now(timezone.utc).isoformat(),
        "lastTransfersCatalogCount": len(catalog),
        "lastTransfersBuiltAt": datetime.now(timezone.utc).isoformat(),
        "accuracyMode": "sheet_exact_sla_text + curated_node_map + missing_topics_created",
    })

    kb_result = update_kb_ashry(rows, len(catalog))

    store["cmsData"] = cms
    store["revision"] = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    STORE.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "authority": "Transfers SLA.xlsx",
        "catalog_count": len(catalog),
        "sheet_rows": len(rows),
        "topics_created": created_topics,
        "nodes_updated": applied,
        "nodes_skipped": skipped,
        "topics_covered_rows": len(covered),
        "topics_missing_rows": missing,
        "row_audit": row_audit,
        "kb_update": kb_result,
        "existing_atlas_topics": [{"id": t["id"], "name": t["name"]} for t in cms["topics"]],
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("catalog", len(catalog), "updated nodes", len(applied), "created topics", len(created_topics), "missing topic rows", len(missing))
    for a in applied:
        print("NODE", a["node_id"], a["old_sla"], "->", a["new_sla"])
    print("--- CREATED TOPICS ---")
    for c in created_topics:
        print(c)
    print("--- MISSING TOPIC COVERAGE ---")
    for m in missing:
        print(f"Row {m['sheet_row']}: [{m['team']}] {m['sla']} | {m['issue']}")
    print("KB", kb_result)


if __name__ == "__main__":
    main()
