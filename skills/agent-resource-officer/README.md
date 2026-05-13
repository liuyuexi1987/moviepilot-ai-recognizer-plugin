# agent-resource-officer

公开版 AgentResourceOfficer Skill 模板，用来让外部智能体通过 MoviePilot 插件接口控制盘搜、影巢、115、夸克、MP/PT 搜索、下载、更新检查、编号选择和 Cookie 修复等资源工作流。插件是服务端执行层；Skill/helper 是客户端调度层。

当前 helper 版本：`0.1.51`

## 当前状态

- 当前插件版本：`Agent影视助手 0.2.70`
- 当前最小循环：`startup -> decide --summary-only -> route --summary-only -> followup --summary-only`
- 当前优先读取字段：`recommended_agent_behavior`、`auto_run_command`、`confirm_command`、`display_command`
- 当前 AI 失败样本只读诊断入口：
  - `python3 scripts/aro_request.py route --text "失败样本 蜘蛛侠" --summary-only`
  - `python3 scripts/aro_request.py route --text "工作清单 蜘蛛侠" --summary-only`
  - `python3 scripts/aro_request.py route --text "样本洞察 蜘蛛侠" --summary-only`
  - `python3 scripts/aro_request.py route --text "重放样本 3" --summary-only`
  - `python3 scripts/aro_request.py route --text "重放 3" --summary-only`
  - `python3 scripts/aro_request.py route --text "确认" --summary-only`
  - `python3 scripts/aro_request.py templates --recipe ai_reingest --compact`
- 当前最低成本入口：
  - `python3 scripts/aro_request.py readiness`
  - `python3 scripts/aro_request.py external-agent`
  - `python3 scripts/aro_request.py route --text "MP搜索 蜘蛛侠" --summary-only`
  - `python3 scripts/aro_request.py route --text "盘搜搜索 蜘蛛侠" --summary-only`
  - `python3 scripts/aro_request.py route --text "影巢搜索 蜘蛛侠" --summary-only`
- 当前搜索口径：
  - `搜索 <片名>` / `找 <片名>` 默认优先走 MP/PT；如果 MP/PT 已关闭，再按当前启用源回退
  - `盘搜搜索 <片名>` 固定先查盘搜，没结果时按开关补查影巢
  - `影巢搜索 <片名>` 固定先查影巢，没结果时按开关补查盘搜
  - `云盘搜索 <片名>` 已废弃，只会返回改用 `盘搜搜索` / `影巢搜索` 的提示
  - `搜索 第 3 集`、`搜索 E03` 这类带集数线索的写法，会直接按 MP/PT 搜索，不再回退到云盘
  - `盘搜更新检查 <片名>` / `影巢更新检查 <片名>` 是云盘侧更新检查；`更新检查 xx 剧` / `检查 xx 剧` 按 MP/PT 搜索处理
  - `MP搜索 <片名>` / `PT搜索 <片名>` 明确走 MoviePilot 原生 PT 搜索；片名有歧义时先返回 MP/TMDB 候选，用户选编号后再搜索 PT
- 标题级 `转存 <片名>` / `115转存 <片名>` / `夸克转存 <片名>` 已取消，只保留先搜索、再按编号继续处理的主线
- `下载 <片名>` 走 MP/PT 直接下载
- `115登录` 不再强依赖 `P115StrmHelper`；有它更适合做 115 整理、STRM 和旧登录态复用，没有它也可以直接扫码登录
- 当前更新口径：
  - `更新 <片名>` / `更新检查 <片名>` / `检查 <片名>` 先走更新检查
  - 直接展示TMDB 参考进度、盘搜最新集资源、影巢最新集资源
  - 不要先清空会话，不要先改走影巢候选
  - 资源列表必须保留原始编号，方便后续直接回编号
- 当前破坏性目录命令：
  - `清空夸克默认转存目录`
  - `清空夸克默认目录`
  - `清空115转存目录`
  - `清空115默认转存目录`
  - `清空115默认目录`
  - 只在用户原话明确提出时执行，不要从模糊“清理一下”里自行推断
- 当前影巢签到修复入口：
  - `python3 scripts/aro_request.py hdhive-cookie-refresh`
  - `python3 scripts/aro_request.py hdhive-checkin-repair`
  - 推荐做法：先确保 Edge 已登录 `https://hdhive.com`，再用上面两条命令自动写回完整 Cookie，不要手工复制 Cookie
