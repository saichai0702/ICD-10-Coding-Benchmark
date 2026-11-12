"""Build the pinned, license-clean reference bundle the agent can search.

Sources
  raw/fy2027/   files downloaded from cms.gov (public domain, no license click-through):
                ICD-10-CM FY2027 (order file, tabular, alphabetic index, external-cause index),
                ICD-10-PCS FY2027 (order file, tables), Official Guidelines (CM + PCS) FY2027,
                POA exempt list FY2027, HCPCS Level II October 2026.
  $GWEN_DATASETS_ROOT  local copies of NCCI PTP/MUE and the Medicare Coverage Database.

License rule — nothing AMA- or ADA-licensed may enter the bundle:
  * CPT codes, CPT descriptors and CPT modifiers (AMA)       -> excluded
  * CDT dental codes, HCPCS D-codes (ADA)                    -> excluded
  * NCCI PTP / MUE: only rows where every code is HCPCS Level II (letter + 4 digits, not D)
  * LCD / NCD: ICD-10 coverage lists + policy prose; CPT-style numbers redacted; the
    LCD/article coding sections and article HCPCS/CPT tables are dropped; documents whose
    title is a CPT descriptor are dropped.

Run:  python scripts/build_reference.py
"""
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

csv.field_size_limit(sys.maxsize)

HERE = Path(__file__).resolve().parent.parent
RAW = HERE / "data/raw" / "fy2027" / "x"
LOCAL = Path(os.environ.get("GWEN_DATASETS_ROOT", "/Users/pgn001/Downloads/harness5/datasets"))
OUT = HERE / "data" / "reference"

CM_DIR = RAW / "2027-code-descriptions-tabular-order" / "Code Descriptions"
CM_XML = RAW / "2027-code-tables-tabular-index" / "Table and Index"
PCS_ORDER = RAW / "2027-icd-10-pcs-order-file-long-abbreviated-titles" / "icd10pcs_order_2027.txt"
PCS_XML = RAW / "2027-icd-10-pcs-code-tables-index" / "icd10pcs_tables_2027.xml"
POA = RAW / "2027-poa-exempt-codes" / "POAexemptCodesFY27.txt"
HCPCS_TXT = RAW / "october-2026-alpha-numeric-hcpcs-file" / "HCPC2026_OCT_ANWEB_09232026.txt"
GUIDES = {"cm": HERE / "data/raw/fy2027/fy-2027-icd-10-cm-coding-guidelines.pdf",
          "pcs": HERE / "data/raw/fy2027/2027-official-icd-10-pcs-coding-guidelines.pdf"}

LEVEL2 = re.compile(r"^[A-CE-V][0-9]{4}$")        # HCPCS Level II, excluding D (CDT)
CPT_LIKE = re.compile(r"\b\d{4}[0-9FTU]\b")       # CPT category I/II/III code pattern
LCD_KEEP = {"33996"}                              # Vitamin D Assay Testing (title is not a CPT descriptor)
ARTICLE_KEEP = {"56798"}                          # Billing and Coding: Vitamin D Assay Testing (pairs with L33996)
LCD_DISTRACTOR_WORDS = ("vitamin d", "colorectal", "hyaluronan", "knee")
NCD_SECTIONS = {"210.3"}


def redact(text: str) -> str:
    return CPT_LIKE.sub("[code redacted]", text or "")


def write_csv(path: Path, header: list[str], rows) -> int:
    n = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)
            n += 1
    return n


def order_file(path: Path):
    """CMS fixed-width order file: order(5) code(7) billable(1) short(60) long."""
    for line in open(path, encoding="latin-1"):
        yield line[0:5], line[6:13].strip(), line[14:15], line[16:76].strip(), line[77:].strip()


