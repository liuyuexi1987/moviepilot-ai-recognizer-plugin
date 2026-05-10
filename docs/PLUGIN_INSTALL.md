# 插件安装说明

这份文档只讲普通用户怎么安装、先装什么、装完从哪里开始。

如果你只是新手，不需要看打包、发布、维护命令。

---

## 先装哪两个

优先安装：

```text
Agent影视助手
AI识别增强
```

这两个就是当前主线：

- `Agent影视助手`：飞书命令入口、外部智能体入口、盘搜、影巢、115、夸克、MP/PT 下载。
- `AI识别增强`：MoviePilot 原生识别失败时，用 LLM 做一层兜底。

旧插件可以先不装。

---

## 插件仓库安装

在 MoviePilot 插件市场里添加自定义插件仓库：

```text
https://github.com/liuyuexi1987/MoviePilot-Plugins
```

然后在插件市场安装：

```text
Agent影视助手
AI识别增强
```

这是最推荐的安装方式。

---

## 本地 ZIP 安装

如果你拿到的是 Release 里的 ZIP 包，也可以在 MoviePilot 插件页本地上传安装。

普通用户只需要优先认这两个包：

```text
AgentResourceOfficer-0.2.68.zip
AIRecognizerEnhancer-0.1.12.zip
```

其他旧插件包只用于兼容旧链路，新装一般不用优先安装。

当前 Release 里还可能看到这些旧插件包：

```text
FeishuCommandBridgeLong-0.5.26.zip
HdhiveOpenApi-0.3.0.zip
QuarkShareSaver-0.1.0.zip
```

---

## 装完 Agent影视助手后做什么

打开 `Agent影视助手` 设置页面，按你要用的功能填写：

| 你想用的功能 | 需要配置 |
|---|---|
| 飞书命令入口 | 飞书应用的 `App ID` / `App Secret` |
| 盘搜搜索 | `盘搜 API 地址` |
| 影巢搜索 | `影巢 OpenAPI Key` |
| 115 转存 | `115 默认目录`，然后发 `115登录` 扫码 |
| 夸克转存 | 夸克 Cookie 或 CookieCloud |
| PT 下载 | 通常依赖 MoviePilot 原生下载器；MP 和 qB 不同机时可填 `PT 下载保存路径` |

不用的功能可以先不填，插件会自动跳过。

---

## 不接智能体，只用飞书

如果你不使用外部智能体，只想把飞书当成命令入口：

1. 在插件设置页配好飞书。
2. 确认只保留一个飞书入口监听，避免旧飞书插件和新插件同时收消息。
3. 直接在飞书里发命令。

常用命令：

```text
云盘搜索 片名
盘搜搜索 片名
影巢搜索 片名
转存 片名
夸克转存 片名
下载 片名
更新检查 片名
115登录
影巢签到
```

完整命令见：[全部命令](./ALL_COMMANDS.md)

---

## 接外部智能体

如果你要让 `OpenClaw`、`Hermes`、`WorkBuddy` 这类外部智能体控制 MoviePilot，安装插件后还要让智能体安装 `agent-resource-officer skill / helper`。

最短路径：

1. MoviePilot 安装并启用 `Agent影视助手`。
2. 把 [外部智能体接入](./AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md) 里的提示词发给你的智能体。
3. 智能体按文档安装 skill，并填写：

```text
ARO_BASE_URL=http://你的MoviePilot地址:3000
ARO_API_KEY=你的 MoviePilot API_TOKEN
```

如果 MoviePilot 在 NAS、智能体在 Win / Mac，请看：

[跨机器部署](./AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md)

### MCP 怎么办

如果你的智能体客户端支持 MoviePilot 官方 MCP，也可以同时接：

```text
MCP 地址：http://你的MP地址:3000/api/v1/mcp
认证头：X-API-KEY=你的 MoviePilot API_TOKEN
```

建议分工：

- 查插件列表、下载器状态、站点状态、历史记录、工作流这类 MoviePilot 管理信息，可以优先用 MCP。
- 盘搜、影巢、云盘搜索、115/夸克转存、编号选择、翻页、Cookie 修复，继续优先用 `agent-resource-officer skill / helper`。
- `MP搜索 / PT搜索 / 下载 / 更新检查` 这类片名资源流，也继续优先交给 `agent-resource-officer`，避免智能体绕过插件规则。

---

## AI识别增强怎么用

`AI识别增强` 不需要额外 Gateway。

它直接复用 MoviePilot 当前已经启用的 LLM 配置，在原生文件名识别失败时做兜底，然后把结果交回 MoviePilot 原生整理链。

详细说明见：[AI识别增强](../AIRecognizerEnhancer/README.md)

---

## 旧插件还要不要装

新装一般不需要优先安装旧插件。

| 旧插件 | 用途 | 建议 |
|---|---|---|
| `FeishuCommandBridgeLong` | 旧飞书入口 | 新环境优先用 Agent影视助手内置飞书入口 |
| `HdhiveOpenApi` | 旧影巢独立能力 | 主能力已收进 Agent影视助手 |
| `QuarkShareSaver` | 旧夸克独立转存 | 主能力已收进 Agent影视助手 |

如果你是老环境迁移，可以暂时保留；如果是新装，先用 `Agent影视助手`。

---

## 维护者文档

如果你只是普通用户，到这里就够了。

资源主线：`Agent影视助手 / AgentResourceOfficer 0.2.68`

当前 Skill helper：`agent-resource-officer 0.1.46`

当前 Release：https://github.com/liuyuexi1987/MoviePilot-Plugins/releases/tag/v0.2.68

如果你要打包、发布或维护仓库，再看：

- [维护命令](docs/MAINTENANCE_COMMANDS.md)
- [维护命令](./MAINTENANCE_COMMANDS.md)
- [发布检查](./RELEASE_CHECKLIST.md)
- [打包说明](./PACKAGING.md)
