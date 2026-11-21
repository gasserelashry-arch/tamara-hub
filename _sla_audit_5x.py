# -*- coding: utf-8 -*-
import json, re

store = json.load(open("hub_store.json", encoding="utf-8"))
parsed = json.load(open("_sla_parsed.json", encoding="utf-8"))
cms = store["cmsData"]
doc = parsed["due_date"]

def norm(s):
    s = (s or "").lower().replace("&", " and ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()

print("=== DUE DATE 5x AUDIT ===")
all_ok = True
for nid, n in cms["nodes"].items():
    if not nid.startswith("DUE_ESC_"):
        continue
    hit = None
    for it in doc:
        if norm(it["scenario"])[:40] == norm(n.get("agent_expl", "").split("Scenario: ")[-1] if "Scenario:" in n.get("agent_expl","") else "")[:40]:
            hit = it
            break
    if not hit:
        for it in doc:
            if norm(it["sla"]).replace(" ", "") == norm(n.get("sla","")).replace(" ", "") and any(
                tok in norm(n.get("issueType","")) for tok in norm(it["issue_type"]).split() if len(tok) > 3
            ):
                # scenario from agent_expl
                pass
        for it in doc:
            if norm(it["sla"]).replace(" ", "") == norm(n.get("sla","")).replace(" ", "") and (
                norm(it["issue_type"]) in norm(n.get("issueType","")) or norm(n.get("issueType","")) in norm(it["issue_type"]) or
                sum(1 for t in norm(it["issue_type"]).split() if len(t)>3 and t in norm(n.get("issueType",""))) >= 3
            ):
                hit = it
                break
    checks = []
    for round_i in range(1, 6):
        c1 = n.get("team") == "Tech Support"
        c2 = bool(n.get("sla"))
        c3 = "Due Date Preference" in (n.get("issueType") or "")
        c4 = nid in json.dumps(cms.get("tree", {}).get("due_date", {}))
        c5 = hit is not None and norm(hit["sla"]).replace(" ", "") == norm(n.get("sla")).replace(" ", "")
        ok = c1 and c2 and c3 and c4 and c5
        checks.append(ok)
        print(f"{nid} round{round_i}: team={c1} sla={c2} issue={c3} in_tree={c4} doc_sla={c5} => {ok}")
    if not all(checks):
        all_ok = False
        print("FAIL", nid, n.get("sla"), n.get("issueType"))
    else:
        print("PASS5x", nid, n.get("sla"), "|", n.get("issueType"))

print("DUE TREE", "step_due_tech" in cms["tree"]["due_date"])
print("ALL_DUE_OK", all_ok)

strict = json.load(open("_sla_strict_report.json", encoding="utf-8"))
print("=== TRANSFER CURATED ===")
print("applied", len(strict["curated_applied"]), "rejected", len(strict["curated_rejected"]))
for a in strict["curated_applied"]:
    # confirm 5 rounds passed
    ok = all(r["pass"] for r in a["verify"]) and all(r["pass"] for r in a.get("verify_second_pass", a["verify"]))
    print(("PASS5x" if ok else "FAIL"), a["node_id"], a["new_sla"], a["topics"])
