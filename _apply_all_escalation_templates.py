# -*- coding: utf-8 -*-
"""
Apply Escalation Templates from KB Ashry + department defaults.

Sources:
1) Explicit 'Before Escalating:' blocks (end of topic, above next topic)
2) Escalation paths found by searching 'escalat*' (refunds, edge cases, steps)
3) Department templates (Tech Support / Trust & Safety / Credit / Collections / Manager)
   for topics that escalate but have no dedicated Before Escalating checklist yet

Safety: 10 verification passes per topic mapping; apply only if all pass.
"""
from __future__ import annotations

import json
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\Users\gasser.elashry\Downloads\Tamara_Hub_Local_Server_Package")
KB = Path(r"C:\Users\gasser.elashry\Downloads\KB Ashry.docx")
STORE = ROOT / "hub_store.json"
REPORT = ROOT / "_all_escalation_templates_10pass_report.json"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

# ---- Department base templates (shared comment structure) ----
DEPT_TEMPLATES = {
    "Tech Support": """BEFORE ESCALATING — Tech Support
Source: KB Ashry escalation paths + Transfers SLA department template

Required steps / info to collect (case comment):
• Customer ID
• Order ID(s) / Payment ID(s) (if applicable)
• Exact issue description + reproduction steps
• Screenshots (customer app and/or CS Hub)
• Timestamp of the issue
• What was already tried with the customer
• Correct Issue Type path
• Macro: Ticket Escalated
• Submit as: Working

Do not escalate until the checklist above is complete.""",
    "Trust & Safety": """BEFORE ESCALATING — Trust & Safety
Source: KB Ashry escalation paths + Transfers SLA department template

Required steps / info to collect (case comment):
• Complete Mandatory Fraud Questions (when fraud/ID risk applies)
• Customer ID / National ID last-4 verification outcome
• Order ID(s) / Payment evidence
• Who the customer does/doesn’t recognize (account, order, shipping name)
• OTP / Absher / phone-sharing answers (if asked)
• Police report mention (if phone stolen / identity theft)
• Screenshots / evidence provided
• Resolution type / Issue Type (e.g. National ID Fraud / Suspected fraud)
• Macro: Ticket Escalated
• Submit as: Working
• Do NOT resolve/close fraud cases before T&S review""",
    "Credit - Risk": """BEFORE ESCALATING — Credit Bureau / Credit - Risk
Source: KB Ashry SIMAH/AECB escalation paths + Transfers SLA department template

Required steps / info to collect (case comment):
• Customer ID / Account identifiers
• Credit bureau type (SIMAH / AECB)
• Exact reporting issue (delayed / incorrect / inquiry update)
• Order ID / Application number (if available)
• Dates of the disputed report entries
• Customer requested outcome (update / correction / clearance letter)
• Screenshots from bureau / CS Hub
• Macro: Ticket Escalated (or bureau-specific macro)
• Submit as: Working""",
    "Government Escalation": """BEFORE ESCALATING — Government / Credit Bureau Escalation (UAE)
Source: Transfers SLA + KB Ashry AECB paths

Required steps / info to collect (case comment):
• Customer ID
• AECB / government reference (if any)
• Order ID / Application number
• Exact inquiry/update requested
• Screenshots / letters attached
• Macro: Ticket Escalated
• Submit as: Working
• SLA reference: 24 hours (Transfers SLA)""",
    "Collections": """BEFORE ESCALATING — Collections
Source: KB Ashry Collection Process + Transfers SLA

Required steps / info to collect (case comment):
• Customer ID
• Outstanding dues summary
• Collection agency name (if mentioned)
• Customer request (hold / dispute / settlement / complaint)
• Payment evidence (if customer claims paid)
• Screenshots / CS Hub payment status
• Macro: Ticket Escalated
• Submit as: Working
• SLA reference: 48 business hours (Transfers SLA)""",
    "Manager Escalation": """BEFORE ESCALATING — Manager Escalation
Source: Transfers SLA Manager Escalation template

Required steps / info to collect (case comment):
• Customer ID
• Full case summary and customer ask
• Why L1 could not resolve / exception needed
• Related Order/Payment IDs
• Evidence / screenshots
• Proposed action (compensation / goodwill / exception)
• Macro: Ticket Escalated
• Submit as: Working
• SLA reference: 24 hours""",
}

