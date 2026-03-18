#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="$ROOT_DIR/AIRecoginzerForwarder"
TARGET_DIR_V2="$ROOT_DIR/plugins.v2/airecoginzerforwarder"
TARGET_DIR_V1="$ROOT_DIR/plugins/airecoginzerforwarder"

mkdir -p "$TARGET_DIR_V2" "$TARGET_DIR_V1"

cp "$SRC_DIR/__init__.py" "$TARGET_DIR_V2/__init__.py"
cp "$SRC_DIR/__init__.py" "$TARGET_DIR_V1/__init__.py"
cp "$SRC_DIR/requirements.txt" "$TARGET_DIR_V1/requirements.txt"

echo "已同步官方插件仓库目录："
echo "$TARGET_DIR_V2/__init__.py"
echo "$TARGET_DIR_V1/__init__.py"
echo "$TARGET_DIR_V1/requirements.txt"
