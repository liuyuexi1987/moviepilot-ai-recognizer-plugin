# MoviePilot-Plugins

[![Release Preflight](https://github.com/liuyuexi1987/MoviePilot-Plugins/actions/workflows/ci.yml/badge.svg)](https://github.com/liuyuexi1987/MoviePilot-Plugins/actions/workflows/ci.yml)

这是一个面向 MoviePilot 的云盘资源整合插件仓库，重点解决 115 云盘、夸克云盘等资源从搜索、解锁、转存到固定目录的流程。资源来源主要围绕两类：`盘搜` 和 `影巢`。盘搜是独立的聚合搜索项目，需要用户自行部署 PanSou 服务并在插件里填写 API 地址；影巢通过 OpenAPI 提供影视资源搜索、解锁、签到和配额查询，填写自己的影巢 OpenAPI Key 后即可使用。当前主线不是堆很多独立小插件，而是把常用能力收拢成两类：

这个项目也为外部智能体做了大量适配工作。它不是让智能体直接拼接影巢、盘搜、115 或夸克的底层接口，而是提供统一入口、低 token 摘要、会话续接、编号选择、计划确认和错误恢复，让 WorkBuddy、Hermes、OpenClaw（小龙虾）等智能体可以用更少上下文完成搜索、展示、选择和转存流程。

- 新主线：`Agent影视助手`、`AI识别增强`，形成云盘资源搜索、转存到固定目录、识别增强和智能体入口流程；如果还需要 STRM、302 播放或媒体库全量/增量同步，再配合 `P115StrmHelper`。
- 旧插件区：保留飞书桥接、影巢 OpenAPI、影巢签到、夸克转存、极影视刷新等独立插件，方便老环境继续使用。

如果你是第一次使用，建议先看“新用户推荐方案”，不用一开始就装所有插件。

仓库文档入口：

```text
docs/INDEX.md
```

## 当前状态

- 当前推荐主线插件：`Agent影视助手`（插件 ID：`AgentResourceOfficer`）
- 当前发布版本：`0.2.68`
- 当前 Skill helper 版本：`0.1.42`
- 当前发布页：<https://github.com/liuyuexi1987/MoviePilot-Plugins/releases/tag/v0.2.68>
- 当前安装说明：[`docs/PLUGIN_INSTALL.md`](./docs/PLUGIN_INSTALL.md)
- 当前外部智能体接入：[`docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md`](./docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md)
- 当前跨机器部署：[`docs/AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md`](./docs/AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md)
- 当前维护入口：先看 [`docs/INDEX.md`](./docs/INDEX.md)；如需命令速查，直接看 [`docs/MAINTENANCE_COMMANDS.md`](./docs/MAINTENANCE_COMMANDS.md)；日常仓库维护运行 `bash scripts/repo-hygiene.sh`，发版前完整检查运行 `bash scripts/release-preflight.sh`

如果你只想快速落地，不要先看历史重构文档，直接从上面 4 个入口开始。

## 本阶段收口重点

- 搜索口径收口：
  - `搜索 <片名>` / `找 <片名>` 默认先走盘搜
  - `云盘搜索 <片名>` 固定走 `盘搜 + 影巢`
  - `影巢搜索 <片名>` 只走影巢
  - `MP搜索 <片名>` / `PT搜索 <片名>` 只走 MoviePilot 原生 PT
- 执行动作收口：
  - `转存 <片名>` 走云盘资源一条龙转存
  - `下载 <片名>` 走 MP/PT 直接下载
  - `夸克转存 <片名>` / `115转存 <片名>` 可强制指定目标网盘
- 更新入口收口：
  - 推荐使用 `更新检查 <片名>` / `检查 <片名>`
  - 统一展示官方参考进度、盘搜最新集资源、影巢最新集资源
- 维护入口收口：
  - `清空115转存目录`
  - `清空夸克转存目录`
  - `影巢签到`
  - `影巢签到日志`
  - `刷新影巢Cookie`
  - `修复影巢签到`
  - `刷新夸克Cookie`
  - `修复夸克转存`

## 当前推荐口令

优先使用这些固定口令，外部智能体和微信通道最稳：

- 搜索：
  - `搜索 <片名>` / `找 <片名>`
  - `盘搜搜索 <片名>`
  - `影巢搜索 <片名>`
  - `云盘搜索 <片名>`
  - `MP搜索 <片名>` / `PT搜索 <片名>`
- 执行：
  - `转存 <片名>`
  - `夸克转存 <片名>`
  - `115转存 <片名>`
  - `下载 <片名>`
- 更新：
  - `更新检查 <片名>`
  - `检查 <片名>`
- 维护：
  - `清空115转存目录`
  - `清空夸克转存目录`
  - `影巢签到`
  - `影巢签到日志`
  - `刷新影巢Cookie`
  - `修复影巢签到`
  - `刷新夸克Cookie`
  - `修复夸克转存`

## 当前已知坑位

- 外部智能体不要把 `云盘搜索` 偷换成 `盘搜搜索`。
  - `云盘搜索 = 盘搜 + 影巢`
  - 如果影巢标题不唯一，应该保留插件返回的“影巢候选未自动展开”提示，而不是直接吃掉影巢结果。
- 外部智能体不要把插件编号列表二次改写成“推荐资源 / 分析结论 / 要不要我帮你下载”。
  - 后续 `选择 7`、`选择 18 详情` 都依赖原始编号。
- `更新` 类请求优先使用：
  - `更新检查 <片名>`
  - `检查 <片名>`
  - 不要先清会话，不要先影巢候选，不要先网页搜索。
- 微信通道不要重新把各源编号从 `1` 开始排。
  - 影巢续接编号优先用 `#17 / #18 / #19` 这类格式，避免被微信重排成有序列表。
- 盘搜和影巢的职责不同：
  - 盘搜更适合看“最近日期 + 标题里的集数”
  - 影巢更适合看“当前资源文本里写到第几集”
- 夸克失败不要一律当成 Cookie 问题。
  - 只有明确提示 `require login [guest]`、`夸克登录态已过期`、`当前夸克登录态不足` 时，才建议执行 Cookie 修复。
  - `41031`、分享者封禁、分享受限属于链接问题，不属于 Cookie 失效。
- 影巢签到和资源 API 不是同一条链。
  - 资源 API 可用，不代表网页签到 Cookie 仍然有效。
  - 影巢签到失效时，优先使用本机导出工具自动写回，不建议手工复制 Cookie。
- `CookieCloud` 对夸克通常够用，但对影巢网页签到不一定够。
  - 影巢网页登录态需要更完整的 Cookie；当前标准恢复方式是导出工具，而不是手工抄 Cookie。
- 插件真实运行态要看容器里的实际加载目录。
  - 只改仓库源码、不同步到容器内真实插件目录时，微信和外部智能体仍可能打到旧逻辑。
- 根目录源码目录与 `plugins/`、`plugins.v2/` 不是“历史垃圾重复代码”，而是当前打包/发布镜像目录。
  - 日常开发优先修改根目录源码插件，再通过同步脚本或发版脚本把变更镜像到 `plugins/` 和 `plugins.v2/`。
  - 不建议手工只改镜像目录，也不建议把这三处贸然改成 symlink。

## 快速开始

1. 在 MoviePilot 插件市场添加这个仓库：

```text
https://github.com/liuyuexi1987/MoviePilot-Plugins
```

2. 新用户优先安装这两个插件：

```text
Agent影视助手
AI识别增强
```

3. `Agent影视助手` 可以独立完成搜索、解锁和转存到配置好的固定目录。如果你还需要 115 STRM、302 播放、媒体库整理或全量/增量同步，继续保留或安装 `P115StrmHelper`。

4. 在 `Agent影视助手` 里按需配置：

```text
影巢 OpenAPI Key
影巢资源入口开关与单资源积分上限
盘搜 API 地址
115 默认目录
夸克 Cookie 或 CookieCloud
飞书 App 信息（可选）
```

如果后面遇到影巢签到失效，不建议手工复制 Cookie。推荐恢复路径是：

```text
1. 在 Edge 登录 https://hdhive.com
2. 运行“影巢Cookie导出.command”自动写回
3. 再执行“影巢签到”或在插件页勾选“立即运行一次”
```

如果后面遇到夸克明确提示登录态失效，推荐恢复路径是：

```text
1. 在 Edge 登录 https://pan.quark.cn
2. 运行“夸克Cookie导出.command”自动写回
3. 再执行“修复夸克转存”或重试原来的夸克转存命令
```

5. 如果要接 WorkBuddy、OpenClaw（小龙虾）、Hermes 或其他外部智能体，把下面文档发给它，让它创建或安装自己的 Skill：

```text
docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md
docs/AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md
skills/agent-resource-officer/SKILL.md
skills/agent-resource-officer/EXTERNAL_AGENTS.md
```

如果 `MoviePilot` 不在当前机器，而是在 NAS、Windows 或另一台 Docker 主机上，先看：

```text
docs/AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md
```

重点不是换另一套方案，而是把 `ARO_BASE_URL`、盘搜地址和 Docker 网络视角配对。

## 常见部署：Win / Mac 跑智能体，NAS 跑 MP

这是当前很推荐的一种落地方式：

- `MoviePilot + Agent影视助手` 跑在 NAS
- `WorkBuddy / OpenClaw / 其他智能体` 跑在你的 Win / Mac 电脑

这套方式是支持的，关键只在于把“谁访问谁”分清楚。

### 一、资源命令怎么走

下面这些固定口令，都是：

- 智能体所在电脑发起
- 请求打到 NAS 上的 `MoviePilot + Agent影视助手`
- 真正的搜索、转存、签到、下载由 NAS 执行

```text
搜索 <片名>
盘搜搜索 <片名>
影巢搜索 <片名>
云盘搜索 <片名>
MP搜索 <片名>
PT搜索 <片名>
转存 <片名>
夸克转存 <片名>
115转存 <片名>
下载 <片名>
更新检查 <片名>
检查 <片名>
```

### 二、Cookie 修复命令怎么走

下面这些命令和普通资源命令不一样：

```text
刷新影巢Cookie
修复影巢签到
刷新夸克Cookie
修复夸克转存
```

它们会：

1. 从**智能体所在电脑本机浏览器**读取 Cookie
2. 写回 NAS 上的 `MoviePilot / Agent影视助手`
3. 必要时重启 `moviepilot-v2`
4. 再补跑签到或重试夸克检查

所以这类修复链的前提是：

- 你先在 **Win / Mac 本机浏览器** 登录对应站点
- 再让智能体执行修复命令

不是让 NAS 自己去读浏览器 Cookie。

### 三、最容易填错的两个地址

1. `ARO_BASE_URL`

这是**智能体所在电脑**访问 NAS 上 MP 的地址，例如：

```text
ARO_BASE_URL=http://192.168.31.61:3000
```

只有当智能体和 MP 在同一台机器时，才应该写：

```text
ARO_BASE_URL=http://127.0.0.1:3000
```

2. `盘搜 API 地址`

这是 **MoviePilot 容器** 去访问盘搜服务的地址。

也就是说：

- `ARO_BASE_URL` 按智能体电脑视角填
- `盘搜 API 地址` 按 MP 容器视角填

这两个视角不要混。

### 四、推荐使用方式

如果你是：

- Win / Mac 日常用 WorkBuddy / OpenClaw
- NAS 上跑 MP

推荐心智就是：

- 资源命令：远程调用 NAS 上 MP
- Cookie 修复：借用本机浏览器登录态，再写回 NAS

如果要看完整接法和排错细节，直接继续看：

- [`docs/AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md`](./docs/AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md)

## 新用户推荐方案

### 方案 A：外部智能体配合

推荐安装：

- `AgentResourceOfficer`：Agent影视助手
- `AIRecognizerEnhancer`：AI识别增强
- `P115StrmHelper`：115 STRM、302、全量/增量同步和媒体库底层能力，来自你的 MoviePilot 插件环境或对应插件仓库

适合场景：

- 你主要使用 WorkBuddy、OpenClaw（小龙虾）、Hermes 或其他更强的外部智能体。
- 希望智能体理解自然语言、展示候选、让你选编号，再调用 MoviePilot 执行。
- 希望能力可以复现到其他机器，而不是只靠聊天记录。

推荐做法：

- 让外部智能体阅读 [外部智能体接入范式](./docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md)。
- 让它创建或安装自己的 `agent-resource-officer` Skill。
- 外部智能体只负责理解需求和展示结果，不直接调用影巢、盘搜、115、夸克底层接口。
- 所有资源动作统一调用 `Agent影视助手` 的 `route` / `pick` / `startup`。

典型链路：

```text
用户 -> 外部智能体 -> Agent影视助手 -> 影巢/盘搜/115/夸克 -> MoviePilot/P115StrmHelper
```

### 方案 B：MP 内置智能体配合

推荐安装：

- `AgentResourceOfficer`
- `AIRecognizerEnhancer`
- `P115StrmHelper`

适合场景：

- 你想尽量留在 MoviePilot 内部生态。
- 你已经把 TG、企业微信、微信、通知渠道或其他消息入口接到了 MoviePilot。
- 你希望通过 MP 内置智能助手 / Agent Tool 调用插件能力。

工作方式：

- 先在 MoviePilot 设置里开启智能助手 / Agent 相关功能。
- 在 MoviePilot 的智能设置里填写可用的 LLM API 信息，包括接口地址、API Key 和模型名。
- 确认 MP 智能助手能正常对话或调用工具后，再启用 `Agent影视助手`。
- `Agent影视助手` 会注册 MoviePilot 原生 Agent Tool。
- MP 内置智能体可以直接调用插件的搜索、选择、115 登录、待任务、飞书健康检查等工具。
- TG / 企业微信这类入口本质上是把消息送进 MoviePilot，再由 MP 内置智能体或插件工具执行。
- 这种方式不需要外部智能体自己维护 Skill，但智能理解能力取决于 MP 当前配置的 LLM 和 Agent 能力。

适合命令：

```text
搜索 蜘蛛侠
盘搜搜索 大君夫人
影巢搜索 蜘蛛侠
115状态
115登录
链接 https://pan.quark.cn/s/xxxx path=/飞书
```

注意：

- 如果你已经有 WorkBuddy、OpenClaw（小龙虾）这类更强的外部智能体，方案 A 通常更灵活。
- 如果你只想用 MP 自带入口，不想维护外部 Skill，方案 B 更省心。

### 方案 C：不用智能体，直接用飞书 Channel

推荐安装：

- `AgentResourceOfficer`
- 可选：`P115StrmHelper`

适合场景：

- 你不想接外部智能体，也不想依赖 MP 内置智能体。
- 你只想在飞书里发固定命令，让插件直接回复结果。
- 家庭或个人使用场景里，飞书就是一个远程控制面板。

工作方式：

- 在 `Agent影视助手` 设置页开启内置飞书 Channel。
- 填入飞书 App ID、App Secret、白名单和回复 ID 类型。
- 飞书消息直接进入插件，由插件解析命令并回复。
- 老 `FeishuCommandBridgeLong` 不必同时开启，避免同一个飞书 App 被两个长连接入口监听。

适合命令：

```text
MP搜索 蜘蛛侠
ps大君夫人
yc蜘蛛侠
选择 1
详情
下一页
115登录
检查115登录
链接 https://115cdn.com/s/xxxx path=/待整理
链接 https://pan.quark.cn/s/xxxx path=/飞书
```

### 基础分工

不管选 A、B 还是 C，底层分工都一样：

- `Agent影视助手` 负责资源入口和执行编排。
- `AI识别增强` 负责识别失败后的本地 LLM 兜底和规则建议。
- `P115StrmHelper` 是可选的媒体库基础设施，负责 115 STRM、302、全量/增量同步、失效清理等能力。

`Agent影视助手` 和 `P115StrmHelper` 不是强绑定关系。更准确的理解是：

```text
Agent影视助手 = 资源入口和智能体/飞书/工具调度层
AI识别增强 = 识别失败后的兜底和规则建议层
P115StrmHelper = 115 媒体库基础设施层
```

本插件脱离 `P115StrmHelper` 也可以使用。它的核心职责是把资源保存到你配置的固定目录；只有当你希望这些资源继续生成 STRM、走 302 播放、进入媒体库整理或执行全量/增量同步时，才需要配合 `P115StrmHelper`。

### 轻量单点方案

只想做影巢签到：

- 安装 `HDHiveDailySign`
- 不需要安装本插件

只想独立转存夸克分享：

- 安装 `QuarkShareSaver`
- 如果已经使用本插件，优先让本插件统一调用夸克转存能力

已经有旧飞书桥接并且不想迁移：

- 可以继续保留 `FeishuCommandBridgeLong`
- 新用户建议优先用 `Agent影视助手` 内置飞书 Channel
- 同一个飞书 App 不建议同时开启两个长连接入口

## 第一块：新主线插件

### Agent影视助手

插件 ID：

- `AgentResourceOfficer`

当前版本：

- `0.2.68`

它是这个仓库当前最推荐的新入口。它负责把资源相关请求统一收口：

- 影巢搜索、候选选片、资源解锁、签到和配额查询
- 影巢资源入口可单独关闭，单资源积分上限默认 20 分，避免外部智能体误解锁高积分资源
- 新会话默认评分策略可在插件设置里统一调整，包括 PT 最低做种数、建议确认分数线、自动入库分数线和默认自动化开关
- 搜索与推荐结果里的 `score_summary` 现在会统一附带 `decision`，外部智能体可直接读取推荐命令和确认提示，不必自己拼下一步话术
- 写入动作之后的执行回执、统一后续追踪和本地/PT 诊断现在会统一附带 `followup_summary`，用于稳定续接“下载后看哪里、订阅后查哪里、转存后看哪里”
- `score_summary.decision` 和 `followup_summary` 现在都会给出 `preferred_command`、`fallback_command` 与 `compact_commands`，方便外部智能体优先读短命令，不必自己裁剪提示词
- `request_templates` 现在也会直接附带外部智能体执行契约与最小循环，方便新接入的智能体少读文档、直接起步
- `request_templates` 现在还会附带 `entry_playbooks`，把外部智能体、MP 内置智能体、飞书入口各自该调什么 helper/API/Tool 直接列出来
- 盘搜搜索，115 和夸克分组展示
- 盘搜和影巢资源列表支持 `最佳片源` 只读查看当前最高评分候选，`选择 1 详情` 查看指定资源详情；不会因为没有编号而误执行转存或解锁
- 盘搜和影巢资源列表支持 `计划选择 1` 先生成 `plan_id`，确认后才转存或解锁
- 盘搜和影巢资源列表底部会优先提示 `计划选择`，方便外部智能体默认走安全确认链路
- 115 分享链接识别、扫码登录、直转、待任务恢复
- 夸克分享链接识别与转存
- MP 原生搜索、下载、订阅和热门推荐调度
- 外部智能体可直接通过 `assistant/request_templates` 拉 `mp_pt_mainline` 与 `mp_recommendation` 两组低 token 模板，不需要自己猜 workflow body
- 外部智能体也可以拉 `local_ingest` 模板组，直接接入“下载后有没有入库、卡在哪一步、失败原因是什么”的只读诊断链
- MP 热门推荐支持按编号继续进入 MP 原生搜索、影巢或盘搜，适合智能体从推荐片单继续推进到资源搜索
- 推荐列表支持自然语言选择后续来源，例如 `选择 1 盘搜`、`选择1影巢`、`选 2 mp`
- MP 搜索结果支持 `下载1`、`下载第1个`、`订阅蜘蛛侠`、`订阅并搜索蜘蛛侠` 等自然写法，默认只生成 `plan_id`，确认后才执行
- MP 下载任务支持 `下载任务`、`暂停下载 1`、`恢复下载 1`、`删除下载 1`；任务控制默认生成 `plan_id`，确认后才操作下载器
- MP 本地/PT 跟踪链现在有更短的自然语言入口：`记录 片名`、`状态 片名`、`入库 片名`、`诊断 片名`、`最近`、`后续`
- 统一跟进入口支持 `跟进` 和 `跟进 片名`：有已执行计划时自动追执行后状态；有片名时直接走生命周期；都没有时退回最近活动
- `记录 片名` 会按 hash 关联下载历史与整理状态，方便判断资源是否已经进入落库流程
- `状态 片名` 会一次汇总下载任务、下载历史和整理/入库历史
- `入库 片名`、`诊断 片名`、`最近` 会统一输出结构化 `diagnosis_summary`，外部智能体可以少带说明词，直接走短命令
- MP 原生媒体识别支持 `识别 片名`，用于让智能体先确认 MoviePilot 的标题、年份、类型和 TMDB/Douban/IMDB 信息
- MP 原生搜索后支持 `选择 1` 查看 PT 详情、评分理由和风险，再决定是否执行 `下载1`
- MP 原生搜索后支持 `最佳片源` 或 `mp_search_best` 直接查看当前评分最高的 PT 候选，减少智能体自行读列表的 token
- MP 原生搜索后支持 `下载最佳`，按当前最高分候选生成下载计划，仍需确认 `plan_id`
- PT 主线当前统一走计划确认链路：即使评分很高，`下载1` 和 `下载最佳` 也默认先生成 `plan_id`，由用户确认后再真正提交
- 已生成的下载、订阅和控制计划支持自然语言确认：`执行计划` 执行当前会话最近待执行计划，`执行 plan-xxx` 精确执行指定计划
- PT 环境诊断支持 `站点状态`、`下载器状态`，只返回脱敏摘要，便于判断站点启用、Cookie 是否存在和下载器绑定情况
- MP 订阅支持 `订阅列表`、`搜索订阅 1`、`暂停订阅 1`、`恢复订阅 1`、`删除订阅 1`；订阅控制默认生成 `plan_id`
- MP 整理/入库历史支持 `入库历史`、`入库失败 片名`，用于判断下载后是否已经落库，结果只返回路径摘要
- 热门探索支持自然语言入口，例如“看看最近有什么热门影视”“豆瓣热门电影”“今日番剧”
- 智能体偏好画像，以及云盘 / PT 分源评分和自动化建议
- 偏好画像支持自然语言主入口：`偏好` 查看当前偏好，`保存偏好 4K 杜比 HDR 中字 全集 做种>=3 影巢积分20 不自动入库` 写入偏好，`重置偏好` 恢复首次询问
- 外部智能体接入时可以直接拉 `preferences_onboarding` 模板组，固定走“读取偏好 -> 读取评分策略 -> 保存偏好”的低 token 首次接入流程
- `评分策略` 现在也有独立只读入口，外部智能体可以直接读取硬门槛、软提醒和 `score_summary` 约定，不必把规则硬编码进提示词
- 可选内置飞书 Channel
- 给 MP 智能助手、外部智能体、WorkBuddy、OpenClaw（小龙虾）、Hermes 使用的统一 API 和 Skill 范式

典型用法：

```text
2蜘蛛侠
yc蜘蛛侠
1大君夫人
ps大君夫人
链接 https://pan.quark.cn/s/xxxx path=/飞书
链接 https://115cdn.com/s/xxxx path=/待整理
选择 1
计划选择 1
执行计划
详情
下一页
115登录
115状态
```

推荐目录约定：

- 115 默认转存目录：`/待整理`
- 夸克默认转存目录：`/飞书`
- 也可以在指令里写 `path=/目录` 或 `位置=目录`

和 `P115StrmHelper` 的关系：

- 本插件可以处理 115 分享链接、发起扫码登录、尝试轻量直转。
- 本插件脱离 `P115StrmHelper` 也能把资源保存到配置好的固定目录。
- 本插件不负责 STRM 生成、302 播放、媒体库全量/增量同步。
- 如果需要 STRM、302 播放或媒体库同步，这些底层工作仍建议交给 `P115StrmHelper`。

如果升级 MoviePilot 后 `P115StrmHelper` 因旧事件导入失败无法加载，可以尝试仓库里的兼容脚本：

```bash
MP_CONTAINER=moviepilot-v2 ./scripts/patch-p115strmhelper-mp-compat.sh
```

详细说明：

- [AgentResourceOfficer/README.md](./AgentResourceOfficer/README.md)
- [外部智能体接入范式](./docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md)
- [agent-resource-officer Skill](./skills/agent-resource-officer/README.md)

### AI识别增强

插件 ID：

- `AIRecognizerEnhancer`

当前版本：

- `0.1.11`

它负责 MoviePilot 原生识别失败后的兜底。和旧版 AI Gateway 不同，它更偏向直接复用 MoviePilot 当前 LLM 配置，在 MP 内部完成结构化识别。

主要能力：

- 原生识别失败后结构化推断标题、年份、类型、季集
- 失败样本记录、摘要、洞察、清理
- 按失败样本生成自定义识别词建议
- 批量复查、批量建议、批量写入
- 模型异常时尽量退回精确规则兜底

适合场景：

- 动画、冷门剧、长篇连载识别不稳
- 发布组把季集写错
- 标题拼写或干扰词导致 TMDB 误识别
- 想把 AI 识别和 MoviePilot 原生 CustomIdentifiers 闭环起来

详细说明：

- [AIRecognizerEnhancer/README.md](./AIRecognizerEnhancer/README.md)

### 外部智能体和 Skill

如果你想让 WorkBuddy、OpenClaw（小龙虾）、Hermes、微信侧智能体或其他外部智能体来控制 Agent影视助手，推荐不要只发一段聊天提示词，而是让它读仓库后创建或安装自己的 `agent-resource-officer` Skill。

最小复现流程：

```bash
git clone https://github.com/liuyuexi1987/MoviePilot-Plugins.git
cd MoviePilot-Plugins
bash skills/agent-resource-officer/install.sh --dry-run
bash skills/agent-resource-officer/install.sh
```

配置连接信息：

```text
~/.config/agent-resource-officer/config
```

示例：

```text
ARO_BASE_URL=http://127.0.0.1:3000
ARO_API_KEY=your_moviepilot_api_token
```

注意：

- `ARO_BASE_URL` 必须是外部智能体所在环境能访问到的 MoviePilot 地址。
- 同机可以用 `http://127.0.0.1:3000`。
- 容器、局域网或公网部署时，要换成对应可访问地址。
- 不要把 API Key、Cookie、Token 写进普通聊天或公开 Skill 文档。

验证：

```bash
python3 <SKILL_HOME>/agent-resource-officer/scripts/aro_request.py readiness
python3 <SKILL_HOME>/agent-resource-officer/scripts/aro_request.py external-agent
python3 <SKILL_HOME>/agent-resource-officer/scripts/aro_request.py selftest
```

给外部智能体的核心原则：

```text
资源搜索、影巢解锁、115/夸克转存、115 登录状态都调用 Agent影视助手。
不要直接调用影巢、盘搜、115、夸克底层 API。
搜索走 route，编号选择走 pick，同一个用户或群聊固定使用 agent:会话ID。
```

## 第二块：旧插件和兼容插件

这些插件仍然保留，适合已有环境、单点能力或兼容需求。新用户不一定都要安装。

### AI 识别转发

插件 ID：

- `AIRecoginzerForwarder`

当前版本：

- `2.0.1`

作用：

- MoviePilot 原生识别失败后，把标题和路径转发给外部 AI Gateway
- Gateway 完成识别后回调 MoviePilot
- 插件继续触发二次整理

适合场景：

- 已经部署了外部 AI Gateway
- 暂时不想切换到 `AIRecognizerEnhancer`

相关仓库：

- [moviepilot-ai-recognizer-gateway](https://github.com/liuyuexi1987/moviepilot-ai-recognizer-gateway)

详细说明：

- [AIRecoginzerForwarder/README.md](./AIRecoginzerForwarder/README.md)

### 飞书命令桥接

插件 ID：

- `FeishuCommandBridgeLong`

当前版本：

- `0.5.26`

定位：

- 旧飞书长连接兼容入口
- 保留已有用户熟悉的飞书命令体验
- 新用户优先使用 `Agent影视助手` 内置飞书 Channel

适合场景：

- 已经装好旧飞书桥接
- 暂时不想迁移到插件内置飞书
- 需要保留一个独立备份入口

注意：

- 同一个飞书 App 不建议同时被 `FeishuCommandBridgeLong` 和 `Agent影视助手` 内置飞书入口监听。
- 如果你是新环境，建议只开插件内置飞书入口。

详细说明：

- [FeishuCommandBridgeLong/README.md](./FeishuCommandBridgeLong/README.md)

### 影巢 OpenAPI

插件 ID：

- `HdhiveOpenApi`

当前版本：

- `0.3.0`

作用：

- 对接影巢 OpenAPI
- 支持用户信息、签到、资源搜索、资源解锁、115 转存、分享管理、配额查询

当前建议：

- 新的智能体和飞书主线优先使用 `Agent影视助手`。
- 如果你只想单独使用影巢 OpenAPI 插件，也可以继续安装 `HdhiveOpenApi`。

详细说明：

- [HdhiveOpenApi/README.md](./HdhiveOpenApi/README.md)
- [hdhive-search-unlock-to-115 Skill](./skills/hdhive-search-unlock-to-115/README.md)

### HDHive Daily Sign

插件 ID：

- `HDHiveDailySign`

当前版本：

- `1.0.0`

作用：

- 自动完成影巢每日签到
- 支持普通签到、赌狗签到、失败重试、自动登录、历史记录

当前建议：

- 只想轻量签到：用 `HDHiveDailySign`
- 已经使用本插件：也可以直接在 `Agent影视助手` 内开启影巢签到
- OpenAPI 签到需要 Premium 时，网页 Cookie / 账号密码兜底更适合放在签到插件或插件签到页配置

来源说明：

- 这是基于原作者 `madrays` 的影巢签到插件整理出来的自用魔改版
- 如果更想跟进原版更新，推荐关注原作者仓库：[madrays/MoviePilot-Plugins](https://github.com/madrays/MoviePilot-Plugins)

详细说明：

- [HDHiveDailySign/README.md](./HDHiveDailySign/README.md)

### 夸克分享转存

插件 ID：

- `QuarkShareSaver`

当前版本：

- `0.1.0`

作用：

- 把夸克分享链接转存到自己的夸克网盘目录
- 目录不存在时自动创建
- 给智能体、飞书桥接或其他插件提供稳定执行入口

当前建议：

- 新主线优先通过 `Agent影视助手` 调用夸克转存
- 如果只需要单独转存夸克分享，可以独立使用 `QuarkShareSaver`

详细说明：

- [QuarkShareSaver/README.md](./QuarkShareSaver/README.md)

### 极影视刷新（自用魔改）

插件 ID：

- `ZspaceMediaFreshMix`

当前版本：

- `1.0.0`

作用：

- 根据 MoviePilot 最近入库记录刷新极影视分类
- 兼容电影和电视剧混在同一个极影视分类
- 兼容新版极空间 Cookie 字段

来源说明：

- 这是基于原作者 `gxterry` 刷新极影视插件整理出来的自用魔改版
- 如果更想跟进原版更新，推荐关注原作者仓库：[gxterry/MoviePilot-Plugins](https://github.com/gxterry/MoviePilot-Plugins)

详细说明：

- [ZspaceMediaFreshMix/README.md](./ZspaceMediaFreshMix/README.md)

## 安装方式

这个仓库支持 MoviePilot 自定义插件仓库结构：

- `package.json`
- `package.v2.json`
- `plugins/`
- `plugins.v2/`

最新 Release：

- [v2026.04.28.2](https://github.com/liuyuexi1987/MoviePilot-Plugins/releases/tag/v2026.04.28.2)

常用文档：

- [插件安装说明](./docs/PLUGIN_INSTALL.md)
- [GitHub 发布说明](./docs/GITHUB_PUBLISH.md)
- [ZIP 打包说明](./docs/PACKAGING.md)
- [Release Checklist](./docs/RELEASE_CHECKLIST.md)

本地验证：

```bash
python3 scripts/smoke-agent-resource-officer.py
bash scripts/check-skills.sh
bash scripts/verify-skill-dist.sh
```

如果要连真实搜索链路：

```bash
python3 scripts/smoke-agent-resource-officer.py --include-search
```

## 仓库结构

```text
package.json
package.v2.json
icons/
plugins/
plugins.v2/
skills/
AIRecoginzerForwarder/
AIRecognizerEnhancer/
AgentResourceOfficer/
FeishuCommandBridgeLong/
HdhiveOpenApi/
HDHiveDailySign/
QuarkShareSaver/
ZspaceMediaFreshMix/
docs/
scripts/
```

说明：

- `plugins/` 和 `plugins.v2/` 是 MoviePilot 插件仓库实际读取目录。
- 根目录同名插件目录用于主源码、README 和补充文档。
- `skills/` 放公开 Skill 模板，主要给外部智能体复现工作流。

## 一句话总结

新用户优先从这三个能力开始：

- `Agent影视助手`：资源和智能体统一入口
- `AI识别增强`：识别失败后的本地 LLM 兜底
- `P115StrmHelper`：115 STRM、302 和媒体库基础设施

旧插件继续保留，但更多是兼容、轻量单点能力或已有环境迁移使用。