def hcpcs_records():
    """HCPCS Level II fixed-width file -> codes and modifiers (continuation lines joined)."""
    codes, mods, last = {}, {}, None
    for line in open(HCPCS_TXT, encoding="latin-1"):
        code, recid = line[0:5], line[10:11]
        long_d, short_d = line[11:91].rstrip(), line[91:119].strip()
        if recid == "3":
            last = codes.setdefault(code.strip(), {"long": long_d, "short": short_d})
        elif recid == "4" and last is not None:
            last["long"] += " " + long_d.strip()
        elif recid == "7":
            last = mods.setdefault(code.strip(), {"long": long_d, "short": short_d})
        elif recid == "8" and last is not None:
            last["long"] += " " + long_d.strip()
    return codes, mods


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    counts = {}

    # ICD-10-CM / PCS FY2027 (public domain, CDC/CMS)
    counts["icd10cm"] = write_csv(OUT / "icd10cm_codes.csv", ["order_number", "code", "is_billable", "short_description", "long_description"],
                                  order_file(CM_DIR / "icd10cm_order_2027.txt"))
    for name in ("icd10cm_tabular_2027.xml", "icd10cm_index_2027.xml", "icd10cm_eindex_2027.xml"):
        shutil.copyfile(CM_XML / name, OUT / name.replace("_2027", ""))
    counts["icd10pcs"] = write_csv(OUT / "icd10pcs_codes.csv", ["order_number", "code", "is_billable", "short_description", "long_description"],
                                   order_file(PCS_ORDER))
    shutil.copyfile(PCS_XML, OUT / "icd10pcs_tables.xml")
    poa = [l.rstrip("\n").split("\t") for l in open(POA, encoding="latin-1")][1:]
    counts["poa_exempt"] = write_csv(OUT / "poa_exempt.csv", ["code", "description"],
                                     ((c[1].replace(".", ""), c[2]) for c in poa if len(c) >= 3))

    # Official Guidelines as text (public domain)
    for key, pdf in GUIDES.items():
        subprocess.run(["pdftotext", "-layout", str(pdf), str(OUT / f"guidelines_{key}.txt")], check=True)

    # HCPCS Level II October 2026, D-codes (CDT) excluded
    codes, mods = hcpcs_records()
    counts["hcpcs"] = write_csv(OUT / "hcpcs_codes.csv", ["code", "long_description", "short_description"],
                                ((c, redact(v["long"]), redact(v["short"])) for c, v in sorted(codes.items()) if LEVEL2.match(c)))
    counts["hcpcs_modifiers"] = write_csv(OUT / "hcpcs_modifiers.csv", ["modifier", "long_description", "short_description"],
                                          ((m, redact(v["long"]), redact(v["short"])) for m, v in sorted(mods.items())))

    # NCCI: Level II rows only (no CPT)
    with open(LOCAL / "cms-ncci-mue/llm/data.csv", encoding="utf-8") as f:
        counts["ncci_mue_level2"] = write_csv(OUT / "ncci_mue.csv", ["service_setting", "code", "mue_value", "mai", "rationale"],
                                              ((r["service_setting"], r["hcpcs_cpt_code"], r["mue_value"], r["mue_adjudication_indicator"], r["mue_rationale"])
                                               for r in csv.DictReader(f) if LEVEL2.match(r["hcpcs_cpt_code"])))
    with open(LOCAL / "cms-ncci-ptp-edits/llm/data.csv", encoding="utf-8") as f:
        counts["ncci_ptp_level2"] = write_csv(OUT / "ncci_ptp.csv", ["column_1", "column_2", "effective_date", "modifier_indicator", "rationale"],
                                              ((r["column_1_hcpcs_cpt"], r["column_2_hcpcs_cpt"], r["effective_date"], r["modifier_indicator"], r["ptp_edit_rationale"])
                                               for r in csv.DictReader(f)
                                               if r["deletion_date"].strip() == "*" and LEVEL2.match(r["column_1_hcpcs_cpt"]) and LEVEL2.match(r["column_2_hcpcs_cpt"])))

    # Medicare Coverage Database: ICD-10 lists + redacted prose only
    mcd = LOCAL / "mcd-lcd-article-downloads/llm"
    with open(mcd / "lcd.csv", encoding="utf-8") as f:
        lcds = [r for r in csv.DictReader(f) if r["status"] == "A" and (
            r["lcd_id"] in LCD_KEEP or (any(w in r["title"].lower() for w in LCD_DISTRACTOR_WORDS) and ";" not in r["title"]))]
    counts["lcd"] = write_csv(OUT / "lcd.csv", ["lcd_id", "lcd_version", "title", "rev_eff_date", "indication", "doc_reqs", "util_guide"],
                              ((r["lcd_id"], r["lcd_version"], r["title"], r["rev_eff_date"], redact(r["indication"]), redact(r["doc_reqs"]), redact(r["util_guide"]))
                               for r in lcds))
    with open(mcd / "article.csv", encoding="utf-8") as f:
        arts = [r for r in csv.DictReader(f) if r["article_id"] in ARTICLE_KEEP or (
            "billing and coding" in r["title"].lower() and any(w in r["title"].lower() for w in LCD_DISTRACTOR_WORDS) and ";" not in r["title"])]
    keep_ids = {r["article_id"] for r in arts}
    counts["lcd_article"] = write_csv(OUT / "lcd_article.csv", ["article_id", "article_version", "title", "article_eff_date"],
                                      ((r["article_id"], r["article_version"], r["title"], r["article_eff_date"]) for r in arts))
    with open(mcd / "article_x_icd10_covered.csv", encoding="utf-8") as f:
        counts["lcd_article_icd10_covered"] = write_csv(OUT / "lcd_article_icd10_covered.csv", ["article_id", "icd10_code", "icd10_covered_group", "description"],
                                                        ((r["article_id"], r["icd10_code"], r["icd10_covered_group"], r["description"])
                                                         for r in csv.DictReader(f) if r["article_id"] in keep_ids))
    with open(LOCAL / "mcd-ncd-downloads/llm/ncd_trkg.csv", encoding="utf-8") as f:
        counts["ncd"] = write_csv(OUT / "ncd.csv", ["section", "version", "title", "effective_date", "item_service", "indications_limitations"],
                                  ((r["NCD_mnl_sect"].strip(), r["NCD_vrsn_num"], r["NCD_mnl_sect_title"], r["NCD_efctv_dt"], redact(r["itm_srvc_desc"]), redact(r["indctn_lmtn"]))
                                   for r in csv.DictReader(f) if r["NCD_mnl_sect"].strip() in NCD_SECTIONS))

    # Final license audit: no CPT-pattern code in any code column or free-text column.
    id_cols = {"order_number", "lcd_id", "lcd_version", "article_id", "article_version", "rev_eff_date",
               "article_eff_date", "effective_date", "version", "section", "mue_value", "mai", "modifier_indicator"}
    for p in OUT.glob("*.csv"):
        with open(p, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                for col, val in row.items():
                    if col in id_cols:
                        continue
                    hits = CPT_LIKE.findall(val or "")
                    if col in ("code", "column_1", "column_2"):
                        hits = [val] if CPT_LIKE.fullmatch(val or "") else []
                    assert not hits, f"CPT-like code left in {p.name}.{col}: {hits[:5]} :: {str(val)[:120]}"
    for p in OUT.glob("guidelines_*.txt"):
        counts[f"{p.stem}_cpt_like_numbers"] = len(CPT_LIKE.findall(p.read_text(encoding="utf-8")))

    versions = {
        "icd10cm": "FY2027 (discharges / dates of service 2026-10-01 to 2027-09-30) — order file, tabular, index, external-cause index",
        "icd10pcs": "FY2027 — order file + tables",
        "guidelines": "ICD-10-CM and ICD-10-PCS Official Guidelines for Coding and Reporting FY2027",
        "poa_exempt": "FY2027 POA exempt list",
        "hcpcs": "HCPCS Level II October 2026 (D-codes / CDT excluded)",
        "ncci": "NCCI MUE + practitioner PTP, 2026 Q3, HCPCS Level II rows only (CPT rows removed)",
        "lcd_ncd": "Medicare Coverage Database snapshot: ICD-10 coverage lists + policy text, CPT numbers redacted",
        "excluded_licensed": ["CPT codes, descriptors and modifiers (AMA)", "CDT dental codes (ADA)", "AHA Coding Clinic"],
        "counts": counts,
    }
    (OUT / "VERSIONS.json").write_text(json.dumps(versions, indent=2))
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
