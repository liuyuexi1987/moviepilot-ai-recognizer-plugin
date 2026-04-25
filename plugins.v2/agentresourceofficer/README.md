# Agent资源官

这是重构中的新主插件目录，用来承接当前仓库里和“资源搜索、解锁、转存、签到、远程入口”相关的能力。

当前已经不是纯骨架，已经具备第一批可用 API，并且已经在实际 MoviePilot 运行环境里完成了健康检查与会话搜索回归。

- 夸克健康检查
- 夸克分享转存
- 115 依赖健康检查
- 115 分享转存
- 影巢健康检查
- 影巢账号信息
- 影巢签到
- 影巢配额与今日用量
- 影巢每周免费额度
- 影巢 TMDB 搜索
- 影巢关键词候选搜索
- 影巢资源解锁
- 影巢解锁后自动路由到 115 / 夸克执行层
- 通用分享链接自动路由

## 目标

- 统一影巢、盘搜、115、夸克、飞书入口
- 让智能体、飞书、CLI、MP 原生 Agent Tool 共用同一套稳定执行能力
- 把现在分散在多个插件里的能力收拢成一个资源工作流插件

## 计划承接的来源

- `FeishuCommandBridgeLong`
- `HdhiveOpenApi`
- `HDHiveDailySign`
- `QuarkShareSaver`

## 首期模块

- 搜索入口层
  - 盘搜
  - 影巢
  - 智能分流
- 执行层
  - 影巢解锁
  - 115 转存
  - 夸克转存
- 用户态层
  - 影巢签到
  - 用户信息
  - 配额与用量
- 接入层
  - 飞书
  - MP Agent Tool
  - 未来 CLI 封装

## 迁移原则

- 先搬稳定执行能力，再搬会话和交互层
- 保持现有线上链路可用
- 迁移过程中不直接修改旧插件的功能边界

## 当前状态

- 当前版本：`0.1.76`
- 已进入第一阶段可用状态
- 已验证 `影巢健康检查 / 夸克健康检查 / 影巢候选搜索 / 选片进入资源列表`
- 已接入第一批原生 `Agent Tool`
- 已补齐 115 扫码登录原生 `Agent Tool`
- 智能入口现已直接支持 `115登录` / `检查115登录`
- 登录成功后会直接回显 115 可用状态、默认目录和当前会话来源
- 智能入口与原生 Agent Tool 新增 `115状态` 查询
- 智能入口新增 `115帮助`，状态回执会附带下一步建议
- 待继续的 115 任务已支持持久化保存、状态摘要、手动继续、手动取消，并已下沉为原生 Agent Tool 和标准 API
- 影巢候选已支持新主线分页、`详情` / `审查` 按需补主演，飞书切 `auto` 时也能复用
- 影巢部分用户态接口受站点 Premium 权限限制；账号信息会优先回退到 `HDHiveDailySign` 的网页快照，签到会优先尝试 `HDHiveDailySign` 现有 Cookie 做网页兜底
- `115` 自动转存已具备轻量直转层：可优先使用扫码得到的 115 客户端会话，或复用已加载的 115 客户端直接调用分享转存接口；直转失败时再回退 `P115StrmHelper`
- 飞书入口仍会继续迁移进来

这意味着 `Agent资源官` 的“115 分享链接落盘”已经开始和 `P115StrmHelper` 解耦；但 STRM 生成、302、全量/增量同步、媒体库整理仍建议继续交给 `P115StrmHelper`。
对于登录方式，当前已经不再推荐粘贴网页版 Cookie，而是优先走 `p115client` 同款扫码会话。

如遇到 `P115StrmHelper` 因 `TransferOverwriteCheckEventData` 导入失败而无法加载，可执行仓库脚本：

```bash
MP_CONTAINER=moviepilot-v2 ./scripts/patch-p115strmhelper-mp-compat.sh
```

