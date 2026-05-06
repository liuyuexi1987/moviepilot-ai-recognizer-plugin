#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

show_help() {
  cat <<'EOF'
Usage:
  bash scripts/pre-release-check.sh

Runs the low-level repository release checks:
- sync repo layout
- ensure clean worktree
- shell/Python syntax
- skill selftests
- metadata/doc drift checks
- package build and manifest verification

Set RUN_AGENT_RESOURCE_OFFICER_LIVE_SMOKE=1 to include live smoke.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  show_help
  exit 0
fi
export PYTHONDONTWRITEBYTECODE=1
mkdir -p .tmp
LOCK_DIR="$ROOT_DIR/.tmp/pre-release-check.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "pre-release-check 已在运行，请等待当前检查结束后重试。" >&2
  exit 1
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

PACKAGE_PLUGINS=(
  AIRecognizerEnhancer
  AgentResourceOfficer
  FeishuCommandBridgeLong
  HdhiveOpenApi
  QuarkShareSaver
)

release_git_status() {
  git status --short -- . ':(exclude)SESSION_HANDOFF_*.md'
}

echo "[1/6] 同步官方仓库布局..."
bash scripts/sync-repo-layout.sh >/dev/null
bash scripts/sync-package-v2.sh >/dev/null

echo "[2/6] 检查 Git 工作区是否干净..."
if [ -n "$(release_git_status)" ]; then
  echo "Git 工作区不干净，请先提交或处理变更；如果只有同步结果，请提交同步后的文件。" >&2
  release_git_status
  exit 1
fi

echo "[3/6] 检查插件语法..."
while IFS= read -r shell_file; do
  bash -n "$shell_file"
done < <(find scripts skills -name '*.sh' -type f | sort)
echo "shell_syntax_ok"
python3 scripts/check-maintenance-commands.py >/dev/null
echo "script_help_ok"
grep -Fq 'WORKFLOW_NAME="${WORKFLOW_NAME:-Release Preflight}"' scripts/verify-release-preflight-artifact.sh
grep -Fq 'WORKFLOW_FILE="${WORKFLOW_FILE:-ci.yml}"' scripts/verify-release-preflight-artifact.sh
grep -Fq 'exec bash scripts/verify-release-preflight-artifact.sh "$@"' scripts/verify-ci-artifact.sh
grep -Fq 'bash scripts/release-preflight.sh' scripts/create-draft-release.sh
grep -Fq 'bash scripts/release-preflight.sh' scripts/update-draft-release-assets.sh
echo "release_script_entrypoints_ok"
python3 - <<'PY'
from pathlib import Path

roots = [
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
bash scripts/check-skills.sh
python3 scripts/check-agent-resource-officer-feishu.py
if [[ "${RUN_AGENT_RESOURCE_OFFICER_LIVE_SMOKE:-0}" == "1" ]]; then
  echo "[3.1] 执行 AgentResourceOfficer 本机 live smoke..."
  python3 scripts/smoke-agent-resource-officer.py --include-search
fi

echo "[4/6] 检查 package.json 与运行代码元数据..."
PACKAGE_PLUGIN_LIST="${PACKAGE_PLUGINS[*]}" python3 - <<'PY'
import ast
import json
import os
import re
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
    missing_fields = [
        key
        for key in ("name", "description", "version", "author", "icon", "labels", "level", "history")
        if not str(meta.get(key) or "").strip()
    ]
    if missing_fields:
        failed.append((plugin_id, "package.json", {"missing_fields": ",".join(missing_fields)}))
        continue
    if not isinstance(meta.get("version"), str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-.][0-9A-Za-z.]+)?", meta.get("version", "")):
        failed.append((plugin_id, "package.json", {"invalid_version": meta.get("version")}))
        continue
    if not isinstance(meta.get("labels"), str):
        failed.append((plugin_id, "package.json", {"invalid_labels_type": type(meta.get("labels")).__name__}))
        continue
    if not isinstance(meta.get("level"), int) or meta.get("level") < 1:
        failed.append((plugin_id, "package.json", {"invalid_level": meta.get("level")}))
        continue
    if not isinstance(meta.get("history"), dict) or not meta.get("history"):
        failed.append((plugin_id, "package.json", {"invalid_history": type(meta.get("history")).__name__}))
        continue
    bad_history = [
        key for key, value in meta.get("history", {}).items()
        if not isinstance(key, str) or not key.strip() or not isinstance(value, str) or not value.strip()
    ]
    if bad_history:
        failed.append((plugin_id, "package.json", {"invalid_history_items": ",".join(map(str, bad_history))}))
        continue
    if meta.get("v2") is not True:
        failed.append((plugin_id, "package.json", {"invalid_v2": meta.get("v2")}))
        continue
    history = meta.get("history") if isinstance(meta.get("history"), dict) else {}
    if str(meta.get("version")) not in history:
        failed.append((plugin_id, "package.json", {"missing_history_for_version": meta.get("version")}))
        continue
    icon_file = Path("icons") / str(meta.get("icon"))
    if not icon_file.exists():
        failed.append((plugin_id, "package.json", {"missing_icon": str(icon_file)}))
        continue
    candidates = [
        Path(plugin_id) / "__init__.py",
        Path("plugins") / plugin_id.lower() / "__init__.py",
        Path("plugins.v2") / plugin_id.lower() / "__init__.py",
    ]
    found = [item for item in candidates if item.exists()]
    if not found:
        failed.append((plugin_id, "source", {"missing_init": "no __init__.py found in root/plugins/plugins.v2"}))
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

install_doc = Path("docs/PLUGIN_INSTALL.md").read_text(encoding="utf-8")
missing_zip_names = [
    f"{plugin_id}-{meta.get('version')}.zip"
    for plugin_id, meta in pkg.items()
    if f"{plugin_id}-{meta.get('version')}.zip" not in install_doc
]
if missing_zip_names:
    print("docs/PLUGIN_INSTALL.md 缺少当前 ZIP 文件名:")
    print("\n".join(missing_zip_names))
    raise SystemExit(1)

root_readme = Path("README.md").read_text(encoding="utf-8")
missing_readme_items = []
for plugin_id, meta in pkg.items():
    for item in (plugin_id, str(meta.get("name") or ""), str(meta.get("version") or "")):
        if item and item not in root_readme:
            missing_readme_items.append(f"{plugin_id}: README.md missing {item}")
if missing_readme_items:
    print("README.md 插件清单与 package.json 不一致:")
    print("\n".join(missing_readme_items))
    raise SystemExit(1)

changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
missing_changelog_items = []
for plugin_id, meta in pkg.items():
    current_version_line = f"- `{plugin_id}`: `{meta.get('version')}`"
    if current_version_line not in changelog:
        missing_changelog_items.append(f"{plugin_id}: CHANGELOG.md missing {current_version_line}")
if missing_changelog_items:
    print("CHANGELOG.md 当前核心版本与 package.json 不一致:")
    print("\n".join(missing_changelog_items))
    raise SystemExit(1)

ci_workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
required_ci_fragments = [
    "name: Release Preflight",
    "actions/upload-artifact@v7",
    "fetch-depth: 0",
    "scripts/release-preflight.sh",
    "moviepilot-release-assets-",
    "dist/*.zip",
    "dist/SHA256SUMS.txt",
    "dist/MANIFEST.json",
    "dist/skills/*.zip",
    "dist/skills/SHA256SUMS.txt",
    "dist/skills/MANIFEST.json",
    "if-no-files-found: error",
]
draft_release_workflow = Path(".github/workflows/draft-release.yml").read_text(encoding="utf-8")
required_draft_release_fragments = [
    "workflow_dispatch:",
    "contents: write",
    "fetch-depth: 0",
    "scripts/create-draft-release.sh",
    "dry_run",
]
missing_workflow_fragments = []
for fragment in required_ci_fragments:
    if fragment not in ci_workflow:
        missing_workflow_fragments.append(f"ci.yml: {fragment}")
for fragment in required_draft_release_fragments:
    if fragment not in draft_release_workflow:
        missing_workflow_fragments.append(f"draft-release.yml: {fragment}")
if missing_workflow_fragments:
    print(".github/workflows 缺少发布流程配置:")
    print("\n".join(missing_workflow_fragments))
    raise SystemExit(1)
PY
echo "检查当前状态文档..."
python3 scripts/check-doc-current-state.py

echo "检查 Markdown 本地链接..."
python3 - <<'PY'
import re
import urllib.parse
from pathlib import Path

root = Path(".").resolve()
failed = []

def resolve_with_mirror_fallback(md_file: Path, target: str) -> Path:
    direct = (md_file.parent / target).resolve()
    if direct.exists():
        return direct
    if md_file.parts and md_file.parts[0] in {"plugins", "plugins.v2"}:
        stripped = target
        while stripped.startswith("../"):
            stripped = stripped[3:]
        if stripped:
            fallback = (root / stripped).resolve()
            return fallback
    return direct

for md_file in sorted(Path(".").rglob("*.md")):
    if ".git" in md_file.parts or md_file.name.startswith("SESSION_HANDOFF_"):
        continue
    text = md_file.read_text(encoding="utf-8", errors="ignore")
    for raw_link in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
        link = raw_link.strip()
        if not link or link.startswith(("#", "http://", "https://", "mailto:")):
            continue
        target = link.split("#", 1)[0].strip()
        if not target:
            continue
        target = urllib.parse.unquote(target)
        target_path = resolve_with_mirror_fallback(md_file, target)
        try:
            target_path.relative_to(root)
        except ValueError:
            continue
        if not target_path.exists():
            failed.append(f"{md_file}: missing link target {link}")
if failed:
    print("\n".join(failed))
    raise SystemExit(1)
print("markdown_links_ok")
PY

echo "检查隐私尾巴..."
python3 - <<'PY'
from pathlib import Path

forbidden = [
    "/Users/" + "jans",
    "Qq-" + "342236586",
    "5c0200" + "b446ee9eb94d2912d4c8b7309c",
    "Authorization: Bearer " + "eyJ",
]
failed = []
for path in sorted(Path(".").rglob("*")):
    if not path.is_file():
        continue
    if ".git" in path.parts or "dist" in path.parts or "__pycache__" in path.parts:
        continue
    if path.name.startswith("SESSION_HANDOFF_") or path.suffix in {".pyc", ".pyo"}:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for needle in forbidden:
        if needle in text:
            failed.append(f"{path}: contains forbidden literal {needle!r}")
if failed:
    print("\n".join(failed))
    raise SystemExit(1)
print("privacy_scan_ok")
PY

echo "[5/6] 打包本地安装 ZIP..."
mkdir -p dist
rm -f dist/*.zip dist/SHA256SUMS.txt dist/MANIFEST.json
rm -rf dist/skills
listed_plugins="$(bash scripts/package-plugin.sh --list | awk '{print $1}' | tr '\n' ' ' | sed 's/ $//')"
expected_plugins="${PACKAGE_PLUGINS[*]}"
if [ "$listed_plugins" != "$expected_plugins" ]; then
  echo "package-plugin.sh --list 输出与发布插件清单不一致" >&2
  echo "expected: $expected_plugins" >&2
  echo "actual:   $listed_plugins" >&2
  exit 1
fi
echo "package_plugin_list_ok"
bash scripts/package-plugin.sh --all
bash scripts/package-skills.sh
bash scripts/verify-release-assets.sh dist >/dev/null
bash scripts/print-release-summary.sh >/dev/null
bash scripts/print-skill-release-summary.sh >/dev/null
release_notes="$(bash scripts/generate-release-notes.sh v0.0.0-dry-run)"
if [[ "$release_notes" != *"external-agent / external-agent --full"* ]]; then
  echo "generate-release-notes.sh 缺少 external-agent 重点说明" >&2
  exit 1
fi
bash scripts/create-draft-release.sh v0.0.0-dry-run --dry-run --skip-check >/dev/null

echo "[6/6] 检查关键文件..."
test -f package.v2.json
test -f package.json
test -f dist/SHA256SUMS.txt
test -f dist/MANIFEST.json
test -f dist/skills/SHA256SUMS.txt
test -f dist/skills/MANIFEST.json
test -f scripts/generate-release-notes.sh
test -f plugins/agentresourceofficer/__init__.py
test -f plugins/agentresourceofficer/agenttool.py
test -f plugins/agentresourceofficer/schemas.py
test -f plugins/agentresourceofficer/services/p115_transfer.py
test -f plugins/airecognizerenhancer/__init__.py
test -f plugins/quarksharesaver/__init__.py
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
