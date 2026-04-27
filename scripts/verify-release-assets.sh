#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

ASSET_DIR="${1:-dist}"
if [[ ! -d "$ASSET_DIR" ]]; then
  echo "发布产物目录不存在: $ASSET_DIR" >&2
  exit 1
fi

skill_asset_dir=""
if [[ -d "$ASSET_DIR/skills" ]]; then
  skill_asset_dir="$ASSET_DIR/skills"
elif [[ -d "$ASSET_DIR/dist/skills" ]]; then
  skill_asset_dir="$ASSET_DIR/dist/skills"
fi

if [[ -z "$skill_asset_dir" ]]; then
  echo "发布产物目录缺少 Skill 产物子目录: $ASSET_DIR" >&2
  exit 1
fi

DIST_DIR="$ASSET_DIR" bash scripts/verify-dist.sh
DIST_DIR="$skill_asset_dir" bash scripts/verify-skill-dist.sh
echo "release_assets_verify_ok dir=$ASSET_DIR"