执行后重启 MoviePilot，再检查 `AgentResourceOfficer` 的 `p115/health` 是否返回 `p115_ready=true`。

## 当前可用 API

以下接口已经接入：

- `GET /api/v1/plugin/AgentResourceOfficer/quark/health`
- `POST /api/v1/plugin/AgentResourceOfficer/quark/transfer`
- `GET /api/v1/plugin/AgentResourceOfficer/p115/health`
- `GET /api/v1/plugin/AgentResourceOfficer/p115/qrcode`
- `GET /api/v1/plugin/AgentResourceOfficer/p115/qrcode/check`
- `POST /api/v1/plugin/AgentResourceOfficer/p115/transfer`
- `GET /api/v1/plugin/AgentResourceOfficer/p115/pending`
- `POST /api/v1/plugin/AgentResourceOfficer/p115/pending`
- `POST /api/v1/plugin/AgentResourceOfficer/p115/pending/resume`
- `POST /api/v1/plugin/AgentResourceOfficer/p115/pending/cancel`
- `GET /api/v1/plugin/AgentResourceOfficer/hdhive/health`
- `GET /api/v1/plugin/AgentResourceOfficer/hdhive/account`
- `POST /api/v1/plugin/AgentResourceOfficer/hdhive/checkin`
- `GET /api/v1/plugin/AgentResourceOfficer/hdhive/quota`
- `GET /api/v1/plugin/AgentResourceOfficer/hdhive/usage_today`
- `GET /api/v1/plugin/AgentResourceOfficer/hdhive/weekly_free_quota`
- `POST /api/v1/plugin/AgentResourceOfficer/hdhive/search`
- `POST /api/v1/plugin/AgentResourceOfficer/hdhive/search_by_keyword`
- `POST /api/v1/plugin/AgentResourceOfficer/hdhive/unlock`
- `POST /api/v1/plugin/AgentResourceOfficer/hdhive/unlock_and_route`
- `POST /api/v1/plugin/AgentResourceOfficer/share/route`
- `POST /api/v1/plugin/AgentResourceOfficer/assistant/route`
- `POST /api/v1/plugin/AgentResourceOfficer/assistant/pick`
- `GET /api/v1/plugin/AgentResourceOfficer/assistant/capabilities`
- `GET /api/v1/plugin/AgentResourceOfficer/assistant/readiness`
- `GET /api/v1/plugin/AgentResourceOfficer/assistant/startup`
- `GET /api/v1/plugin/AgentResourceOfficer/assistant/maintain`
- `GET /api/v1/plugin/AgentResourceOfficer/assistant/selfcheck`
- `GET /api/v1/plugin/AgentResourceOfficer/assistant/history`
- `POST /api/v1/plugin/AgentResourceOfficer/assistant/action`
- `POST /api/v1/plugin/AgentResourceOfficer/assistant/actions`
- `GET /api/v1/plugin/AgentResourceOfficer/assistant/workflow`
- `POST /api/v1/plugin/AgentResourceOfficer/assistant/workflow`
- `GET /api/v1/plugin/AgentResourceOfficer/assistant/sessions`
- `POST /api/v1/plugin/AgentResourceOfficer/assistant/sessions/clear`
- `GET /api/v1/plugin/AgentResourceOfficer/assistant/session`
- `POST /api/v1/plugin/AgentResourceOfficer/assistant/session`
- `POST /api/v1/plugin/AgentResourceOfficer/assistant/session/clear`
- `POST /api/v1/plugin/AgentResourceOfficer/session/hdhive/search`
- `POST /api/v1/plugin/AgentResourceOfficer/session/hdhive/pick`

## 当前可用 Agent Tool

