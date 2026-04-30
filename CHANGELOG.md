# Changelog

## 当前主线

- 仓库已经从单一 AI Gateway 插件，收拢为 MoviePilot 资源与智能体插件套件。
- 当前发布前检查覆盖 8 个可本地安装插件：
  `AIRecoginzerForwarder`、`AIRecognizerEnhancer`、`AgentResourceOfficer`、`FeishuCommandBridgeLong`、`HdhiveOpenApi`、`HDHiveDailySign`、`QuarkShareSaver`、`ZspaceMediaFreshMix`。
- `AgentResourceOfficer` 已作为新资源主入口，负责影巢、盘搜、115、夸克、内置飞书入口和智能体 Tool 的统一路由。
- `FeishuCommandBridgeLong` 继续保留为兼容/备份入口，新用户优先使用 `AgentResourceOfficer` 内置飞书 Channel。
- `AIRecognizerEnhancer` 作为新识别增强线，逐步替代旧网关转发链路。
- 发布流程已补齐 `plugins/`、`plugins.v2/` 同步、元数据校验、语法检查、ZIP 打包和 GitHub Actions CI。

## 当前核心版本

- `AIRecoginzerForwarder`: `2.0.1`
- `AIRecognizerEnhancer`: `0.1.11`
- `AgentResourceOfficer`: `0.2.31`
- `FeishuCommandBridgeLong`: `0.5.26`
- `HdhiveOpenApi`: `0.3.0`
- `HDHiveDailySign`: `1.0.0`
- `QuarkShareSaver`: `0.1.0`
- `ZspaceMediaFreshMix`: `1.0.0`

## 近期基础设施更新

