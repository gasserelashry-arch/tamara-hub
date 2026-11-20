import json
import re
from pathlib import Path

root = Path(__file__).resolve().parent
store_path = root / "hub_store.json"
html_path = root / "index.html"
if not store_path.exists():
    print("no hub_store.json — keeping existing embed")
    raise SystemExit(0)
store = json.loads(store_path.read_text(encoding="utf-8"))
html = html_path.read_text(encoding="utf-8")
mac = json.dumps(store.get("masterMacros") or [], ensure_ascii=False, separators=(",", ":"))
db = json.dumps(store.get("cmsData") or {}, ensure_ascii=False, indent=2)
html2, n1 = re.subn(
    r'(<script id="tamara-macros-data" type="application/json">\s*)([\s\S]*?)(\s*</script>)',
    lambda m: m.group(1) + mac + m.group(3),
    html,
    count=1,
)
html3, n2 = re.subn(
    r'(<script id="tamara-db-data" type="application/json">\s*)([\s\S]*?)(\s*</script>)',
    lambda m: m.group(1) + db + m.group(3),
    html2,
    count=1,
)
html_path.write_text(html3, encoding="utf-8")
print("embedded macros", n1, "db", n2, "count", len(store.get("masterMacros") or []))
