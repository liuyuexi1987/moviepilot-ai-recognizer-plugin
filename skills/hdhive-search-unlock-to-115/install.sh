#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEX_HOME_DIR="${CODEX_HOME:-"${HOME}/.codex"}"
TARGET_DIR="${CODEX_HOME_DIR}/skills/hdhive-search-unlock-to-115"
DRY_RUN=0

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --target)
      if [[ "$#" -lt 2 ]]; then
        echo "--target requires a directory" >&2
        exit 2
      fi
      TARGET_DIR="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

echo "Source: ${SCRIPT_DIR}"
echo "Target: ${TARGET_DIR}"

TARGET_DIR="${TARGET_DIR%/}"
if [[ -z "${TARGET_DIR}" || "${TARGET_DIR}" == "/" || "${TARGET_DIR}" == "." || "${TARGET_DIR}" == "${HOME}" || "${TARGET_DIR}" == "${CODEX_HOME_DIR}" ]]; then
  echo "Refusing unsafe target: ${TARGET_DIR}" >&2
  exit 2
fi

if [[ -e "${TARGET_DIR}" && ! -d "${TARGET_DIR}" ]]; then
  echo "Refusing non-directory target: ${TARGET_DIR}" >&2
  exit 2
fi

if [[ "$DRY_RUN" == "1" ]]; then
  echo "Dry run: no files changed."
  exit 0
fi

mkdir -p "$(dirname "${TARGET_DIR}")"
if [[ -d "${TARGET_DIR}" && ! -f "${TARGET_DIR}/SKILL.md" ]]; then
  if [[ -n "$(find "${TARGET_DIR}" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    echo "Refusing to overwrite non-skill directory: ${TARGET_DIR}" >&2
    exit 2
  fi
fi

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

echo "Installed hdhive-search-unlock-to-115 skill."