# Topic → department when no specific KB Before Escalating text exists
TOPIC_DEPT = {
    "contact_merchant": "Tech Support",
    "unregistered_dues": "Trust & Safety",
    "declined_order": "Trust & Safety",
    "cant_see_split_pif": "Tech Support",
    "purchase_limits": "Tech Support",
    "change_phone": "Trust & Safety",
    "phone_archiving": "Trust & Safety",
    "due_date": "Tech Support",
    "tamara_health": "Tech Support",
    "change_email": "Tech Support",
    "delete_account": "Tech Support",
    "reactivate_account": "Tech Support",
    "fraud_ads": "Trust & Safety",
    "incorrect_refund": "Tech Support",
    "merchant_fraud": "Trust & Safety",
    "postpone_dues": "Tech Support",
    "shariah": "Tech Support",
    "nid_fraud": "Trust & Safety",
    "credit_bureau": "Credit - Risk",
    "murabha_bnpl_plus": "Tech Support",
    "cant_see_six": "Tech Support",
    "cant_see_tamara": "Tech Support",
    "expired_order": "Tech Support",
    "stuck_order": "Tech Support",
    "wrong_plan": "Tech Support",
    "no_order_otp": "Tech Support",
    "instore_no_sms": "Tech Support",
    "link_bank": "Tech Support",
    "order_ivr": "Tech Support",
    "vulnerable_customer": "Tech Support",
    "autocharge": "Tech Support",
    "payment_methods": "Tech Support",
    "unrecognized_charge": "Trust & Safety",
    "unrecorded_charges": "Tech Support",
    "voided_payment": "Tech Support",
    "promo_cashback": "Tech Support",
    "refunds_cancellations": "Tech Support",
    "smart_membership": "Tech Support",
    "tamara_card": "Tech Support",
    "lavender_membership": "Tech Support",
    "revoke_id": "Tech Support",
    "dispute": "Trust & Safety",
    "open_banking": "Tech Support",
    "tamaras_wallet": "Tech Support",
    "collection_process": "Collections",
    "manager_escalation": "Manager Escalation",
    "profanity_process": "Manager Escalation",
    "payment_link_feature": "Tech Support",
    "customer_processing_fees": "Tech Support",
    "pay_next_month": "Tech Support",
    "compensation_policy": "Manager Escalation",
    "aecb_support": "Government Escalation",
    "deceased_customer": "Tech Support",
    "about_tamara_general": "Tech Support",
    "feedback_jailbroken": "Tech Support",
    "account_passcode": "Tech Support",
    "murabha_early_settlement": "Tech Support",
}

