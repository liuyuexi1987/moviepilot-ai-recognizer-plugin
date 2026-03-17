#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_DIR="$ROOT_DIR/AIRecoginzerForwarder"
DIST_DIR="$ROOT_DIR/dist"

if [ ! -d "$PLUGIN_DIR" ]; then
  echo "插件目录不存在: $PLUGIN_DIR" >&2
  exit 1
fi

if ! command -v zip >/dev/null 2>&1; then
  echo "未找到 zip 命令，请先安装 zip。" >&2
  exit 1
fi

VERSION="$(python3 - <<'PY'
from pathlib import Path
import re
text = Path("AIRecoginzerForwarder/__init__.py").read_text(encoding="utf-8")
match = re.search(r'plugin_version\s*=\s*"([^"]+)"', text)
print(match.group(1) if match else "unknown")
PY
)"

mkdir -p "$DIST_DIR"

ZIP_NAME="AIRecoginzerForwarder-${VERSION}.zip"
ZIP_PATH="$DIST_DIR/$ZIP_NAME"

rm -f "$ZIP_PATH"

cd "$ROOT_DIR"
zip -r "$ZIP_PATH" "AIRecoginzerForwarder" \
  -x "*/__pycache__/*" \
  -x "*.pyc" \
  -x "*.pyo" \
  -x "*.DS_Store" >/dev/null

echo "已生成插件安装包:"
echo "$ZIP_PATH"
