# #!/usr/bin/env python3
# """codetools — the coder's reference desk inside the environment.

# Lookup only, public-domain sources only (CMS/CDC). No CPT or CDT content is included.
# It never contains the answer for a chart.

#   codetools index <words...>             ICD-10-CM Alphabetic Index (start here, then verify in the tabular)
#   codetools eindex <words...>            External Cause Index (falls, places of occurrence, activities)
#   codetools icd lookup <code>            tabular: title, billable?, POA-exempt?, notes incl. parents
#   codetools icd search <words...>        search tabular titles + inclusion terms
#   codetools pcs table <3 chars>          ICD-10-PCS table, e.g. 0QS (body part / approach / device / qualifier)
#   codetools pcs lookup <code>            ICD-10-PCS code title, valid?
#   codetools pcs search <words...>        search ICD-10-PCS titles
#   codetools guidelines <cm|pcs> <words...>   search the Official Guidelines for Coding and Reporting
#   codetools hcpcs lookup|search ...      HCPCS Level II
#   codetools modifier <mod>               HCPCS Level II modifier
#   codetools ptp <code1> <code2>          NCCI PTP edit (HCPCS Level II pairs only)
#   codetools mue <code>                   NCCI MUE (HCPCS Level II only)
#   codetools lcd search <words...>        LCDs and Billing & Coding articles by title
#   codetools lcd show <lcd_id>            LCD policy text
#   codetools lcd covered <article_id> <icd10>   is this diagnosis on the article's covered list?
#   codetools ncd show <section>           NCD text, e.g. 210.3
#   codetools versions                     code-set versions in this environment
# """
# from __future__ import annotations

# import csv
# import json
# import os
# import re
# import sqlite3
# import sys
# import textwrap
# import xml.etree.ElementTree as ET
# from pathlib import Path

# csv.field_size_limit(sys.maxsize)
# REF = Path(os.environ.get("CODING_REF", "/opt/reference"))
# DB = REF / "ref.sqlite"


# # ── index build (run once at image build) ─────────────────────────────────

# def _load(cur, table, path):
#     with open(path, newline="", encoding="utf-8") as f:
#         r = csv.DictReader(f)
#         cols = r.fieldnames
#         cur.execute(f"CREATE TABLE {table} ({', '.join(chr(34) + c + chr(34) + ' TEXT' for c in cols)})")
#         cur.executemany(f"INSERT INTO {table} VALUES ({', '.join('?' * len(cols))})",
#                         ([row[c] for c in cols] for row in r))


# def _tabular_rows():
#     tree = ET.parse(REF / "icd10cm_tabular.xml")
#     tags = ("inclusionTerm", "includes", "excludes1", "excludes2", "codeFirst",
#             "useAdditionalCode", "codeAlso", "notes", "sevenChrNote")
#     rows = []

#     def walk(node, parent):
#         name = node.findtext("name").replace(".", "")
#         notes = {t: [n.text or "" for n in el.findall("note")] for t in tags if (el := node.find(t)) is not None}
#         sev = node.find("sevenChrDef")
#         if sev is not None:
#             notes["sevenChrDef"] = [f"{e.get('char')} = {e.text}" for e in sev.findall("extension")]
#         rows.append((name, parent, json.dumps(notes), " | ".join(notes.get("inclusionTerm", []))))
#         for child in node.findall("diag"):
#             walk(child, name)

#     for sec in tree.getroot().iter("section"):
#         for d in sec.findall("diag"):
#             walk(d, "")
#     return rows


# def _index_rows(path: Path, kind: str):
#     """Flatten the Alphabetic Index: one row per term path with its code / see / see-also."""
#     rows = []

#     def text(el):
#         return " ".join(" ".join(t.strip() for t in el.itertext()).split()) if el is not None else ""

#     def walk(node, path_terms):
#         title = text(node.find("title"))
#         p = path_terms + [title]
#         code = (node.findtext("code") or "").strip()
#         see, see_also = text(node.find("see")), text(node.find("seeAlso"))
#         manif = (node.findtext("manif") or "").strip()
#         if code or see or see_also or manif:
#             rows.append((kind, " > ".join(p), code, see, see_also, manif))
#         for child in node.findall("term"):
#             walk(child, p)

#     for letter in ET.parse(path).getroot().iter("letter"):
#         for mt in letter.findall("mainTerm"):
#             walk(mt, [])
#     return rows


