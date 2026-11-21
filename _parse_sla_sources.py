# -*- coding: utf-8 -*-
import zipfile, xml.etree.ElementTree as ET, os, re, json

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}

def col_row(ref):
    m = re.match(r"([A-Z]+)(\d+)", ref)
    col = 0
    for ch in m.group(1):
        col = col * 26 + (ord(ch) - 64)
    return col, int(m.group(2))

def read_xlsx(path):
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", NS):
                texts = [t.text or "" for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")]
                shared.append("".join(texts))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        sheets = []
        for sh in wb.findall("a:sheets/a:sheet", NS):
            sheets.append((sh.attrib.get("name"), sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        out = []
        for name, rid in sheets:
            target = rid_to_target[rid]
            if not target.startswith("xl/"):
                target = "xl/" + target.lstrip("/")
            root = ET.fromstring(z.read(target))
            grid = {}
            max_r = max_c = 0
            for c in root.findall(".//a:sheetData/a:row/a:c", NS):
                ref = c.attrib.get("r")
                if not ref: continue
                col, row = col_row(ref)
                max_r, max_c = max(max_r, row), max(max_c, col)
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
                if team or lob or issue or sla:
                    rows.append({"row": r, "team": team, "lob": lob, "issue": issue, "sla": sla})
            out.append({"sheet": name, "rows": rows})
        return out

def read_docx_due_date(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        tables = root.findall(".//w:tbl", NS)
        items = []
        for tbl in tables:
            for tr in tbl.findall("./w:tr", NS):
                cells = []
                for tc in tr.findall("./w:tc", NS):
                    cell_text = "".join(t.text or "" for t in tc.findall(".//w:t", NS)).strip()
                    cells.append(cell_text)
                if len(cells) >= 2 and cells[0]:
                    right = cells[1]
                    issue = ""
                    sla = ""
                    m_issue = re.search(r"Issue type \(CS\)\s*(.+?)(?=SLA\s*\d|$)", right, re.I | re.S)
                    if m_issue:
                        issue = re.sub(r"\s+", " ", m_issue.group(1)).strip()
                    m_sla = re.search(r"SLA\s*(\d+)\s*Days?", right, re.I)
                    if m_sla:
                        sla = m_sla.group(1) + " Days"
                    items.append({
                        "scenario": cells[0],
                        "issue_type": issue,
                        "sla": sla,
                        "raw_right": right[:500],
                    })
        return items

xlsx = read_xlsx(r"C:\Users\gasser.elashry\Downloads\Transfers SLA.xlsx")
docx = read_docx_due_date(os.path.join(r"C:\Users\gasser.elashry\Downloads", "DUE DATE Preference SLA's.docx"))
out = {"transfers": xlsx, "due_date": docx}
path = r"C:\Users\gasser.elashry\Downloads\Tamara_Hub_Local_Server_Package\_sla_parsed.json"
with open(path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("transfers rows", sum(len(s["rows"]) for s in xlsx))
print("due_date items", len(docx))
print("wrote", path)
for it in docx:
    print("DUE:", it["sla"], "|", it["issue_type"], "|", it["scenario"][:80])
