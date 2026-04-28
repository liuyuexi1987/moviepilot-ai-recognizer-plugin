# agent-resource-officer

公开版 AgentResourceOfficer Skill 模板，用来让外部智能体通过 MoviePilot 插件接口控制资源工作流。

当前 helper 版本：`0.1.7`

## 使用方式

1. 把整个目录复制到自己的 Skill 搜索路径，例如：

```text
~/.codex/skills/agent-resource-officer
```

也可以直接运行安装脚本：

```bash
bash install.sh --dry-run
bash install.sh
bash install.sh --target /path/to/skills/agent-resource-officer
```

2. 配置本机连接信息：

```text
~/.config/agent-resource-officer/config
```

示例：

```text
ARO_BASE_URL=http://127.0.0.1:3000
ARO_API_KEY=your_moviepilot_api_token
```

3. 让外部智能体使用本 Skill。

## 推荐入口

```bash
python3 scripts/aro_request.py auto
python3 scripts/aro_request.py auto --summary-only
python3 scripts/aro_request.py decide --summary-only
python3 scripts/aro_request.py decide --command-only
python3 scripts/aro_request.py doctor --limit 5
python3 scripts/aro_request.py doctor --summary-only
python3 scripts/aro_request.py feishu-health
python3 scripts/aro_request.py recover --summary-only
python3 scripts/aro_request.py version
python3 scripts/aro_request.py selftest
python3 scripts/aro_request.py commands
python3 scripts/aro_request.py config-check
python3 scripts/aro_request.py readiness
python3 scripts/aro_request.py startup
python3 scripts/aro_request.py templates --recipe bootstrap
python3 scripts/aro_request.py selfcheck
python3 scripts/aro_request.py sessions
python3 scripts/aro_request.py recover
python3 scripts/aro_request.py route --text "盘搜搜索 大君夫人"
python3 scripts/aro_request.py pick --choice 1
```

`auto` 会先读取 `startup.recommended_request_templates`，再自动拉取推荐的低 token recipe。

`selftest` 不连接 MoviePilot，只验证本地 helper 的决策和命令生成逻辑。

`version` 会输出当前 helper 版本。

`commands` 会输出 helper 命令目录、是否联网、是否可能写入。`writes` 固定为布尔值，具体触发条件在 `write_condition`。

注意：`workflow` 是 dry-run，不会解锁或转存资源，但会保存一个待确认执行的 plan，因此在命令目录里属于写入型命令。

`config-check` 只检查连接配置来源和是否存在，不输出真实 API Key。

`readiness` 会一次运行配置检查、本地 selftest 和 MoviePilot 插件 selfcheck。

`decide` 是单次决策入口：

- 有可恢复会话时，返回 `decision=continue_session`
- 没有可恢复会话时，返回 `decision=start_recipe`

无论落到哪一边，低 token 摘要都会尽量附带下一步 helper 命令。

只需要下一步命令时，用：

```bash
python3 scripts/aro_request.py decide --command-only
python3 scripts/aro_request.py decide --command-only --confirmed
```

默认会在需要确认的场景输出查看命令；已经获得用户确认后，再加 `--confirmed` 输出执行命令。

如果只想拿自动启动流的最小决策结果，直接用：

```bash
python3 scripts/aro_request.py auto --summary-only
```

`doctor` 是只读诊断入口，会一次返回 `startup + selfcheck + sessions + recover` 的压缩结果，适合外部智能体在真正执行前做开场检查。

`feishu-health` 会检查 `AgentResourceOfficer` 内置飞书入口是否启用、长连接是否运行，以及飞书 SDK / 白名单 / 回复配置状态；MP 内置智能助手可直接使用 `agent_resource_officer_feishu_health`。

如果只想拿最省 token 的决策结果，直接用：

```bash
python3 scripts/aro_request.py doctor --summary-only
python3 scripts/aro_request.py recover --summary-only
```

它还会直接给出：

- `helper_commands.inspect_helper_command`
- `helper_commands.execute_helper_command`

## 恢复与排查

```bash
python3 scripts/aro_request.py sessions --limit 10
python3 scripts/aro_request.py sessions --kind assistant_hdhive --limit 5
python3 scripts/aro_request.py session --session default
python3 scripts/aro_request.py recover
python3 scripts/aro_request.py recover --execute
python3 scripts/aro_request.py history --limit 10
python3 scripts/aro_request.py plans --limit 10
python3 scripts/aro_request.py plans --plan-id plan-xxx
python3 scripts/aro_request.py plans --executed --include-actions --limit 5
python3 scripts/aro_request.py plan-execute --plan-id plan-xxx
python3 scripts/aro_request.py plans-clear --plan-id plan-xxx
```

- `sessions` / `history` / `plans` / `recover` 默认不再强制绑到 `default` 会话。
- 只有显式传 `--session` 或 `--session-id` 时，才会收窄到单个会话。
- `plans-clear` 是写入型清理命令，优先使用 `--plan-id` 精确清理；批量清理时再使用 `--session`、`--executed`、`--unexecuted` 或 `--all-plans`。

## 说明

- 这是面向公开仓库的通用模板。
- 重点使用 `AgentResourceOfficer` 的 `assistant/startup` 和 `assistant/request_templates`。
- HTTP 调用使用 `?apikey=MP_API_TOKEN`。
- 不包含个人路径、API Key、Cookie 或 Token。
- 推荐搭配支持 Skill 和工具调度的外部智能体使用，例如腾讯 WorkBuddy，或兼容 Codex Skill 工作流的客户端。
- 版本记录见 [CHANGELOG.md](./CHANGELOG.md)。