- `agent_resource_officer_hdhive_search`
- `agent_resource_officer_hdhive_pick`
- `agent_resource_officer_smart_entry`
- `agent_resource_officer_smart_pick`
- `agent_resource_officer_help`
- `agent_resource_officer_capabilities`
- `agent_resource_officer_readiness`
- `agent_resource_officer_history`
- `agent_resource_officer_execute_action`
- `agent_resource_officer_execute_actions`
- `agent_resource_officer_run_workflow`
- `agent_resource_officer_route_share`
- `agent_resource_officer_sessions`
- `agent_resource_officer_sessions_clear`
- `agent_resource_officer_session_state`
- `agent_resource_officer_session_clear`
- `agent_resource_officer_p115_qrcode_start`
- `agent_resource_officer_p115_qrcode_check`
- `agent_resource_officer_p115_status`
- `agent_resource_officer_p115_pending`
- `agent_resource_officer_p115_resume_pending`
- `agent_resource_officer_p115_cancel_pending`

## 调用示例

### 1. 直接转存夸克分享

```json
POST /api/v1/plugin/AgentResourceOfficer/share/route
{
  "url": "https://pan.quark.cn/s/xxxx",
  "path": "/飞书",
  "apikey": "你的 MP API Token"
}
```

### 2. 直接转存 115 分享

```json
POST /api/v1/plugin/AgentResourceOfficer/share/route
{
  "url": "https://115cdn.com/s/xxxx?password=abcd",
  "path": "/待整理",
  "apikey": "你的 MP API Token"
}
```

### 3. 获取 115 扫码登录二维码

```text
GET /api/v1/plugin/AgentResourceOfficer/p115/qrcode?client_type=alipaymini&apikey=你的 MP API Token
```

拿到 `uid / time / sign` 后，继续轮询：

```text
GET /api/v1/plugin/AgentResourceOfficer/p115/qrcode/check?uid=...&time=...&sign=...&client_type=alipaymini&apikey=你的 MP API Token
```

扫码确认成功后，`Agent资源官` 会自动保存扫码会话，不需要再手动粘贴 Cookie。

### 4. 按关键词搜索影巢资源

```json
POST /api/v1/plugin/AgentResourceOfficer/hdhive/search_by_keyword
{
  "keyword": "蜘蛛侠",
  "media_type": "movie",
  "candidate_limit": 10,
  "limit": 12,
  "apikey": "你的 MP API Token"
}
```

### 5. 解锁影巢资源后自动落盘

```json
POST /api/v1/plugin/AgentResourceOfficer/hdhive/unlock_and_route
{
  "slug": "资源 slug",
  "path": "/待整理",
  "apikey": "你的 MP API Token"
}
```

### 6. 用会话方式完成“先选片，再选资源”

```json
POST /api/v1/plugin/AgentResourceOfficer/session/hdhive/search
{
  "keyword": "蜘蛛侠",
  "media_type": "movie",
  "path": "/待整理",
  "apikey": "你的 MP API Token"
}
```

返回 `session_id` 后，再继续：

```json
POST /api/v1/plugin/AgentResourceOfficer/session/hdhive/pick
{
  "session_id": "上一步返回的 session_id",
  "index": 1,
  "apikey": "你的 MP API Token"
}
```

第一次 `pick` 是选影片，第二次 `pick` 是选资源并自动解锁落盘。

为了便于飞书、智能体和 CLI 共用，这个接口同时兼容这些选项字段：

- `index`
- `choice`
- `selection`
- `number`

例如：

```json
POST /api/v1/plugin/AgentResourceOfficer/session/hdhive/pick
{
  "session_id": "上一步返回的 session_id",
  "choice": 1,
  "apikey": "你的 MP API Token"
}
```

### 7. 用统一智能入口直接调用

```json
POST /api/v1/plugin/AgentResourceOfficer/assistant/route
{
  "session": "demo-session",
  "text": "2蜘蛛侠",
  "apikey": "你的 MP API Token"
}
```

也支持：

```json
POST /api/v1/plugin/AgentResourceOfficer/assistant/route
{
  "session": "demo-session",
  "text": "ps大君夫人",
  "apikey": "你的 MP API Token"
}
```

