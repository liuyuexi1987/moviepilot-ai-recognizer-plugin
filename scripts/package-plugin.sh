#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
PLUGIN_NAME="${1:-AIRecoginzerForwarder}"
PLUGIN_DIR="$ROOT_DIR/$PLUGIN_NAME"

if [ -x "$ROOT_DIR/scripts/sync-repo-layout.sh" ]; then
  "$ROOT_DIR/scripts/sync-repo-layout.sh" >/dev/null
fi

if [ ! -d "$PLUGIN_DIR" ]; then
  echo "插件目录不存在: $PLUGIN_DIR" >&2
  exit 1
fi

if ! command -v zip >/dev/null 2>&1; then
  echo "未找到 zip 命令，请先安装 zip。" >&2
  exit 1
fi

VERSION="$(PLUGIN_NAME="$PLUGIN_NAME" python3 - <<'PY'
from pathlib import Path
import re
import os
plugin_name = os.environ["PLUGIN_NAME"]
text = Path(plugin_name, "__init__.py").read_text(encoding="utf-8")
match = re.search(r'plugin_version\s*=\s*"([^"]+)"', text)
print(match.group(1) if match else "unknown")
PY
)"

mkdir -p "$DIST_DIR"

ZIP_NAME="${PLUGIN_NAME}-${VERSION}.zip"
ZIP_PATH="$DIST_DIR/$ZIP_NAME"

rm -f "$ZIP_PATH"

cd "$ROOT_DIR"
PLUGIN_NAME="$PLUGIN_NAME" zip -r "$ZIP_PATH" "$PLUGIN_NAME" \
  -x "*/__pycache__/*" \
  -x "*.pyc" \
  -x "*.pyo" \
  -x "*.DS_Store" >/dev/null

echo "已生成插件安装包:"
echo "$ZIP_PATH"
