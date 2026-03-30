#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

sync_plugin() {
  local src_dir="$1"
  local target_name="$2"

  local target_dir_v2="$ROOT_DIR/plugins.v2/$target_name"
  local target_dir_v1="$ROOT_DIR/plugins/$target_name"

  mkdir -p "$target_dir_v2" "$target_dir_v1"

  cp "$src_dir/__init__.py" "$target_dir_v2/__init__.py"
  cp "$src_dir/__init__.py" "$target_dir_v1/__init__.py"
  if [[ -f "$src_dir/requirements.txt" ]]; then
    cp "$src_dir/requirements.txt" "$target_dir_v1/requirements.txt"
  fi

  echo "$target_dir_v2/__init__.py"
  echo "$target_dir_v1/__init__.py"
  if [[ -f "$src_dir/requirements.txt" ]]; then
    echo "$target_dir_v1/requirements.txt"
  fi
}

echo "已同步官方插件仓库目录："
sync_plugin "$ROOT_DIR/AIRecoginzerForwarder" "airecoginzerforwarder"
sync_plugin "$ROOT_DIR/FeishuCommandBridgeLong" "feishucommandbridgelong"