或：

```json
POST /api/v1/plugin/AgentResourceOfficer/assistant/route
{
  "session": "demo-session",
  "text": "链接 https://pan.quark.cn/s/xxxx 位置=分享",
  "apikey": "你的 MP API Token"
}
```

外部智能体也可以直接走结构化参数，不必再拼中文命令：

```json
POST /api/v1/plugin/AgentResourceOfficer/assistant/route
{
  "session": "demo-session",
  "mode": "pansou",
  "keyword": "大君夫人",
  "apikey": "你的 MP API Token"
}
```

或者：

```json
POST /api/v1/plugin/AgentResourceOfficer/assistant/route
{
  "session": "demo-session",
  "url": "https://115cdn.com/s/xxxx?password=abcd",
  "path": "/待整理",
  "apikey": "你的 MP API Token"
}
```

继续选择时：

```json
POST /api/v1/plugin/AgentResourceOfficer/assistant/pick
{
  "session": "demo-session",
  "index": 1,
  "apikey": "你的 MP API Token"
}
```

在真正执行前，也推荐先探测统一入口能力：

```text
GET /api/v1/plugin/AgentResourceOfficer/assistant/capabilities?apikey=你的 MP API Token
```

从 `0.1.32` 开始，`assistant/route` 与 `assistant/pick` 的 `data` 会统一附带：

- `session`
- `session_id`
- `session_state`
- `next_actions`

这样外部智能体拿到回执后，就可以直接根据结构化字段判断当前阶段、可选编号、建议动作和待继续的 115 任务，不必再解析长文本提示。

从 `0.1.33` 开始，还新增了：

- `GET /assistant/sessions`
- `agent_resource_officer_sessions`

这样外部智能体在重启、断线或多会话并行时，可以先列出当前活跃会话，再决定恢复哪个 session 继续执行。

从 `0.1.34` 开始：

- `smart_entry / smart_pick / help / session / clear` 都支持直接传 `session_id`
- 新增 `POST /assistant/sessions/clear`
- 新增 `agent_resource_officer_sessions_clear`

这样外部智能体既可以按 `session_id` 精准恢复指定会话，也可以在需要时按类型、待继续 115 状态、过期状态或全量方式批量清理 assistant 会话。

从 `0.1.35` 开始，`session_state` 和统一回执又新增了：

- `protocol_version`
- `action_templates`

