#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

CLEAN_DIST=0

show_help() {
  cat <<'EOF'
Usage:
  bash scripts/clean-generated.sh [--dist]

Removes local generated files that should never be committed.

Options:
  --dist   Also remove dist/ release assets.
  --help   Show this help.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --dist)
      CLEAN_DIST=1
      shift
      ;;
    --help|-h)
      show_help
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      show_help >&2
      exit 2
      ;;
  esac
done

find . \
  -path ./.git -prune -o \
  -name '__pycache__' -type d -print -exec rm -rf {} + \
  -o -name '*.pyc' -type f -print -delete \
  -o -name '*.pyo' -type f -print -delete \
  -o -name '.DS_Store' -type f -print -delete

if [[ "$CLEAN_DIST" == "1" ]]; then
  rm -rf dist
  echo "removed dist/"
fi

echo "clean_generated_ok"
