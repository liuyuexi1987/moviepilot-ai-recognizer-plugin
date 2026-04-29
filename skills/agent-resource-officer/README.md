# agent-resource-officer

公开版 AgentResourceOfficer Skill 模板，用来让外部智能体通过 MoviePilot 插件接口控制 115 云盘、夸克云盘等云盘资源工作流。

当前 helper 版本：`0.1.19`

公开仓库：

```text
https://github.com/liuyuexi1987/MoviePilot-Plugins
```

## 使用方式

1. 获取仓库：

```bash
git clone https://github.com/liuyuexi1987/MoviePilot-Plugins.git
cd MoviePilot-Plugins
```

2. 把整个目录复制到自己的 Skill 搜索路径，例如：

```text
<SKILL_HOME>/agent-resource-officer
```

也可以直接运行安装脚本：

```bash
bash install.sh --dry-run
bash install.sh
bash install.sh --target /path/to/skills/agent-resource-officer
```

3. 配置连接信息：

```text
~/.config/agent-resource-officer/config
```

示例：

```text
ARO_BASE_URL=http://127.0.0.1:3000
ARO_API_KEY=your_moviepilot_api_token
```

`ARO_BASE_URL` 按实际部署填写：同机可以用 `http://127.0.0.1:3000`，局域网可以用 `http://你的局域网IP:3000`，公网反代可以用自己的 HTTPS 域名。

