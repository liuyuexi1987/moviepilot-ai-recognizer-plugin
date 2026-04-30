#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

show_help() {
  cat <<'EOF'
Usage:
  bash scripts/repo-hygiene.sh

Runs the lightweight repository maintenance checks:
1. git fetch --prune origin
2. remote/local branch audit
3. local branch archive dry-run
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  show_help
  exit 0
fi

echo "[1/3] fetch --prune origin"
git fetch --prune origin >/dev/null

echo "[2/3] remote/local branch audit"
python3 scripts/audit-remote-branches.py

echo "[3/3] local archive dry-run"
python3 scripts/archive-local-branches.py