`action_templates` 会直接给出下一步可调用的 Tool / API / method / body 模板。外部智能体拿到回执后，不必再自己总结“下一步怎么调”，可以直接复用这些结构化模板继续执行。
从 `0.1.61` 开始，支持低 token 的 assistant 模板会自动在 `body` 和 `action_body` 中带上 `compact=true`，外部智能体原样回放即可得到精简回执。
从 `0.1.62` 开始，POST JSON 里的 `compact` 也会按布尔语义解析，`"false"`、`"0"`、`"off"` 不会再被误判为开启。
从 `0.1.63` 开始，`dry_run`、`stop_on_error`、`include_raw_results`、`prefer_unexecuted`、`all_plans`、`stale_only`、`all_sessions`、`execute` 等 POST 布尔字段也统一按同样规则解析。
从 `0.1.64` 开始，新增 `assistant/selfcheck`，用于快速确认 compact 模板、布尔解析和协议字段是否健康。
从 `0.1.65` 开始，`assistant/selfcheck` 也下沉为 MP 原生 Tool：`agent_resource_officer_selfcheck`。
从 `0.1.66` 开始，`assistant/pulse` 和 compact `assistant/capabilities` 会把 `assistant/selfcheck` 放进推荐启动链路，外部智能体开场即可先做协议自检。
从 `0.1.67` 开始，新增 `assistant/startup` 和 `agent_resource_officer_startup`，一次返回启动状态、自检结果、核心工具、端点、默认目录和恢复建议，减少外部智能体开场多次探测。
从 `0.1.68` 开始，`assistant/startup` 会直接携带恢复用的 `session` / `session_id` / `action_templates`，外部智能体拿到启动包后可直接执行推荐恢复动作。
从 `0.1.69` 开始，`assistant/startup` 增加 `maintenance` 计数，直接返回活跃会话、保存计划和待执行计划数量，便于外部智能体判断是否需要恢复或清理。
从 `0.1.70` 开始，`assistant/startup.maintenance` 增加低风险清理模板：清理过期会话、清理已执行计划；不会自动清理待执行计划。
从 `0.1.71` 开始，`assistant/plans?compact=true` 的 `total` 表示当前过滤条件命中的计划数，同时返回 `total_all`，避免把全部计划数误判为待执行计划数。
从 `0.1.72` 开始，`assistant/startup.maintenance` 增加 `stale_sessions`、`saved_plans_executed` 和 `recommended_actions`，外部智能体可直接判断当前是否值得做维护清理。
从 `0.1.73` 开始，新增 `assistant/maintain` 与 `agent_resource_officer_maintain`，支持 dry-run 查看低风险维护建议，也支持 `execute=true` 执行过期会话和已执行计划清理。
从 `0.1.74` 开始，`assistant/selfcheck` 会检查 `assistant/maintain` endpoint 和 `agent_resource_officer_maintain` Tool 是否已正确出现在工具清单中。
从 `0.1.75` 开始，`assistant/capabilities` 增加 `assistant_maintain` 字段说明，并把 `assistant/maintain` 纳入 compact endpoint 和推荐启动链路。
从 `0.1.76` 开始，`assistant/maintain` 的 GET 请求固定为 dry-run，即使带 `execute=true` 也不会执行清理；只有 POST `execute=true` 才会实际维护。

从 `0.1.36` 开始，还新增了：

- `POST /assistant/action`
- `agent_resource_officer_execute_action`

这样外部智能体不只可以“读模板”，还可以直接把 `action_templates` 里的 `name + action_body` 回传给 Agent资源官 执行，进一步减少上层自定义映射逻辑。

从 `0.1.37` 开始，还新增了：

- `POST /assistant/actions`
- `agent_resource_officer_execute_actions`

这样外部智能体可以一次提交多个 `action_body`，让 Agent资源官 在同一个请求里顺序执行多步动作。默认只返回精简执行摘要，进一步减少多次往返和上层 token 消耗；只有显式需要时才附带每一步原始返回。

例如：

```json
POST /api/v1/plugin/AgentResourceOfficer/assistant/actions
{
  "session": "demo-batch",
  "actions": [
    {
      "name": "start_pansou_search",
      "keyword": "大君夫人"
    },
    {
      "name": "pick_pansou_result",
      "choice": 1
    }
  ],
  "stop_on_error": true,
  "apikey": "你的 MP API Token"
}
```

从 `0.1.38` 开始，还新增了：

- `GET /assistant/workflow`
- `POST /assistant/workflow`
- `agent_resource_officer_run_workflow`

这样外部智能体可以直接按预设场景调用，不需要自己拼 `actions` 数组。当前内置工作流包括：

- `pansou_search`
- `pansou_transfer`
- `hdhive_candidates`
- `hdhive_unlock`
- `share_transfer`
- `p115_login_start`
- `p115_status`

例如：

```json
POST /api/v1/plugin/AgentResourceOfficer/assistant/workflow
{
  "session": "demo-workflow",
  "name": "pansou_transfer",
  "keyword": "大君夫人",
  "choice": 1,
  "apikey": "你的 MP API Token"
}
```

从 `0.1.39` 开始，还新增了：

- `GET /assistant/readiness`
- `agent_resource_officer_readiness`

