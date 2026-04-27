#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"

if [[ "${1:-}" == "--list" ]]; then
  ROOT_DIR="$ROOT_DIR" python3 - <<'PY'
import json
import os
from pathlib import Path

package_file = Path(os.environ["ROOT_DIR"]) / "package.json"
package = json.loads(package_file.read_text(encoding="utf-8"))
for plugin_id, meta in package.items():
    print(f"{plugin_id}\t{meta.get('version', 'unknown')}")
PY
  exit 0
fi

REQUESTED_PLUGIN_NAME="${1:-AIRecoginzerForwarder}"
PLUGIN_NAME="$(REQUESTED_PLUGIN_NAME="$REQUESTED_PLUGIN_NAME" ROOT_DIR="$ROOT_DIR" python3 - <<'PY'
import json
import os
from pathlib import Path

requested = os.environ["REQUESTED_PLUGIN_NAME"]
package_file = Path(os.environ["ROOT_DIR"]) / "package.json"
if package_file.exists():
    package = json.loads(package_file.read_text(encoding="utf-8"))
    for plugin_id in package:
        if plugin_id.lower() == requested.lower():
            print(plugin_id)
            break
    else:
        print(requested)
else:
    print(requested)
PY
)"
PLUGIN_DIR="$ROOT_DIR/$PLUGIN_NAME"
PLUGIN_KEY="$(printf '%s' "$PLUGIN_NAME" | tr '[:upper:]' '[:lower:]')"
PLUGIN_DOC_DIR="$ROOT_DIR/$PLUGIN_NAME"

if [ -x "$ROOT_DIR/scripts/sync-repo-layout.sh" ]; then
  "$ROOT_DIR/scripts/sync-repo-layout.sh" >/dev/null
fi

if [ ! -f "$PLUGIN_DIR/__init__.py" ]; then
  if [ -f "$ROOT_DIR/plugins/$PLUGIN_KEY/__init__.py" ]; then
    PLUGIN_DIR="$ROOT_DIR/plugins/$PLUGIN_KEY"
  elif [ -f "$ROOT_DIR/plugins.v2/$PLUGIN_KEY/__init__.py" ]; then
    PLUGIN_DIR="$ROOT_DIR/plugins.v2/$PLUGIN_KEY"
  fi
fi

if [ ! -f "$PLUGIN_DIR/__init__.py" ]; then
  echo "插件源码目录不存在或缺少 __init__.py: $PLUGIN_NAME" >&2
  exit 1
fi

if ! command -v zip >/dev/null 2>&1; then
  echo "未找到 zip 命令，请先安装 zip。" >&2
  exit 1
fi

VERSION="$(PLUGIN_DIR="$PLUGIN_DIR" python3 - <<'PY'
from pathlib import Path
import re
import os
plugin_dir = Path(os.environ["PLUGIN_DIR"])
text = (plugin_dir / "__init__.py").read_text(encoding="utf-8")
match = re.search(r'plugin_version\s*=\s*"([^"]+)"', text)
print(match.group(1) if match else "unknown")
PY
)"

mkdir -p "$DIST_DIR"

ZIP_NAME="${PLUGIN_NAME}-${VERSION}.zip"
ZIP_PATH="$DIST_DIR/$ZIP_NAME"

rm -f "$ZIP_PATH"

STAGE_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$STAGE_DIR"
}
trap cleanup EXIT

STAGE_PLUGIN_DIR="$STAGE_DIR/$PLUGIN_NAME"
mkdir -p "$STAGE_PLUGIN_DIR"
if command -v rsync >/dev/null 2>&1; then
  rsync -a \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '*.pyo' \
    --exclude '.DS_Store' \
    "$PLUGIN_DIR/" "$STAGE_PLUGIN_DIR/"
else
  cp -R "$PLUGIN_DIR/." "$STAGE_PLUGIN_DIR/"
  find "$STAGE_PLUGIN_DIR" -name '__pycache__' -type d -prune -exec rm -rf {} +
  find "$STAGE_PLUGIN_DIR" \( -name '*.pyc' -o -name '*.pyo' -o -name '.DS_Store' \) -delete
fi

if [ ! -f "$STAGE_PLUGIN_DIR/README.md" ] && [ -f "$PLUGIN_DOC_DIR/README.md" ]; then
  cp "$PLUGIN_DOC_DIR/README.md" "$STAGE_PLUGIN_DIR/README.md"
fi

cd "$STAGE_DIR"
zip -r "$ZIP_PATH" "$PLUGIN_NAME" \
  -x "*/__pycache__/*" \
  -x "*.pyc" \
  -x "*.pyo" \
  -x "*.DS_Store" >/dev/null

echo "已生成插件安装包:"
echo "$ZIP_PATH"