- `AgentResourceOfficer 0.2.31`：收紧 compact 协议中的评分摘要返回；普通站点、下载器、任务诊断不再继承上一轮搜索的 `score_summary`，避免外部智能体误读上下文。
- `AgentResourceOfficer 0.2.30`：细化评分风险结构；`hard_risk_reasons` 表示真正阻断自动化的风险，`risk_reasons` 保留为确认前提醒，避免软提醒被误算为阻断。
- `AgentResourceOfficer 0.2.29`：收口 MP 原生 PT 主线；补齐做种/热度/字幕/站点等评分理由，下载/订阅/控制统一走 `plan_id` 确认链路，并强化 MP 原生推荐续接。
- `AgentResourceOfficer 0.2.28`：插件展示名统一改为 `Agent影视助手`，并同步仓库文档、Skill 文案和兼容插件引用。
- `AgentResourceOfficer 0.2.27`：优化盘搜和影巢资源列表的下一步提示；默认引导外部智能体先生成计划，再确认执行。
- `AgentResourceOfficer 0.2.26`：新增云盘写入计划入口；盘搜和影巢资源可用“计划选择 1”先生成 `plan_id`，再确认执行。
- `AgentResourceOfficer 0.2.25`：修复云盘会话最佳/详情选择安全；盘搜和影巢资源阶段的“最佳片源”只展示详情，不会误选最后一条执行。
- `AgentResourceOfficer 0.2.24`：补齐 PT 下载自动化闭环；仅在用户开启自动入库且评分达标、无硬风险时，下载选择和下载最佳才会直接提交。
- `AgentResourceOfficer 0.2.23`：新增偏好画像自然语言入口；可用“偏好”“保存偏好 ...”“重置偏好”查看、保存或重置智能体片源偏好。
- `AgentResourceOfficer 0.2.22`：新增计划确认自然语言入口；可用“执行计划”或“执行 plan-xxx”确认执行已生成的下载、订阅或控制计划。
- `AgentResourceOfficer 0.2.21`：新增“下载最佳”入口；在 MP 搜索会话中按最高评分 PT 候选生成下载计划，仍需用户确认 `plan_id` 后才会下载。
- `AgentResourceOfficer 0.2.20`：新增 MP 搜索最佳候选详情入口；智能体可用“最佳片源”或 `mp_search_best` 直接查看当前评分最高 PT 候选。
- `AgentResourceOfficer 0.2.19`：新增 MP 搜索结果详情入口；MP 搜索后“选择 1”会先展示 PT 详情、评分理由和风险，再由用户确认是否下载。
- `AgentResourceOfficer 0.2.18`：新增 MP 原生媒体识别详情入口；智能体可用“识别 片名”或 `mp_media_detail` 工作流确认 TMDB/Douban/IMDB 信息后再搜索、下载或订阅。
- `AgentResourceOfficer 0.2.17`：新增 MP 生命周期追踪聚合入口；智能体可用“追踪 片名”一次查看下载任务、下载历史和整理/入库历史。
- `AgentResourceOfficer 0.2.16`：新增 MP 下载历史查询，并按 hash 关联整理/入库状态；智能体可用“下载历史 片名”追踪资源是否已提交下载和是否落库。
- `AgentResourceOfficer 0.2.15`：新增 MP 整理/入库历史查询；智能体可用“入库历史”“入库失败 片名”判断下载后是否已落库，接口只返回脱敏摘要。
- `AgentResourceOfficer 0.2.14`：新增 MP 订阅列表查询与订阅控制计划；智能体可查看订阅规则，并对搜索、暂停、恢复、删除订阅生成 `plan_id` 后确认执行。
- `AgentResourceOfficer 0.2.13`：新增 MP 下载器与 PT 站点环境诊断入口；只返回启用状态、优先级、绑定下载器和 Cookie 是否存在，不暴露 Cookie 明文。
- `AgentResourceOfficer 0.2.12`：补齐 MP 原生下载任务查询与任务控制入口；智能体可查看下载中任务，并对暂停、恢复、删除生成 `plan_id` 后确认执行。
- `AgentResourceOfficer 0.2.11`：MP 下载/订阅命令支持无空格自然写法，例如“下载1”“下载第1个”“订阅蜘蛛侠”“订阅并搜索蜘蛛侠”；自然语言写入默认生成 `plan_id`，确认后才执行。
- `AgentResourceOfficer 0.2.10`：推荐列表选择支持自然语言指定后续来源，例如“选择 1 盘搜”“选择1影巢”“选 2 mp”，飞书与智能体可不用结构化 mode 参数。
- `AgentResourceOfficer 0.2.09`：热门推荐入口支持自然语言别名，例如“看看最近有什么热门影视”“豆瓣热门电影”“正在热映”“今日番剧”，智能体和飞书可直接用人话触发 MP 推荐。
- `AgentResourceOfficer 0.2.08`：MP 热门推荐列表支持保存会话并按编号继续搜索，智能体可把推荐条目直接转入 MP 原生搜索、影巢或盘搜。
- `AgentResourceOfficer 0.2.07`：影巢搜索默认使用自动媒体类型识别，未指定电影/剧集时不再提前按电影过滤，修复新剧搜索被误判无结果的问题。
- `AgentResourceOfficer 0.2.06`：新增 `scoring_policy` 能力，结构化暴露插件内置云盘/PT 评分规则与硬门槛，方便智能体解释但不重打分。
- `AgentResourceOfficer 0.2.05`：新增低 token `score_summary`，让智能体直接读取云盘和 PT 评分推荐、风险与确认建议。
- `AgentResourceOfficer 0.2.04`：增强智能体偏好引导协议，主响应返回低 token `preference_status`，未初始化时优先提示保存偏好。
- `AgentResourceOfficer 0.2.03`：新增智能体偏好画像、云盘/PT 分源评分、MP 原生搜索下载订阅推荐工作流，并让写入动作优先生成 `plan_id`。
- `AgentResourceOfficer 0.2.02`：新增影巢资源搜索/解锁总开关与单资源积分上限，降低外部智能体误解锁高积分资源的风险。
- `AgentResourceOfficer 0.2.01`：减少状态轮询时的重复工具加载日志，并同步新展示名 `Agent影视助手`、专属图标、外部智能体文档和飞书/Skill 接入口说明。
- `AgentResourceOfficer 0.1.119`：新增本插件内置影巢签到日志，可通过 API、飞书或智能体查看最近签到、自动刷新 Cookie 和失败原因。
- `AgentResourceOfficer 0.1.118`：本插件内置影巢 Cookie 自动刷新：签到兜底失败时可使用账号密码自动登录、保存新 Cookie 并重试。
- `AgentResourceOfficer 0.1.117`：影巢签到收口到本插件：新增定时签到配置、默认赌狗模式、网页 Cookie 兜底和智能入口签到命令。
- `AgentResourceOfficer 0.1.116`：新增 `workbuddy_quickstart` 请求模板和 `route_text` 模板，方便 WorkBuddy、微信侧智能体复现标准接入口。
- `AgentResourceOfficer 0.1.115`：`assistant/route` 支持 `MP搜索`、`原生搜索`、`搜索资源`、`搜索` 前缀，统一外部智能体与飞书入口的原生 MP 搜索用法。
- `AgentResourceOfficer 0.1.114`：飞书冲突检测会结合旧桥接配置、health 和 get_state，避免把已禁用但仍加载的旧插件误判为冲突。
- `AgentResourceOfficer 0.1.113`：飞书健康检查补充可启用判断、缺失项和迁移建议，便于从旧飞书桥接迁移。
- `AgentResourceOfficer 0.1.112`：修正 `assistant/startup` 在无可恢复会话时仍推荐 `continue` 的问题，避免外部智能体被空会话误导。
- `AgentResourceOfficer 0.1.111`：飞书配置页补充回复 ID 类型和命令白名单，便于从旧飞书桥接完整迁移。
- `FeishuCommandBridgeLong 0.5.26`：更新插件市场描述，明确本插件是旧飞书长连接兼容/备份入口。
- `AgentResourceOfficer 0.1.110`：飞书健康检查新增旧桥接运行状态和冲突提示，避免内置飞书入口与 `FeishuCommandBridgeLong` 同时监听同一个飞书 App。
- `AgentResourceOfficer 0.1.109` 新增 MP 原生 Tool `agent_resource_officer_feishu_health`，让内置智能助手可直接检查本插件内置飞书入口状态。
- 新增完整发布前检查脚本：`scripts/pre-release-check.sh`。
- 新增统一打包脚本：`scripts/package-plugin.sh`。
- 新增仓库布局同步脚本：`scripts/sync-repo-layout.sh`。
- GitHub Actions 已接入完整发布前检查，避免 README、package 元数据、运行代码版本和 ZIP 包产物不一致。
- `package.v2.json` 现在由 `package.json` 去除 `v2` 字段后保持一致。
- CI 已升级到 `actions/checkout@v6` 和 `actions/setup-python@v6`，并支持手动 `workflow_dispatch`。
- 发布检查现在会校验插件清单、必填元数据、图标文件、Python 语法、Skill helper 自测、Skill 安装 dry-run、ZIP 入口文件、README 和生成文件污染。
- `package-plugin.sh` 支持 `--help`、`--list`、`--all`，并支持按 `package.json` 进行大小写不敏感插件名规范化。
- `package-plugin.sh --all` 和 `pre-release-check.sh` 会在打包前清理旧 ZIP，避免旧版本附件混入发布。
- `update-draft-release-assets.sh` 会在覆盖 Draft Release 前清理旧版本 ZIP 与旧校验附件，避免同一插件多个版本同时出现在草稿附件中。