这个接口是给外部智能体启动前使用的轻量探针，会返回插件版本、是否启用、115/影巢/夸克状态、活跃会话数量、推荐入口和启动提示。外部智能体可以先调它，看到 `can_start=true` 后再进入 `assistant/workflow` 或 `assistant/actions`。

从 `0.1.40` 开始，还新增了：

- `GET /assistant/history`
- `agent_resource_officer_history`

这个接口会记录最近的批量动作和预设工作流执行摘要，包括会话、动作名、成功状态、时间、简短结果和每步摘要。外部智能体在断线、超时或用户询问“刚才跑到哪了”时，可以先查它再决定是否继续、重试或清理会话。

从 `0.1.41` 开始，`POST /assistant/workflow` 支持 `dry_run=true`；从 `0.1.42` 开始，`dry_run` 会持久化计划并返回 `plan_id`：

- 只生成 `workflow_actions`
- 不实际搜索、解锁或转存
- 返回 `execute_body`，外部智能体确认后可原样改为 `dry_run=false` 执行
- 返回 `execute_plan_body`，外部智能体也可以只携带 `plan_id` 调用 `/assistant/plan/execute`

例如：

```json
POST /api/v1/plugin/AgentResourceOfficer/assistant/workflow?apikey=你的MP_API_TOKEN
{
  "session": "demo-plan",
  "name": "pansou_transfer",
  "keyword": "大君夫人",
  "choice": 1,
  "dry_run": true
}
```

随后可直接执行保存的计划：

```json
POST /api/v1/plugin/AgentResourceOfficer/assistant/plan/execute?apikey=你的MP_API_TOKEN
{
  "plan_id": "plan-..."
}
```

从 `0.1.43` 开始，保存计划也可以独立查询和清理；从 `0.1.56` 开始，计划列表支持 `compact=true` 低 token 回执：

- `GET /assistant/plans`：查看最近保存的计划，可按 `session`、`session_id`、`executed` 过滤
- `POST /assistant/plans/clear`：按 `plan_id`、会话、执行状态或 `all_plans=true` 清理计划
- `agent_resource_officer_plans`：MP 智能助手查看计划
- `agent_resource_officer_plans_clear`：MP 智能助手清理计划

常用查询：

```text
GET /api/v1/plugin/AgentResourceOfficer/assistant/plans?apikey=你的MP_API_TOKEN&executed=false&compact=true
```

清理单个计划：

```json
POST /api/v1/plugin/AgentResourceOfficer/assistant/plans/clear?apikey=你的MP_API_TOKEN
{
  "plan_id": "plan-..."
}
```

从 `0.1.44` 开始，`assistant/plan/execute` 还支持按会话自动恢复最近计划：

- 传 `plan_id`：精确执行指定计划
- 不传 `plan_id`，只传 `session` 或 `session_id`：默认优先执行该会话下最近一条“未执行”计划
- 如果该会话下没有未执行计划，会自动回退到最近一条计划，便于断线恢复

例如：

```json
POST /api/v1/plugin/AgentResourceOfficer/assistant/plan/execute?apikey=你的MP_API_TOKEN
{
  "session": "demo-plan"
}
```

从 `0.1.45` 开始，计划恢复动作会直接进入结构化回执：

- `assistant/session` 的 `session_state.saved_plan` 会显示当前会话最近计划
- 若存在待执行计划，`action_templates` 会包含 `execute_latest_plan`
- `assistant/readiness` 的 `saved_plans.action_templates` 会列出最近待执行计划的直接执行模板

从 `0.1.46` 开始，`execute_latest_plan` 和 `execute_plan` 也能通过 `assistant/action` 执行。外部智能体可以把模板里的 `action_body` 原样回传给：

```json
POST /api/v1/plugin/AgentResourceOfficer/assistant/action?apikey=你的MP_API_TOKEN
{
  "name": "execute_latest_plan",
  "session": "demo-plan",
  "prefer_unexecuted": true
}
```

从 `0.1.47` 开始，`assistant/sessions` 也会直接暴露计划恢复信号：

