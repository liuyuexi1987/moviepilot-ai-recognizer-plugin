#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

show_help() {
  cat <<'EOF'
Usage:
  bash scripts/update-draft-release-assets.sh <tag> [--skip-check]

Rebuilds or verifies local release assets, updates an existing GitHub Draft
Release's notes, uploads all assets with --clobber, then downloads and verifies
the release assets.
EOF
}

TAG=""
SKIP_CHECK=0
for arg in "$@"; do
  case "$arg" in
    --skip-check)
      SKIP_CHECK=1
      ;;
    --help|-h)
      show_help
      exit 0
      ;;
    *)
      if [[ -z "$TAG" ]]; then
        TAG="$arg"
      else
        echo "未知参数: $arg" >&2
        show_help >&2
        exit 2
      fi
      ;;
  esac
done

if [[ -z "$TAG" ]]; then
  echo "缺少 release tag。" >&2
  show_help >&2
  exit 2
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "未找到 gh 命令，无法更新 GitHub Draft Release。" >&2
  exit 1
fi

if [[ "$SKIP_CHECK" == "1" ]]; then
  bash scripts/verify-release-assets.sh dist
else
  bash scripts/pre-release-check.sh
fi

notes_file="$(mktemp)"
asset_stage_dir="$(mktemp -d)"
cleanup() {
  rm -f "$notes_file"
  rm -rf "$asset_stage_dir"
}
trap cleanup EXIT

{
  echo "# $TAG"
  echo
  echo "本次 Release 附件包含 MoviePilot 本地安装 ZIP、公开 Skill ZIP、PLUGIN/SKILL SHA256SUMS 和 MANIFEST。"
  echo
  bash scripts/print-release-summary.sh
  echo
  echo "## 公开 Skill 模板"
  echo
  bash scripts/print-skill-release-summary.sh
} >"$notes_file"

cp dist/*.zip "$asset_stage_dir/"
cp dist/SHA256SUMS.txt "$asset_stage_dir/PLUGIN_SHA256SUMS.txt"
cp dist/MANIFEST.json "$asset_stage_dir/PLUGIN_MANIFEST.json"
cp dist/skills/*.zip "$asset_stage_dir/"
cp dist/skills/SHA256SUMS.txt "$asset_stage_dir/SKILL_SHA256SUMS.txt"
cp dist/skills/MANIFEST.json "$asset_stage_dir/SKILL_MANIFEST.json"

gh release edit "$TAG" --notes-file "$notes_file"
gh release upload "$TAG" "$asset_stage_dir"/* --clobber
bash scripts/verify-release-download.sh "$TAG"
echo "draft_release_assets_update_ok tag=$TAG"