# def _pcs_rows():
#     rows = []
#     for tbl in ET.parse(REF / "icd10pcs_tables.xml").getroot().iter("pcsTable"):
#         head = {a.get("pos"): a for a in tbl.findall("axis")}
#         key = "".join(head[p].find("label").get("code") for p in ("1", "2", "3"))
#         lines = [f"{head[p].findtext('title')}: {head[p].find('label').get('code')} = {head[p].findtext('label')}" for p in ("1", "2", "3")]
#         definition = head["3"].findtext("definition") or ""
#         if definition:
#             lines.append(f"  definition: {definition}")
#         for i, row in enumerate(tbl.findall("pcsRow"), 1):
#             lines.append(f"-- row {i}")
#             for ax in row.findall("axis"):
#                 vals = ", ".join(f"{l.get('code')}={l.text}" for l in ax.findall("label"))
#                 lines.append(f"  pos {ax.get('pos')} {ax.findtext('title')}: {vals}")
#         rows.append((key, "\n".join(lines)))
#     return rows


# def build_index():
#     if DB.exists():
#         DB.unlink()
#     con = sqlite3.connect(DB)
#     cur = con.cursor()
#     for t, f in (("icd", "icd10cm_codes.csv"), ("pcs", "icd10pcs_codes.csv"), ("poa_exempt", "poa_exempt.csv"),
#                  ("hcpcs", "hcpcs_codes.csv"), ("modifiers", "hcpcs_modifiers.csv"), ("mue", "ncci_mue.csv"),
#                  ("ptp", "ncci_ptp.csv"), ("lcd", "lcd.csv"), ("article", "lcd_article.csv"),
#                  ("article_icd", "lcd_article_icd10_covered.csv"), ("ncd", "ncd.csv")):
#         _load(cur, t, REF / f)
#     cur.execute("CREATE TABLE tab (code TEXT, parent TEXT, notes TEXT, incl TEXT)")
#     cur.executemany("INSERT INTO tab VALUES (?,?,?,?)", _tabular_rows())
#     cur.execute("CREATE TABLE idx (kind TEXT, path TEXT, code TEXT, see TEXT, see_also TEXT, manif TEXT)")
#     cur.executemany("INSERT INTO idx VALUES (?,?,?,?,?,?)", _index_rows(REF / "icd10cm_index.xml", "index"))
#     cur.executemany("INSERT INTO idx VALUES (?,?,?,?,?,?)", _index_rows(REF / "icd10cm_eindex.xml", "eindex"))
#     cur.execute("CREATE TABLE pcs_table (key TEXT, body TEXT)")
#     cur.executemany("INSERT INTO pcs_table VALUES (?,?)", _pcs_rows())
#     for sql in ("CREATE INDEX i1 ON icd(code)", "CREATE INDEX i2 ON pcs(code)", "CREATE INDEX i3 ON ptp(column_1, column_2)",
#                 "CREATE INDEX i4 ON mue(code)", "CREATE INDEX i5 ON tab(code)", "CREATE INDEX i6 ON article_icd(article_id, icd10_code)",
#                 "CREATE INDEX i7 ON poa_exempt(code)", "CREATE INDEX i8 ON pcs_table(key)"):
#         cur.execute(sql)
#     con.commit()
#     con.close()
#     print(f"index built: {DB}")


# # ── helpers ───────────────────────────────────────────────────────────────

# def db():
#     if not DB.exists():
#         sys.exit("reference index missing; run: codetools build-index")
#     con = sqlite3.connect(DB)
#     con.row_factory = sqlite3.Row
#     return con


# def norm(code: str) -> str:
#     return code.upper().replace(".", "").strip()


# def dotted(code: str) -> str:
#     return code if len(code) <= 3 else f"{code[:3]}.{code[3:]}"


# def clean(html: str, width=100, limit=6000) -> str:
#     txt = re.sub(r"<[^>]+>", " ", html or "")
#     txt = re.sub(r"&nbsp;|&#160;", " ", txt)
#     txt = re.sub(r"\s+", " ", txt).strip()
#     return textwrap.fill(txt[:limit] + (" …[truncated]" if len(txt) > limit else ""), width)


# def like_all(cols, words):
#     conds = " AND ".join("(" + " OR ".join(f"lower({c}) LIKE ?" for c in cols) + ")" for _ in words)
#     return conds, [f"%{w.lower()}%" for w in words for _ in cols]


# # ── commands ──────────────────────────────────────────────────────────────