# Explicit KB content mappings (high priority overrides)
KB_TOPIC_BINDINGS = [
    # Before Escalating markers
    {
        "topics": ["change_phone"],
        "match": lambda h, b: "manual phone number change" in h,
        "team": "Trust & Safety",
        "source": "Before Escalating: Manual Phone Number Change",
    },
    {
        "topics": ["unrecognized_charge"],
        "match": lambda h, b: "order fraud" in h,
        "team": "Trust & Safety",
        "source": "Before Escalating: Order Fraud",
    },
    {
        "topics": ["unrecognized_charge"],
        "match": lambda h, b: "unrecognized charges" in h and "before escalating" in h,
        "team": "Trust & Safety",
        "source": "Before Escalating: Unrecognized Charges",
    },
    # Refunds family
    {
        "topics": ["refunds_cancellations", "incorrect_refund"],
        "match": lambda h, b: (
            "refund has not been triggered" in b
            or "incorrect refund amount" in b
            or ("when will i receive my refund" in h and "customer id" in b)
        ),
        "team": "Tech Support",
        "source": "KB Refund Edge Cases (Escalation)",
    },
    {
        "topics": ["murabha_early_settlement", "murabha_bnpl_plus"],
        "match": lambda h, b: "early settlement" in h or "murabha refund" in b or "early settlement" in b,
        "team": "Tech Support",
        "source": "KB Murabha / Early Settlement escalation",
    },
    {
        "topics": ["tamaras_wallet"],
        "match": lambda h, b: "mada refund was attempted after the 30-day" in b or ("wallet" in b and "refund" in b and "mada" in b),
        "team": "Tech Support",
        "source": "KB Payment/Refund wallet path",
    },
    # NID / T&S
    {
        "topics": ["nid_fraud", "unregistered_dues"],
        "match": lambda h, b: ("mandatory fraud questions" in b)
        or ("trust & safety" in b and "national id" in b)
        or ("national id fraud" in b and "ticket escalated" in b),
        "team": "Trust & Safety",
        "source": "KB National ID Fraud escalate to T&S",
    },
    {
        "topics": ["revoke_id"],
        "match": lambda h, b: "revoke id verification" in h or ("incorrect personal information on file" in b and "ticket escalated" in b),
        "team": "Tech Support",
        "source": "KB Revoke ID Verification escalation scenarios",
    },
    {
        "topics": ["phone_archiving"],
        "match": lambda h, b: "phone number archiving" in h or "phone no. archiving" in b or "tawakkalna/absher" in b,
        "team": "Trust & Safety",
        "source": "KB Phone Number Archiving required documents",
    },
    {
        "topics": ["fraud_ads"],
        "match": lambda h, b: "fraud ads" in h or "fraudulent / misleading ads" in b,
        "team": "Trust & Safety",
        "source": "KB Fraud Ads path",
    },
    # Payments / tech
    {
        "topics": ["payment_methods"],
        "match": lambda h, b: "technical support team" in b and ("card" in b or "3ds" in b or "mada" in b),
        "team": "Tech Support",
        "source": "KB Card decline / payment technical escalation",
    },
    {
        "topics": ["purchase_limits"],
        "match": lambda h, b: "pre-qual" in b or "pre-qualification" in b or "check your limit" in b,
        "team": "Tech Support",
        "source": "KB Pre-qual / purchase limit escalation scenarios",
    },
    {
        "topics": ["unrecorded_charges"],
        "match": lambda h, b: "unrecorded charges" in h or "payment not reflected on cs" in b,
        "team": "Tech Support",
        "source": "KB Unrecorded Charges escalation steps",
    },
    {
        "topics": ["dispute"],
        "match": lambda h, b: "claims creation" in b or "escalate to merchant" in b or "buyer protection" in b,
        "team": "Trust & Safety",
        "source": "KB Claims / Dispute escalation steps",
    },
    {
        "topics": ["credit_bureau"],
        "match": lambda h, b: "simah escalation" in h or ("simah" in b and "escalation steps" in h),
        "team": "Credit - Risk",
        "source": "KB SIMAH Escalation Steps",
    },
    {
        "topics": ["aecb_support"],
        "match": lambda h, b: "aecb" in h or "aecb" in b,
        "team": "Government Escalation",
        "source": "KB AECB Escalation Steps",
    },
    {
        "topics": ["collection_process"],
        "match": lambda h, b: "collection" in h or "collections will update the case" in b,
        "team": "Collections",
        "source": "KB Collection Process escalation scenarios",
    },
    {
        "topics": ["customer_processing_fees"],
        "match": lambda h, b: "processing fees" in h,
        "team": "Tech Support",
        "source": "KB Processing Fees escalation steps",
    },
]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().replace("&", " and ")).strip()


def texts(el):
    return "".join(t.text or "" for t in el.findall(".//w:t", NS)).strip()


