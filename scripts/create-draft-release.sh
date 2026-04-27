#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

show_help() {
  cat <<'EOF'
Usage:
  bash scripts/create-draft-release.sh <tag> [--dry-run] [--skip-check]

Options:
  <tag>         GitHub Release tag, for example v2026.04.28
  --dry-run     Run checks and print the release command without creating a release
  --skip-check  Skip pre-release-check.sh and use existing dist/ files
  --help        Show this help
EOF
}

TAG=""
DRY_RUN=0
SKIP_CHECK=0
for arg in "$@"; do
  case "$arg" in
    --dry-run)
      DRY_RUN=1
      ;;
    --skip-check)
      SKIP_CHECK=1
      ;;
    --help|-h)
      show_help
      exit 0
      ;;
    *)
      if [ -z "$TAG" ]; then
        TAG="$arg"
      else
        echo "未知参数: $arg" >&2
        show_help >&2
        exit 1
      fi
      ;;
  esac
done

if [ -z "$TAG" ]; then
  echo "缺少 release tag。" >&2
  show_help >&2
  exit 1
fi

if [ "$SKIP_CHECK" -eq 0 ]; then
  bash scripts/pre-release-check.sh
else
  bash scripts/verify-dist.sh
fi

notes_file="$(mktemp)"
cleanup() {
  rm -f "$notes_file"
}
trap cleanup EXIT

{
  echo "# $TAG"
  echo
  echo "本次 Release 附件包含 MoviePilot 本地安装 ZIP、SHA256SUMS.txt 和 MANIFEST.json。"
  echo
  bash scripts/print-release-summary.sh
} >"$notes_file"

files=(dist/*.zip dist/SHA256SUMS.txt dist/MANIFEST.json)
for file_path in "${files[@]}"; do
  if [ ! -f "$file_path" ]; then
    echo "缺少发布附件: $file_path" >&2
    exit 1
  fi
done

if [ "$DRY_RUN" -eq 1 ]; then
  echo "draft_release_dry_run_ok tag=$TAG"
  echo "notes_file=$notes_file"
  printf 'files=%s\n' "${files[@]}"
  exit 0
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "未找到 gh 命令，无法创建 GitHub Release。" >&2
  exit 1
fi

gh release create "$TAG" \
  --draft \
  --title "$TAG" \
  --notes-file "$notes_file" \
  "${files[@]}"
