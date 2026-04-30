#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

show_help() {
  cat <<'EOF'
Usage:
  bash scripts/release-preflight.sh

Runs the full release preflight in two stages:
1. repo-hygiene.sh
2. pre-release-check.sh
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  show_help
  exit 0
fi

echo "[1/2] repo hygiene"
bash scripts/repo-hygiene.sh

echo "[2/2] pre-release check"
bash scripts/pre-release-check.sh