- 当前夸克登录修复入口：
  - `python3 scripts/aro_request.py quark-cookie-refresh`
  - `python3 scripts/aro_request.py quark-transfer-repair`
  - 推荐做法：先确保 Edge 已登录 `https://pan.quark.cn`，登录态失效时优先刷新 Cookie；只有明确是 `require login [guest]` 这类登录态问题时才自动修复

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
优先使用已安装 skill 目录里的 config；没有本地 config 时，才回退到 ~/.config/agent-resource-officer/config
```

示例：

```text
ARO_BASE_URL=http://127.0.0.1:3000
ARO_API_KEY=your_moviepilot_api_token
ARO_HDHIVE_COOKIE_EXPORT_DIR=/绝对路径/MoviePilot-Plugins/tools/hdhive-cookie-export
ARO_QUARK_COOKIE_EXPORT_DIR=/绝对路径/MoviePilot-Plugins/tools/quark-cookie-export
```

`install.sh` 首次安装时会把当前全局配置复制到 `<target>/config`；后续重装会保留这个本地 config。这样 `Hermes`、`WorkBuddy`、`OpenClaw` 可以各用各的连接地址，不会再共用同一份默认配置。

`ARO_BASE_URL` 按实际部署填写：同机可以用 `http://127.0.0.1:3000`，局域网可以用 `http://你的局域网IP:3000`，公网反代可以用自己的 HTTPS 域名。

如果你要让 helper 直接调用本机“影巢 Cookie 导出”工具，可选配置：

```text
ARO_HDHIVE_COOKIE_EXPORT_DIR=/绝对路径/MoviePilot-Plugins/tools/hdhive-cookie-export
ARO_HDHIVE_COOKIE_EXPORT_PYTHON=/绝对路径/python
ARO_HDHIVE_COOKIE_BROWSER=edge
ARO_HDHIVE_COOKIE_SITE_URL=https://hdhive.com
ARO_HDHIVE_COOKIE_RESTART_CONTAINER=moviepilot-v2
ARO_QUARK_COOKIE_EXPORT_DIR=/绝对路径/MoviePilot-Plugins/tools/quark-cookie-export
ARO_QUARK_COOKIE_EXPORT_PYTHON=/绝对路径/python
ARO_QUARK_COOKIE_BROWSER=edge
ARO_QUARK_COOKIE_SITE_URL=https://pan.quark.cn
ARO_QUARK_COOKIE_RESTART_CONTAINER=moviepilot-v2
```

如果你直接使用本仓库，helper 也会优先自动尝试仓库里的：

- `tools/hdhive-cookie-export/`
- `tools/quark-cookie-export/`

`route` 支持两种写法：

- `python3 scripts/aro_request.py route "盘搜搜索 大君夫人"`
- `python3 scripts/aro_request.py route --text "盘搜搜索 大君夫人"`
- `python3 scripts/aro_request.py route "影巢搜索 大君夫人"`
- `python3 scripts/aro_request.py route "MP搜索 蜘蛛侠"`

`route`、`pick`、`workflow`、`plan-execute`、`followup` 还支持：

- `--summary-only`
- `--command-only`

适合外部智能体只拿“下一步怎么做”的最小结果。

夸克默认目录清空入口：

```bash
python3 scripts/aro_request.py route "清空夸克默认转存目录"
```

这条命令只针对当前配置的夸克默认转存目录，按当前层项目执行清空：当前层文件会直接删除，当前层文件夹也会一并删除（删除文件夹时会连同文件夹内内容一起清掉）。不要把它当成 115 清理，也不要从普通清理意图里自动触发，更不要先 grep helper 源码判断“支不支持”。

115 默认目录清空入口：

```bash
python3 scripts/aro_request.py route "清空115转存目录"
python3 scripts/aro_request.py route "清空115默认转存目录"
```

这条命令只针对当前配置的 115 默认转存目录，按当前层项目执行清空：当前层文件会直接删除，当前层文件夹也会一并删除（删除文件夹时会连同文件夹内内容一起清掉）。它是显式破坏性命令，不要从普通清理意图里自动触发，也不要先 grep helper 源码判断“支不支持”。

`pick`、`plan-execute`、`followup` 也支持更短的位置参数写法：