- 每个会话摘要会带 `has_pending_plan` 和最近计划摘要
- `assistant/sessions` 的 `action_templates` 会包含 `execute_session_latest_plan`
- 外部智能体拿到 `session_id` 后，可以直接按模板恢复该会话最近计划

从 `0.1.48` 开始，`assistant/sessions` 也会列出“只有计划、没有会话缓存”的 session：

- `dry_run` 之后即使还没产生会话状态，也能从 `assistant/sessions` 看到该 session
- 这类会话会显示为 `assistant_workflow_plan / planned`
- 外部智能体可以从会话列表直接恢复，不必先调用 `assistant/plans`

从 `0.1.49` 开始，恢复协议被提炼成统一结构字段：

- `assistant/session`、统一回执、`assistant/readiness`、`assistant/sessions` 都会带 `recovery`
- `recovery` 会明确给出当前最推荐的恢复模式、推荐动作、推荐 Tool 和可直接复用的 `action_template`
- `assistant/action` 现在也支持 `execute_session_latest_plan`，会话列表里的恢复模板可以原样回放

从 `0.1.50` 开始，`assistant/session` 与 `assistant/sessions` 也回到统一包裹形状：

- 返回里会有标准字段：`protocol_version / action / ok / session / session_id / session_state / next_actions / action_templates / recovery`
- 同时继续保留原有的会话摘要字段，避免已有调用方断掉
- 外部智能体现在可以把 `session / sessions / readiness / route / pick` 全部按同一套回执协议消费

从 `0.1.51` 开始，推荐把断线续跑统一交给 `assistant/recover`：

- `GET /assistant/recover`：只查看当前最推荐的恢复动作
- `POST /assistant/recover`：可传 `session` 或 `session_id` 精确检查，也可不传让插件从全局会话和计划里自动挑选
- `execute=true` 时会直接执行推荐动作，适合外部智能体把“刚才到哪了，继续”压成一个稳定入口
- 对应 MP 智能助手 Tool：`agent_resource_officer_recover`

示例：

```json
POST /api/v1/plugin/AgentResourceOfficer/assistant/recover?apikey=你的MP_API_TOKEN
{
  "session": "demo-plan",
  "execute": true
}
```

从 `0.1.52` 开始，`assistant/recover` 支持低 token 回执：

- 传 `compact=true` 时不会返回完整 `session_state` 和 `sessions`
- 只保留恢复模式、推荐动作、推荐 Tool、当前 session、最小 `action_templates`
- `agent_resource_officer_recover` 默认使用低 token 回执，适合外部智能体高频轮询

示例：

```text
GET /api/v1/plugin/AgentResourceOfficer/assistant/recover?apikey=你的MP_API_TOKEN&compact=true
```

从 `0.1.53` 开始，外部智能体启动前建议先调 `assistant/pulse`：

- 返回固定小结构：版本、启用状态、115/影巢/夸克关键状态、警告、最佳恢复建议
- 不返回完整会话列表，适合 WorkBuddy、飞书桥接、MP 智能助手每次开场快速探测
- 对应 MP 智能助手 Tool：`agent_resource_officer_pulse`

示例：

```text
GET /api/v1/plugin/AgentResourceOfficer/assistant/pulse?apikey=你的MP_API_TOKEN
```

从 `0.1.54` 开始，外部智能体初始化提示词可先读取 `assistant/toolbox`：

- 返回轻量工具清单：推荐启动顺序、关键端点、Tool 名、workflow 名、action 名、默认目录和命令示例
- 不返回会话状态，适合做系统提示或工具说明缓存
- 对应 MP 智能助手 Tool：`agent_resource_officer_toolbox`

示例：

```text
GET /api/v1/plugin/AgentResourceOfficer/assistant/toolbox?apikey=你的MP_API_TOKEN
```

从 `0.1.64` 开始，也可以调用轻量自检：

