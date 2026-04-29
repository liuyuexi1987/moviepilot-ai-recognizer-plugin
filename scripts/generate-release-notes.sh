#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

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
echo "- agent-resource-officer Skill 已内置 external-agent / external-agent --full，可直接生成外部智能体提示词和最小工具约定。"
echo "- live smoke 已覆盖 external-agent request templates、MP搜索、盘搜、影巢别名和 115状态。"
echo "- 内置飞书入口默认关闭；新用户可优先使用资源官内置飞书，旧 FeishuCommandBridgeLong 保留为兼容/备份插件。"
echo "- 115 直转层支持扫码会话；STRM 生成、302、全量/增量同步仍建议继续交给 P115StrmHelper。"
echo "- 附件已包含插件/Skill manifest 与 SHA256 校验文件，下载后可用 verify-release-download 校验。"
echo
bash scripts/print-release-summary.sh
echo
echo "## 公开 Skill 模板"
echo
bash scripts/print-skill-release-summary.sh
