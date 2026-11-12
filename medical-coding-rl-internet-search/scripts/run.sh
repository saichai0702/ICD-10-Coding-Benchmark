#!/usr/bin/env bash
# Run the medical-coding task with Harbor, then write the job report.
#
#   scripts/run.sh -a oracle                                     # sanity check: reward 1.0
#   scripts/run.sh -a claude-code -m anthropic/claude-opus-5-5   # benchmark an agent
#   scripts/run.sh -a claude-code -m anthropic/claude-opus-5-5 -k 3   # 3 attempts
#
# Every argument is passed to `harbor run`. Set --job-name to choose the jobs/<name> folder.
set -euo pipefail
cd "$(dirname "$0")/.."

JOB_NAME="mc-$(date +%Y%m%d-%H%M%S)"
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  [[ "${args[i]}" == "--job-name" ]] && JOB_NAME="${args[i + 1]}"
done
[[ " ${args[*]:-} " == *" --job-name "* ]] || args+=(--job-name "$JOB_NAME")

uv run harbor run -p tasks/medical-coding -y "${args[@]}"
uv run python scripts/job_report.py "jobs/$JOB_NAME"