- `python3 scripts/aro_request.py pick 1`
- `python3 scripts/aro_request.py pick 1 详情`
- `python3 scripts/aro_request.py plan-execute plan-xxx`
- `python3 scripts/aro_request.py followup plan-xxx`

影巢 Cookie 刷新与签到修复：

```bash
python3 scripts/aro_request.py hdhive-cookie-refresh
python3 scripts/aro_request.py hdhive-checkin-repair
```

前者会从智能体所在电脑的本机浏览器导出完整网页 Cookie，并自动写回 MoviePilot/AgentResourceOfficer；后者会在刷新 Cookie 后直接再跑一次 `影巢签到`。当 `影巢签到` 或 `影巢签到日志` 明确提示网页登录态失效时，优先使用这两条命令，不要手工复制 Cookie。

夸克 Cookie 刷新与转存修复：

```bash
python3 scripts/aro_request.py quark-cookie-refresh
python3 scripts/aro_request.py quark-transfer-repair
python3 scripts/aro_request.py quark-transfer-repair --retry-text "选择 7" --session default
```

前者会从智能体所在电脑的本机浏览器导出夸克 Cookie，并自动写回 `AgentResourceOfficer` / `QuarkShareSaver`；后者会在刷新 Cookie 后检查夸克健康状态，必要时还能顺手重试一条刚才失败的转存命令。只有明确报出 `require login [guest]`、`夸克登录态已过期` 这类登录态问题时，才建议走这条修复链；分享受限、分享者封禁等错误不要误判成 Cookie 失效。

`plan-execute` 返回里会保留插件给出的 `recommended_action` 和 `follow_up_hint`。如果不想自己解析下一步，也可以直接执行 `python3 scripts/aro_request.py followup --session 'agent:<会话ID>'`。

`workflow`、`session`、`history`、`plans` 也支持常用短写法：

