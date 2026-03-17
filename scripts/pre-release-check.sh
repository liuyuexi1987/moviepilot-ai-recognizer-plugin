#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/5] 检查 Git 工作区是否干净..."
if [ -n "$(git status --short)" ]; then
  echo "Git 工作区不干净，请先提交或处理变更。" >&2
  git status --short
  exit 1
fi

echo "[2/5] 检查插件语法..."
python3 -m py_compile AIRecoginzerForwarder/__init__.py
python3 -m py_compile plugins.v2/airecoginzerforwarder/__init__.py

echo "[3/5] 同步官方仓库布局..."
bash scripts/sync-repo-layout.sh >/dev/null

echo "[4/5] 打包本地安装 ZIP..."
bash scripts/package-plugin.sh >/dev/null

VERSION="$(python3 - <<'PY'
from pathlib import Path
import re
text = Path("AIRecoginzerForwarder/__init__.py").read_text(encoding="utf-8")
match = re.search(r'plugin_version\s*=\s*"([^"]+)"', text)
print(match.group(1) if match else "unknown")
PY
)"

ZIP_PATH="dist/AIRecoginzerForwarder-${VERSION}.zip"

echo "[5/5] 检查关键文件..."
test -f package.v2.json
test -f plugins.v2/airecoginzerforwarder/__init__.py
test -f AIRecoginzerForwarder/README.md
test -f AIRecoginzerForwarder/requirements.txt
test -f "$ZIP_PATH"

echo
echo "插件仓库发布前检查通过。"
echo "ZIP 包：$ROOT_DIR/$ZIP_PATH"
