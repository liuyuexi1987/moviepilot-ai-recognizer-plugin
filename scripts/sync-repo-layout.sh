#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

sync_plugin() {
  local src_dir="$1"
  local target_name="$2"

  local target_dir_v2="$ROOT_DIR/plugins.v2/$target_name"
  local target_dir_v1="$ROOT_DIR/plugins/$target_name"

  mkdir -p "$target_dir_v2" "$target_dir_v1"

  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete --delete-excluded --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r \
      --exclude '__pycache__' \
      --exclude '*.pyc' \
      --exclude '*.pyo' \
      --exclude '.DS_Store' \
      "$src_dir/" "$target_dir_v2/"
    rsync -a --delete --delete-excluded --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r \
      --exclude '__pycache__' \
      --exclude '*.pyc' \
      --exclude '*.pyo' \
      --exclude '.DS_Store' \
      "$src_dir/" "$target_dir_v1/"
  else
    find "$target_dir_v2" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
    find "$target_dir_v1" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
    cp -R "$src_dir/." "$target_dir_v2/"
    cp -R "$src_dir/." "$target_dir_v1/"
    find "$target_dir_v2" "$target_dir_v1" -name '__pycache__' -type d -prune -exec rm -rf {} +
    find "$target_dir_v2" "$target_dir_v1" \( -name '*.pyc' -o -name '*.pyo' -o -name '.DS_Store' \) -delete
  fi
  find "$target_dir_v2" "$target_dir_v1" -type d -exec chmod 755 {} +
  find "$target_dir_v2" "$target_dir_v1" -type f -exec chmod 644 {} +

  echo "$target_dir_v2"
  echo "$target_dir_v1"
}

echo "已同步官方插件仓库目录："
ROOT_DIR="$ROOT_DIR" python3 - <<'PY' | while IFS=$'\t' read -r src_dir target_name; do
import json
import os
from pathlib import Path

root_dir = Path(os.environ["ROOT_DIR"])
package = json.loads((root_dir / "package.json").read_text(encoding="utf-8"))
for plugin_id in package:
    if (root_dir / plugin_id / "__init__.py").exists():
        print(f"{plugin_id}\t{plugin_id.lower()}")
PY
  sync_plugin "$ROOT_DIR/$src_dir" "$target_name"
done
