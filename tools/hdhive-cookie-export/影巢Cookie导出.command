#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python"
SCRIPT_PATH="${SCRIPT_DIR}/export_yc_cookie.py"

echo "=============================="
echo "影巢 Cookie 快速导出"
echo "=============================="
echo
echo "先确保你已经在 Edge 里登录影巢，并打开过 https://hdhive.com 。"
echo

if [[ ! -x "${PYTHON_BIN}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "未找到可用的 python3，请先安装 Python。"
    echo
    read "DUMMY?按回车关闭..."
    exit 1
  fi
fi

if [[ ! -f "${SCRIPT_PATH}" ]]; then
  echo "未找到导出脚本：${SCRIPT_PATH}"
  echo
  read "DUMMY?按回车关闭..."
  exit 1
fi

SITE="https://hdhive.com"
BROWSER="edge"
RUN_ARGS=(
  "${SITE}"
  --browser "${BROWSER}"
  --write-mp
  --mp-db /Applications/Dockge/moviepilotv2/config/user.db
  --mp-plugin-key plugin.HdhiveSign
  --restart-container moviepilot-v2
  --hdhive-json /Applications/Dockge/moviepilotv2/config/plugins/hdhivedailysign.json
)
SUCCESS_HINT="导出完成，Cookie 已写回 MoviePilot / HDHiveDailySign，并已重启 moviepilot-v2。"
SUCCESS_HINT_2="后面你不用再手动复制或粘贴 Cookie。"

echo
echo "将使用固定配置自动执行："
echo "- 站点：${SITE}"
echo "- 浏览器：${BROWSER}"
echo "- 模式：写回 MoviePilot + 同步 HDHiveDailySign + 重启容器"
echo
echo "正在执行..."
echo

if ! "${PYTHON_BIN}" "${SCRIPT_PATH}" "${RUN_ARGS[@]}"; then
  echo
  echo "执行失败。"
  echo "请确认 Edge 里已经登录影巢，并且已经打开过 ${SITE} 。"
  echo
  read "DUMMY?按回车关闭..."
  exit 1
fi

echo
echo "${SUCCESS_HINT}"
echo "${SUCCESS_HINT_2}"
echo
read "DUMMY?按回车关闭..."
