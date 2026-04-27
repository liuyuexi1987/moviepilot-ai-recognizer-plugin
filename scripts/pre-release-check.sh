#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PACKAGE_PLUGINS=(
  AIRecoginzerForwarder
  AIRecognizerEnhancer
  AgentResourceOfficer
  FeishuCommandBridgeLong
  HdhiveOpenApi
  HDHiveDailySign
  QuarkShareSaver
  ZspaceMediaFreshMix
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
    Path("skills"),
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
python3 skills/agent-resource-officer/scripts/aro_request.py selftest >/dev/null
echo "agent_resource_officer_skill_selftest_ok"
bash skills/agent-resource-officer/install.sh --dry-run --target "$ROOT_DIR/.tmp-skill-install-check/agent-resource-officer" >/dev/null
echo "agent_resource_officer_skill_install_dry_run_ok"
python3 skills/hdhive-search-unlock-to-115/scripts/hdhive_agent_tool.py selftest >/dev/null
echo "hdhive_skill_selftest_ok"

echo "[4/6] 检查 package.json 与运行代码元数据..."
PACKAGE_PLUGIN_LIST="${PACKAGE_PLUGINS[*]}" python3 - <<'PY'
import ast
import json
import os
from pathlib import Path

pkg = json.loads(Path("package.json").read_text(encoding="utf-8"))
pkg_v2 = json.loads(Path("package.v2.json").read_text(encoding="utf-8"))
package_plugins = set(pkg)
release_plugins = set(os.environ["PACKAGE_PLUGIN_LIST"].split())
if package_plugins != release_plugins:
    missing = sorted(package_plugins - release_plugins)
    extra = sorted(release_plugins - package_plugins)
    if missing:
        print("pre-release-check 未覆盖 package.json 插件:", ", ".join(missing))
    if extra:
        print("pre-release-check 包含 package.json 之外的插件:", ", ".join(extra))
    raise SystemExit(1)
normalized_pkg_v2 = {
    plugin_id: {key: value for key, value in meta.items() if key != "v2"}
    for plugin_id, meta in pkg.items()
}
if normalized_pkg_v2 != pkg_v2:
    print("package.v2.json 与 package.json 去除 v2 字段后的内容不一致")
    raise SystemExit(1)

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
import json
import os

plugin_name = os.environ["PLUGIN_NAME"]
with open("package.json", "r", encoding="utf-8") as file_obj:
    package = json.load(file_obj)
print((package.get(plugin_name) or {}).get("version") or "unknown")
PY
  )"
  zip_path="dist/${plugin_name}-${version}.zip"
  test -f "$zip_path"
  PLUGIN_NAME="$plugin_name" ZIP_PATH="$zip_path" python3 - <<'PY'
import os
import zipfile

plugin_name = os.environ["PLUGIN_NAME"]
zip_path = os.environ["ZIP_PATH"]
required_readme = f"{plugin_name}/README.md"
required_init = f"{plugin_name}/__init__.py"
bad_entries = []
with zipfile.ZipFile(zip_path) as zip_file:
    names = set(zip_file.namelist())
    for name in names:
        if "__pycache__" in name or name.endswith((".pyc", ".pyo", ".DS_Store")):
            bad_entries.append(name)
if required_readme not in names:
    print(f"{zip_path} 缺少 {required_readme}")
    raise SystemExit(1)
if required_init not in names:
    print(f"{zip_path} 缺少 {required_init}")
    raise SystemExit(1)
if bad_entries:
    print(f"{zip_path} 包含不应发布的生成文件:")
    print("\n".join(sorted(bad_entries)))
    raise SystemExit(1)
PY
done

echo
echo "插件仓库发布前检查通过。"
echo "ZIP 包目录：$ROOT_DIR/dist"