- `python3 scripts/aro_request.py workflow mp_media_detail 蜘蛛侠`
- `python3 scripts/aro_request.py session agent:demo`
- `python3 scripts/aro_request.py history agent:demo`
- `python3 scripts/aro_request.py plans plan-xxx`

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
python3 scripts/aro_request.py followup --session agent:<用户ID>
python3 scripts/aro_request.py templates --recipe followup --compact
python3 scripts/aro_request.py templates --recipe ai_reingest --compact
python3 scripts/aro_request.py version
python3 scripts/aro_request.py selftest
python3 scripts/aro_request.py commands
python3 scripts/aro_request.py external-agent
python3 scripts/aro_request.py external-agent --full
python3 scripts/aro_request.py config-check
python3 scripts/aro_request.py readiness
python3 scripts/aro_request.py startup
python3 scripts/aro_request.py templates --recipe bootstrap
python3 scripts/aro_request.py templates --recipe mp_pt
python3 scripts/aro_request.py templates --recipe recommend
python3 scripts/aro_request.py preferences --session agent:demo
python3 scripts/aro_request.py selfcheck
python3 scripts/aro_request.py sessions
python3 scripts/aro_request.py session-clear default
python3 scripts/aro_request.py sessions-clear --has-pending-p115 --limit 10
python3 scripts/aro_request.py recover
python3 scripts/aro_request.py route "盘搜搜索 大君夫人"
python3 scripts/aro_request.py route "影巢搜索 蜘蛛侠"
python3 scripts/aro_request.py route "MP搜索 蜘蛛侠"
python3 scripts/aro_request.py route "PT搜索 蜘蛛侠"
python3 scripts/aro_request.py route "下载 蜘蛛侠"
python3 scripts/aro_request.py route "失败样本 蜘蛛侠"
python3 scripts/aro_request.py route "工作清单 蜘蛛侠"
python3 scripts/aro_request.py route "样本洞察 蜘蛛侠"
python3 scripts/aro_request.py route "重放样本 3"
python3 scripts/aro_request.py route "重放 3"
python3 scripts/aro_request.py route "确认"
python3 scripts/aro_request.py route "先计划"
python3 scripts/aro_request.py route "确认执行"
python3 scripts/aro_request.py route "先看详情"
python3 scripts/aro_request.py route "计划"
python3 scripts/aro_request.py route "详情"
python3 scripts/aro_request.py route "MP搜索 蜘蛛侠"
python3 scripts/aro_request.py route "PT搜索 蜘蛛侠"
python3 scripts/aro_request.py route "盘搜搜索 蜘蛛侠"
python3 scripts/aro_request.py route "影巢搜索 蜘蛛侠"
python3 scripts/aro_request.py pick 1
```

`auto` 会先读取 `startup.recommended_request_templates`，再自动拉取推荐的低 token recipe。

`selftest` 不连接 MoviePilot，只验证本地 helper 的决策和命令生成逻辑。

`version` 会输出当前 helper 版本。

`commands` 会输出 helper 命令目录、是否联网、是否可能写入。`writes` 固定为布尔值，具体触发条件在 `write_condition`。

`external-agent` 会输出可直接交给 WorkBuddy、Hermes、OpenClaw（小龙虾）、微信侧智能体或其他外部智能体的系统提示词和最小工具约定；`external-agent --full` 会输出完整接入说明。输出中会明确给出 `compat_aliases` 和 `deprecated_aliases`。旧命令 `workbuddy` 仍保留为兼容别名，但已标记为 deprecated。

如果你对接的是 MP 内置智能体，优先读取 `request_templates` 和原生 Agent Tool，不要让模型自己拼底层影巢、盘搜、115、夸克接口。飞书入口同样复用 `route / pick / followup`，只是消息来源不同。

从 `0.2.66` 开始，`request_templates` 还会直接给出 `entry_playbooks`，把外部智能体、MP 内置智能体、飞书入口各自该调什么 helper / HTTP / Tool 以及优先读取哪些字段直接列出来。新接入方优先读这个结构，不要再自己拼第二套启动脚手架。

如果外部智能体已经确定是 MP 原生 PT 搜索/下载/订阅任务，优先拉 `mp_pt` recipe；如果是插件状态、下载器状态、订阅列表这类管理查询，优先拉 `mp_admin` recipe。当前公开主线尽量保持小而稳：搜索、下载、订阅、状态查询、Cookie 修复。

首次交给外部智能体使用时，建议先运行 `preferences`。如果返回需要初始化偏好，智能体应询问用户：清晰度、杜比视界/HDR、字幕、电视剧是否全集优先、PT 最低做种、影巢积分上限、默认目录、是否允许高分资源自动入库。偏好会用于云盘和 PT 分源评分。

如果你希望“新会话默认就更保守或更激进”，不要在智能体侧硬编码阈值，直接到 Agent影视助手 插件设置里修改默认评分策略：`PT 最低做种数`、`建议确认分数线`、`自动入库分数线`、`默认允许高分自动入库`。

`route`、`pick`、`workflow` 等主响应会带上低 token 的 `preference_status`。如果其中 `needs_onboarding=true`，智能体应先完成偏好询问与保存，再继续自动选择或入库。

偏好也可以直接走主入口自然语言：`偏好` 查看，`保存偏好 4K 杜比 HDR 中字 全集 做种>=3 影巢积分20 不自动入库` 写入，`重置偏好` 清除。

如果用户已经提前说明“只用夸克”“没有 115”“不用盘搜”“只用 MP/PT”，也可以直接保存进偏好，例如：

- `保存偏好 只有夸克 不用115`
- `保存偏好 只用盘搜 不用影巢`
- `保存偏好 只用 MP/PT`

之后优先用显式前缀搜索：

- `python3 scripts/aro_request.py route "MP搜索 蜘蛛侠"`
- `python3 scripts/aro_request.py route "PT搜索 蜘蛛侠"`
- `python3 scripts/aro_request.py route "盘搜搜索 蜘蛛侠"`
- `python3 scripts/aro_request.py route "影巢搜索 蜘蛛侠"`
- `python3 scripts/aro_request.py route "下载 蜘蛛侠"`

当前原则是：少命令、少歧义、少二次加工。不要再从 helper 层自行拼“智能搜索/资源决策/执行最佳”这类复合入口。

AI 失败样本链现在分两步：

- `失败样本 / 工作清单 / 样本洞察`：只读诊断
- `重放样本 3` 或会话内 `重放 3`：只生成待确认计划
- `确认`：执行当前会话里最近一条 AI 重放计划
- 重放后可直接继续：`诊断`、`入库状态`

真正执行仍然要回复 `执行计划 <plan_id>`，不会直接裸重放。

搜索类响应可能带有 `score_summary`，包含 `best` 和 `top_recommendations`。外部智能体应优先读取这个结构化摘要，而不是解析长文本；存在 `hard_risk_reasons` 时不要自动执行，`risk_reasons` 只作为确认前需要解释的提醒。

`score_summary.decision` 是优先读取的下一步建议层，里面会给出 `label`、`decision_hint`、`preferred_command`、`fallback_command`、`compact_commands` 和 `recommended_commands`。外部智能体应优先复用前两档短命令，不要自己再拼另一套确认话术。

执行计划后的回执，以及后续的 `execution_followup`、`smart_followup`、`mp_lifecycle_status`、`mp_ingest_status`、`mp_recent_activity`，现在会统一附带 `followup_summary`。外部智能体应优先读取 `preferred_command`、`fallback_command` 和 `compact_commands` 来决定“接下来查下载、查入库还是查诊断”，不要再靠不同 message 文案分支判断。

从 `0.2.63` 开始，compact 主响应顶层也会直接给出统一的 `command_source`、`command_policy`、`preferred_requires_confirmation`、`fallback_requires_confirmation`、`can_auto_run_preferred`、`preferred_command`、`fallback_command`、`compact_commands`。优先级已经固定为：

1. `error_summary`
2. `followup_summary`
3. `score_summary.decision`

外部智能体如果只想要“下一条最短命令”，直接读取顶层字段即可，不必自己再判断嵌套结构来源；如果还要判断“这一步能不能直接执行”，则读取 `command_policy` 和两个 `*_requires_confirmation` 标志。

从 helper `0.1.30` 开始，`route / pick / workflow / plan-execute / followup` 也能直接把这层顶层字段压成 `--summary-only` / `--command-only` 输出。外部智能体如果不想自己解析 JSON，可以直接调用 helper。

从 helper `0.1.31` 开始，这些摘要还会继续保留：

- `command_policy`
- `preferred_requires_confirmation`
- `fallback_requires_confirmation`
- `can_auto_run_preferred`

也就是外部智能体不只知道“下一条命令是什么”，还知道“这条命令能不能直接跑，还是该先停下来确认”。

从 helper `0.1.32` 开始，`--summary-only` 会直接给出一层更适合自动续跑的决策字段：

- `recommended_agent_behavior`
- `auto_run_command`
- `confirm_command`
- `display_command`
- `stop_after_auto`
- `reason`

推荐解释：

- `auto_continue`：可以直接执行 `auto_run_command`
- `auto_continue_then_wait_confirmation`：先执行 `auto_run_command`，然后停下来把 `confirm_command` 展示给用户确认
- `wait_user_confirmation`：不要自动执行，先让用户确认 `confirm_command`
- `show_only`：只展示 `display_command`
- `stop`：当前没有适合继续自动执行的短命令

从 helper `0.1.33` 开始，这套决策字段不只覆盖 `route / pick / workflow / plan-execute / followup`，也会覆盖 `decide / auto / doctor / recover` 这类老摘要入口。外部智能体可以统一只读：

- `recommended_agent_behavior`
- `auto_run_command`
- `confirm_command`

如果原摘要本身已经带业务层 `reason`，helper 会额外补 `execution_reason`，避免把原原因覆盖掉。

推荐把外部智能体的执行分支压成这 5 类：

- `auto_continue`：直接执行 `auto_run_command`
- `auto_continue_then_wait_confirmation`：先执行 `auto_run_command`，再向用户确认 `confirm_command`
- `wait_user_confirmation`：不要自动执行，先展示 `confirm_command`
- `show_only`：只展示 `display_command`
- `stop`：当前不要继续自动执行

推荐的最小启动流也已经固定：

1. `startup`
2. `decide --summary-only`
3. `route "<用户原始指令>" --summary-only`
4. 按 `recommended_agent_behavior` 决定自动继续、确认或停止
5. 涉及执行计划后，再走 `followup --summary-only`

评分由插件内置规则执行。外部智能体如需解释规则，可读取 `scoring-policy` 或 `capabilities.scoring_policy`；不要在智能体侧重新打分，也不要绕过 `hard_risk_reasons`。

`config-check` 只检查连接配置来源和是否存在，不输出真实 API Key。

`readiness` 会一次运行配置检查、本地 selftest 和 MoviePilot 插件 selfcheck。

WorkBuddy、Hermes、OpenClaw（小龙虾）、微信侧智能体或其他外部智能体接入时，可以直接复用：

- [外部智能体接入 Agent影视助手](../../docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md)
- Skill 包内外部智能体接入文件：`skills/agent-resource-officer/EXTERNAL_AGENTS.md`
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

如果已确定任务类型，可以直接指定 recipe 获取更具体的下一步命令：

```bash
python3 scripts/aro_request.py decide --recipe mp_pt --command-only
python3 scripts/aro_request.py decide --recipe recommend --command-only
```

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
python3 scripts/aro_request.py session default
python3 scripts/aro_request.py session-clear default
python3 scripts/aro_request.py sessions-clear --has-pending-p115 --limit 10
python3 scripts/aro_request.py recover
python3 scripts/aro_request.py recover --execute
python3 scripts/aro_request.py history --limit 10
python3 scripts/aro_request.py history agent:demo
python3 scripts/aro_request.py plans --limit 10
python3 scripts/aro_request.py plans plan-xxx
python3 scripts/aro_request.py plans --executed --include-actions --limit 5
python3 scripts/aro_request.py plan-execute plan-xxx
python3 scripts/aro_request.py followup --session agent:<用户ID>
python3 scripts/aro_request.py followup plan-xxx
python3 scripts/aro_request.py plans-clear plan-xxx
```

