#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

show_help() {
  cat <<'EOF'
Usage:
  bash scripts/create-draft-release.sh <tag> [--dry-run] [--skip-check]

Options:
  <tag>         GitHub Release tag, for example v2026.04.28.1
  --dry-run     Run checks and print the release command without creating a release
  --skip-check  Skip release-preflight.sh and use existing dist/ files
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
  bash scripts/release-preflight.sh
else
  bash scripts/verify-release-assets.sh dist
fi

notes_file="$(mktemp)"
asset_stage_dir="$(mktemp -d)"
cleanup() {
  rm -f "$notes_file"
  rm -rf "$asset_stage_dir"
}
trap cleanup EXIT

bash scripts/generate-release-notes.sh "$TAG" >"$notes_file"

cp dist/*.zip "$asset_stage_dir/"
cp dist/SHA256SUMS.txt "$asset_stage_dir/PLUGIN_SHA256SUMS.txt"
cp dist/MANIFEST.json "$asset_stage_dir/PLUGIN_MANIFEST.json"
cp dist/skills/*.zip "$asset_stage_dir/"
cp dist/skills/SHA256SUMS.txt "$asset_stage_dir/SKILL_SHA256SUMS.txt"
cp dist/skills/MANIFEST.json "$asset_stage_dir/SKILL_MANIFEST.json"

files=("$asset_stage_dir"/*)
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
