# hdhive-search-unlock-to-115

这是放在仓库里的公开版 Skill 模板，目标是让别人可以快速复制到自己的 Codex 环境使用。

这份仓库副本已经做过去隐私处理：

- 不包含你的本机绝对路径
- 不包含 API Key、Token、Cookie
- 不绑定你的 Docker 目录结构

## 使用方式

1. 把整个目录复制到自己的 `~/.codex/skills/hdhive-search-unlock-to-115`
2. 根据自己的环境设置：
   - `MP_APP_ENV`
   - `MP_BASE_URL`
   - `TMDB_API_KEY`
3. 再让智能体使用这个 Skill

## 备注

- 这是“公开模板”，不是你本机运行中的原样副本
- 仓库里保留的是解决思路和可复用脚本，不保留个人环境细节
- 如果用户环境路径不同，优先通过环境变量或命令行参数覆盖
