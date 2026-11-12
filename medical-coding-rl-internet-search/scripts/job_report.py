"""Summarise a Harbor job of the medical-coding task (one trial = all 36 cases).

Reads every trial's verifier/report.json (written by tests/report.py) and writes
  jobs/<job>/benchmark_report.md    per trial, and per case across trials (mean over attempts)
  jobs/<job>/benchmark_report.csv   one row per (trial, case)

Run:  uv run python scripts/job_report.py jobs/<job-name>    (scripts/run.sh does this for you)
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    job = Path(sys.argv[1]).resolve()
    trials = []
    for trial in sorted(p for p in job.iterdir() if p.is_dir()):
        rep_path = trial / "verifier" / "report.json"
        result = json.loads((trial / "result.json").read_text()) if (trial / "result.json").is_file() else {}
        agent = result.get("agent_info") or {}
        exc = result.get("exception_info")
        trials.append({
            "trial": trial.name,
            "agent": " ".join(filter(None, [agent.get("name"), (agent.get("model_info") or {}).get("name")])),
            "exception": (exc or {}).get("exception_type", "") if isinstance(exc, dict) else (str(exc) if exc else ""),
            "report": json.loads(rep_path.read_text()) if rep_path.is_file() else None,
        })
    if not trials:
        sys.exit(f"no trials found in {job}")

    rows = []
    for t in trials:
        for c in (t["report"] or {}).get("cases", []):
            rows.append({"trial": t["trial"], "agent": t["agent"], "case_id": c["case_id"],
                         "playbook_example": c.get("playbook_example"), "setting": c.get("setting"),
                         "edge_case_tags": " ".join(c.get("edge_case_tags") or []),
                         "reward": c["reward"], "passed": c["passed"], "gate": c.get("gate") or "",
                         "failed_checks": "; ".join(c.get("failed_checks", []))})
    if rows:
        with open(job / "benchmark_report.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)

    md = [f"# Medical coding benchmark: {job.name}", "",
          "| trial | agent | reward | cases fully correct | mean case reward | schema valid | exception |",
          "|---|---|---|---|---|---|---|"]
    for t in trials:
        r = t["report"] or {}
        md.append(f"| {t['trial']} | {t['agent'] or '-'} | {r.get('reward', 0)} | "
                  f"{r.get('cases_passed', 0)}/{r.get('cases_total', 36)} | {r.get('mean_case_reward', 0)} | "
                  f"{'yes' if r.get('schema_valid') else 'no'} | {t['exception'] or '-'} |")
    md.append("")

    by_case = defaultdict(list)
    for row in rows:
        by_case[row["case_id"]].append(row)
    if by_case:
        md += ["## By case (mean over trials)", "",
               "| case | setting | mean reward | fully correct | last gate / failed checks |", "|---|---|---|---|---|"]
        for cid, rs in sorted(by_case.items()):
            last = rs[-1]
            md.append(f"| {cid} | {last['setting']} | {sum(r['reward'] for r in rs) / len(rs):.3f} | "
                      f"{sum(r['passed'] for r in rs)}/{len(rs)} | "
                      f"{(last['gate'] or last['failed_checks']).replace('|', '/')} |")
        md.append("")
    md.append("Per-case details for each trial: `<trial>/verifier/report.md`.")
    (job / "benchmark_report.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[: 4 + len(trials)]))
    print(f"wrote {job / 'benchmark_report.md'}" + (f" and {job / 'benchmark_report.csv'}" if rows else ""))


if __name__ == "__main__":
    main()