## 历史版本

## v2026.04.28.1

- 同日补丁发布，更新 `FeishuCommandBridgeLong 0.5.26`。
- 插件市场描述明确旧飞书桥接的兼容/备份定位，新用户优先使用 `AgentResourceOfficer` 内置飞书入口。
- Release 附件重新打包，包含 `FeishuCommandBridgeLong-0.5.26.zip`。

## v2026.04.28

- 正式发布多插件套件 Release，附件包含 8 个 MoviePilot 本地安装 ZIP、2 个公开 Skill ZIP、插件/Skill manifest 和 SHA256 校验文件。
- `AgentResourceOfficer 0.1.116` 作为主资源入口，统一承接影巢、盘搜、115、夸克、飞书 Channel 和智能体 Tool。
- 内置飞书入口默认关闭，可作为新远程控制入口；`FeishuCommandBridgeLong` 保留为兼容/备份插件。
- 115 直转层支持扫码会话，并在必要时回退 `P115StrmHelper`；STRM 生成和 302 仍建议由 `P115StrmHelper` 负责。
- 发布链路已验证：本地 `pre-release-check`、GitHub Actions、正式 Release 下载回验均通过。

## v2.0.0-alpha.1

- 拆分为独立插件仓库
- 统一对外文案为 AI Gateway
- 保留 `standard` / `enhanced` 识别增强模式
- 保留异步回调与二次整理流程
- 与 `moviepilot-ai-recognizer-gateway` 配套设计
