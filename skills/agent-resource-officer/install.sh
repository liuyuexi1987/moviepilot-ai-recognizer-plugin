#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEX_HOME_DIR="${CODEX_HOME:-"${HOME}/.codex"}"
TARGET_DIR="${CODEX_HOME_DIR}/skills/agent-resource-officer"
DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    --dry-run)
      DRY_RUN=1
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

echo "Source: ${SCRIPT_DIR}"
echo "Target: ${TARGET_DIR}"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "Dry run: no files changed."
  exit 0
fi

mkdir -p "$(dirname "${TARGET_DIR}")"
rm -rf "${TARGET_DIR}"
mkdir -p "${TARGET_DIR}"

if command -v rsync >/dev/null 2>&1; then
  rsync -a \
    --exclude '.DS_Store' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    "${SCRIPT_DIR}/" "${TARGET_DIR}/"
else
  cp -R "${SCRIPT_DIR}/." "${TARGET_DIR}/"
  find "${TARGET_DIR}" -name '.DS_Store' -delete
  find "${TARGET_DIR}" -name '__pycache__' -type d -prune -exec rm -rf {} +
  find "${TARGET_DIR}" -name '*.pyc' -delete
fi

echo "Installed agent-resource-officer skill."
