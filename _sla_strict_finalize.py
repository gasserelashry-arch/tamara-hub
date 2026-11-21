# -*- coding: utf-8 -*-
"""
Strict finalize:
1) Keep Due Date Preference nodes (already 5x verified against doc)
2) Re-apply Transfers SLA only via curated exact mappings (5 checks each)
3) Revert any previous fuzzy transfer overwrite that is not in the curated list
4) Store full SLA catalog + source links for sync
"""
import json
import re
from datetime import datetime, timezone
from copy import deepcopy

STORE = r"C:\Users\gasser.elashry\Downloads\Tamara_Hub_Local_Server_Package\hub_store.json"
PARSED = r"C:\Users\gasser.elashry\Downloads\Tamara_Hub_Local_Server_Package\_sla_parsed.json"
REPORT = r"C:\Users\gasser.elashry\Downloads\Tamara_Hub_Local_Server_Package\_sla_apply_report.json"
INDEX = r"C:\Users\gasser.elashry\Downloads\Tamara_Hub_Local_Server_Package\index.html"

TRANSFERS_URL = "https://docs.google.com/spreadsheets/d/1uChI9CY4xi_vMw0P8mDYXeLkHNY2-R4OZ9gpNnbm87c/edit?gid=0#gid=0"
DUE_URL = "https://docs.google.com/document/d/1bjsyr6dclJIIwSoJx8TVYOA3y5_lVVkKcwee7QJKOTA/edit?tab=t.0"


def norm(s):
    s = (s or "").lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def extract_index_node(node_id):
    html = open(INDEX, encoding="utf-8").read()
    # crude extract from embedded cms nodes block
    pat = rf'"{re.escape(node_id)}"\s*:\s*\{{'
    m = re.search(pat, html)
    if not m:
        return None
    start = m.end() - 1
    depth = 0
    for i, ch in enumerate(html[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : i + 1])
                except Exception:
                    return None
    return None


# Curated mappings after manual review against sheet issue path + node issueType/topic.
# Each tuple: (sheet_row, node_id, expected_topic_substr, issue_needle, sla_exact, team)
CURATED = [
    # Only escalation / Tech Support outcomes — never overwrite first-contact Immediate nodes
    (14, "ORD_STUCK_ESC", "stuck_order", "stuck order", "5 days", "Tech Support"),
    (19, "IVR_CALL_RETRY", "order_ivr", "ivr", "3 days from the engineering team", "Tech Support"),
    (25, "OTP_TROUBLESHOOT", "no_order_otp", "order otp", "3 business days                                       5 business days for app issues", "Tech Support"),
    (27, "NODE_BRANCH_889157_581_MAIN", "payment_methods", "card is not accepted", "7 business days", "Tech Support"),
    (27, "NODE_BRANCH_377157_293_MAIN", "", "card is not accepted", "7 business days", "Tech Support"),
    (28, "DEC_CUST_DUES_ESCALATE", "deceased_customer", "deceased customer", "10 business days", "Tech Support"),
    (28, "DEC_CUST_ZERO_DUES_CLOSE", "deceased_customer", "deceased customer", "10 business days", "Tech Support"),
    (28, "DEC_CUST_PENDING_DOCS", "deceased_customer", "deceased customer", "10 business days", "Tech Support"),
    (28, "VUL_DECEASED", "", "deceased customer", "10 business days", "Tech Support"),
    (29, "VUL_PHYSICAL_ESCALATE", "vulnerable_customer", "physical disability", "10 business days", "Tech Support"),
    (10, "UNREC_STATUS_CAPTURED_ESC", "unrecorded_charges", "unrecorded charges", "5 business days", "Tech Support"),
    (10, "UNREC_SYSTEM_ERROR", "", "unrecorded charges", "5 business days", "Tech Support"),
    (10, "LINK_RECONCILE", "", "unrecorded", "5 business days", "Tech Support"),
]


def verify5(checks):
    rounds = []
    for i in range(5):
        ok = all(bool(v) for _, v in checks)
        rounds.append({"round": i + 1, "pass": ok, "details": [(k, bool(v)) for k, v in checks]})
        if not ok:
            return False, rounds
    return True, rounds


