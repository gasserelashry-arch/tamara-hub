# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
store = json.loads((ROOT / "hub_store.json").read_text(encoding="utf-8"))
cms = store["cmsData"]
cat = cms.get("transfersSlaCatalog") or []
print("catalog", len(cat))
if cat:
    cats = sorted({(c.get("category") or "").strip() for c in cat})
    print("categories", len(cats))
    print("empty_category_rows", sum(1 for c in cat if not (c.get("category") or "").strip()))
    print("sample", {k: cat[0].get(k) for k in ["id", "category", "situation", "team", "sla"]})
    print("first_cats", cats[:15])

be = cms.get("beforeEscalatingTemplates") or {}
print("beforeEscalating", sorted(be.keys()))
topics = [t for t in cms["topics"] if t["id"] != "transfers_sla"]
missing = [t for t in topics if t["id"] not in be]
print("topics", len(topics), "with_BE", len(be), "missing_BE", len(missing))
for t in missing:
    print("-", t["id"], "|", t["name"])

html = (ROOT / "index.html").read_text(encoding="utf-8")
print("embedded_beforeEscalating", "beforeEscalatingTemplates" in html)
print("embedded_catalog_marker", '"transfersSlaCatalog"' in html)
# extract embedded cms catalog length roughly
m = re.search(r'"transfersSlaCatalog"\s*:\s*(\[)', html)
print("catalog_in_html", bool(m))
pending = html.count("PENDING — Escalation template")
print("pending_templates_in_html", pending)