# def index_search(words, kind):
#     conds, params = like_all(["path"], words)
#     rows = db().execute(f"SELECT * FROM idx WHERE kind=? AND {conds} LIMIT 80", [kind] + params).fetchall()
#     for r in rows:
#         extra = "".join([f"  [{r['manif']}]" if r["manif"] else "", f"  see: {r['see']}" if r["see"] else "",
#                          f"  see also: {r['see_also']}" if r["see_also"] else ""])
#         print(f"{r['path']}  ->  {r['code'] or '-'}{extra}")
#     if not rows:
#         print("no index entry — try the main term only (e.g. the condition noun)")
#     else:
#         print("\n(Index codes may be incomplete, e.g. a dash means more characters are needed. Always verify with: codetools icd lookup <code>)")


# def icd_search(words):
#     conds, params = like_all(["i.long_description", "t.incl"], words)
#     rows = db().execute(f"SELECT i.code, i.is_billable, i.long_description FROM icd i LEFT JOIN tab t ON t.code=i.code "
#                         f"WHERE {conds} ORDER BY i.order_number LIMIT 60", params).fetchall()
#     for r in rows:
#         print(f"{dotted(r['code']):10} {'billable' if r['is_billable']=='1' else 'header  '}  {r['long_description']}")
#     if not rows:
#         print("no match — try fewer words, or use: codetools index <term>")


# def icd_lookup(code):
#     con = db()
#     c = norm(code)
#     r = con.execute("SELECT * FROM icd WHERE code=?", (c,)).fetchone()
#     if not r:
#         print(f"{dotted(c)}: NOT A VALID ICD-10-CM CODE in the FY2027 code set")
#         return
#     exempt = con.execute("SELECT 1 FROM poa_exempt WHERE code=?", (c,)).fetchone()
#     print(f"{dotted(c)}  {'BILLABLE' if r['is_billable']=='1' else 'NOT BILLABLE (header — needs more characters)'}"
#           f"{'  · POA EXEMPT' if exempt else ''}")
#     print(f"  {r['long_description']}")
#     cur = c
#     while cur:
#         t = con.execute("SELECT * FROM tab WHERE code=?", (cur,)).fetchone()
#         if not t:
#             cur = cur[:-1] if len(cur) > 3 else ""
#             continue
#         notes = json.loads(t["notes"])
#         if notes:
#             print(f"  notes at {dotted(t['code'])}:")
#             for k, v in notes.items():
#                 for n in v:
#                     print(f"    [{k}] {n}")
#         cur = t["parent"]


# def pcs_cmd(sub, args):
#     con = db()
#     if sub == "table":
#         r = con.execute("SELECT body FROM pcs_table WHERE key=?", (args[0].upper(),)).fetchone()
#         print(r["body"] if r else "no such PCS table")
#     elif sub == "lookup":
#         r = con.execute("SELECT * FROM pcs WHERE code=?", (norm(args[0]),)).fetchone()
#         print(f"{r['code']}  {'VALID' if r['is_billable']=='1' else 'not a complete code'}\n  {r['long_description']}" if r
#               else f"{args[0]}: NOT A VALID ICD-10-PCS CODE in the FY2027 code set")
#     else:
#         conds, params = like_all(["long_description"], args)
#         for r in con.execute(f"SELECT * FROM pcs WHERE is_billable='1' AND {conds} LIMIT 60", params):
#             print(f"{r['code']:9} {r['long_description']}")


# def guidelines(which, words):
#     text = (REF / f"guidelines_{which}.txt").read_text(encoding="utf-8")
#     paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
#     hits = [p for p in paras if all(w.lower() in p.lower() for w in words)]
#     for p in hits[:12]:
#         print(re.sub(r"[ \t]+", " ", p.strip()), "\n" + "-" * 60)
#     print(f"{len(hits)} matching paragraph(s){' (showing 12)' if len(hits) > 12 else ''}")


# def hcpcs_cmd(sub, args):
#     con = db()
#     if sub == "lookup":
#         r = con.execute("SELECT * FROM hcpcs WHERE code=?", (args[0].upper(),)).fetchone()
#         print(f"{r['code']}  {r['long_description']}" if r else
#               f"{args[0]}: not a HCPCS Level II code (CPT is not part of this environment)")
#     else:
#         conds, params = like_all(["long_description"], args)
#         for r in con.execute(f"SELECT * FROM hcpcs WHERE {conds} LIMIT 40", params):
#             print(f"{r['code']:7} {r['long_description']}")


# def modifier(mod):
#     r = db().execute("SELECT * FROM modifiers WHERE modifier=?", (mod.upper(),)).fetchone()
#     print(f"{r['modifier']}  {r['long_description']}" if r else
#           f"{mod}: not a HCPCS Level II modifier (CPT modifiers are not part of this environment)")


