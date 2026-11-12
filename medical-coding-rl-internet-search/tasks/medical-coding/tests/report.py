#!/usr/bin/env python3
"""Human-readable report for one trial (runs after score.py inside the verifier).

  * validates coded_claims.json against output_schema.json (stdlib only, no installs)
  * per case: reward, gate, failed checks, expected vs submitted codes (from groundtruth.json)
  * summary by playbook example, setting and edge case
  * writes report.json (machine-readable) and report.md (for people) next to reward.txt

The schema check is informational: it never changes the reward. score.py is the only grader.

Usage: report.py --claims coded_claims.json --details reward-details.json \
                 --groundtruth groundtruth.json --schema output_schema.json --out /logs/verifier
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}
FIELDS = ("code", "system", "role", "poa", "modifiers", "units")


def _is_type(v, t: str) -> bool:
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, _TYPES[t])


def validate(inst, schema: dict, root: dict | None = None, path: str = "$") -> list[str]:
    """Minimal JSON Schema (2020-12) validator for the keywords output_schema.json uses."""
    root = root or schema
    errs: list[str] = []
    if "$ref" in schema:
        node = root
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        errs += validate(inst, node, root, path)
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is_type(inst, t) for t in types):
            return errs + [f"{path}: expected {'/'.join(types)}, got {type(inst).__name__}"]
    if "const" in schema and inst != schema["const"]:
        errs.append(f"{path}: must be {schema['const']!r}")
    if "enum" in schema and inst not in schema["enum"]:
        errs.append(f"{path}: {inst!r} is not one of {schema['enum']}")
    if isinstance(inst, str):
        if len(inst) < schema.get("minLength", 0):
            errs.append(f"{path}: must not be empty")
        if "pattern" in schema and not re.search(schema["pattern"], inst):
            errs.append(f"{path}: {inst!r} does not match {schema['pattern']}")
    if _is_type(inst, "number") and "minimum" in schema and inst < schema["minimum"]:
        errs.append(f"{path}: {inst} < {schema['minimum']}")
    if isinstance(inst, dict):
        if len(inst) < schema.get("minProperties", 0):
            errs.append(f"{path}: must have at least {schema['minProperties']} entries")
        for k in schema.get("required", []):
            if k not in inst:
                errs.append(f"{path}: missing required field '{k}'")
        props, extra = schema.get("properties", {}), schema.get("additionalProperties", True)
        for k, v in inst.items():
            if "propertyNames" in schema:
                errs += [e.replace(f"{path}.{k}:", f"{path}: key", 1)
                         for e in validate(k, schema["propertyNames"], root, f"{path}.{k}")]
            if k in props:
                errs += validate(v, props[k], root, f"{path}.{k}")
            elif extra is False:
                errs.append(f"{path}: unexpected field '{k}'")
            elif isinstance(extra, dict):
                errs += validate(v, extra, root, f"{path}.{k}")
    if isinstance(inst, list) and "items" in schema:
        for i, v in enumerate(inst):
            errs += validate(v, schema["items"], root, f"{path}[{i}]")
    for sub in schema.get("allOf", []):
        errs += validate(inst, sub, root, path)
    if "anyOf" in schema and all(validate(inst, s, root, path) for s in schema["anyOf"]):
        errs.append(f"{path}: matches none of the allowed forms")
    if "not" in schema and not validate(inst, schema["not"], root, path):
        errs.append(f"{path}: contains a field that is not allowed here")
    if "if" in schema:
        branch = "then" if not validate(inst, schema["if"], root, path) else "else"
        if branch in schema:
            errs += validate(inst, schema[branch], root, path)
    return errs


def cell(v):
    return "-" if v in (None, [], "") else (", ".join(map(str, v)) if isinstance(v, list) else str(v))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", required=True)
    ap.add_argument("--details", required=True)
    ap.add_argument("--groundtruth", required=True)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    groundtruth = json.loads(Path(a.groundtruth).read_text())
    details = json.loads(Path(a.details).read_text()) if Path(a.details).is_file() else {"cases": {}}

    claims, schema_errors = {}, []
    try:
        claims = json.loads(Path(a.claims).read_text())
        schema_errors = validate(claims, json.loads(Path(a.schema).read_text()))
        claims = claims if isinstance(claims, dict) else {}
    except FileNotFoundError:
        schema_errors = [f"{a.claims} was not written"]
    except json.JSONDecodeError as e:
        schema_errors = [f"{a.claims} is not valid JSON: {e}"]

    cases = []
    for cid, gt in groundtruth.items():
        res = details.get("cases", {}).get(cid, {})
        claim = claims.get(cid) if isinstance(claims.get(cid), dict) else {}
        cases.append({
            "case_id": cid, **gt.get("meta", {}),
            "reward": res.get("reward", 0.0), "passed": res.get("passed", False), "gate": res.get("gate"),
            "earned": res.get("earned"), "max_points": res.get("max_points"),
            "query_expected": gt["query_needed"], "query_raised": bool(claim.get("query_needed")),
            "query_text": claim.get("query_text"),
            "failed_checks": [c["name"] for c in res.get("checks", []) if not c["ok"]],
            "expected_codes": [{k: c.get(k) for k in FIELDS} for c in gt["codes"]],
            "submitted_codes": [{k: c.get(k) for k in FIELDS} for c in claim.get("codes", []) if isinstance(c, dict)],
            "schema_errors": [e for e in schema_errors if e.startswith(f"$.{cid}")],
        })

    report = {k: details.get(k) for k in ("reward", "mode", "mean_case_reward", "cases_total", "cases_passed",
                                         "unknown_case_ids", "file_error")}
    report.update({"schema_valid": not schema_errors, "schema_errors": schema_errors, "cases": cases})
    (out / "report.json").write_text(json.dumps(report, indent=2))

    md = ["# Medical coding report", "",
          f"**Reward:** {report['reward']} ({report['mode']})  ·  {report['cases_passed']}/{report['cases_total']} cases "
          f"fully correct  ·  mean case reward {report['mean_case_reward']}", ""]
    if report["file_error"]:
        md += [f"**File error:** {report['file_error']}", ""]
    if report["unknown_case_ids"]:
        md += [f"**Unknown case ids in the answer (ignored):** {', '.join(report['unknown_case_ids'])}", ""]
    q = [c for c in cases if c["query_expected"]]
    md += [f"Provider queries: {sum(c['query_raised'] for c in q)}/{len(q)} required queries raised; "
           f"{sum(c['query_raised'] for c in cases if not c['query_expected'])} needless queries.", ""]

    for key, title in (("playbook_example", "playbook example"), ("setting", "setting"), ("edge_case_tags", "edge case")):
        groups = defaultdict(list)
        for c in cases:
            for k in (c.get(key) if isinstance(c.get(key), list) else [c.get(key)]):
                groups[k or "-"].append(c)
        md += [f"## By {title}", "", f"| {title} | cases | mean reward | fully correct |", "|---|---|---|---|"]
        md += [f"| {k} | {len(g)} | {sum(c['reward'] for c in g) / len(g):.3f} | {sum(c['passed'] for c in g)}/{len(g)} |"
               for k, g in sorted(groups.items())]
        md.append("")

    md += ["## By case", "", "| case | setting | reward | gate / failed checks |", "|---|---|---|---|"]
    md += [f"| {c['case_id']} | {c.get('setting', '-')} | {c['reward']:.3f} | "
           f"{(c['gate'] or '; '.join(c['failed_checks']) or '').replace('|', '/')} |" for c in cases]

    md += ["", "## Case details"]
    for c in cases:
        md += ["", f"### {c['case_id']}: {c.get('title', '')}  ({c['reward']:.3f})", "",
               f"Query: expected {'yes' if c['query_expected'] else 'no'}, raised {'yes' if c['query_raised'] else 'no'}", ""]
        for title, rows in (("Expected", c["expected_codes"]), ("Submitted", c["submitted_codes"])):
            md += [f"{title}:", "", "| code | system | role | POA | modifiers | units |", "|---|---|---|---|---|---|"]
            md += [f"| {cell(r['code'])} | {cell(r['system'])} | {cell(r['role'])} | {cell(r['poa'])} | "
                   f"{cell(r['modifiers'])} | {cell(r['units'])} |" for r in rows] or ["| (none) | | | | | |"]
            md.append("")

    md += ["## Output schema", ""]
    md += ["Valid."] if not schema_errors else [f"- {e}" for e in schema_errors[:200]]
    (out / "report.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[:6]))


if __name__ == "__main__":
    main()
