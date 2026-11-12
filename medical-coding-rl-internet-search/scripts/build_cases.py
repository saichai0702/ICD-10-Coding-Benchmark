"""Write the 36 cases (data points) from data/cases.py into the Harbor task tasks/medical-coding/.

  environment/cases/<ID>/chart/*.txt, encounter.json   inputs the agent codes (all 36 cases)
  environment/reference.tar.gz                         FY2027 reference bundle (from data/reference/)
  solution/groundtruth.json                            ONE file: {case_id: expected output + scoring info}
  tests/groundtruth.json                               byte-identical copy for the verifier (see below)
  tests/valid_codes.json.gz                            billable-code lists for the scorer

Why two copies of groundtruth.json: Harbor uploads solution/ only for the oracle agent. A real
agent's run is graded with tests/ only, so the verifier needs its own copy. Edit nothing by hand:
this script writes both from data/cases.py and they are always identical.

Audits every case: oracle evidence must be in the chart, only allowed code systems, and no
CPT-like code anywhere. Stops on the first problem.

Run:  python scripts/build_cases.py
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import re
import shutil
import sys
import tarfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "tasks" / "medical-coding"
sys.path.insert(0, str(ROOT / "data"))
from cases import CASES  # noqa: E402

csv.field_size_limit(sys.maxsize)
REF = ROOT / "data" / "reference"
SYSTEMS = ("ICD-10-CM", "ICD-10-PCS", "HCPCS", "CDM")


def build_valid_codes() -> None:
    sets = {"icd10cm": set(), "icd10pcs": set(), "hcpcs": set()}
    for row in csv.DictReader(open(REF / "icd10cm_codes.csv", encoding="utf-8")):
        if row["is_billable"] == "1":
            sets["icd10cm"].add(row["code"])
    for row in csv.DictReader(open(REF / "icd10pcs_codes.csv", encoding="utf-8")):
        if row["is_billable"] == "1":
            sets["icd10pcs"].add(row["code"])
    for row in csv.DictReader(open(REF / "hcpcs_codes.csv", encoding="utf-8")):
        sets["hcpcs"].add(row["code"].strip().upper())
    with gzip.GzipFile(TASK / "tests" / "valid_codes.json.gz", "wb", mtime=0) as f:
        f.write(json.dumps({k: sorted(v) for k, v in sets.items()}).encode())


def build_reference_tarball() -> None:
    """One deterministic tar.gz of data/reference/ (ref.sqlite is built inside the image)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for p in sorted(REF.iterdir()):
            if p.is_file() and p.suffix != ".sqlite":
                info = tar.gettarinfo(str(p), arcname=p.name)
                info.mtime, info.uid, info.gid, info.uname, info.gname, info.mode = 0, 0, 0, "", "", 0o644
                with open(p, "rb") as f:
                    tar.addfile(info, f)
    with gzip.GzipFile(TASK / "environment" / "reference.tar.gz", "wb", mtime=0) as gz:
        gz.write(buf.getvalue())


def expected_code(g) -> dict:
    """One expected claim line, in exactly the format the agent must write."""
    c = {"code": g.code, "system": g.system,
         "role": g.role or ("line" if g.system in ("HCPCS", "CDM") else "secondary")}
    if g.poa:
        c["poa"] = g.poa
    if g.system in ("HCPCS", "CDM"):
        c["modifiers"] = g.modifiers or []
        c["units"] = g.units or 1
    c["evidence"] = g.evidence
    if g.accept:
        c["accept"] = g.accept          # equally correct alternative codes (scoring only)
    if g.role is None and g.system not in ("HCPCS", "CDM"):
        c["role_scored"] = False        # sequencing not graded for this code (scoring only)
    return c


def groundtruth_entry(case) -> dict:
    return {
        "query_needed": case.query_needed,
        "query_text": case.query_topic,
        "codes": [expected_code(g) for g in case.codes],
        "scoring": {"optional": case.optional,      # neither rewarded nor penalised
                    "forbidden": case.forbidden,    # known-wrong: heavier penalty if billed
                    "cdm_lines": case.cdm_lines},   # charge-master line ids valid for this chart
        "meta": {"title": case.title, "playbook_example": case.template, "setting": case.setting,
                 "edge_case_tags": case.tags, "gold_review_status": case.review},
    }


def audit(case) -> None:
    norm = lambda s: re.sub(r"\s+", " ", s.lower())
    chart_all = norm(" ".join(case.docs.values()))
    for g in case.codes:
        assert norm(g.evidence) in chart_all, f"{case.id}: evidence not in chart: {g.evidence!r}"
        assert g.system in SYSTEMS, f"{case.id}: system {g.system} not allowed"
    everything = (" ".join(case.docs.values()) + case.title + json.dumps([asdict(g) for g in case.codes])
                  + " ".join(case.forbidden))
    cpt = re.findall(r"\b\d{4}[0-9FTU]\b", everything)
    assert not cpt, f"{case.id}: CPT-like code(s) {cpt} in case content"


def main() -> None:
    build_valid_codes()
    build_reference_tarball()
    env_cases = TASK / "environment" / "cases"
    if env_cases.exists():
        shutil.rmtree(env_cases)
    groundtruth = {}
    for case in CASES:
        audit(case)
        d = env_cases / case.id
        (d / "chart").mkdir(parents=True)
        for name, text in case.docs.items():
            (d / "chart" / name).write_text(text)
        encounter = {"case_id": case.id, "setting": case.setting, "claim_type": case.claim, **case.dates,
                     "payer": "Medicare" if case.template in ("ICD-08", "ICD-09", "ICD-10") else "Medicare fee-for-service",
                     "code_set": "FY2027 ICD-10-CM/PCS; HCPCS Level II October 2026"}
        (d / "encounter.json").write_text(json.dumps(encounter, indent=2) + "\n")
        groundtruth[case.id] = groundtruth_entry(case)
    text = json.dumps(dict(sorted(groundtruth.items())), indent=2) + "\n"
    (TASK / "solution" / "groundtruth.json").write_text(text)
    (TASK / "tests" / "groundtruth.json").write_text(text)
    print(f"wrote {len(CASES)} cases to {env_cases.relative_to(ROOT)} and solution/groundtruth.json")


if __name__ == "__main__":
    main()