def read_paras(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    return [texts(p) for p in root.findall(".//w:p", NS) if texts(p)]


def extract_kb_blocks(paras: list[str]) -> list[dict]:
    """Pull Before Escalating + nearby escalation bodies (end-of-topic style)."""
    blocks = []
    for i, p in enumerate(paras):
        header = p
        label = ""
        kind = None
        m = re.search(r"Before\s+Escalating\s*:\s*(.*)$", p, re.I)
        if m:
            kind = "BEFORE"
            label = re.sub(r"\s+", " ", m.group(1)).strip(" -–—\t")
        elif re.search(
            r"Edge Cases\s*\(Escalation\)|Escalation scenarios|Escalation Steps|escalate(?:d)?\s+to(?:\s+the)?\s+(Tech|Trust|Technical)",
            p,
            re.I,
        ):
            kind = "ESCALATION_PATH"
            for j in range(i - 1, max(-1, i - 30), -1):
                if 8 <= len(paras[j]) <= 120:
                    label = paras[j]
                    break
            if not label:
                label = p[:100]
        else:
            continue

        body = []
        for j in range(i, min(len(paras), i + 40)):
            line = paras[j]
            if j > i and re.search(r"Before\s+Escalating\s*:", line, re.I):
                break
            if j > i and re.match(
                r"^(BNPL|Pay By Finance|ATLAS TRANSFERS|National Identity|Order Tracking|ORDERS\b)",
                line,
                re.I,
            ):
                break
            body.append(line)
            # keep refund checklist compact
            if kind == "ESCALATION_PATH" and len(body) > 25 and re.search(r"support scenarios|macro →", line, re.I):
                break

        text = "\n".join(body)
        # Keep only useful checklist-like lines for template body
        useful = []
        for ln in body:
            if re.search(
                r"step|customer id|order id|required|ask |check |confirm |screenshot|timestamp|"
                r"cool-off|macro|issue type|submit as|refund|escalate|q\d|document|evidence|"
                r"payment|case comment|fraud|otp|police|absher|tawakkalna",
                ln,
                re.I,
            ):
                useful.append(re.sub(r"[ \t]{2,}", " | ", ln).strip())
        blocks.append(
            {
                "idx": i,
                "kind": kind,
                "label": label,
                "header": header,
                "text": text,
                "useful": useful[:40],
            }
        )
    return blocks


def format_kb_template(label: str, team: str, useful: list[str], source: str) -> str:
    lines = [
        f"BEFORE ESCALATING — {label or 'Checklist'}",
        f"Escalate to: {team}",
        f"Source: {source}",
        "",
        "Required steps / info to collect:",
    ]
    for u in useful:
        if not u:
            continue
        if not re.match(r"^(•|-|Q\d|Step|\d)", u):
            u = "• " + u
        lines.append(u[:320])
    lines.append("")
    lines.append("Add all answers in the case comment, then escalate with correct Issue Type / Macro / Status.")
    return "\n".join(lines)


def inject_special_sections(paras: list[str], blocks: list[dict]) -> list[dict]:
    """Add synthetic blocks for important sections that lack Before Escalating header."""
    full = "\n".join(paras)
    # Phone archiving required documents
    for i, p in enumerate(paras):
        if re.search(r"Phone Number Archiving", p, re.I):
            body = paras[i : i + 20]
            blocks.append(
                {
                    "idx": i,
                    "kind": "SPECIAL",
                    "label": "Phone Number Archiving",
                    "header": p,
                    "text": "\n".join(body),
                    "useful": [re.sub(r"[ \t]{2,}", " | ", x) for x in body if re.search(r"required|screenshot|contract|absher|tawakkalna|macro|issue type|step", x, re.I)],
                }
            )
            break
    # Mandatory Fraud Questions
    for i, p in enumerate(paras):
        if re.search(r"Mandatory Fraud Questions", p, re.I):
            body = paras[i : i + 12]
            blocks.append(
                {
                    "idx": i,
                    "kind": "SPECIAL",
                    "label": "Mandatory Fraud Questions (National ID Fraud)",
                    "header": p,
                    "text": "\n".join(body),
                    "useful": [re.sub(r"[ \t]{2,}", " | ", x) for x in body],
                }
            )
            break
    # Refund edge cases checklist (force include even if already present)
    for i, p in enumerate(paras):
        if re.search(r"Edge Cases\s*\(Escalation\)", p, re.I):
            body = paras[i : i + 18]
            blocks.append(
                {
                    "idx": i,
                    "kind": "SPECIAL",
                    "label": "Refunds Edge Cases (Escalation)",
                    "header": p,
                    "text": "\n".join(body),
                    "useful": [re.sub(r"[ \t]{2,}", " | ", x) for x in body if re.search(r"refund|customer id|order id|cool-off|screenshot|incorrect|triggered|loan|case comment", x, re.I)],
                }
            )
            break
    _ = full
    return blocks


def build_topic_templates(paras: list[str], topic_ids: set[str]) -> dict[str, dict]:
    blocks = inject_special_sections(paras, extract_kb_blocks(paras))
    out: dict[str, dict] = {}

    # 1) Explicit KB bindings
    for block in blocks:
        h = norm(block["header"] + " " + block["label"])
        b = norm(block["text"])
        for bind in KB_TOPIC_BINDINGS:
            try:
                matched = bind["match"](h, b)
            except Exception:
                matched = False
            if not matched:
                continue
            team = bind["team"]
            tpl = format_kb_template(block["label"], team, block["useful"] or block["text"].splitlines()[:15], bind["source"])
            for tid in bind["topics"]:
                if tid not in topic_ids:
                    continue
                # Prefer BEFORE blocks over generic paths if both exist
                prev = out.get(tid)
                if prev and prev.get("kind") == "BEFORE" and block["kind"] != "BEFORE":
                    continue
                out[tid] = {
                    "topic_id": tid,
                    "label": block["label"],
                    "team": team,
                    "template": tpl,
                    "source": bind["source"],
                    "kind": block["kind"],
                    "origin": "kb_explicit",
                }

    # 2) Department defaults for remaining topics
    for tid, dept in TOPIC_DEPT.items():
        if tid in out or tid not in topic_ids:
            continue
        base = DEPT_TEMPLATES.get(dept) or DEPT_TEMPLATES["Tech Support"]
        out[tid] = {
            "topic_id": tid,
            "label": f"{dept} (department template)",
            "team": dept,
            "template": base + f"\n\nTopic mapping: {tid}",
            "source": f"Department template — {dept}",
            "kind": "DEPT_DEFAULT",
            "origin": "department_default",
        }
    return out


def run_10_passes(item: dict, cms: dict) -> dict:
    tid = item["topic_id"]
    topic_ids = {t["id"] for t in cms.get("topics") or []}
    tpl = item.get("template") or ""
    passes = []
    passes.append({"id": 1, "name": "topic_exists", "ok": tid in topic_ids})
    passes.append({"id": 2, "name": "template_non_empty", "ok": len(tpl) >= 80})
    passes.append({"id": 3, "name": "has_before_escalating_header", "ok": "BEFORE ESCALATING" in tpl.upper()})
    passes.append({"id": 4, "name": "has_required_info_section", "ok": bool(re.search(r"required|collect|case comment", tpl, re.I))})
    passes.append({"id": 5, "name": "team_assigned", "ok": bool(item.get("team"))})
    passes.append(
        {
            "id": 6,
            "name": "team_is_known_department",
            "ok": any(
                k.lower() in (item.get("team") or "").lower()
                for k in ["Tech", "Trust", "Credit", "Government", "Collections", "Manager"]
            ),
        }
    )
    passes.append({"id": 7, "name": "not_atlas_appendix_bleed", "ok": "ATLAS TRANSFERS SLA AUTHORITY" not in tpl})
    passes.append({"id": 8, "name": "length_under_8k", "ok": len(tpl) <= 8000})
    # KB explicit should mention escalate/team/checklist; dept defaults always ok structurally
    if item.get("origin") == "kb_explicit":
        passes.append({"id": 9, "name": "kb_useful_content", "ok": bool(re.search(r"customer id|order id|step|screenshot|fraud|macro", tpl, re.I))})
    else:
        passes.append({"id": 9, "name": "dept_template_complete", "ok": "Macro: Ticket Escalated" in tpl or "Ticket Escalated" in tpl})
    passes.append({"id": 10, "name": "source_recorded", "ok": bool(item.get("source"))})
    failed = [p for p in passes if not p["ok"]]
    return {
        "topic_id": tid,
        "label": item.get("label"),
        "team": item.get("team"),
        "origin": item.get("origin"),
        "source": item.get("source"),
        "passes_ok": 10 - len(failed),
        "all_passed": not failed,
        "failed": failed,
        "passes": passes,
        "template": tpl,
    }


def apply_templates(cms: dict, verified: list[dict]) -> dict:
    cms.setdefault("beforeEscalatingTemplates", {})
    cms.setdefault("departmentEscalationTemplates", DEPT_TEMPLATES)
    catalog = cms.get("transfersSlaCatalog") or []
    applied = {"topics": [], "catalog": [], "nodes": 0}

    for item in verified:
        tid = item["topic_id"]
        tpl = item["template"]
        team = item["team"]
        cms["beforeEscalatingTemplates"][tid] = {
            "label": item.get("label"),
            "team": team,
            "template": tpl,
            "source": item.get("source"),
            "origin": item.get("origin"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "verified_10_pass": True,
        }
        applied["topics"].append(tid)

        # Update matching catalog rows by team + keyword overlap with topic id tokens
        tokens = [t for t in tid.split("_") if len(t) > 3]
        for cat in catalog:
            cat_team = (cat.get("team") or "").lower()
            blob = norm((cat.get("situation") or "") + " " + (cat.get("issueFull") or "") + " " + (cat.get("category") or ""))
            team_ok = team.split()[0].lower() in cat_team or ("trust" in team.lower() and "trust" in cat_team) or (
                "credit" in team.lower() and "credit" in cat_team
            ) or ("government" in team.lower() and "government" in cat_team) or (
                "collection" in team.lower() and "collection" in cat_team
            ) or ("manager" in team.lower() and "manager" in cat_team)
            token_ok = any(t in blob for t in tokens) if tokens else False
            # For KB explicit refunds etc., prefer token match; for dept defaults, team match is enough if currently PENDING
            pending = (cat.get("escalationTemplate") or "").startswith("PENDING")
            if item.get("origin") == "kb_explicit" and token_ok:
                cat["escalationTemplate"] = tpl
                cat["_escalation_source"] = item.get("source")
                cat["_escalation_verified_10pass"] = True
                applied["catalog"].append(cat.get("id"))
            elif item.get("origin") == "department_default" and team_ok and pending and token_ok:
                cat["escalationTemplate"] = tpl
                cat["_escalation_source"] = item.get("source")
                cat["_escalation_verified_10pass"] = True
                applied["catalog"].append(cat.get("id"))

        # Attach on escalation nodes under topic
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
                node["escalation_template"] = tpl
                if not node.get("team"):
                    node["team"] = team
                node["_escalation_source"] = item.get("source")
                applied["nodes"] += 1
            for opt in node.get("options") or []:
                if opt.get("next"):
                    walk(opt["next"])

        for step in tree.values():
            for opt in (step or {}).get("options") or []:
                if opt.get("next"):
                    walk(opt["next"])

    cms.setdefault("slaSources", {})
    cms["slaSources"]["allEscalationTemplatesAppliedAt"] = datetime.now(timezone.utc).isoformat()
    cms["slaSources"]["escalationKbPath"] = str(KB)
    return applied


def main(apply: bool = False):
    paras = read_paras(KB)
    store = json.loads(STORE.read_text(encoding="utf-8"))
    cms = store["cmsData"]
    topic_ids = {t["id"] for t in cms.get("topics") or [] if t["id"] != "transfers_sla"}
    built = build_topic_templates(paras, topic_ids)

    results = [run_10_passes(built[tid], cms) for tid in sorted(built.keys())]
    ready = [r for r in results if r["all_passed"]]
    blocked = [r for r in results if not r["all_passed"]]

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kb_path": str(KB),
        "topics_built": len(built),
        "ready": len(ready),
        "blocked": len(blocked),
        "kb_explicit": sum(1 for r in ready if r["origin"] == "kb_explicit"),
        "department_default": sum(1 for r in ready if r["origin"] == "department_default"),
        "results": [
            {
                "topic_id": r["topic_id"],
                "origin": r["origin"],
                "team": r["team"],
                "passes_ok": r["passes_ok"],
                "all_passed": r["all_passed"],
                "failed": r["failed"],
                "source": r["source"],
            }
            for r in results
        ],
    }

    if apply and ready:
        applied = apply_templates(cms, ready)
        store["cmsData"] = cms
        store["revision"] = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        STORE.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
        report["apply_status"] = "applied"
        report["applied"] = {
            "topics": applied["topics"],
            "catalog_count": len(set(applied["catalog"])),
            "nodes": applied["nodes"],
        }
    else:
        report["apply_status"] = "dry_run_only" if not apply else "skipped_none_ready"

    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("built", len(built), "ready", len(ready), "blocked", len(blocked))
    print("kb_explicit", report.get("kb_explicit"), "dept_default", report.get("department_default"))
    for r in results:
        mark = "PASS" if r["all_passed"] else "FAIL"
        if r["origin"] == "kb_explicit" or not r["all_passed"]:
            print(mark, r["passes_ok"], "/10", r["topic_id"], "->", r["team"], "|", r["origin"], "|", r["source"][:60])
    print("apply_status", report["apply_status"])
    print("report", REPORT)


if __name__ == "__main__":
    import sys

    main(apply="--apply" in sys.argv)