```text
GET /api/v1/plugin/AgentResourceOfficer/assistant/selfcheck?apikey=你的MP_API_TOKEN
```

对应 MP 智能助手 Tool：`agent_resource_officer_selfcheck`

从 `0.1.67` 开始，外部智能体更推荐先调用启动聚合包：

```text
GET /api/v1/plugin/AgentResourceOfficer/assistant/startup?apikey=你的MP_API_TOKEN
```

对应 MP 智能助手 Tool：`agent_resource_officer_startup`

从 `0.1.55` 开始，`assistant/session` 和 `assistant/sessions` 支持低 token 回执；从 `0.1.56` 开始，`assistant/history` 和 `assistant/plans` 也支持同样的精简模式；从 `0.1.57` 开始，`assistant/actions`、`assistant/workflow` 和 `assistant/plan/execute` 也支持 `compact=true`；从 `0.1.58` 开始，启动入口 `assistant/capabilities` 和 `assistant/readiness` 也支持 `compact=true`；从 `0.1.59` 开始，`assistant/action` 单动作执行也支持 `compact=true`；从 `0.1.60` 开始，`assistant/route` 和 `assistant/pick` 主交互链路也支持 `compact=true`；从 `0.1.61` 开始，`action_templates` 默认携带 `compact=true`：

- `compact=true` 时不会再嵌套完整 `session_state`
- `assistant/session` 返回当前会话阶段、恢复建议、待执行计划和待继续 115 任务摘要
- `assistant/sessions` 返回活跃会话列表摘要，适合外部智能体做会话选择
- `assistant/history` 返回最近执行动作、成功状态和简短结果
- `assistant/plans` 返回计划 ID、执行状态和可直接复用的执行模板
- `assistant/actions` 返回批量动作执行摘要
- `assistant/workflow` 的 dry_run 返回 plan_id 和执行模板，不再携带完整动作数组
- `assistant/plan/execute` 返回计划执行摘要，不再携带完整动作数组
- `assistant/capabilities` 返回能力、工作流和 Tool 名称清单
- `assistant/readiness` 返回服务布尔状态、待执行计划和恢复建议
- `assistant/action` 返回单动作执行摘要，适合 action_template 原样回放
- `assistant/route` 返回搜索、直链、115 状态等智能入口摘要
- `assistant/pick` 返回选择、详情、翻页、解锁落盘等继续处理摘要

示例：

```text
GET /api/v1/plugin/AgentResourceOfficer/assistant/capabilities?apikey=你的MP_API_TOKEN&compact=true
GET /api/v1/plugin/AgentResourceOfficer/assistant/readiness?apikey=你的MP_API_TOKEN&compact=true
GET /api/v1/plugin/AgentResourceOfficer/assistant/session?apikey=你的MP_API_TOKEN&session=default&compact=true
GET /api/v1/plugin/AgentResourceOfficer/assistant/sessions?apikey=你的MP_API_TOKEN&compact=true
GET /api/v1/plugin/AgentResourceOfficer/assistant/history?apikey=你的MP_API_TOKEN&compact=true
GET /api/v1/plugin/AgentResourceOfficer/assistant/plans?apikey=你的MP_API_TOKEN&compact=true
POST /api/v1/plugin/AgentResourceOfficer/assistant/route?apikey=你的MP_API_TOKEN
{"text":"盘搜搜索 大君夫人","compact":true}
POST /api/v1/plugin/AgentResourceOfficer/assistant/pick?apikey=你的MP_API_TOKEN
{"session":"default","choice":1,"compact":true}
POST /api/v1/plugin/AgentResourceOfficer/assistant/action?apikey=你的MP_API_TOKEN
{"name":"show_115_status","compact":true}
POST /api/v1/plugin/AgentResourceOfficer/assistant/workflow?apikey=你的MP_API_TOKEN
{"name":"p115_status","dry_run":true,"compact":true}
```
