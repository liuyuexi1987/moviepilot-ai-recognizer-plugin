#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="$ROOT_DIR/AIRecoginzerForwarder"
TARGET_DIR="$ROOT_DIR/plugins.v2/airecoginzerforwarder"

mkdir -p "$TARGET_DIR"

cp "$SRC_DIR/__init__.py" "$TARGET_DIR/__init__.py"

echo "已同步官方插件仓库目录："
echo "$TARGET_DIR/__init__.py"
