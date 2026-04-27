#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

skill_install_dry_run() {
  local skill_name="$1"
  bash "skills/${skill_name}/install.sh" --dry-run --target "$ROOT_DIR/.tmp-skill-install-check/${skill_name}" >/dev/null
  echo "${skill_name}_install_dry_run_ok"
}

for required in \
  skills/agent-resource-officer/SKILL.md \
  skills/agent-resource-officer/README.md \
  skills/agent-resource-officer/CHANGELOG.md \
  skills/agent-resource-officer/install.sh \
  skills/hdhive-search-unlock-to-115/SKILL.md \
  skills/hdhive-search-unlock-to-115/README.md \
  skills/hdhive-search-unlock-to-115/CHANGELOG.md \
  skills/hdhive-search-unlock-to-115/install.sh
do
  if [[ ! -f "$required" ]]; then
    echo "Skill 文件缺失: $required" >&2
    exit 1
  fi
done

python3 skills/agent-resource-officer/scripts/aro_request.py selftest >/dev/null
echo "agent_resource_officer_skill_selftest_ok"
skill_install_dry_run "agent-resource-officer"

python3 skills/hdhive-search-unlock-to-115/scripts/hdhive_agent_tool.py selftest >/dev/null
echo "hdhive_skill_selftest_ok"
skill_install_dry_run "hdhive-search-unlock-to-115"

python3 - <<'PY'
import ast
import subprocess
from pathlib import Path

skills = [
    (
        "AgentResourceOfficer",
        Path("skills/agent-resource-officer/scripts/aro_request.py"),
        Path("skills/agent-resource-officer/README.md"),
        Path("skills/agent-resource-officer/CHANGELOG.md"),
        ["python3", "skills/agent-resource-officer/scripts/aro_request.py", "version"],
        "agent_resource_officer_helper_version_ok",
    ),
    (
        "hdhive-search-unlock-to-115",
        Path("skills/hdhive-search-unlock-to-115/scripts/hdhive_agent_tool.py"),
        Path("skills/hdhive-search-unlock-to-115/README.md"),
        Path("skills/hdhive-search-unlock-to-115/CHANGELOG.md"),
        ["python3", "skills/hdhive-search-unlock-to-115/scripts/hdhive_agent_tool.py", "version"],
        "hdhive_skill_helper_version_ok",
    ),
]


def read_helper_version(helper_file: Path) -> str:
    tree = ast.parse(helper_file.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "HELPER_VERSION" and isinstance(node.value, ast.Constant):
                return str(node.value.value)
    return ""


for display_name, helper_file, readme_file, changelog_file, version_command, ok_label in skills:
    helper_version = read_helper_version(helper_file)
    if not helper_version:
        print(f"{display_name} helper 版本未找到")
        raise SystemExit(1)
    readme = readme_file.read_text(encoding="utf-8")
    changelog = changelog_file.read_text(encoding="utf-8")
    if f"当前 helper 版本：`{helper_version}`" not in readme:
        print(f"{display_name} README helper 版本未同步")
        raise SystemExit(1)
    if f"## {helper_version}" not in changelog:
        print(f"{display_name} CHANGELOG 缺少当前 helper 版本")
        raise SystemExit(1)
    subprocess.run(version_command, check=True, stdout=subprocess.DEVNULL)
    print(f"{ok_label} {helper_version}")
PY

echo "skills_check_ok"
