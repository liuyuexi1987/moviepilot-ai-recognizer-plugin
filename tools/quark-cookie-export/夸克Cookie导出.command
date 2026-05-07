#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "未找到可用的 python3，请先安装 Python。"
    read -r -p "按回车键退出..."
    exit 1
  fi
fi

cd "$SCRIPT_DIR"
"$PYTHON_BIN" export_quark_cookie.py https://pan.quark.cn --browser edge --write-mp --restart-container moviepilot-v2

echo
echo "导出完成，夸克 Cookie 已写回 MoviePilot，并已重启 moviepilot-v2。"
echo "后面你不用再手动复制或粘贴 Cookie。"
read -r -p "按回车键退出..."
