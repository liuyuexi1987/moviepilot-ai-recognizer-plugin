# 插件安装说明

这个仓库是 MoviePilot 自定义插件仓库，当前同时提供资源工作流、飞书桥接、AI 识别增强、影巢、夸克和极影视刷新等插件。

推荐优先使用 MoviePilot 自定义插件仓库安装；只有需要离线安装或调试单插件时，再使用本地 ZIP。

## 方式 1：插件仓库安装

在 MoviePilot 中添加本仓库作为自定义插件仓库：

```text
https://github.com/liuyuexi1987/MoviePilot-Plugins
```

添加后在插件市场安装需要的插件。

## 方式 2：本地 ZIP 安装

发布前可在仓库根目录生成所有可本地安装的 ZIP：

```bash
bash scripts/pre-release-check.sh
```

如果只是本地临时打包、不需要完整验收，也可以执行：

```bash
bash scripts/package-plugin.sh --all
```

正式发布前仍建议使用 `pre-release-check.sh`，它会额外检查元数据、Skill helper 和 ZIP 内容。

生成目录：

```text
dist/
```

当前会生成：

- `AIRecoginzerForwarder-2.0.1.zip`
- `AIRecognizerEnhancer-0.1.11.zip`
- `AgentResourceOfficer-0.1.110.zip`
- `FeishuCommandBridgeLong-0.5.25.zip`
- `HDHiveDailySign-1.0.0.zip`
- `HdhiveOpenApi-0.3.0.zip`
- `QuarkShareSaver-0.1.0.zip`
- `ZspaceMediaFreshMix-1.0.0.zip`

然后在 MoviePilot 插件页面选择本地上传安装。

## Skill 模板安装

仓库同时提供两个公开 Skill 模板，给外部智能体调用 MoviePilot 资源工作流使用：

发布产物里会包含：

- `agent-resource-officer-<version>.zip`
- `hdhive-search-unlock-to-115-<version>.zip`

如果使用源码仓库，也可以直接运行安装脚本：

```bash
bash skills/agent-resource-officer/install.sh --dry-run
bash skills/agent-resource-officer/install.sh

bash skills/hdhive-search-unlock-to-115/install.sh --dry-run
bash skills/hdhive-search-unlock-to-115/install.sh
```

安装后可先跑本地自测：

```bash
python3 ~/.codex/skills/agent-resource-officer/scripts/aro_request.py selftest
python3 ~/.codex/skills/hdhive-search-unlock-to-115/scripts/hdhive_agent_tool.py selftest
```

## 推荐安装组合

智能体 / 资源工作流主线：

- `AgentResourceOfficer`
- `FeishuCommandBridgeLong`
- `QuarkShareSaver`
- 需要旧影巢 OpenAPI 页面时再装 `HdhiveOpenApi`

AI 识别线：

- 新方案优先用 `AIRecognizerEnhancer`
- 旧 Gateway 回调方案继续保留 `AIRecoginzerForwarder`

影巢签到：

- 只需要轻量签到时用 `HDHiveDailySign`
- OpenAPI 签到如果要求付费接口，普通用户优先保留轻量签到插件

极影视刷新：

- 使用 `ZspaceMediaFreshMix`

## AI Gateway 说明

`AIRecognizerEnhancer` 不需要额外 Gateway，直接复用 MoviePilot 当前 LLM 配置。

只有继续使用旧 `AIRecoginzerForwarder` 时，才需要单独部署 `moviepilot-ai-recognizer-gateway`，并在插件里填写 Webhook 地址，例如：

```text
http://moviepilot-ai-recognizer-gateway:9000/webhook
```

如果 MoviePilot 和 Gateway 不在同一 Docker 网络内，再改用宿主机可访问的地址。
