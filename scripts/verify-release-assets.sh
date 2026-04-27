#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

ASSET_DIR="${1:-dist}"
if [[ ! -d "$ASSET_DIR" ]]; then
  echo "发布产物目录不存在: $ASSET_DIR" >&2
  exit 1
fi

if [[ -f "$ASSET_DIR/PLUGIN_SHA256SUMS.txt" && -f "$ASSET_DIR/PLUGIN_MANIFEST.json" && -f "$ASSET_DIR/SKILL_SHA256SUMS.txt" && -f "$ASSET_DIR/SKILL_MANIFEST.json" ]]; then
  tmp_dir="$(mktemp -d)"
  cleanup() {
    rm -rf "$tmp_dir"
  }
  trap cleanup EXIT
  plugin_dir="$tmp_dir/plugin"
  skill_dir="$tmp_dir/skills"
  mkdir -p "$plugin_dir" "$skill_dir"
  cp "$ASSET_DIR/PLUGIN_SHA256SUMS.txt" "$plugin_dir/SHA256SUMS.txt"
  cp "$ASSET_DIR/PLUGIN_MANIFEST.json" "$plugin_dir/MANIFEST.json"
  cp "$ASSET_DIR/SKILL_SHA256SUMS.txt" "$skill_dir/SHA256SUMS.txt"
  cp "$ASSET_DIR/SKILL_MANIFEST.json" "$skill_dir/MANIFEST.json"
  ASSET_DIR="$ASSET_DIR" PLUGIN_DIR="$plugin_dir" SKILL_DIR="$skill_dir" python3 - <<'PY'
import json
import os
import shutil
from pathlib import Path

asset_dir = Path(os.environ["ASSET_DIR"])
plugin_dir = Path(os.environ["PLUGIN_DIR"])
skill_dir = Path(os.environ["SKILL_DIR"])

plugin_manifest = json.loads((asset_dir / "PLUGIN_MANIFEST.json").read_text(encoding="utf-8"))
skill_manifest = json.loads((asset_dir / "SKILL_MANIFEST.json").read_text(encoding="utf-8"))

for item in plugin_manifest.get("plugins") or []:
    zip_name = item.get("zip")
    if not zip_name:
        continue
    src = asset_dir / zip_name
    if not src.exists():
        print(f"Release 附件缺少插件 ZIP: {zip_name}")
        raise SystemExit(1)
    shutil.copy2(src, plugin_dir / zip_name)

for item in skill_manifest.get("skills") or []:
    zip_name = item.get("zip")
    if not zip_name:
        continue
    src = asset_dir / zip_name
    if not src.exists():
        print(f"Release 附件缺少 Skill ZIP: {zip_name}")
        raise SystemExit(1)
    shutil.copy2(src, skill_dir / zip_name)
PY
  DIST_DIR="$plugin_dir" bash scripts/verify-dist.sh
  DIST_DIR="$skill_dir" bash scripts/verify-skill-dist.sh
  echo "release_assets_verify_ok dir=$ASSET_DIR"
  exit 0
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
