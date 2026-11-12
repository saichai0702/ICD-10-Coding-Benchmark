#!/usr/bin/env bash
# Harbor verifier: grade /app/output/coded_claims.json against groundtruth.json, then write a report.
# Writes /logs/verifier/{reward.txt, reward-details.json, report.json, report.md, coded_claims.json}
set -uo pipefail

CLAIMS=/app/output/coded_claims.json
OUT=/logs/verifier
mkdir -p "$OUT"
rm -f "$OUT/reward.txt" "$OUT/reward-details.json"

# 1. Grade every case (deterministic, no LLM). Writes reward.txt and reward-details.json.
python3 /tests/score.py \
  --claims "$CLAIMS" \
  --groundtruth /tests/groundtruth.json \
  --cases /app/cases \
  --valid /tests/valid_codes.json.gz \
  --out "$OUT" \
  --mode "${SCORE_MODE:-partial}"

# 2. Report (schema check + per-case expected vs submitted). Never changes the reward.
python3 /tests/report.py \
  --claims "$CLAIMS" \
  --details "$OUT/reward-details.json" \
  --groundtruth /tests/groundtruth.json \
  --schema /tests/output_schema.json \
  --out "$OUT" > /dev/null || echo "report.py failed (reward unaffected)" >&2

# Keep a copy of what the agent submitted next to its grade.
[ -f "$CLAIMS" ] && cp "$CLAIMS" "$OUT/coded_claims.json"

# Harbor needs a reward even if grading crashed.
[ -s "$OUT/reward.txt" ] || echo 0 > "$OUT/reward.txt"
exit 0
