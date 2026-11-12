"""Check the verifier without Docker: the oracle must score 1.0 on every case, and
typical mistakes (the playbook's landmines) must score below 1.0.

Run:  python generator/scripts/selftest.py
"""
from __future__ import annotations

import copy
import gzip
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "tasks" / "medical-coding"
sys.path.insert(0, str(TASK / "tests"))
import score as S  # noqa: E402

GT = json.loads((TASK / "solution" / "groundtruth.json").read_text())
CASES_DIR = TASK / "environment" / "cases"
with gzip.open(TASK / "tests" / "valid_codes.json.gz", "rt") as f:
    VALID = {k: set(v) for k, v in json.load(f).items()}


def system_of(code: str) -> str:
    c = code.replace(".", "")
    for sys_, key in (("ICD-10-CM", "icd10cm"), ("ICD-10-PCS", "icd10pcs"), ("HCPCS", "hcpcs")):
        if c in VALID[key]:
            return sys_
    return "CDM" if c[:3] in ("PRO", "LAB", "INJ") else "ICD-10-CM"


def run(cid: str, claim: dict) -> dict:
    """Score one case's claim straight from the task folder (no Docker)."""
    return S.score_case(claim, GT[cid], S.chart_text(CASES_DIR, cid), VALID)


def oracle(cid: str) -> dict:
    gt = GT[cid]
    return {"query_needed": gt["query_needed"], "query_text": gt["query_text"],
            "codes": [{k: v for k, v in c.items() if k not in ("accept", "role_scored")} for c in gt["codes"]]}


def whole_file_checks() -> bool:
    """End to end through score_all: oracle file = 1.0, empty/missing/partial files < 1.0."""
    import tempfile
    ok = True
    with tempfile.TemporaryDirectory() as d:
        def total(obj):
            p = Path(d) / "claims.json"
            if obj is None:
                p.unlink(missing_ok=True)
            else:
                p.write_text(json.dumps(obj))
            return S.score_all(p, GT, CASES_DIR, VALID)["reward"]
        full = {cid: oracle(cid) for cid in GT}
        half = dict(list(full.items())[: len(full) // 2])
        r = {"oracle file": total(full), "empty object": total({}), "missing file": total(None),
             "first half of cases only": total(half)}
        for name, val in r.items():
            print(f"  {name:26} reward {val}")
        ok = r["oracle file"] == 1.0 and r["empty object"] == 0 and r["missing file"] == 0 and 0 < r["first half of cases only"] < 1
    return ok


def main() -> None:
    tasks = sorted(GT)
    fails = 0
    print(f"{'task':9} {'oracle':>6} {'empty':>6} {'no-ev':>6} {'mutant':>7}  mutant")
    for t in tasks:
        o = oracle(t)
        r_or = run(t, o)["reward"]
        r_empty = run(t, {"query_needed": False, "codes": []})["reward"]
        noev = copy.deepcopy(o)
        for c in noev["codes"]:
            c["evidence"] = "made up quote"
        r_noev = run(t, noev)["reward"]
        gold = {**GT[t], **GT[t]["scoring"]}
        # Landmine mutant: the "obvious" wrong answer for this variant.
        m = copy.deepcopy(o)
        if gold["query_needed"]:
            m["query_needed"], what = False, "skip the query"
        elif gold["forbidden"]:
            fc = gold["forbidden"][0]
            m["codes"].append({"code": fc, "system": system_of(fc), "role": "secondary",
                               "evidence": "x", "modifiers": [], "units": 1})
            what = f"add {gold['forbidden'][0]}"
        else:
            m["codes"] = m["codes"][1:]
            what = "drop first code"
        r_m = run(t, m)["reward"]
        ok = r_or == 1.0 and r_empty < 1 and (r_noev < 1 or not o["codes"]) and r_m < 1
        fails += not ok
        print(f"{t:9} {r_or:6.2f} {r_empty:6.2f} {r_noev:6.2f} {r_m:7.2f}  {what}{'' if ok else '   <-- FAIL'}")
        if r_or != 1.0:
            print(json.dumps(run(t, o), indent=1)[:1500])

    # Spot checks of specific landmines
    t = "ICD01-B"
    m = oracle(t)
    for c in m["codes"]:
        c["poa"] = "Y"
    print(f"\nICD01-B all POA=Y (sepsis was NOT POA): {run(t, m)['reward']}")
    t = "ICD10-A"
    m = oracle(t)
    m["codes"][1]["units"] = 40
    print(f"ICD10-A J3301 units 40 (mg) instead of 4 (10 mg units): {run(t, m)['reward']}")
    m = oracle(t)
    m["codes"][1]["modifiers"] = []
    print(f"ICD10-A J3301 without JZ: {run(t, m)['reward']}")
    m = oracle(t)
    m["codes"].append({"code": "20611", "system": "CPT", "role": "line", "evidence": "x"})
    print(f"ICD10-A answer contains a CPT code (licensed, gate): {run(t, m)['reward']} / {run(t, m)['gate']}")
    t = "ICD04-A"
    m = oracle(t)
    m["codes"][1]["code"] = "W01.0XXA"
    print(f"ICD04-A playbook's W01.0XXA instead of index-directed W18.09XA (accepted pending CCS): {run(t, m)['reward']}")
    m = oracle(t)
    m["codes"].append({"code": "Z99.99", "system": "ICD-10-CM", "evidence": "x"})
    print(f"ICD10-A includes an invalid code (gate): {run(t, m)['reward']} / {run(t, m)['gate']}")
    t = "ICD07-A"
    m = oracle(t)
    m["codes"] = [{"code": "J18.9", "system": "ICD-10-CM", "role": "first_listed", "evidence": "Probable pneumonia"}]
    print(f"ICD07-A codes 'probable pneumonia' as confirmed in ED: {run(t, m)['reward']}")
    print("\nWhole answer file (task reward = mean over cases):")
    file_ok = whole_file_checks()
    print(f"\n{len(tasks) - fails}/{len(tasks)} cases behave as expected; whole-file checks {'ok' if file_ok else 'FAILED'}")
    sys.exit(1 if fails or not file_ok else 0)


if __name__ == "__main__":
    main()
