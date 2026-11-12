"""Oracle: turn /solution/groundtruth.json into /app/output/coded_claims.json.

groundtruth.json is {case_id: expected output + scoring info}. The agent's answer file has the
same keys; each value is the claim in the format instruction.md describes. The oracle copies the
expected claim and drops the scoring-only fields (accept, role_scored, scoring, meta).
"""
import json
from pathlib import Path

groundtruth = json.loads(Path("/solution/groundtruth.json").read_text())
claims = {}
for case_id, gt in groundtruth.items():
    claims[case_id] = {
        "query_needed": gt["query_needed"],
        "query_text": gt["query_text"],
        "codes": [{k: v for k, v in c.items() if k not in ("accept", "role_scored")} for c in gt["codes"]],
    }

out = Path("/app/output/coded_claims.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(claims, indent=2) + "\n")
print(f"wrote {len(claims)} claims to {out}")