# def ptp(a, b):
#     rows = db().execute("SELECT * FROM ptp WHERE (column_1=? AND column_2=?) OR (column_1=? AND column_2=?)", (a, b, b, a)).fetchall()
#     if not rows:
#         print(f"no active PTP edit between {a} and {b} (HCPCS Level II pairs only)")
#     for r in rows:
#         mi = {"0": "0 = modifier NOT allowed", "1": "1 = modifier allowed if clinically justified", "9": "9 = n/a"}.get(r["modifier_indicator"], r["modifier_indicator"])
#         print(f"column 1 (payable): {r['column_1']}  column 2 (denied if billed together): {r['column_2']}\n"
#               f"  modifier indicator {mi}; effective {r['effective_date']}; rationale: {r['rationale']}")


# def mue(code):
#     rows = db().execute("SELECT * FROM mue WHERE code=?", (code,)).fetchall()
#     if not rows:
#         print(f"{code}: no published MUE here (HCPCS Level II only; absence does not mean unlimited)")
#     for r in rows:
#         print(f"{r['service_setting']:20} MUE={r['mue_value']}  MAI={r['mai']}  ({r['rationale']})")


# def lcd_cmd(sub, args):
#     con = db()
#     if sub == "search":
#         conds, params = like_all(["title"], args)
#         for r in con.execute(f"SELECT * FROM lcd WHERE {conds}", params):
#             print(f"LCD L{r['lcd_id']} v{r['lcd_version']}  {r['title']}  (revision effective {r['rev_eff_date'][:10]})")
#         for r in con.execute(f"SELECT * FROM article WHERE {conds}", params):
#             print(f"Article A{r['article_id']} v{r['article_version']}  {r['title']}  (effective {r['article_eff_date'][:10]})")
#     elif sub == "show":
#         r = con.execute("SELECT * FROM lcd WHERE lcd_id=? ORDER BY CAST(lcd_version AS INT) DESC", (args[0].lstrip("Ll"),)).fetchone()
#         if not r:
#             return print("LCD not found")
#         print(f"LCD L{r['lcd_id']} version {r['lcd_version']}: {r['title']} (revision effective {r['rev_eff_date'][:10]})")
#         for k in ("indication", "util_guide", "doc_reqs"):
#             if r[k]:
#                 print(f"\n== {k} ==\n{clean(r[k])}")
#     elif sub == "covered":
#         aid, code = args[0].lstrip("Aa"), norm(args[1])
#         r = con.execute("SELECT * FROM article_icd WHERE article_id=? AND replace(upper(icd10_code),'.','')=?", (aid, code)).fetchone()
#         print(f"{dotted(code)} IS on the covered list of article A{aid} (group {r['icd10_covered_group']}): {r['description']}" if r
#               else f"{dotted(code)} is NOT on the covered list of article A{aid}")


# def ncd_show(section):
#     r = db().execute("SELECT * FROM ncd WHERE section=? ORDER BY CAST(version AS INT) DESC", (section,)).fetchone()
#     if not r:
#         return print("NCD not found")
#     print(f"NCD {r['section']} v{r['version']}: {r['title']} (effective {r['effective_date'][:10]})")
#     for k in ("item_service", "indications_limitations"):
#         print(f"\n== {k} ==\n{clean(r[k], limit=9000)}")


# def main(argv):
#     if not argv or argv[0] in ("-h", "--help", "help"):
#         return print(__doc__)
#     cmd, rest = argv[0], argv[1:]
#     try:
#         if cmd == "build-index":
#             build_index()
#         elif cmd == "versions":
#             print((REF / "VERSIONS.json").read_text())
#         elif cmd in ("index", "eindex"):
#             index_search(rest, cmd)
#         elif cmd == "icd":
#             icd_search(rest[1:]) if rest[0] == "search" else icd_lookup(rest[1])
#         elif cmd == "pcs":
#             pcs_cmd(rest[0], rest[1:])
#         elif cmd == "guidelines":
#             guidelines(rest[0], rest[1:])
#         elif cmd == "hcpcs":
#             hcpcs_cmd(rest[0], rest[1:])
#         elif cmd == "modifier":
#             modifier(rest[0])
#         elif cmd == "ptp":
#             ptp(rest[0].upper(), rest[1].upper())
#         elif cmd == "mue":
#             mue(rest[0].upper())
#         elif cmd == "lcd":
#             lcd_cmd(rest[0], rest[1:])
#         elif cmd == "ncd":
#             ncd_show(rest[1] if rest[0] == "show" else rest[0])
#         else:
#             print(__doc__)
#     except IndexError:
#         print(__doc__)


# if __name__ == "__main__":
#     main(sys.argv[1:])