4. 让外部智能体使用本 Skill。

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
python3 scripts/aro_request.py external-agent
python3 scripts/aro_request.py external-agent --full
python3 scripts/aro_request.py config-check
python3 scripts/aro_request.py readiness
python3 scripts/aro_request.py startup
python3 scripts/aro_request.py templates --recipe bootstrap
python3 scripts/aro_request.py preferences --session agent:demo
python3 scripts/aro_request.py selfcheck
python3 scripts/aro_request.py sessions
python3 scripts/aro_request.py session-clear --session default
python3 scripts/aro_request.py sessions-clear --has-pending-p115 --limit 10
python3 scripts/aro_request.py recover
python3 scripts/aro_request.py route --text "盘搜搜索 大君夫人"
python3 scripts/aro_request.py pick --choice 1
```

`auto` 会先读取 `startup.recommended_request_templates`，再自动拉取推荐的低 token recipe。

`selftest` 不连接 MoviePilot，只验证本地 helper 的决策和命令生成逻辑。

`version` 会输出当前 helper 版本。

`commands` 会输出 helper 命令目录、是否联网、是否可能写入。`writes` 固定为布尔值，具体触发条件在 `write_condition`。

`external-agent` 会输出可直接交给 WorkBuddy、Hermes、OpenClaw（小龙虾）、微信侧智能体或其他外部智能体的系统提示词和最小工具约定；`external-agent --full` 会输出完整接入说明。旧命令 `workbuddy` 仍保留为兼容别名。

注意：`workflow` 会直接执行只读工作流；涉及下载、订阅、解锁或转存的写入工作流会默认保存待确认执行的 `plan_id`。

例外：如果用户偏好里明确开启 `auto_ingest_enabled=true`，并且 PT 候选评分达到自动阈值且没有硬风险，`下载1` 和 `下载最佳` 可以直接提交下载。默认偏好关闭自动入库。

首次交给外部智能体使用时，建议先运行 `preferences`。如果返回需要初始化偏好，智能体应询问用户：清晰度、杜比视界/HDR、字幕、电视剧是否全集优先、PT 最低做种、影巢积分上限、默认目录、是否允许高分资源自动入库。偏好会用于云盘和 PT 分源评分。

`route`、`pick`、`workflow` 等主响应会带上低 token 的 `preference_status`。如果其中 `needs_onboarding=true`，智能体应先完成偏好询问与保存，再继续自动选择或入库。

偏好也可以直接走主入口自然语言：`偏好` 查看，`保存偏好 4K 杜比 HDR 中字 全集 做种>=3 影巢积分20 不自动入库` 写入，`重置偏好` 清除。

搜索类响应可能带有 `score_summary`，包含 `best` 和 `top_recommendations`。外部智能体应优先读取这个结构化摘要，而不是解析长文本；存在 `risk_reasons` 时不要自动执行，`score_level=confirm` 时先向用户解释原因并确认。

评分由插件内置规则执行。外部智能体如需解释规则，可读取 `scoring-policy` 或 `capabilities.scoring_policy`；不要在智能体侧重新打分，也不要绕过 `risk_reasons`。

`config-check` 只检查连接配置来源和是否存在，不输出真实 API Key。

`readiness` 会一次运行配置检查、本地 selftest 和 MoviePilot 插件 selfcheck。

WorkBuddy、Hermes、OpenClaw（小龙虾）、微信侧智能体或其他外部智能体接入时，可以直接复用：

- [外部智能体接入 Agent云盘资源整合](../../docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md)
- [Skill 包内外部智能体接入文件](./EXTERNAL_AGENTS.md)
- `PROMPTS.md` 里的外部智能体提示词段落

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
python3 scripts/aro_request.py session-clear --session default
python3 scripts/aro_request.py sessions-clear --has-pending-p115 --limit 10
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
- `session-clear` / `sessions-clear` 是写入型清理命令，用于清理放弃的会话或 pending 115 恢复状态。
- `plans-clear` 是写入型清理命令，优先使用 `--plan-id` 精确清理；批量清理时再使用 `--session`、`--executed`、`--unexecuted` 或 `--all-plans`。

## 偏好与评分

```bash
python3 scripts/aro_request.py preferences --session agent:demo
python3 scripts/aro_request.py preferences --session agent:demo --preferences-json '{"prefer_resolution":"4K","prefer_dolby_vision":true,"prefer_hdr":true,"prefer_chinese_subtitle":true,"prefer_complete_series":true,"pt_min_seeders":3,"hdhive_max_unlock_points":20,"auto_ingest_enabled":false}'
python3 scripts/aro_request.py route --text "保存偏好 4K 杜比 HDR 中字 全集 做种>=3 影巢积分20 不自动入库" --session agent:demo
python3 scripts/aro_request.py workflow --workflow mp_search --keyword "蜘蛛侠"
python3 scripts/aro_request.py workflow --workflow mp_media_detail --keyword "蜘蛛侠"
python3 scripts/aro_request.py workflow --workflow mp_search_best --keyword "蜘蛛侠"
python3 scripts/aro_request.py workflow --workflow mp_search_detail --keyword "蜘蛛侠" --choice 1
python3 scripts/aro_request.py workflow --workflow mp_search_download --keyword "蜘蛛侠" --choice 1
python3 scripts/aro_request.py workflow --workflow mp_recommend --source tmdb_trending --media-type all --limit 20
python3 scripts/aro_request.py workflow --workflow mp_recommend_search --source tmdb_trending --media-type all --choice 1 --mode mp
python3 scripts/aro_request.py workflow --workflow mp_recommend_search --source tmdb_trending --media-type all --choice 1 --mode hdhive
```

智能体也可以直接走自然语言路由：

```bash
python3 scripts/aro_request.py route --text "看看最近有什么热门影视"
python3 scripts/aro_request.py route --text "豆瓣热门电影"
python3 scripts/aro_request.py route --text "今日番剧"
```

推荐列表出来后，可以用自然语言继续：

```bash
python3 scripts/aro_request.py route --text "选择 1"
python3 scripts/aro_request.py route --text "选择 1 盘搜"
python3 scripts/aro_request.py route --text "选择1影巢"
```

MP 原生搜索结果出来后，也可以直接：

```bash
python3 scripts/aro_request.py route --text "下载1"
python3 scripts/aro_request.py route --text "下载第1个"
python3 scripts/aro_request.py route --text "订阅蜘蛛侠"
python3 scripts/aro_request.py route --text "订阅并搜索蜘蛛侠"
python3 scripts/aro_request.py route --text "MP搜索 蜘蛛侠" --session agent:demo
python3 scripts/aro_request.py pick --choice 1 --session agent:demo
python3 scripts/aro_request.py route --text "最佳片源" --session agent:demo
python3 scripts/aro_request.py route --text "下载最佳" --session agent:demo
python3 scripts/aro_request.py route --text "执行计划" --session agent:demo
python3 scripts/aro_request.py route --text "执行 plan-xxxx" --session agent:demo
```

下载任务也可以走同一入口。查询是读操作；暂停、恢复、删除会先返回 `plan_id`，确认后再执行：

```bash
python3 scripts/aro_request.py route --text "下载任务"
python3 scripts/aro_request.py route --text "下载历史"
python3 scripts/aro_request.py route --text "下载历史 蜘蛛侠"
python3 scripts/aro_request.py workflow --workflow mp_download_history --keyword "蜘蛛侠" --limit 10
python3 scripts/aro_request.py route --text "追踪 蜘蛛侠"
python3 scripts/aro_request.py workflow --workflow mp_lifecycle_status --keyword "蜘蛛侠" --limit 5
python3 scripts/aro_request.py route --text "识别 蜘蛛侠"
python3 scripts/aro_request.py workflow --workflow mp_media_detail --keyword "蜘蛛侠"
python3 scripts/aro_request.py route --text "暂停下载 1"
python3 scripts/aro_request.py route --text "恢复下载 1"
python3 scripts/aro_request.py route --text "删除下载 1"
```

PT 环境诊断也可以直接询问；站点结果只返回脱敏摘要，不会暴露 Cookie：

```bash
python3 scripts/aro_request.py route --text "站点状态"
python3 scripts/aro_request.py route --text "下载器状态"
python3 scripts/aro_request.py workflow --workflow mp_sites --status active --limit 30
python3 scripts/aro_request.py workflow --workflow mp_downloaders
```

MP 订阅也可以交给资源官统一调度。查询是读操作；搜索、暂停、恢复、删除订阅会先返回 `plan_id`：

```bash
python3 scripts/aro_request.py route --text "订阅列表"
python3 scripts/aro_request.py route --text "搜索订阅 1"
python3 scripts/aro_request.py route --text "暂停订阅 1"
python3 scripts/aro_request.py route --text "恢复订阅 1"
python3 scripts/aro_request.py route --text "删除订阅 1"
python3 scripts/aro_request.py workflow --workflow mp_subscribes --status all --limit 20
python3 scripts/aro_request.py workflow --workflow mp_subscribe_control --control search --target 1
```

MP 整理/入库历史是只读查询，适合让智能体确认下载后是否已经落库：

```bash
python3 scripts/aro_request.py route --text "入库历史"
python3 scripts/aro_request.py route --text "入库失败 蜘蛛侠"
python3 scripts/aro_request.py workflow --workflow mp_transfer_history --keyword "蜘蛛侠" --status all --limit 10
```

- 云盘资源按清晰度、HDR/DV、字幕、完整度、目录和网盘类型评分；影巢额外受积分上限保护。
- PT 资源按做种数、免费/促销、下载折算、清晰度、HDR/DV、字幕和标题匹配评分；做种低于阈值不会自动下载。
- 下载、订阅、影巢解锁、网盘转存默认先生成 `plan_id`，确认后再执行。

## 说明

- 这是面向公开仓库的通用模板。
- 重点使用 `AgentResourceOfficer` 的 `assistant/startup` 和 `assistant/request_templates`。
- HTTP 调用使用 `?apikey=MP_API_TOKEN`。
- 不包含个人路径、API Key、Cookie 或 Token。
- 推荐搭配支持 Skill 和工具调度的外部智能体使用，例如腾讯 WorkBuddy、Hermes、OpenClaw（小龙虾），或其他兼容 Skill 工作流的客户端。
- 版本记录见 [CHANGELOG.md](./CHANGELOG.md)。
