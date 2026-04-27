#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

show_help() {
  cat <<'EOF'
Usage:
  bash scripts/verify-release-download.sh <tag>

Downloads GitHub Release or Draft Release assets for <tag> and verifies
plugin ZIP, Skill ZIP, SHA256SUMS and MANIFEST files.
EOF
}

TAG="${1:-}"
if [[ "$TAG" == "--help" || "$TAG" == "-h" ]]; then
  show_help
  exit 0
fi
if [[ -z "$TAG" ]]; then
  echo "缺少 release tag。" >&2
  show_help >&2
  exit 2
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "未找到 gh 命令，无法下载 GitHub Release 附件。" >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

gh release download "$TAG" --dir "$tmp_dir" --clobber
bash scripts/verify-release-assets.sh "$tmp_dir"
echo "release_download_verify_ok tag=$TAG"
