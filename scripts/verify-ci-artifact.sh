#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${1:-}"
if ! command -v gh >/dev/null 2>&1; then
  echo "未找到 gh 命令，无法下载 GitHub Actions artifact。" >&2
  exit 1
fi
if ! command -v unzip >/dev/null 2>&1; then
  echo "未找到 unzip 命令，无法解压 GitHub Actions artifact。" >&2
  exit 1
fi

if [ -z "$RUN_ID" ]; then
  RUN_ID="$(gh run list --workflow CI --branch main --status success --limit 1 --json databaseId --jq '.[0].databaseId')"
fi
if [ -z "$RUN_ID" ] || [ "$RUN_ID" = "null" ]; then
  echo "未找到可用的成功 CI run。" >&2
  exit 1
fi

artifact_count="$(gh api "repos/liuyuexi1987/MoviePilot-Plugins/actions/runs/$RUN_ID/artifacts" --jq '.artifacts | length')"
if [ "$artifact_count" -lt 1 ]; then
  echo "CI run $RUN_ID 没有 artifact。" >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

gh run download "$RUN_ID" --dir "$tmp_dir" >/dev/null
artifact_dir="$(find "$tmp_dir" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [ -z "$artifact_dir" ]; then
  echo "CI run $RUN_ID artifact 下载后没有目录。" >&2
  exit 1
fi

DIST_DIR="$artifact_dir" bash scripts/verify-dist.sh
echo "ci_artifact_verify_ok run=$RUN_ID"
