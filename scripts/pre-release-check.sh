#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PACKAGE_PLUGINS=(
  AIRecoginzerForwarder
  AIRecognizerEnhancer
  AgentResourceOfficer
  FeishuCommandBridgeLong
  QuarkShareSaver
)

release_git_status() {
  git status --short -- . ':(exclude)SESSION_HANDOFF_*.md'
}

echo "[1/6] 同步官方仓库布局..."
bash scripts/sync-repo-layout.sh >/dev/null

echo "[2/6] 检查 Git 工作区是否干净..."
if [ -n "$(release_git_status)" ]; then
  echo "Git 工作区不干净，请先提交或处理变更；如果只有同步结果，请提交同步后的文件。" >&2
  release_git_status
  exit 1
fi

echo "[3/6] 检查插件语法..."
python3 - <<'PY'
from pathlib import Path

roots = [
    Path("AIRecoginzerForwarder"),
    Path("AIRecognizerEnhancer"),
    Path("AgentResourceOfficer"),
    Path("FeishuCommandBridgeLong"),
    Path("QuarkShareSaver"),
    Path("plugins"),
    Path("plugins.v2"),
]
failed = []
count = 0
for root in roots:
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        count += 1
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as exc:
            failed.append(f"{path}: {exc}")
if failed:
    print("\n".join(failed))
    raise SystemExit(1)
print(f"syntax_ok files={count}")
PY

echo "[4/6] 检查 package.json 与运行代码元数据..."
python3 - <<'PY'
import ast
import json
from pathlib import Path

pkg = json.loads(Path("package.json").read_text(encoding="utf-8"))
failed = []
for plugin_id, meta in pkg.items():
    candidates = [
        Path(plugin_id) / "__init__.py",
        Path("plugins") / plugin_id.lower() / "__init__.py",
        Path("plugins.v2") / plugin_id.lower() / "__init__.py",
    ]
    found = [item for item in candidates if item.exists()]
    if not found:
        continue
    for init_file in found:
        tree = ast.parse(init_file.read_text(encoding="utf-8"))
        values = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Name) or not isinstance(node.value, ast.Constant):
                    continue
                if target.id in {"plugin_version", "plugin_author", "plugin_icon"}:
                    values[target.id] = str(node.value.value)
        icon = values.get("plugin_icon", "")
        expected_icon = str(meta.get("icon") or "")
        icon_ok = (not icon) or icon == expected_icon or icon.endswith("/" + expected_icon)
        meta_ok = values.get("plugin_version") == meta.get("version") and values.get("plugin_author") == meta.get("author")
        if not (icon_ok and meta_ok):
            failed.append((plugin_id, str(init_file), values))
if failed:
    for item in failed:
        print(item)
    raise SystemExit(1)
PY

echo "[5/6] 打包本地安装 ZIP..."
for plugin_name in "${PACKAGE_PLUGINS[@]}"; do
  bash scripts/package-plugin.sh "$plugin_name" >/dev/null
done

echo "[6/6] 检查关键文件..."
test -f package.v2.json
test -f package.json
test -f plugins/airecoginzerforwarder/__init__.py
test -f plugins/airecoginzerforwarder/requirements.txt
test -f plugins.v2/airecoginzerforwarder/__init__.py
test -f plugins/agentresourceofficer/__init__.py
test -f plugins/agentresourceofficer/agenttool.py
test -f plugins/agentresourceofficer/schemas.py
test -f plugins/agentresourceofficer/services/p115_transfer.py
test -f plugins/airecognizerenhancer/__init__.py
test -f plugins/quarksharesaver/__init__.py
test -f AIRecoginzerForwarder/README.md
test -f AIRecoginzerForwarder/requirements.txt
for plugin_name in "${PACKAGE_PLUGINS[@]}"; do
  version="$(PLUGIN_NAME="$plugin_name" python3 - <<'PY'
from pathlib import Path
import os
import re

plugin_name = os.environ["PLUGIN_NAME"]
text = Path(plugin_name, "__init__.py").read_text(encoding="utf-8")
match = re.search(r'plugin_version\s*=\s*"([^"]+)"', text)
print(match.group(1) if match else "unknown")
PY
)"
  test -f "dist/${plugin_name}-${version}.zip"
done

echo
echo "插件仓库发布前检查通过。"
echo "ZIP 包目录：$ROOT_DIR/dist"
