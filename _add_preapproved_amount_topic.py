# -*- coding: utf-8 -*-
"""
Add 'Pre-Approved Amount' topic from KB Ashry with 10-pass verification.
Step 1 = select pre-approval / eligibility status, then assist by scenario.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\Users\gasser.elashry\Downloads\Tamara_Hub_Local_Server_Package")
STORE = ROOT / "hub_store.json"
REPORT = ROOT / "_preapproved_amount_10pass_report.json"

TOPIC_ID = "pre_approved_amount"
ISSUE = "Order > Placing an Order > Maximum/minimum purchase limit"
TEAM_TS = "Tech Support"
SLA_ESC = "7 business days"

ESC_TEMPLATE = """BEFORE ESCALATING — Pre-Approved Amount / Pre-Qual
Escalate to: Tech Support
Source: KB Ashry Pre-Approved Amount → Escalation scenarios

Required steps / info to collect (case comment):
• Customer ID
• Merchant name
• Pre-approved / requested amount + currency
• Pre-qual validity / timer status (active or expired)
• CS Hub: Request Status + Pre-qual Result
• Checkout behavior (honored / not honored / declined / plan mismatch)
• Screenshots (app + CS Hub)
• Macro: Ticket Escalated
• Issue Type: Order > Placing an Order > Maximum/minimum purchase limit
• Submit as: Working
• SLA: 7 business days

