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
- `AgentResourceOfficer`: `0.1.111`
- `FeishuCommandBridgeLong`: `0.5.25`
- `HdhiveOpenApi`: `0.3.0`
- `HDHiveDailySign`: `1.0.0`
- `QuarkShareSaver`: `0.1.0`
- `ZspaceMediaFreshMix`: `1.0.0`

## 近期基础设施更新

- `AgentResourceOfficer 0.1.111`：飞书配置页补充回复 ID 类型和命令白名单，便于从旧飞书桥接完整迁移。
- `AgentResourceOfficer 0.1.110`：飞书健康检查新增旧桥接运行状态和冲突提示，避免内置飞书入口与 `FeishuCommandBridgeLong` 同时监听同一个飞书 App。
- `AgentResourceOfficer 0.1.109` 新增 MP 原生 Tool `agent_resource_officer_feishu_health`，让内置智能助手可直接检查资源官内置飞书入口状态。
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

## v2026.04.28

- 正式发布多插件套件 Release，附件包含 8 个 MoviePilot 本地安装 ZIP、2 个公开 Skill ZIP、插件/Skill manifest 和 SHA256 校验文件。
- `AgentResourceOfficer 0.1.111` 作为主资源入口，统一承接影巢、盘搜、115、夸克、飞书 Channel 和智能体 Tool。
- 内置飞书入口默认关闭，可作为新远程控制入口；`FeishuCommandBridgeLong` 保留为兼容/备份插件。
- 115 直转层支持扫码会话，并在必要时回退 `P115StrmHelper`；STRM 生成和 302 仍建议由 `P115StrmHelper` 负责。
- 发布链路已验证：本地 `pre-release-check`、GitHub Actions、正式 Release 下载回验均通过。

## v2.0.0-alpha.1

- 拆分为独立插件仓库
- 统一对外文案为 AI Gateway
- 保留 `standard` / `enhanced` 识别增强模式
- 保留异步回调与二次整理流程
- 与 `moviepilot-ai-recognizer-gateway` 配套设计
