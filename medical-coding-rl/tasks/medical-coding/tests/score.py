#!/usr/bin/env python3
"""Deterministic grader (no LLM judge): compare the agent's coded_claims.json with groundtruth.json.

Both files are keyed by case id. Each case is scored separately with the playbook's rules:
  * every code must exist (billable) in the pinned code set        -> case reward 0
  * CPT / CDT codes are licensed and are never valid output          -> case reward 0
  * if the ground truth says "query the provider", the agent must    -> else case reward 0
  * each expected code is scored: code 2, role 1, POA 1 (inpatient), modifiers 1 + units 1
    (HCPCS/CDM lines); evidence quote not found word for word in the chart: -0.5
  * extra unsupported code -1, known-wrong ("forbidden") code -3, needless query -1
  * case reward = earned / max, clipped to [0, 1]; a missing case scores 0

Task reward = mean of the 36 case rewards (SCORE_MODE=partial, default),
           or 1 only if every case is fully correct (SCORE_MODE=binary).

Usage: score.py --claims coded_claims.json --groundtruth groundtruth.json --cases /app/cases \
                --valid valid_codes.json.gz --out /logs/verifier [--mode partial|binary]
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
from pathlib import Path

W_CODE, W_ROLE, W_POA, W_MOD, W_UNITS, W_QUERY = 2.0, 1.0, 1.0, 1.0, 1.0, 2.0
P_EXTRA, P_FORBIDDEN, P_EVIDENCE, P_NEEDLESS_QUERY = 1.0, 3.0, 0.5, 1.0
PRINCIPAL = {"principal", "first_listed", "principal_procedure"}
LINE_SYSTEMS = {"HCPCS", "CDM"}   # CDM = hospital charge-master line (no CPT in this environment)


def norm_code(code: str, system: str) -> str:
    c = str(code).upper().strip()
    if system in ("ICD-10-CM", "ICD-10-PCS"):
        c = c.replace(".", "")
    return c.split("-")[0] if system in LINE_SYSTEMS else c


def norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").lower()).strip()


def norm_mods(mods) -> set[str]:
    return {str(m).upper().strip() for m in (mods or []) if str(m).strip()}


def parse_claim(data):
    """Validate one case's claim object and normalise its lines."""
    if not isinstance(data, dict) or not isinstance(data.get("codes", []), list):
        raise ValueError("claim must be an object with a 'codes' list")
    items = []
    for i, c in enumerate(data.get("codes", [])):
        if not isinstance(c, dict) or "code" not in c or "system" not in c:
            raise ValueError(f"codes[{i}] needs 'code' and 'system'")
        system = str(c["system"]).upper().replace("ICD10", "ICD-10").strip()
        mods = norm_mods(c.get("modifiers"))
        if system in LINE_SYSTEMS and "-" in str(c["code"]):            # tolerate "20611-RT"
            mods |= norm_mods(str(c["code"]).split("-")[1:])
        items.append({"code": norm_code(c["code"], system), "system": system,
                      "role": (c.get("role") or "").lower(), "poa": (c.get("poa") or "").upper() or None,
                      "mods": mods, "units": int(c.get("units") or 1), "evidence": c.get("evidence", "")})
    return bool(data.get("query_needed")), items


def is_valid(item, valid) -> bool:
    s, c = item["system"], item["code"]
    return {"ICD-10-CM": c in valid["icd10cm"], "ICD-10-PCS": c in valid["icd10pcs"],
            "HCPCS": c in valid["hcpcs"], "CDM": c in valid["cdm"]}.get(s, False)