- `sessions` / `history` / `plans` / `recover` 默认不再强制绑到 `default` 会话。
- 只有显式传 `--session` 或 `--session-id` 时，才会收窄到单个会话。
- `followup` 会按最近已执行计划自动选择合适的只读后续动作，适合接在 `plan-execute` 后面。
- `session-clear` / `sessions-clear` 是写入型清理命令，用于清理放弃的会话或 pending 115 恢复状态。
- `plans-clear` 是写入型清理命令，优先使用 `--plan-id` 精确清理；批量清理时再使用 `--session`、`--executed`、`--unexecuted` 或 `--all-plans`。

长线程维护：

如果外部智能体接的是微信、WorkBuddy、Claw、Hermes 或 OpenClaw 这类长期不断开的线程，用久以后可能会被旧测试上下文污染。典型表现是：`15详情` 被改写成 `选择 15`、编号续接到旧结果、或展示格式突然回到旧规则。

这时先清当前 session 和旧计划，再让智能体重新读取 Skill：

```bash
python3 scripts/aro_request.py session-clear --session default
python3 scripts/aro_request.py plans-clear --session default
```

如果你给每个用户或群聊分配了固定 session，例如 `agent:wechat-room-1`，把 `default` 换成实际 session。不要把这一步放到普通搜索或更新检查前自动执行，否则会破坏正常编号续接。

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
python3 scripts/aro_request.py workflow mp_media_detail 蜘蛛侠
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
python3 scripts/aro_request.py route --text "MP搜索 蜘蛛侠" --session agent:demo
python3 scripts/aro_request.py pick --choice 1 --session agent:demo
python3 scripts/aro_request.py route --text "计划选择 1" --session agent:demo
python3 scripts/aro_request.py route --text "最佳片源" --session agent:demo
python3 scripts/aro_request.py route --text "下载最佳" --session agent:demo
python3 scripts/aro_request.py route --text "执行计划" --session agent:demo
python3 scripts/aro_request.py route --text "执行 plan-xxxx" --session agent:demo
```

盘搜和影巢资源列表里的 `最佳片源`、`选择 1 详情` 是只读查看，不会转存或解锁。普通 `搜索/找 <片名>` 返回的盘搜列表，默认先按编号直接选；想先确认时再发 `选择 1 详情`。只有用户明确要求保留计划确认链时，才发 `计划选择 1`。

普通 `搜索/找 <片名>` 的返回应尽量原样展示资源官给出的编号列表，不要再二次改写成“资源状态”“推荐清单”“费用/评分/推荐星级”之类的摘要。最好的做法是保留原列表和下一步提示，只在前后补一两句极短说明。

`盘搜搜索 <片名>` 和 `影巢搜索 <片名>` 也应尽量原样展示资源官给出的组合结果。不要把插件已经给出的 `盘搜结果 / 影巢结果` 两段重新压成“剧集信息 / 推荐资源 / 分析结论”的导购摘要。优先保留：
- `盘搜结果`
- `影巢结果`
- 原始编号
- 盘搜原始链接
- 插件原生下一步提示

`盘搜搜索` / `影巢搜索` 返回后，不要自行改写成每个来源各自从 `1` 开始编号的小表格，也不要只摘“亮点”。如果插件返回了全局编号，就保留全局编号；如果插件提示“影巢候选未自动展开”，也应原样保留这句，而不是把它改成一句“影巢还有候选，需要可发影巢搜索”然后丢掉上文结构。

`MP搜索` / `PT搜索` 返回后，也不要自行改写成简表。尤其不要重写英文 release title，插件会在点号标题里加入隐藏断点，并用 `🌱`、`🎁`、`💾`、`⭐` 等 emoji 改善手机微信阅读；这些标记都应原样保留。

`更新检查` / `检查` 返回后，同样不要改写成 `#: 来源 / 详情 / 日期` 这种字段表。插件已经会输出 `🟨 盘搜结果`、`🟦 影巢结果`、`🗄 #编号 夸克`、`📺 #编号 115`、`🕒日期`、`📌 集数`，这些行应原样保留，最多在列表后追加一段很短的自然语言建议。

