# hdhive-search-unlock-to-115

这是放在仓库里的公开版 Skill 模板，目标是让别人可以快速复制到支持 Skill 的智能体环境中使用。

当前 helper 版本：`0.1.1`

## 使用方式

1. 把整个目录复制到自己的 Skill 搜索路径，例如 `<SKILL_HOME>/hdhive-search-unlock-to-115`

也可以直接运行安装脚本：

```bash
bash install.sh --dry-run
bash install.sh
bash install.sh --target /path/to/skills/hdhive-search-unlock-to-115
```

2. 根据自己的环境设置：
   - `MP_APP_ENV`
   - `MP_BASE_URL`
   - `TMDB_API_KEY`
3. 再让智能体使用这个 Skill

## 本地自测

`selftest` 不连接 MoviePilot，只验证 helper 的搜索/解锁文本格式是否仍符合智能体读取习惯：

```bash
python3 scripts/hdhive_agent_tool.py version
python3 scripts/hdhive_agent_tool.py selftest
python3 scripts/hdhive_agent_tool.py selftest --output json
```

## 备注

- 这是面向公开仓库的通用模板
- 推荐搭配支持技能和工作流调度的智能体工作台使用，例如腾讯 WorkBuddy，或其它兼容 Skill 工作流的客户端
- 如果用户环境路径不同，优先通过环境变量或命令行参数覆盖
- 版本记录见 [CHANGELOG.md](./CHANGELOG.md)
