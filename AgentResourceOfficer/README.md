# Agent资源官

这是重构中的新主插件目录，用来承接当前仓库里和“资源搜索、解锁、转存、签到、远程入口”相关的能力。

当前已经不是纯骨架，已经具备第一批可用 API，并且已经在实际 MoviePilot 运行环境里完成了健康检查与会话搜索回归。

- 夸克健康检查
- 夸克分享转存
- 115 依赖健康检查
- 115 分享转存
- 影巢健康检查
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

- 当前版本：`0.1.6`
- 已进入第一阶段可用状态
- 已验证 `影巢健康检查 / 夸克健康检查 / 影巢候选搜索 / 选片进入资源列表`
- 已接入第一批原生 `Agent Tool`
- `115` 自动转存层目前仍受 `P115StrmHelper` 与当前 MP 版本兼容性影响，需单独继续收口
- 飞书入口、签到与更完整的用户态能力仍会继续迁移进来

## 当前可用 API

以下接口已经接入：

- `GET /api/v1/plugin/AgentResourceOfficer/quark/health`
- `POST /api/v1/plugin/AgentResourceOfficer/quark/transfer`
- `GET /api/v1/plugin/AgentResourceOfficer/p115/health`
- `POST /api/v1/plugin/AgentResourceOfficer/p115/transfer`
- `GET /api/v1/plugin/AgentResourceOfficer/hdhive/health`
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

### 3. 按关键词搜索影巢资源

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

### 4. 解锁影巢资源后自动落盘

```json
POST /api/v1/plugin/AgentResourceOfficer/hdhive/unlock_and_route
{
  "slug": "资源 slug",
  "path": "/待整理",
  "apikey": "你的 MP API Token"
}
```

### 5. 用会话方式完成“先选片，再选资源”

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

### 6. 用统一智能入口直接调用

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