`MP搜索` / `PT搜索` 返回后，也不要自行改写成简表。尤其不要重写英文 release title，插件会在点号标题里加入隐藏断点，并用 `🌱`、`🎁`、`💾`、`⭐` 等 emoji 改善手机微信阅读；这些标记都应原样保留。

`更新检查` / `检查` 返回后，同样不要改写成 `#: 来源 / 详情 / 日期` 这种字段表。插件已经会输出 `🟨 盘搜结果`、`🟦 影巢结果`、`🗄 #编号 夸克`、`📺 #编号 115`、`🕒日期`、`📌 集数`，这些行应原样保留，最多在列表后追加一段很短的自然语言建议。

夸克转存失败时，不要自己补一段“可能是默认转存目录不存在或有问题”“换个 path=/ 试试”这类猜测。只有当插件明确指出路径问题时，才建议改路径；如果插件只返回 `夸克转存失败：无法转存到 /飞书`，更稳妥的表述应是“原因未明，先不要自行推断路径问题”。

下载任务也可以走同一入口。查询是读操作；暂停、恢复、删除会先返回 `plan_id`，确认后再执行：

```bash
python3 scripts/aro_request.py route --text "下载任务"
python3 scripts/aro_request.py route --text "记录"
python3 scripts/aro_request.py route --text "记录 蜘蛛侠"
python3 scripts/aro_request.py workflow --workflow mp_download_history --keyword "蜘蛛侠" --limit 10
python3 scripts/aro_request.py route --text "状态 蜘蛛侠"
python3 scripts/aro_request.py workflow --workflow mp_lifecycle_status --keyword "蜘蛛侠" --limit 5
python3 scripts/aro_request.py route --text "后续"
python3 scripts/aro_request.py route --text "跟进"
python3 scripts/aro_request.py route --text "跟进 蜘蛛侠"
python3 scripts/aro_request.py route --text "入库 蜘蛛侠"
python3 scripts/aro_request.py route --text "诊断 蜘蛛侠"
python3 scripts/aro_request.py route --text "最近"
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

MP 订阅也可以交给 Agent影视助手统一调度。查询是读操作；刷新、暂停、恢复、删除订阅会先返回 `plan_id`：

```bash
python3 scripts/aro_request.py route --text "订阅列表"
python3 scripts/aro_request.py route --text "刷新订阅 1"
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
- PT 资源按做种数、免费/促销、下载热度、清晰度、HDR/DV、字幕、标题匹配、站点和发布组评分；高分也默认先返回 `plan_id`，不会直接下载。
- 下载、订阅、影巢解锁、网盘转存默认先生成 `plan_id`，确认后再执行。

## 说明

- 这是面向公开仓库的通用模板。
- 重点使用 `AgentResourceOfficer` 的 `assistant/startup` 和 `assistant/request_templates`。
- HTTP 调用使用 `?apikey=MP_API_TOKEN`。
- 不包含个人路径、API Key、Cookie 或 Token。
- 推荐搭配支持 Skill 和工具调度的外部智能体使用，例如腾讯 WorkBuddy、Hermes、OpenClaw（小龙虾），或其他兼容 Skill 工作流的客户端。
- 版本记录见：`skills/agent-resource-officer/CHANGELOG.md`。
