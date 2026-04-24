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

- 当前版本：`0.1.15`
- 已进入第一阶段可用状态
- 已验证 `影巢健康检查 / 夸克健康检查 / 影巢候选搜索 / 选片进入资源列表`
- 已接入第一批原生 `Agent Tool`
- 已补齐 115 扫码登录原生 `Agent Tool`
- 智能入口现已直接支持 `115登录` / `检查115登录`
- 登录成功后会直接回显 115 可用状态、默认目录和当前会话来源
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
- `POST /api/v1/plugin/AgentResourceOfficer/session/hdhive/search`
- `POST /api/v1/plugin/AgentResourceOfficer/session/hdhive/pick`

## 当前可用 Agent Tool

- `agent_resource_officer_hdhive_search`
- `agent_resource_officer_hdhive_pick`
- `agent_resource_officer_route_share`
- `agent_resource_officer_p115_qrcode_start`
- `agent_resource_officer_p115_qrcode_check`

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

继续选择时：

```json
POST /api/v1/plugin/AgentResourceOfficer/assistant/pick
{
  "session": "demo-session",
  "index": 1,
  "apikey": "你的 MP API Token"
}
```
