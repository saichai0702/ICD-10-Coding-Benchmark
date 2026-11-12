#!/usr/bin/env bash
# One-step setup for both benchmarks.
#
#   ./setup.sh               # uv sync both folders + download data/raw (raw.zip from Google Drive)
#   ./setup.sh --skip-raw    # uv sync only (data/raw is only needed to rebuild the reference data)
#   ./setup.sh --force       # re-download raw.zip and replace medical-coding-rl/data/raw/
set -euo pipefail
cd "$(dirname "$0")"

SKIP_RAW=0
RAW_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --skip-raw) SKIP_RAW=1 ;;
    *) RAW_ARGS+=("$arg") ;;
  esac
done

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Install it with:"
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi
command -v docker >/dev/null 2>&1 || echo "Warning: docker not found; Harbor needs Docker to run the tasks."

for dir in medical-coding-rl medical-coding-rl-internet-search; do
  echo "==> uv sync in $dir"
  (cd "$dir" && uv sync)
done

if [[ $SKIP_RAW -eq 0 ]]; then
  echo "==> Downloading raw CMS data (raw.zip) into medical-coding-rl/data/raw/"
  (cd medical-coding-rl && uv run --with gdown python scripts/download_raw.py ${RAW_ARGS[@]+"${RAW_ARGS[@]}"})
fi

echo "==> Setup complete."