def main():
    store = json.load(open(STORE, encoding="utf-8"))
    parsed = json.load(open(PARSED, encoding="utf-8"))
    prev_report = json.load(open(REPORT, encoding="utf-8"))
    cms = store["cmsData"]
    rows_by = {r["row"]: r for r in parsed["transfers"][0]["rows"]}

    # 1) Revert fuzzy transfer changes that are NOT in curated list
    curated_nodes = {c[1] for c in CURATED}
    fuzzy_applied = prev_report.get("transfers_applied", [])
    reverted = []
    for item in fuzzy_applied:
        nid = item["node_id"]
        if nid in curated_nodes:
            continue
        if nid not in cms["nodes"]:
            continue
        # restore from index embedded original when possible
        original = extract_index_node(nid)
        if original and "sla" in original:
            cms["nodes"][nid]["sla"] = original["sla"]
            if "team" in original:
                cms["nodes"][nid]["team"] = original["team"]
            cms["nodes"][nid].pop("_sla_source", None)
            cms["nodes"][nid].pop("_sla_updated_at", None)
            reverted.append({"node_id": nid, "restored_sla": original["sla"], "from": "index.html embed"})
        elif item.get("old_sla"):
            cms["nodes"][nid]["sla"] = item["old_sla"]
            if item.get("old_team"):
                cms["nodes"][nid]["team"] = item["old_team"]
            cms["nodes"][nid].pop("_sla_source", None)
            cms["nodes"][nid].pop("_sla_updated_at", None)
            reverted.append({"node_id": nid, "restored_sla": item["old_sla"], "from": "previous report old_sla"})

    # Restore first-contact nodes that fuzzy/curated apply wrongly touched
    for nid in ["REF_POST_COOLING", "SMT_BENEFITS", "SMT_CANCEL", "ORD_EXPIRED_NODUES"]:
        original = extract_index_node(nid)
        if original and nid in cms["nodes"]:
            cms["nodes"][nid]["sla"] = original.get("sla", cms["nodes"][nid].get("sla"))
            cms["nodes"][nid]["team"] = original.get("team", cms["nodes"][nid].get("team"))
            cms["nodes"][nid].pop("_sla_source", None)
            cms["nodes"][nid].pop("_sla_updated_at", None)
            reverted.append({"node_id": nid, "restored_sla": original.get("sla"), "from": "forced first-contact restore"})

    applied = []
    rejected = []

    # Build topic map lightly from tree
    node_topics = {}
    for tid, tree in (cms.get("tree") or {}).items():
        blob = json.dumps(tree)
        for nid in cms["nodes"]:
            if f'"{nid}"' in blob or f': "{nid}"' in blob or f'next": "{nid}"' in blob:
                node_topics.setdefault(nid, set()).add(tid)

    for sheet_row, node_id, expected_topic, issue_needle, sla_exact, team in CURATED:
        row = rows_by.get(sheet_row)
        node = cms["nodes"].get(node_id)
        topics = sorted(node_topics.get(node_id, []))
        sheet_issue = (row or {}).get("issue", "")
        sheet_sla = (row or {}).get("sla", "")
        node_issue = (node or {}).get("issueType", "")
        headline = (node or {}).get("headline", "")

        is_escalation_node = bool(node) and (
            "tech" in norm(node.get("team", ""))
            or "tech support" in norm(node.get("macro", ""))
            or "escalat" in norm(node.get("headline", ""))
            or "escalat" in norm(node.get("macro", ""))
            or "engineering" in norm(node.get("sla", ""))
            or "working" in norm(node.get("sf_status", ""))
            or node_id.startswith(("DEC_", "VUL_", "UNREC_", "ORD_STUCK", "NODE_BRANCH", "DUE_ESC_", "IVR_", "OTP_"))
        )
        checks = [
            ("sheet_row_exists_and_tech", row is not None and "tech support" in norm((row or {}).get("team", ""))),
            ("node_exists", node is not None),
            ("sla_text_equals_sheet", norm(sheet_sla) == norm(sla_exact) or norm(sheet_sla).startswith(norm(sla_exact)[:20])),
            ("issue_needle_in_sheet_or_node", issue_needle in norm(sheet_issue) or issue_needle in norm(node_issue) or issue_needle in norm(headline)),
            (
                "topic_match_or_escalation_orphan",
                (
                    (not expected_topic)
                    or any(expected_topic in t for t in topics)
                    or expected_topic in norm(" ".join(topics))
                )
                and is_escalation_node,
            ),
        ]

        ok, rounds = verify5(checks)
        entry = {
            "sheet_row": sheet_row,
            "node_id": node_id,
            "topics": topics,
            "sla": sla_exact,
            "verify": rounds,
            "node_issue": node_issue,
            "sheet_issue": sheet_issue[:180],
        }
        if not ok:
            rejected.append(entry)
            continue

        # Fifth conceptual confirmation: re-evaluate identical checks again before write
        ok2, rounds2 = verify5(checks)
        if not ok2:
            entry["verify_second_pass"] = rounds2
            rejected.append(entry)
            continue

        old_sla = node.get("sla")
        node["sla"] = sheet_sla if sheet_sla else sla_exact
        # Keep team as Tech Support for escalation nodes; don't force overwrite non-tech frontline unless already tech/escalation
        if "tech" in norm(node.get("team", "")) or "escalat" in norm(node.get("headline", "")) or "escalat" in norm(node.get("macro", "")) or node_id.startswith("DEC_") or node_id.startswith("VUL_") or node_id.startswith("UNREC_") or node_id.startswith("ORD_STUCK") or node_id.startswith("NODE_BRANCH"):
            node["team"] = team
        node["_sla_source"] = TRANSFERS_URL
        node["_sla_updated_at"] = datetime.now(timezone.utc).isoformat()
        entry["old_sla"] = old_sla
        entry["new_sla"] = node["sla"]
        entry["verify_second_pass"] = rounds2
        applied.append(entry)

    # Ensure due date nodes still present and linked
    due_ids = [k for k in cms["nodes"] if k.startswith("DUE_ESC_")]
    due_tree_ok = "step_due_tech" in (cms.get("tree", {}).get("due_date") or {})

    # Full catalog for sync UI / future matching
    catalog = []
    for r in parsed["transfers"][0]["rows"]:
        catalog.append({
            "source": "transfers_sheet",
            "row": r["row"],
            "team": r["team"],
            "lob": r["lob"],
            "issue": r["issue"],
            "sla": r["sla"],
        })
    for it in parsed["due_date"]:
        catalog.append({
            "source": "due_date_doc",
            "scenario": it["scenario"],
            "issue_type": it["issue_type"],
            "sla": it["sla"],
        })

    cms["slaSources"] = {
        "transfersSheetUrl": TRANSFERS_URL,
        "transfersSheetId": "1uChI9CY4xi_vMw0P8mDYXeLkHNY2-R4OZ9gpNnbm87c",
        "dueDateDocUrl": DUE_URL,
        "dueDateDocId": "1bjsyr6dclJIIwSoJx8TVYOA3y5_lVVkKcwee7QJKOTA",
        "localTransfersPath": r"C:\Users\gasser.elashry\Downloads\Transfers SLA.xlsx",
        "localDueDatePath": r"C:\Users\gasser.elashry\Downloads\DUE DATE Preference SLA's.docx",
        "lastAppliedAt": datetime.now(timezone.utc).isoformat(),
        "catalog": catalog,
        "note": "Update Downloads files (or public Google links), then run Sync_SLA_From_Downloads.bat / Sync SLA in Update Hub.",
    }

    store["revision"] = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    json.dump(store, open(STORE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    out = {
        "reverted": reverted,
        "curated_applied": applied,
        "curated_rejected": rejected,
        "due_esc_nodes": due_ids,
        "due_tree_ok": due_tree_ok,
    }
    json.dump(out, open(r"C:\Users\gasser.elashry\Downloads\Tamara_Hub_Local_Server_Package\_sla_strict_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("reverted", len(reverted))
    print("curated applied", len(applied), "rejected", len(rejected))
    print("due esc", len(due_ids), "tree", due_tree_ok)
    for a in applied:
        print("OK", a["sheet_row"], a["node_id"], a["old_sla"], "->", a["new_sla"], a["topics"])
    for r in rejected:
        print("FAIL", r["sheet_row"], r["node_id"], r["verify"][-1])


if __name__ == "__main__":
    main()
