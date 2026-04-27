# Changelog

## 当前主线

- 仓库已经从单一 AI Gateway 插件，收拢为 MoviePilot 资源与智能体插件套件。
- 当前发布前检查覆盖 8 个可本地安装插件：
  `AIRecoginzerForwarder`、`AIRecognizerEnhancer`、`AgentResourceOfficer`、`FeishuCommandBridgeLong`、`HdhiveOpenApi`、`HDHiveDailySign`、`QuarkShareSaver`、`ZspaceMediaFreshMix`。
- `AgentResourceOfficer` 已作为新资源主入口，负责影巢、盘搜、115、夸克和智能体 Tool 的统一路由。
- `FeishuCommandBridgeLong` 继续保留 legacy 快路径，同时可委托给 `AgentResourceOfficer` 的智能入口。
- `AIRecognizerEnhancer` 作为新识别增强线，逐步替代旧网关转发链路。
- 发布流程已补齐 `plugins/`、`plugins.v2/` 同步、元数据校验、语法检查、ZIP 打包和 GitHub Actions CI。

## 当前核心版本

- `AIRecoginzerForwarder`: `2.0.1`
- `AIRecognizerEnhancer`: `0.1.11`
- `AgentResourceOfficer`: `0.1.107`
- `FeishuCommandBridgeLong`: `0.5.25`
- `HdhiveOpenApi`: `0.3.0`
- `HDHiveDailySign`: `1.0.0`
- `QuarkShareSaver`: `0.1.0`
- `ZspaceMediaFreshMix`: `1.0.0`

## 近期基础设施更新

- 新增完整发布前检查脚本：`scripts/pre-release-check.sh`。
- 新增统一打包脚本：`scripts/package-plugin.sh`。
- 新增仓库布局同步脚本：`scripts/sync-repo-layout.sh`。
- GitHub Actions 已接入完整发布前检查，避免 README、package 元数据、运行代码版本和 ZIP 包产物不一致。
- `package.v2.json` 现在由 `package.json` 去除 `v2` 字段后保持一致。
- CI 已升级到 `actions/checkout@v6` 和 `actions/setup-python@v6`，并支持手动 `workflow_dispatch`。
- 发布检查现在会校验插件清单、必填元数据、图标文件、Python 语法、Skill helper 自测、Skill 安装 dry-run、ZIP 入口文件、README 和生成文件污染。
- `package-plugin.sh` 支持 `--help`、`--list`、`--all`，并支持按 `package.json` 进行大小写不敏感插件名规范化。
- `package-plugin.sh --all` 和 `pre-release-check.sh` 会在打包前清理旧 ZIP，避免旧版本附件混入发布。

## 历史版本

## v2.0.0-alpha.1

- 拆分为独立插件仓库
- 统一对外文案为 AI Gateway
- 保留 `standard` / `enhanced` 识别增强模式
- 保留异步回调与二次整理流程
- 与 `moviepilot-ai-recognizer-gateway` 配套设计