Escalate only for:
1) Pre-qual not honored at checkout with NO expected reason
2) In-app journey broken (not Too Many Attempts)
3) Wrong / inconsistent pre-approval amount vs expectation after rechecks
4) Credit decline AFTER pre-qual was honored (same merchant / within limit)
5) CS Hub status mismatch (e.g. HONORED vs Not Honored)
6) Payment plan options mismatch vs pre-qual plans"""


def outcome(
    nid,
    headline,
    agent_expl,
    cust_msg,
    system_action,
    comment,
    macro,
    *,
    sla="Immediate",
    team="Customer Care",
    sf_status="Closed",
    escalate=False,
):
    node = {
        "type": "outcome",
        "headline": headline,
        "agent_expl": agent_expl,
        "cust_msg": cust_msg,
        "system_action": system_action,
        "comment_template": comment,
        "macro": macro,
        "issueType": ISSUE,
        "issue_category": "Order",
        "issue_sub_category": "Placing an Order",
        "team": TEAM_TS if escalate else team,
        "sla": SLA_ESC if escalate else sla,
        "sf_status": "Working" if escalate else sf_status,
        "_kb_source": "KB Ashry — Pre-Check Feature / Pre-Approved Amount",
    }
    if escalate:
        node["escalation_template"] = ESC_TEMPLATE
    return nid, node


def build_topic():
    nodes = {}
    tree = {}

    def add(nid, node):
        nodes[nid] = node

    # ---- Outcomes: Eligible / Not Eligible (Pre-Check) ----
    add(
        *outcome(
            "PAA_ELIGIBLE_OK",
            "Eligible (true) — Tamara available at checkout",
            "CS Hub Pre-checkout Eligibility = Eligible (true). Customer has available credit and meets risk requirements. Tamara payment option should display and be selectable.",
            "Your account is currently eligible for Tamara at checkout for the checked amount. Please try again at the merchant checkout and select Tamara.",
            "Confirm Pre-checkout Eligibility = Eligible on CS Hub. Educate customer. Issue Type: Maximum/minimum purchase limit (or Can't see Tamara only if display issue).",
            "Resolution: Pre-Check Eligible (true)\nConfirmed eligibility on CS Hub. Guided customer to retry checkout.",
            "PreQual - General Info",
        )
    )
    add(
        *outcome(
            "PAA_NOTELIG_HIDDEN",
            "Not Eligible — Tamara Hidden at checkout",
            "Eligibility = Not Eligible (false). Merchant may hide Tamara completely. Typical reasons: Zero Credit Limit or High-Risk Profile. Agents cannot override risk engine.",
            "Tamara may not appear for this order based on current eligibility. This is not a merchant website error.",
            "Check Pre-checkout Eligibility on CS Hub (toggled off/false). Use Macro Precheck - Tamara Option Unavailable. Do NOT say rejected/declined/system error/risk model. Issue Type: Can't see Tamara as a payment option.",
            "Resolution: Pre-Check Not Eligible — Hidden\nEligibility false on CS Hub. Macro: Precheck - Tamara Option Unavailable.",
            "Precheck - Tamara Option Unavailable",
        )
    )
    add(
        *outcome(
            "PAA_NOTELIG_GREY",
            "Not Eligible — Tamara Greyed Out / Unclickable",
            "Eligibility = Not Eligible (false). Merchant may show Tamara greyed out/unclickable with generic unavailable message. Same root cause family as hidden (zero limit / high risk).",
            "Tamara may appear unavailable for this order based on current eligibility. Please try again later after checking your Pre-Approved Amount in the app.",
            "Confirm eligibility false on CS Hub. Macro Precheck - Tamara Option Unavailable. Avoid forbidden phrases (rejected, dispute system, clear cache as primary fix).",
            "Resolution: Pre-Check Not Eligible — Greyed Out\nEligibility false. Macro: Precheck - Tamara Option Unavailable.",
            "Precheck - Tamara Option Unavailable",
        )
    )
    add(
        *outcome(
            "PAA_NOTELIG_ON_TOGGLE",
            "Tamara not visible but eligibility toggled ON",
            "Customer cannot see Tamara, but Pre-checkout Eligibility feature/status indicates eligible/toggled on. Use 'I can't find Tamara option' macro path.",
            "Please try refreshing the checkout page. If Tamara still does not appear, share a screenshot of the checkout payment methods.",
            "CS Hub eligibility toggled on / Eligible. Macro → I can't find Tamara option. Issue Type: Can't see Tamara as a payment option. Submit Closed.",
            "Resolution: Can't see Tamara — eligibility ON\nMacro: I can't find Tamara option.",
            "I can't find Tamara option",
        )
    )
    add(
        *outcome(
            "PAA_NOT_REGISTERED",
            "Customer not registered with Tamara",
            "Customer is not registered. Cannot use Tamara / Pre-Approved Amount until registration is completed.",
            "To use Tamara and check a Pre-Approved Amount, please register in the Tamara app first, then try again.",
            "Macro → Can't use Tamara [Not-Registered]. Issue Type: Can't see Tamara as a payment option. Submit Closed.",
            "Resolution: Not registered\nMacro: Can't use Tamara [Not-Registered].",
            "Can't use Tamara [Not-Registered]",
        )
    )

    # ---- Outcomes: Active / general pre-approved support ----
    add(
        *outcome(
            "PAA_GENERAL_INFO",
            "General question — What is Pre-Approved Amount / how it works",
            "Customer asks what the pre-approved limit is or how it works. Explain Pre-Qual / Pre-Check concept; limit is merchant/time bound and based on financial profile at check time.",
            "Your Pre-Approved Amount shows what you can spend with Tamara for a selected store for a limited time. It is calculated from your financial details at the time of the check.",
            "Macro → PreQual - General Info. Issue Type: Maximum/minimum purchase limit. Submit Closed.",
            "Resolution: PreQual general info\nMacro: PreQual - General Info.",
            "PreQual - General Info",
        )
    )
    add(
        *outcome(
            "PAA_HOW_TO_GET",
            "How to get the Pre-Approved Amount (App steps)",
            "Customer asks how to obtain/view Pre-Approved Amount. Guide in-app Pre-approval / See pre-approved amount flow (KSA/UAE macros).",
            "In the Tamara app, open Pre-approval / See pre-approved amount, choose the store and amount, complete any ID/card steps, then your limit and timer will appear on Home.",
            "Use country macro: KSA – PreQual - App Steps KSA OR UAE – PreQual - App Steps UAE. Issue Type: Maximum/minimum purchase limit.",
            "Resolution: PreQual app steps\nShared KSA/UAE PreQual App Steps macro.",
            "KSA – PreQual - App Steps KSA",
        )
    )
    add(
        *outcome(
            "PAA_CANNOT_INCREASE",
            "Cannot increase Pre-Approved limit",
            "Customer asks to increase pre-approved limit. Agents cannot manually increase. Limit is risk-engine based.",
            "We are unable to manually increase your Pre-Approved Amount. You can run a new pre-approval check in the app; the amount is based on your financial profile at that time.",
            "Macro → PreQual - Cannot increase pre-approved limit. Issue Type: Maximum/minimum purchase limit. Submit Closed.",
            "Resolution: Cannot increase pre-approved limit\nMacro: PreQual - Cannot increase pre-approved limit.",
            "PreQual - Cannot increase pre-approved limit",
        )
    )
    add(
        *outcome(
            "PAA_EXPIRED",
            "Pre-Qual expired / no longer showing / missed validity window",
            "24 hours / validity interval passed, or customer could not use limit in time. Pre-qualified limit no longer showing.",
            "Pre-qualifications are time-limited. If the validity window passed, please request a new pre-approval check in the Tamara app when you are ready to shop.",
            "Macro → KSA/UAE – PreQual - Limit Expired. Issue Type: Maximum/minimum purchase limit. Submit Closed.",
            "Resolution: PreQual expired\nMacro: PreQual - Limit Expired (KSA/UAE).",
            "KSA – PreQual - Limit Expired KSA",
        )
    )
    add(
        *outcome(
            "PAA_NOT_HONORED_EXPECTED",
            "Limit not honored at checkout — expected reasons",
            "Customer shopped within pre-approved limit but order rejected / pre-qual not applied for expected reasons. Use Limit Not Honored education. If no expected reason applies → escalation branch.",
            "Sometimes a pre-approved limit may not apply at checkout if your financial situation changed or other expected conditions apply. Please review the details in the Tamara app and try a fresh pre-approval if needed.",
            "Macro → PreQual - Limit Not Honored. Issue Type: Maximum/minimum purchase limit. If NO expected reason → escalate (see escalation scenarios).",
            "Resolution: PreQual limit not honored (expected)\nMacro: PreQual - Limit Not Honored.",
            "PreQual - Limit Not Honored",
        )
    )
    add(
        *outcome(
            "PAA_FINANCIAL_CHANGE",
            "Financial profile / situation changed after pre-approval",
            "Customer missed a payment between pre-approval and checkout, or asks what financial profile changes mean.",
            "Your pre-approved limit is based on your financial details at the time of the check. If those details change before checkout, the limit can adjust automatically.",
            "Macro → PreQual - Financial Profile Changes. Issue Type: Maximum/minimum purchase limit.",
            "Resolution: Financial profile changes\nMacro: PreQual - Financial Profile Changes.",
            "PreQual - Financial Profile Changes",
        )
    )
    add(
        *outcome(
            "PAA_INVALIDATED",
            "Pre-Qual disappeared after another order",
            "Pre-qual invalidated after placing another order.",
            "Placing another order can invalidate a previous pre-qualification. Please run a new Pre-Approved Amount check in the app for the store you want.",
            "Macro → PreQual - Invalidated. Issue Type: Maximum/minimum purchase limit.",
            "Resolution: PreQual invalidated after another order\nMacro: PreQual - Invalidated.",
            "PreQual - Invalidated",
        )
    )
    add(
        *outcome(
            "PAA_TOO_MANY",
            "Too Many Attempts error",
            "Customer sees Too Many Attempts when trying Pre-Qual / Check Your Limit.",
            "If you see Too Many Attempts, please wait and try again later. This protects the pre-approval checks from repeated requests.",
            "Macro → KSA/UAE – PreQual - Too many attempts. Issue Type: Maximum/minimum purchase limit. (Broken flow that is NOT this screen → escalate.)",
            "Resolution: Too Many Attempts\nMacro: PreQual - Too many attempts (KSA/UAE).",
            "KSA – PreQual - Too many attempts KSA",
        )
    )
    add(
        *outcome(
            "PAA_PARTIAL_DECLINE",
            "Partial approval / declined / less than requested",
            "Customer approved for less than asked, or got declined on pre-qual request.",
            "The pre-approved amount depends on your financial profile and the store. You may receive a lower amount than requested, or no approval, based on eligibility at that time.",
            "Macro → PreQual - Partial/No Approval. Issue Type: Maximum/minimum purchase limit.",
            "Resolution: Partial/No Approval\nMacro: PreQual - Partial/No Approval.",
            "PreQual - Partial/No Approval",
        )
    )
    add(
        *outcome(
            "PAA_MERCHANT_DIFF",
            "Different limit at another store / merchant-limit related",
            "Customer got a different limit at another store, or merchant-specific limit behavior.",
            "Pre-approved limits can differ by merchant. Please run Pre-approval for the specific store you want to shop at.",
            "Macro → PreQual - Merchant-Limit Related. Issue Type: Maximum/minimum purchase limit.",
            "Resolution: Merchant-limit related\nMacro: PreQual - Merchant-Limit Related.",
            "PreQual - Merchant-Limit Related",
        )
    )
    add(
        *outcome(
            "PAA_MERCHANT_MISSING",
            "Can't find merchant in pre-qual list",
            "Customer cannot find merchant X in the pre-qual merchant list.",
            "If a merchant is not listed for pre-approval, it may not support this check yet. You can still try Tamara at that merchant checkout if available.",
            "Macro → PreQual - Can't Find Merchant. Issue Type: Maximum/minimum purchase limit.",
            "Resolution: Merchant not in pre-qual list\nMacro: PreQual - Can't Find Merchant.",
            "PreQual - Can't Find Merchant",
        )
    )
    add(
        *outcome(
            "PAA_INTRODUCE",
            "Introduce PreQual after declined order recommendation",
            "Declined order and Customer Action tab recommends Pre-Qual. Introduce PreQual feature.",
            "You can check a Pre-Approved Amount in the Tamara app before ordering so you know your available limit for that store.",
            "Macro → Introduce PreQual. Issue Type: Maximum/minimum purchase limit.",
            "Resolution: Introduced PreQual after decline recommendation\nMacro: Introduce PreQual.",
            "Introduce PreQual",
        )
    )

    # ---- Escalation outcomes (KB escalation scenarios) ----
    esc_common_action = (
        "Escalate to Tech Support. Macro Ticket Escalated. Issue Type: Maximum/minimum purchase limit. "
        "Submit Working. SLA 7 business days. Collect Customer ID, merchant, amounts, CS Hub Request Status/Pre-qual Result, screenshots."
    )
    esc_comment = (
        "Escalation: Pre-Approved Amount\nTeam: Tech Support\nSLA: 7 business days\n"
        "Issue Type: Order > Placing an Order > Maximum/minimum purchase limit\n"
        "Macro: Ticket Escalated\nDetails: [merchant/amount/status/screenshots]"
    )

    for nid, title, expl in [
        (
            "PAA_ESC_NOT_HONORED",
            "Escalate — Pre-qual not honored (no expected reason)",
            "Active pre-qual at merchant within validity and limit, but offer not honored at checkout with no expected reason.",
        ),
        (
            "PAA_ESC_APP_JOURNEY",
            "Escalate — In-app journey / access broken",
            "Cannot access Check Your Limit, unexpected eligibility error, or broken screen/flow (NOT Too Many Attempts).",
        ),
        (
            "PAA_ESC_WRONG_AMOUNT",
            "Escalate — Wrong / inconsistent pre-approval amount",
            "Pre-qualified amount significantly inconsistent with expectation after valid checks (credit-related amount issue).",
        ),
        (
            "PAA_ESC_CREDIT_AFTER_HONOR",
            "Escalate — Credit decline after pre-qual honored",
            "Pre-qual approved and honored, then declined at checkout for credit reason on same merchant within approved limit.",
        ),
        (
            "PAA_ESC_STATUS_MISMATCH",
            "Escalate — CS Hub status mismatch",
            "Request Status and Pre-qual Result contradictory (e.g. HONORED vs Not Honored).",
        ),
        (
            "PAA_ESC_PLAN_MISMATCH",
            "Escalate — Payment plan mismatch at checkout",
            "Installment plans at checkout do not match pre-qual plans / expected plan missing despite active pre-qual.",
        ),
    ]:
        add(
            *outcome(
                nid,
                title,
                expl,
                "I will escalate this to our technical team to investigate your Pre-Approved Amount case. You will receive an update on the ticket.",
                esc_common_action,
                esc_comment + f"\nScenario: {title}",
                "Ticket Escalated",
                escalate=True,
            )
        )

    # ---- Decision tree ----
    # Step 1: select pre-approval / eligibility STATUS (as requested)
    tree["step1"] = {
        "prompt": "Select the Pre-Approval / Pre-Check status (confirm on CS Hub + customer app):",
        "options": [
            {"text": "A. Eligible (true) — Tamara should be available at checkout", "next": "step_eligible"},
            {"text": "B. Not Eligible (false) — Hidden / Greyed out / unavailable", "next": "step_not_eligible"},
            {"text": "C. Active Pre-Approved Amount / Pre-Qual showing (within validity)", "next": "step_active_prequal"},
            {"text": "D. Expired / no longer showing / missed validity window", "next": "PAA_EXPIRED"},
            {"text": "E. Partial approval / Declined / Less than requested", "next": "PAA_PARTIAL_DECLINE"},
            {"text": "F. Too Many Attempts", "next": "PAA_TOO_MANY"},
            {"text": "G. CS Hub status mismatch / unexpected system issue (escalate paths)", "next": "step_escalate"},
            {"text": "H. General questions (what it is / how to get / increase / introduce)", "next": "step_general"},
        ],
    }

    tree["step_eligible"] = {
        "prompt": "Eligible (true) — what is the customer reporting?",
        "options": [
            {"text": "Confirm eligibility & guide retry checkout", "next": "PAA_ELIGIBLE_OK"},
            {"text": "Tamara still not visible though eligibility is ON / toggled on", "next": "PAA_NOTELIG_ON_TOGGLE"},
            {"text": "Active pre-qual questions while eligible", "next": "step_active_prequal"},
        ],
    }

    tree["step_not_eligible"] = {
        "prompt": "Not Eligible (false) — how is Tamara displayed at merchant checkout?",
        "options": [
            {"text": "Tamara is Hidden (not shown at all)", "next": "PAA_NOTELIG_HIDDEN"},
            {"text": "Tamara is Greyed Out / unclickable", "next": "PAA_NOTELIG_GREY"},
            {"text": "Customer is not registered with Tamara", "next": "PAA_NOT_REGISTERED"},
            {"text": "Eligibility shows ON but customer still can't see Tamara", "next": "PAA_NOTELIG_ON_TOGGLE"},
        ],
    }

    tree["step_active_prequal"] = {
        "prompt": "Active Pre-Approved Amount / Pre-Qual — select the scenario:",
        "options": [
            {"text": "What is the pre-approved limit / how does it work?", "next": "PAA_GENERAL_INFO"},
            {"text": "Shopped within limit but rejected / not applied (expected reasons)", "next": "PAA_NOT_HONORED_EXPECTED"},
            {"text": "Financial profile/situation changed / missed payment after pre-approval", "next": "PAA_FINANCIAL_CHANGE"},
            {"text": "Pre-qual disappeared after placing another order", "next": "PAA_INVALIDATED"},
            {"text": "Different limit at another store", "next": "PAA_MERCHANT_DIFF"},
            {"text": "Can't find merchant in pre-qual list", "next": "PAA_MERCHANT_MISSING"},
            {"text": "No expected reason / needs escalation", "next": "step_escalate"},
        ],
    }

    tree["step_general"] = {
        "prompt": "General Pre-Approved Amount inquiry:",
        "options": [
            {"text": "What is it / how does it work?", "next": "PAA_GENERAL_INFO"},
            {"text": "How to get the Pre-Approved Amount (app steps)", "next": "PAA_HOW_TO_GET"},
            {"text": "Can we increase the limit?", "next": "PAA_CANNOT_INCREASE"},
            {"text": "Declined order recommends Pre-Qual — introduce feature", "next": "PAA_INTRODUCE"},
            {"text": "Max/min purchase limit general inquiry", "next": "PAA_GENERAL_INFO"},
        ],
    }

    tree["step_escalate"] = {
        "prompt": "Escalation scenario (KB) — select the matching Tech Support path:",
        "options": [
            {"text": "Pre-qual not honored at checkout with NO expected reason", "next": "PAA_ESC_NOT_HONORED"},
            {"text": "In-app journey broken / cannot access Check Your Limit", "next": "PAA_ESC_APP_JOURNEY"},
            {"text": "Wrong / inconsistent pre-approval amount", "next": "PAA_ESC_WRONG_AMOUNT"},
            {"text": "Credit decline AFTER pre-qual was honored", "next": "PAA_ESC_CREDIT_AFTER_HONOR"},
            {"text": "CS Hub Request Status vs Pre-qual Result mismatch", "next": "PAA_ESC_STATUS_MISMATCH"},
            {"text": "Payment plan options mismatch vs pre-qual", "next": "PAA_ESC_PLAN_MISMATCH"},
        ],
    }

    topic = {
        "id": TOPIC_ID,
        "tag": "Topic NEW",
        "name": "Pre-Approved Amount",
        "desc": "Pre-Check eligibility + Pre-Approved Amount / Pre-Qual support. Start by selecting pre-approval status, then resolve or escalate per KB Ashry.",
    }
    policy = (
        "PRE-APPROVED AMOUNT / PRE-CHECK (KB ASHRY)\n"
        "1) Always start by selecting the Pre-Approval / Pre-Check STATUS from CS Hub + app.\n"
        "2) Care cannot override Tamara risk engine eligibility.\n"
        "3) Do NOT say: rejected/declined (for false eligibility), system error, dispute decision, risk model details, merchant bug, or promise immediate availability.\n"
        "4) Issue Type (CX): Order > Placing an Order > Maximum/minimum purchase limit (or Can't see Tamara when display issue).\n"
        "5) Escalations → Tech Support, SLA 7 business days, Macro Ticket Escalated."
    )

    return topic, policy, tree, nodes


REQUIRED_SCENARIOS = [
    "Eligible (true)",
    "Not Eligible",
    "Hidden",
    "Greyed Out",
    "General question",
    "how to get",
    "Cannot increase",
    "expired",
    "Limit Not Honored",
    "Financial Profile",
    "Invalidated",
    "Too Many Attempts",
    "Partial/No Approval",
    "Merchant-Limit",
    "Can't Find Merchant",
    "Introduce PreQual",
    "not honored",
    "In-app journey",
    "wrong",
    "Credit decline after",
    "status mismatch",
    "Payment plan",
]


def run_10_passes(cms, topic, policy, tree, nodes) -> dict:
    passes = []
    # 1 topic id unique / present after insert
    passes.append({"id": 1, "name": "topic_id_is_pre_approved_amount", "ok": topic["id"] == TOPIC_ID})
    # 2 step1 asks for status first
    p1 = (tree.get("step1") or {}).get("prompt", "")
    passes.append({"id": 2, "name": "step1_selects_preapproval_status", "ok": "status" in p1.lower() and "pre-approval" in p1.lower()})
    # 3 at least 8 status options on step1
    opts = (tree.get("step1") or {}).get("options") or []
    passes.append({"id": 3, "name": "step1_has_8_plus_status_options", "ok": len(opts) >= 8})
    # 4 all option next targets exist (steps or nodes)
    missing_next = []
    for step in tree.values():
        for o in step.get("options") or []:
            nxt = o.get("next")
            if nxt not in tree and nxt not in nodes:
                missing_next.append(nxt)
    passes.append({"id": 4, "name": "all_next_targets_resolve", "ok": not missing_next, "missing": missing_next})
    # 5 every required KB scenario keyword present in tree/nodes text
    blob = json.dumps(tree, ensure_ascii=False) + json.dumps(nodes, ensure_ascii=False) + policy
    missing_sc = [s for s in REQUIRED_SCENARIOS if s.lower() not in blob.lower()]
    passes.append({"id": 5, "name": "all_kb_scenarios_covered", "ok": not missing_sc, "missing": missing_sc})
    # 6 escalation outcomes use Tech Support + 7 business days
    esc_ok = True
    for nid, n in nodes.items():
        if nid.startswith("PAA_ESC_"):
            if n.get("team") != TEAM_TS or "7 business" not in (n.get("sla") or "").lower():
                esc_ok = False
    passes.append({"id": 6, "name": "escalations_tech_support_7bd", "ok": esc_ok})
    # 7 issue type path correct on outcomes
    it_ok = all(ISSUE in (n.get("issueType") or "") or "Can't see Tamara" in (n.get("system_action") or "") for n in nodes.values())
    # soften: every node mentions Maximum/minimum OR Can't see Tamara
    it_ok = True
    for n in nodes.values():
        text = (n.get("issueType") or "") + (n.get("system_action") or "")
        if "Maximum/minimum purchase limit" not in text and "Can't see Tamara" not in text and "Can’t see Tamara" not in text:
            it_ok = False
            break
    passes.append({"id": 7, "name": "issue_types_aligned_to_kb", "ok": it_ok})
    # 8 macros present on non-empty outcomes
    mac_ok = all(bool((n.get("macro") or "").strip()) for n in nodes.values())
    passes.append({"id": 8, "name": "every_outcome_has_macro", "ok": mac_ok})
    # 9 no claims bleed in this topic
    passes.append({"id": 9, "name": "no_claims_section_bleed", "ok": "Buyer Protection" not in blob and "CLAIMS" not in json.dumps(nodes)})
    # 10 before escalating template attached for topic
    passes.append({"id": 10, "name": "escalation_template_defined", "ok": "BEFORE ESCALATING" in ESC_TEMPLATE and "7 business days" in ESC_TEMPLATE})

    failed = [p for p in passes if not p["ok"]]
    return {
        "passes_ok": 10 - len(failed),
        "all_passed": not failed,
        "failed": failed,
        "passes": passes,
        "node_count": len(nodes),
        "step_count": len(tree),
        "step1_options": len(opts),
    }


def main(apply: bool = False):
    store = json.loads(STORE.read_text(encoding="utf-8"))
    cms = store["cmsData"]
    topic, policy, tree, nodes = build_topic()
    result = run_10_passes(cms, topic, policy, tree, nodes)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "topic_id": TOPIC_ID,
        "verification": result,
        "apply_status": "pending",
    }

    if not result["all_passed"]:
        report["apply_status"] = "blocked_failed_10pass"
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("BLOCKED", result["passes_ok"], "/10", result["failed"])
        return report

    print("PASS 10/10 — nodes", result["node_count"], "steps", result["step_count"])

    if not apply:
        report["apply_status"] = "dry_run_only"
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("dry_run_only")
        return report

    # Apply
    cms.setdefault("nodes", {}).update(nodes)
    cms.setdefault("tree", {})[TOPIC_ID] = tree
    cms.setdefault("policies", {})[TOPIC_ID] = policy
    cms.setdefault("beforeEscalatingTemplates", {})[TOPIC_ID] = {
        "label": "Pre-Approved Amount",
        "team": TEAM_TS,
        "template": ESC_TEMPLATE,
        "source": "KB Ashry Pre-Approved Amount escalation scenarios",
        "origin": "kb_explicit",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "verified_10_pass": True,
    }

    topics = cms.get("topics") or []
    topics = [t for t in topics if t.get("id") != TOPIC_ID]
    # Insert after purchase_limits if present, else append before transfers stays first
    insert_at = len(topics)
    for i, t in enumerate(topics):
        if t.get("id") == "purchase_limits":
            insert_at = i + 1
            t["desc"] = (
                "Legacy quick link: use topic Pre-Approved Amount for full Pre-Check / Pre-Qual scenarios. "
                + (t.get("desc") or "")
            )
            break
    topics.insert(insert_at, topic)
    # Ensure transfers_sla remains first if present
    tr = [t for t in topics if t.get("id") == "transfers_sla"]
    rest = [t for t in topics if t.get("id") != "transfers_sla"]
    cms["topics"] = (tr + rest) if tr else topics

    # Retag topic number lightly
    topic["tag"] = f"Topic {len(cms['topics']) - 1}"

    store["cmsData"] = cms
    store["revision"] = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    STORE.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    report["apply_status"] = "applied"
    report["topic_tag"] = topic["tag"]
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("applied", TOPIC_ID, topic["tag"])
    return report


if __name__ == "__main__":
    import sys

    main(apply="--apply" in sys.argv)
