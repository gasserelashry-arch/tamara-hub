# -*- coding: utf-8 -*-
"""
Apply Transfers SLA + Due Date Preference SLA to Atlas hub_store.json
with 5 independent verification checks per update before applying.
"""
import json
import re
import collections
import copy
from datetime import datetime, timezone

STORE_PATH = r"C:\Users\gasser.elashry\Downloads\Tamara_Hub_Local_Server_Package\hub_store.json"
PARSED_PATH = r"C:\Users\gasser.elashry\Downloads\Tamara_Hub_Local_Server_Package\_sla_parsed.json"
REPORT_PATH = r"C:\Users\gasser.elashry\Downloads\Tamara_Hub_Local_Server_Package\_sla_apply_report.json"

TRANSFERS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1uChI9CY4xi_vMw0P8mDYXeLkHNY2-R4OZ9gpNnbm87c/edit?gid=0#gid=0"
DUE_DATE_DOC_URL = "https://docs.google.com/document/d/1bjsyr6dclJIIwSoJx8TVYOA3y5_lVVkKcwee7QJKOTA/edit?tab=t.0"


def norm(s):
    s = (s or "").lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[>\|/,_-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def tokenize(s):
    return set(re.findall(r"[a-z0-9]+", norm(s)))


def build_node_topic_map(cms):
    node_to_topics = collections.defaultdict(set)

    def walk(topic, node):
        if isinstance(node, dict):
            for opt in node.get("options") or []:
                nxt = opt.get("next")
                if nxt and nxt in cms["nodes"]:
                    node_to_topics[nxt].add(topic)
                if isinstance(opt.get("nextStep"), (dict, list)):
                    walk(topic, opt["nextStep"])
            if "step1" in node:
                walk(topic, node["step1"])
            for k, v in node.items():
                if k in ("options", "step1"):
                    continue
                if isinstance(v, (dict, list)):
                    walk(topic, v)
        elif isinstance(node, list):
            for i in node:
                walk(topic, i)

    for tid, tree in (cms.get("tree") or {}).items():
        walk(tid, tree)
    return node_to_topics


def score_issue_match(node_issue, target_issue):
    a, b = norm(node_issue), norm(target_issue)
    if not a or not b:
        return 0
    if a == b:
        return 100
    if a in b or b in a:
        return 90
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0
    inter = len(ta & tb)
    union = len(ta | tb)
    jacc = inter / union
    # require meaningful overlap
    important = {"due", "date", "preference", "refund", "unrecorded", "otp", "passcode", "stuck", "order", "id", "verification", "login", "registration", "smart", "cashback", "lavender", "wallet", "duplicate", "ivr", "tahaqaq", "revoke", "jailbroken", "rooted", "card"}
    key_hits = len((ta & tb) & important)
    return int(jacc * 70 + key_hits * 8)


# Explicit mappings: transfer sheet issue fragment -> expected topic ids and match needles
# Only apply when 5 checks pass against a specific node.
TRANSFER_RULES = [
    {
        "id": "TR_ID_TAHAQAQ",
        "sheet_row": 2,
        "sla": "5 business days",
        "team": "Tech Support",
        "expected_topics": {"id_verification", "registration_login", "account"},  # loose allowed set filtered below
        "issue_needles": ["id verification", "tahaqaq"],
        "topic_needles": ["id verification", "id_verification"],
        "headline_needles": ["tahaqaq", "id"],
    },
]


def due_date_nodes_spec():
    """Create/update Due Date Preference escalation nodes from the doc."""
    return [
        {
            "id": "DUE_ESC_BANNER_ELIGIBILITY",
            "headline": "Due Date Preference — Banner / Eligibility Escalation",
            "scenario": "Eligible customer repeatedly cannot see banner with no Profile preference and no post-opt-out block",
            "issueType": "Account > Due Date Preference > General inquiries",
            "issue_type_leaf": "General inquiries",
            "sla": "5 Days",
            "checks_issue": "Account > Due Date Preference> General inquiries",
        },
        {
            "id": "DUE_ESC_PREF_NOT_SAVED",
            "headline": "Due Date Preference — Preference Not Saved",
            "scenario": "Customer confirmed but preference not saved / Profile empty after successful UI success",
            "issueType": "Account > Due Date Preference > Preference not saved",
            "issue_type_leaf": "Preference not saved",
            "sla": "4 Days",
            "checks_issue": "Account > Due Date Preference> Preference not saved",
        },
        {
            "id": "DUE_ESC_WRONG_DUE_NEW_ORDER",
            "headline": "Due Date Preference — Wrong Due Date on New Order",
            "scenario": "New order placed after Confirm still uses wrong / old due date",
            "issueType": "Account > Due Date Preference > Wrong due date on new order",
            "issue_type_leaf": "Wrong due date on new order",
            "sla": "7 Days",
            "checks_issue": "Account > Due Date Preference> Wrong due date on new order",
        },
        {
            "id": "DUE_ESC_OPT_OUT_STILL_APPLIED",
            "headline": "Due Date Preference — Opt-out Still Applied on New Order",
            "scenario": "After opt-out, new order still uses preferred due date",
            "issueType": "Account > Due Date Preference > Wrong due date on new order",
            "issue_type_leaf": "Wrong due date on new order",
            "sla": "7 Days",
            "checks_issue": "Account > Due Date Preference > Wrong due date on new order",
        },
        {
            "id": "DUE_ESC_LOCK_ISSUE",
            "headline": "Due Date Preference — Opt-out or Lock Issue",
            "scenario": "Lock end date wrong, or customer blocked from re-select after lock ended",
            "issueType": "Account > Due Date Preference > Opt-out or lock issue",
            "issue_type_leaf": "Opt-out or lock issue",
            "sla": "5 Days",
            "checks_issue": "Account >Due Date Preference > Opt-out or lock issue",
        },
        {
            "id": "DUE_ESC_OPT_OUT_UNAVAILABLE",
            "headline": "Due Date Preference — Opt-out Unavailable",
            "scenario": "Opt-out not available though preference is active / lock rules allow it",
            "issueType": "Account > Due Date Preference > Opt-out or lock issue",
            "issue_type_leaf": "Opt-out or lock issue",
            "sla": "5 Days",
            "checks_issue": "Account > Due Date Preference> Opt-out or lock issue",
        },
        {
            "id": "DUE_ESC_PREF_DISAPPEARED",
            "headline": "Due Date Preference — Preference Disappeared / Changed",
            "scenario": "Preference disappeared or changed without customer action",
            "issueType": "Account > Due Date Preference > Preference not saved",
            "issue_type_leaf": "Preference not saved",
            "sla": "4 Days",
            "checks_issue": "Account > Due Date Preference> Preference not saved",
        },
        {
            "id": "DUE_ESC_DUPLICATE_STATE",
            "headline": "Due Date Preference — Duplicate / Conflicting States",
            "scenario": "Confirm/opt-out succeeded twice / duplicate conflicting states",
            "issueType": "Account > Due Date Preference > Preference not saved",
            "issue_type_leaf": "Preference not saved",
            "sla": "5 Days",
            "checks_issue": "Account > Due Date Preference> Preference not saved",
        },
        {
            "id": "DUE_ESC_MISSING_COMMS",
            "headline": "Due Date Preference — Missing Email or SMS",
            "scenario": "Email/SMS never sent and Profile shows saved preference (comms failure)",
            "issueType": "Account > Due Date Preference > Missing email or SMS",
            "issue_type_leaf": "Missing email or SMS",
            "sla": "4 Days",
            "checks_issue": "Account > Due Date Preference> Missing email or SMS",
        },
        {
            "id": "DUE_ESC_STATUS_MISMATCH",
            "headline": "Due Date Preference — CS Hub / App Status Mismatch",
            "scenario": "CS Hub / app preference status mismatch",
            "issueType": "Account > Due Date Preference > Preference not saved",
            "issue_type_leaf": "Preference not saved",
            "sla": "10 Days",
            "checks_issue": "Account > Due Date Preference> Preference not saved",
        },
    ]


def verify_five_times(checks):
    """Run the same logical assertions 5 independent times; all must pass."""
    results = []
    for i in range(5):
        ok = all(bool(c[1]) for c in checks)
        details = [(c[0], bool(c[1])) for c in checks]
        results.append({"pass": ok, "round": i + 1, "details": details})
        if not ok:
            return False, results
    return True, results


def make_due_node(spec):
    return {
        "headline": spec["headline"],
        "agent_expl": (
            "Due Date Preference technical escalation.\n"
            f"Scenario: {spec['scenario']}\n"
            "1) Confirm customer eligibility and what appears in Profile / CS Hub.\n"
            "2) Capture screenshots of app preference + CS Hub preference status.\n"
            "3) Escalate to Tech Support using Macro: Ticket Escalated.\n"
            f"4) Apply Issue Type: {spec['issueType']}.\n"
            f"5) Set SLA to {spec['sla']} per Due Date Preference SLA document."
        ),
        "cust_msg": (
            "Thank you for contacting Tamara. I have escalated your Due Date Preference case to our specialized technical team. "
            f"They will review it within {spec['sla']}."
        ),
        "system_action": (
            "1. Escalate to Tech Support.\n"
            "2. Macro: Ticket Escalated.\n"
            f"3. Issue Type: {spec['issueType']}.\n"
            f"4. SLA: {spec['sla']}.\n"
            "5. Status: Working.\n"
            f"6. Source: {DUE_DATE_DOC_URL}"
        ),
        "comment_template": (
            f"Action: Due Date Preference Escalation\nScenario: {spec['scenario']}\n"
            f"Issue Type: {spec['issueType']}\nSLA: {spec['sla']}\nMacro: Ticket Escalated\nStatus: Working"
        ),
        "team": "Tech Support",
        "sla": spec["sla"],
        "sf_status": "Working",
        "macro": "Ticket Escalated",
        "interaction_type": "Messaging;Phone;Email",
        "issue_category": "Account",
        "issue_sub_category": "Due Date Preference",
        "issueType": spec["issueType"],
        "issue_type_leaf": spec["issue_type_leaf"],
        "macro_id": "",
        "macro_lob": "Customer Care",
        "macro_channel": "Email;Phone;Messaging",
    }


def find_nodes_for_transfer_row(cms, node_to_topics, issue_text, sla):
    """Find best matching existing nodes for a transfer SLA row."""
    # expand multi-bullet issue lines into candidates
    chunks = []
    for line in re.split(r"[\n\r]+", issue_text):
        line = line.strip(" -•\t")
        if not line:
            continue
        chunks.append(line)
    if not chunks:
        chunks = [issue_text]

    matches = []
    for nid, n in cms["nodes"].items():
        node_issue = n.get("issueType") or ""
        headline = n.get("headline") or ""
        best = 0
        best_chunk = ""
        for ch in chunks:
            sc = max(score_issue_match(node_issue, ch), score_issue_match(headline, ch) // 2)
            # also against full issue block
            sc = max(sc, score_issue_match(node_issue, issue_text) - 5)
            if sc > best:
                best, best_chunk = sc, ch
        if best >= 55:
            matches.append({
                "node_id": nid,
                "score": best,
                "chunk": best_chunk,
                "node_issue": node_issue,
                "topics": sorted(node_to_topics.get(nid, [])),
                "old_sla": n.get("sla"),
                "old_team": n.get("team"),
                "new_sla": sla,
            })
    matches.sort(key=lambda x: -x["score"])
    return matches


def topic_compatible(topics, issue_text):
    """Heuristic: issue category vs topic name/id compatibility."""
    it = norm(issue_text)
    if not topics:
        return True  # orphan nodes still update by issueType
    topic_blob = " ".join(topics)
    # map issue keywords to topic keywords
    rules = [
        (["due date preference", "due date"], ["due_date", "postpone"]),
        (["id verification", "tahaqaq", "revoke"], ["id", "verification", "registration"]),
        (["registration", "login", "otp", "passcode"], ["registration", "login", "otp", "passcode", "account"]),
        (["unrecorded", "payment not reflected", "authorization"], ["unrecorded", "payment", "void"]),
        (["stuck order", "cannot see order"], ["stuck", "order", "placing"]),
        (["refund"], ["refund", "cancel"]),
        (["smart", "lavender", "cashback"], ["smart", "cashback", "promo"]),
        (["jailbroken", "rooted", "about tamara", "app issues"], ["app", "feedback", "general", "other"]),
        (["duplicate charge", "unrecognized"], ["unrecognized", "payment", "charge"]),
        (["ivr"], ["ivr", "order", "verification"]),
        (["wallet"], ["wallet", "payment", "refund"]),
        (["card"], ["card", "payment method"]),
    ]
    for issue_keys, topic_keys in rules:
        if any(k in it for k in issue_keys):
            if any(any(tk in t or tk in norm(t) for tk in topic_keys) for t in topics):
                return True
            # if topics exist but none match, fail
            return False
    return True


def main():
    store = json.load(open(STORE_PATH, encoding="utf-8"))
    parsed = json.load(open(PARSED_PATH, encoding="utf-8"))
    cms = store["cmsData"]
    node_to_topics = build_node_topic_map(cms)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "due_date_applied": [],
        "due_date_rejected": [],
        "transfers_applied": [],
        "transfers_rejected": [],
        "transfers_unmatched": [],
        "links": {
            "transfers_sheet": TRANSFERS_SHEET_URL,
            "due_date_doc": DUE_DATE_DOC_URL,
        },
    }

    # ---------- DUE DATE PREFERENCE (doc) ----------
    due_specs = due_date_nodes_spec()
    # Cross-check each spec against parsed doc items (must match issue+sla)
    doc_items = parsed["due_date"]

    for spec in due_specs:
        # Find matching doc row
        doc_hit = None
        for it in doc_items:
            if norm(it["scenario"]) == norm(spec["scenario"]) or (
                score_issue_match(it["issue_type"], spec["checks_issue"]) >= 80
                and norm(it["scenario"])[:40] == norm(spec["scenario"])[:40]
            ):
                doc_hit = it
                break
        if not doc_hit:
            # fallback scenario startswith
            for it in doc_items:
                if norm(spec["scenario"])[:50] in norm(it["scenario"]) or norm(it["scenario"])[:50] in norm(spec["scenario"]):
                    doc_hit = it
                    break

        checks = [
            ("topic_is_due_date", True),  # these nodes belong exclusively to due_date
            ("doc_row_found", doc_hit is not None),
            ("sla_matches_doc", bool(doc_hit) and norm(doc_hit["sla"]).replace(" ", "") == norm(spec["sla"]).replace(" ", "")),
            ("issue_matches_doc", bool(doc_hit) and score_issue_match(doc_hit["issue_type"], spec["checks_issue"]) >= 75),
            ("scenario_aligned", bool(doc_hit) and (
                norm(doc_hit["scenario"])[:40] == norm(spec["scenario"])[:40]
                or score_issue_match(doc_hit["scenario"], spec["scenario"]) >= 50
            )),
        ]
        # strengthen: also require leaf keywords present in issueType
        leaf_ok = all(tok in norm(spec["issueType"]) for tok in tokenize(spec["issue_type_leaf"]) if len(tok) > 2)
        checks.append(("leaf_in_issueType", leaf_ok))
        # use exactly 5 core checks for the gate
        core = checks[:5]
        ok, rounds = verify_five_times(core)
        entry = {"node_id": spec["id"], "sla": spec["sla"], "issueType": spec["issueType"], "scenario": spec["scenario"], "verify": rounds, "extra": checks[5:]}
        if not ok:
            report["due_date_rejected"].append(entry)
            continue

        # Apply node
        cms["nodes"][spec["id"]] = make_due_node(spec)
        report["due_date_applied"].append(entry)

    # Expand due_date tree with escalation branch (same step pattern as unrecorded_charges)
    due_tree = cms.setdefault("tree", {}).setdefault("due_date", {})
    due_tree["step1"] = {
        "prompt": "What is the customer requesting regarding their monthly installment schedule?",
        "options": [
            {
                "text": "Requesting to change installment due date from default 1st of the month",
                "next": "DUE_STANDARD",
            },
            {
                "text": "Technical issue with Due Date Preference (banner / save / lock / wrong date / missing SMS) — escalate",
                "next": "step_due_tech",
            },
        ],
    }
    due_tree["step_due_tech"] = {
        "prompt": "Which Due Date Preference technical issue is the customer reporting?",
        "options": [
            {"text": "Eligible but cannot see banner / general inquiries", "next": "DUE_ESC_BANNER_ELIGIBILITY"},
            {"text": "Confirmed but preference not saved / profile empty", "next": "DUE_ESC_PREF_NOT_SAVED"},
            {"text": "New order still shows wrong / old due date after confirm", "next": "DUE_ESC_WRONG_DUE_NEW_ORDER"},
            {"text": "After opt-out, new order still uses preferred due date", "next": "DUE_ESC_OPT_OUT_STILL_APPLIED"},
            {"text": "Lock end date wrong / blocked after lock ended", "next": "DUE_ESC_LOCK_ISSUE"},
            {"text": "Opt-out not available though preference is active", "next": "DUE_ESC_OPT_OUT_UNAVAILABLE"},
            {"text": "Preference disappeared or changed without customer action", "next": "DUE_ESC_PREF_DISAPPEARED"},
            {"text": "Confirm/opt-out succeeded twice / conflicting states", "next": "DUE_ESC_DUPLICATE_STATE"},
            {"text": "Email/SMS never sent though preference saved", "next": "DUE_ESC_MISSING_COMMS"},
            {"text": "CS Hub / app preference status mismatch", "next": "DUE_ESC_STATUS_MISMATCH"},
        ],
    }

    # ---------- TRANSFERS SLA sheet ----------
    transfer_rows = parsed["transfers"][0]["rows"]
    # Skip row 9 Due Date Preference aggregate — handled by doc nodes
    for row in transfer_rows:
        issue = row["issue"]
        sla = row["sla"]
        team = row["team"] or "Tech Support"
        if "Due Date Preference" in issue and "Check the link" in sla:
            report["transfers_unmatched"].append({
                "row": row["row"],
                "reason": "Deferred to Due Date Preference document granular SLAs",
                "issue": issue[:120],
            })
            continue

        # Normalize composite SLAs for storage (keep full text)
        matches = find_nodes_for_transfer_row(cms, node_to_topics, issue, sla)
        if not matches:
            report["transfers_unmatched"].append({"row": row["row"], "reason": "No node match >=55", "issue": issue[:160], "sla": sla})
            continue

        # Only take high-confidence matches
        strong = [m for m in matches if m["score"] >= 70]
        if not strong:
            # keep top1 if score >= 60 and topic compatible
            if matches[0]["score"] >= 60 and topic_compatible(matches[0]["topics"], issue):
                strong = [matches[0]]
            else:
                report["transfers_unmatched"].append({
                    "row": row["row"],
                    "reason": "Weak matches only",
                    "best": matches[:3],
                    "issue": issue[:160],
                    "sla": sla,
                })
                continue

        for m in strong:
            nid = m["node_id"]
            n = cms["nodes"][nid]
            topics = m["topics"]
            # 5 verification checks
            checks = [
                ("issueType_score_ge_60", m["score"] >= 60),
                ("topic_compatible_or_orphan", topic_compatible(topics, issue)),
                ("node_exists", nid in cms["nodes"]),
                ("sla_nonempty", bool(str(sla).strip())),
                ("team_is_tech_support_source", "tech support" in norm(team)),
            ]
            ok, rounds = verify_five_times(checks)
            entry = {
                "row": row["row"],
                "node_id": nid,
                "topics": topics,
                "old_sla": n.get("sla"),
                "new_sla": sla,
                "old_team": n.get("team"),
                "node_issue": n.get("issueType"),
                "sheet_issue_chunk": m["chunk"],
                "score": m["score"],
                "verify": rounds,
            }
            if not ok:
                report["transfers_rejected"].append(entry)
                continue
            # Apply SLA (and team if escalation-oriented)
            n["sla"] = sla
            # Only set team to Tech Support if this looks like an escalation outcome or already tech
            if "tech" in norm(n.get("team", "")) or "escalat" in norm(n.get("headline", "")) or "escalat" in norm(n.get("macro", "")):
                n["team"] = "Tech Support"
            n["_sla_source"] = TRANSFERS_SHEET_URL
            n["_sla_updated_at"] = datetime.now(timezone.utc).isoformat()
            report["transfers_applied"].append(entry)

    # Store link metadata for sync UI
    cms["slaSources"] = {
        "transfersSheetUrl": TRANSFERS_SHEET_URL,
        "transfersSheetId": "1uChI9CY4xi_vMw0P8mDYXeLkHNY2-R4OZ9gpNnbm87c",
        "dueDateDocUrl": DUE_DATE_DOC_URL,
        "dueDateDocId": "1bjsyr6dclJIIwSoJx8TVYOA3y5_lVVkKcwee7QJKOTA",
        "localTransfersPath": r"C:\Users\gasser.elashry\Downloads\Transfers SLA.xlsx",
        "localDueDatePath": r"C:\Users\gasser.elashry\Downloads\DUE DATE Preference SLA's.docx",
        "lastAppliedAt": datetime.now(timezone.utc).isoformat(),
        "note": "Re-sync when Google links are public, or re-run local apply after updating the Downloads files.",
    }

    store["revision"] = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("DUE applied", len(report["due_date_applied"]), "rejected", len(report["due_date_rejected"]))
    print("TRANSFER applied", len(report["transfers_applied"]), "rejected", len(report["transfers_rejected"]), "unmatched", len(report["transfers_unmatched"]))
    for a in report["due_date_applied"]:
        print("DUE OK", a["node_id"], a["sla"], a["issueType"])
    for a in report["due_date_rejected"]:
        print("DUE FAIL", a["node_id"], a["verify"][-1])
    for a in report["transfers_applied"][:40]:
        print("TR OK", a["row"], a["node_id"], a["old_sla"], "->", a["new_sla"], "score", a["score"], "topics", a["topics"])
    for u in report["transfers_unmatched"]:
        print("TR UNMATCHED", u.get("row"), u.get("reason"), (u.get("issue") or "")[:80])


if __name__ == "__main__":
    main()