def score_case(claim, gt: dict, chart_text: str, valid: dict) -> dict:
    """Score one case. `claim` is the agent's value for this case (or None if missing)."""
    out = {"reward": 0.0, "passed": False, "checks": [], "gate": None}

    def check(name, ok, pts, earned):
        out["checks"].append({"name": name, "ok": bool(ok), "points": pts, "earned": earned})

    if claim is None:
        out["gate"] = "case missing from coded_claims.json"
        return out
    try:
        agent_query, items = parse_claim(claim)
    except (ValueError, TypeError) as e:
        out["gate"] = f"unreadable claim: {e}"
        return out

    scoring = gt.get("scoring", {})
    valid = {**valid, "cdm": set(scoring.get("cdm_lines", []))}
    bad = [f"{i['system']} {i['code']}" for i in items if not is_valid(i, valid)]
    if bad:
        out["gate"] = f"invalid, non-billable or licensed (CPT/CDT) code(s) for this environment: {', '.join(bad)}"
        return out
    if gt["query_needed"] and not agent_query:
        out["gate"] = "documentation required a provider query, but none was raised (guessing is not allowed)"
        return out

    earned = maxpts = 0.0
    if gt["query_needed"]:
        maxpts += W_QUERY
        earned += W_QUERY
        check("query raised", True, W_QUERY, W_QUERY)
    elif agent_query:
        earned -= P_NEEDLESS_QUERY
        check("unnecessary query", False, 0, -P_NEEDLESS_QUERY)

    used = set()
    for g in gt["codes"]:
        sys_ = g["system"]
        targets = {norm_code(g["code"], sys_)} | {norm_code(a, sys_) for a in g.get("accept", [])}
        gmods = norm_mods(g.get("modifiers"))
        cands = [k for k, it in enumerate(items) if k not in used and it["code"] in targets and it["system"] == sys_]
        if sys_ in LINE_SYSTEMS and len(cands) > 1:   # same code on two lines: pick best modifier match
            cands.sort(key=lambda k: -len(items[k]["mods"] & gmods) + len(items[k]["mods"] ^ gmods) * 0.1)
        label = f"{sys_} {g['code']}" + (f"-{'-'.join(sorted(gmods))}" if gmods else "")
        scored_role = g.get("role") and g["role"] != "line" and g.get("role_scored", True)
        pts = W_CODE + (W_ROLE if scored_role else 0) + (W_POA if g.get("poa") else 0) \
            + (W_MOD + W_UNITS if sys_ in LINE_SYSTEMS else 0)
        maxpts += pts
        if not cands:
            check(f"{label}: missing", False, pts, 0)
            continue
        k = cands[0]
        used.add(k)
        it, got, notes = items[k], W_CODE, []
        if scored_role:
            if (g["role"] in PRINCIPAL) == (it["role"] in PRINCIPAL):
                got += W_ROLE
            else:
                notes.append(f"role {it['role'] or '-'} (expected {g['role']})")
        if g.get("poa"):
            if it["poa"] == g["poa"]:
                got += W_POA
            else:
                notes.append(f"POA {it['poa']} (expected {g['poa']})")
        if sys_ in LINE_SYSTEMS:
            if it["mods"] == gmods:
                got += W_MOD
            else:
                notes.append(f"modifiers {sorted(it['mods'])} (expected {sorted(gmods)})")
            if it["units"] == int(g.get("units") or 1):
                got += W_UNITS
            else:
                notes.append(f"units {it['units']} (expected {g.get('units')})")
        if not it["evidence"] or norm_text(it["evidence"]) not in chart_text:
            got -= P_EVIDENCE
            notes.append("evidence quote not found in chart")
        earned += got
        check(label + (f": {'; '.join(notes)}" if notes else ""), got == pts, pts, got)

    optional = {norm_code(c, "ICD-10-CM") for c in scoring.get("optional", [])} | set(scoring.get("optional", []))
    forbidden = {norm_code(c, "ICD-10-CM") for c in scoring.get("forbidden", [])} | set(scoring.get("forbidden", []))
    for k, it in enumerate(items):
        if k in used or it["code"] in optional:
            continue
        pen = P_FORBIDDEN if it["code"] in forbidden else P_EXTRA
        earned -= pen
        check(f"extra {it['system']} {it['code']}" + (" (known-wrong for this chart)" if pen == P_FORBIDDEN else " (not supported)"),
              False, 0, -pen)

    out["max_points"], out["earned"] = maxpts, earned
    out["reward"] = round(max(0.0, min(1.0, earned / maxpts)) if maxpts else 0.0, 4)
    out["passed"] = out["reward"] == 1.0
    return out


def chart_text(cases_dir: Path, case_id: str) -> str:
    chart = cases_dir / case_id / "chart"
    return " ".join(norm_text(p.read_text()) for p in sorted(chart.glob("*")) if p.is_file())


def score_all(claims_path: Path, groundtruth: dict, cases_dir: Path, valid: dict, mode: str = "partial") -> dict:
    file_error, claims = None, {}
    try:
        claims = json.loads(claims_path.read_text())
        if not isinstance(claims, dict):
            file_error, claims = "coded_claims.json must be an object keyed by case id", {}
    except (OSError, json.JSONDecodeError) as e:
        file_error = f"unreadable coded_claims.json: {e}"

    cases = {cid: score_case(claims.get(cid), gt, chart_text(cases_dir, cid), valid)
             for cid, gt in groundtruth.items()}
    if file_error:
        for res in cases.values():
            res["gate"] = file_error
    n = len(cases)
    mean = round(sum(r["reward"] for r in cases.values()) / n, 4) if n else 0.0
    n_passed = sum(r["passed"] for r in cases.values())
    return {"reward": mean if mode == "partial" else float(n_passed == n), "mode": mode,
            "mean_case_reward": mean, "cases_total": n, "cases_passed": n_passed,
            "unknown_case_ids": sorted(set(claims) - set(groundtruth)), "file_error": file_error,
            "cases": cases}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", required=True)
    ap.add_argument("--groundtruth", required=True)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--valid", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=["partial", "binary"], default="partial")
    a = ap.parse_args()
    groundtruth = json.loads(Path(a.groundtruth).read_text())
    with gzip.open(a.valid, "rt") as f:
        valid = {k: set(v) for k, v in json.load(f).items()}
    res = score_all(Path(a.claims), groundtruth, Path(a.cases), valid, a.mode)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "reward.txt").write_text(f"{res['reward']:g}\n")
    (out / "reward-details.json").write_text(json.dumps(res, indent=2))
    print(f"reward {res['reward']:g} ({res['mode']}): {res['cases_passed']}/{res['cases_total']} cases fully correct, "
          f"mean case reward {res['mean_case_reward']:g}")


if __name__ == "__main__":
    main()
