#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PLUGIN_VERSION="$(python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path('package.json').read_text())
print(((data.get('AgentResourceOfficer') or {}).get('version')) or '')
PY
)"

PLUGIN_HIGHLIGHT="$(python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path('package.json').read_text())
plugin = data.get('AgentResourceOfficer') or {}
version = plugin.get('version', '')
history = plugin.get('history') or {}
print((history.get(version) or '').strip())
PY
)"

HELPER_VERSION="$(python3 - <<'PY'
import re
from pathlib import Path
text = Path('skills/agent-resource-officer/scripts/aro_request.py').read_text()
match = re.search(r'HELPER_VERSION = "([^"]+)"', text)
print(match.group(1) if match else '')
PY
)"

HELPER_HIGHLIGHT="$(python3 - <<'PY'
import re
from pathlib import Path

helper_text = Path('skills/agent-resource-officer/scripts/aro_request.py').read_text()
match = re.search(r'HELPER_VERSION = "([^"]+)"', helper_text)
version = match.group(1) if match else ''
lines = Path('skills/agent-resource-officer/CHANGELOG.md').read_text().splitlines()
target = None
for i, line in enumerate(lines):
    if line.strip() == f'## {version}':
        target = i
        break
if target is None:
    print('')
else:
    bullets = []
    for line in lines[target + 1:]:
        if line.startswith('## '):
            break
        if line.startswith('- '):
            bullets.append(line[2:].strip())
    print('；'.join(bullets[:2]))
PY
)"

show_help() {
  cat <<'EOF'
Usage:
  bash scripts/generate-release-notes.sh <tag>

Prints the unified GitHub Release notes body for the given tag.
Requires dist/ and dist/skills/ manifests to exist.
EOF
}

TAG="${1:-}"
if [[ "$TAG" == "--help" || "$TAG" == "-h" ]]; then
  show_help
  exit 0
fi
if [[ -z "$TAG" || "$#" -ne 1 ]]; then
  echo "缺少 release tag。" >&2
  show_help >&2
  exit 2
fi

echo "# $TAG"
echo
echo "本次 Release 附件包含 MoviePilot 本地安装 ZIP、公开 Skill ZIP、PLUGIN/SKILL SHA256SUMS 和 MANIFEST。"
echo
echo "## 本次重点"
echo
echo "- AgentResourceOfficer 是推荐主入口，统一承接影巢、盘搜、115、夸克、飞书 Channel 和智能体 Tool。"
if [[ -n "$PLUGIN_VERSION" && -n "$PLUGIN_HIGHLIGHT" ]]; then
  echo "- Agent影视助手 ${PLUGIN_VERSION}：${PLUGIN_HIGHLIGHT}"
fi
echo "- agent-resource-officer Skill 已内置 external-agent / external-agent --full，可直接生成外部智能体提示词和最小工具约定。"
if [[ -n "$HELPER_VERSION" && -n "$HELPER_HIGHLIGHT" ]]; then
  echo "- agent-resource-officer helper ${HELPER_VERSION}：${HELPER_HIGHLIGHT}"
fi
echo "- live smoke 已覆盖 external-agent request templates、MP搜索、盘搜、影巢别名和 115状态。"
echo "- 内置飞书入口默认关闭；新用户可优先使用本插件内置飞书，旧 FeishuCommandBridgeLong 保留为兼容/备份插件。"
echo "- 115 直转层支持扫码会话；STRM 生成、302、全量/增量同步仍建议继续交给 P115StrmHelper。"
echo "- 附件已包含插件/Skill manifest 与 SHA256 校验文件，下载后可用 verify-release-download 校验。"
echo
bash scripts/print-release-summary.sh
echo
echo "## 公开 Skill 模板"
echo
bash scripts/print-skill-release-summary.sh
