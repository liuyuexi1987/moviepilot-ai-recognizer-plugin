# MoviePilot-Plugins

[![Release Preflight](https://github.com/liuyuexi1987/MoviePilot-Plugins/actions/workflows/ci.yml/badge.svg)](https://github.com/liuyuexi1987/MoviePilot-Plugins/actions/workflows/ci.yml)

MoviePilot 插件仓库，核心是两个插件：

- **Agent影视助手** — 找资源、转存、下载、订阅、签到，一站搞定
- **AI识别增强** — 影片识别失败时用 LLM 兜底，并沉淀失败样本

如果你是第一次接触这个仓库，先看这两个就够了。其他插件大多是旧链路兼容、补充能力或自用扩展。

---

## 快速开始

### 1. 安装插件

在 MoviePilot 插件市场添加本仓库：

```text
https://github.com/liuyuexi1987/MoviePilot-Plugins
```

然后优先安装：

```text
Agent影视助手
AI识别增强
```

### 2. 填写配置

在 `Agent影视助手` 设置里按需填写：

- 影巢 OpenAPI Key
- 盘搜 API 地址
- 115 默认目录
- 夸克 Cookie 或 CookieCloud
- 飞书 / 智能体配置（可选）

### 3. 开始使用

```text
搜索 <片名>
云盘搜索 <片名>
转存 <片名>
下载 <片名>
更新检查 <片名>
```

如果需要识别兜底，再开启 **AI识别增强**。

---

## 两个主线插件

### Agent影视助手

一个插件收口所有主工作流：

| 能力 | 包含 |
|------|------|
| 云盘资源 | 搜索（盘搜 / 影巢 / 云盘）· 转存（115 / 夸克）· 更新检查 · 目录命名建议 |
| 原生 MP/PT | MP搜索 · PT搜索 · 下载 · 订阅 · 任务 / 历史 / 站点查询 · 热门推荐 |
| 115 / 夸克 / 影巢 | 登录检查 · 状态查询 · Cookie刷新 · 签到 · 转存目录清理 |
| 外部入口 | 飞书长连接 · OpenClaw / Hermes / WorkBuddy 兼容 · 会话续接 · 编号选择 |

详细说明：[Agent影视助手](./AgentResourceOfficer/README.md)

### AI识别增强

它和 MP 原生识别的区别可以简单理解成：

| | MP 原生 | AI识别增强 |
|---|---------|------------|
| 定位 | 一次性自动补救 | 失败样本治理层 |
| 能力 | 失败后智能助手接管一次 | 保存失败样本 · 生成识别词建议 · 回放 / 复查 / 批量出队 |

适用场景：

- 命名混乱
- 网盘挂载
- 手动整理失败
- 同类资源反复识别错

详细说明：[AI识别增强](./AIRecognizerEnhancer/README.md)

---

## 外部智能体接入

如果你只在 MoviePilot 内使用，装插件就行。

如果要接 `OpenClaw`、`Hermes`、`WorkBuddy` 等外部智能体，需额外安装 skill：

```text
skills/agent-resource-officer/SKILL.md
docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md
```

最短提示词（可直接复制给智能体）：

```text
请安装并使用 agent-resource-officer skill。
先读取：
1. skills/agent-resource-officer/SKILL.md
2. docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md
然后按其中的固定命令和接入规则执行。
```

### NAS + Win/Mac 部署

推荐架构：

- MoviePilot 跑在 NAS
- 智能体跑在 Win / Mac

要点：

- `ARO_BASE_URL` 填 NAS 上 MP 的可达地址
- `盘搜 API 地址` 按 NAS 容器视角填写
- Cookie 刷新命令（影巢 / 夸克）需先在本机浏览器登录对应站点

详细说明：[跨机器部署](./docs/AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md)

---

## 旧组合方案

在 `Agent影视助手` 成为主线之前，这个仓库常见的老组合是：

- `FeishuCommandBridgeLong`
- `QuarkShareSaver`
- `HdhiveOpenApi`

这几条旧链路放在一起时，分工大致是：

- `FeishuCommandBridgeLong`
  - 负责飞书消息入口
  - 把“搜索、选择、转存、115 登录”这些动作从聊天消息转成插件调用
- `HdhiveOpenApi`
  - 负责影巢搜索、解锁、签到、配额查询
  - 处理“先搜影巢，再解锁资源”这条链
- `QuarkShareSaver`
  - 负责夸克分享链接的实际转存
  - 是夸克侧的轻量执行层

把它们拼起来以后，整体效果就是：

- 飞书里发命令
- 飞书桥接负责接收和分流
- 影巢插件负责搜影巢和解锁
- 夸克插件负责夸克转存

这套老方案现在仍然能用，但问题也很明显：

- 插件分散
- 会话分散
- 失败恢复分散
- 外部智能体接入不统一

所以现在更推荐直接使用：

- `Agent影视助手`

它本质上就是把上面这条旧组合主线，尽量收拢成一个统一入口。

---

## 全部插件

下面是当前仓库里所有主要插件。首页只给一行说明；详细作用、配置和用法请点进去看各自 README。

| 插件 | 主要作用 | 详细说明 |
| --- | --- | --- |
| `AgentResourceOfficer` / Agent影视助手 | 当前主线插件，统一承接盘搜、影巢、115、夸克、更新检查、Cookie 修复和智能体入口 | [查看说明](./AgentResourceOfficer/README.md) |
| `AIRecognizerEnhancer` / AI识别增强 | MoviePilot 原生识别失败后的本地 LLM 兜底和失败样本治理 | [查看说明](./AIRecognizerEnhancer/README.md) |
| `FeishuCommandBridgeLong` / 飞书命令桥接 | 旧飞书长连接兼容/备份入口；新环境优先使用 Agent影视助手 内置入口 | [查看说明](./FeishuCommandBridgeLong/README.md) |
| `HdhiveOpenApi` / 影巢 OpenAPI | 影巢搜索、解锁、签到、配额查询、115 转存的独立 OpenAPI 插件 | [查看说明](./HdhiveOpenApi/README.md) |
| `QuarkShareSaver` / 夸克分享转存 | 夸克分享链接直转自己的夸克目录，适合作为轻量执行入口 | [查看说明](./QuarkShareSaver/README.md) |

---

## 相关文档

- [文档索引](./docs/INDEX.md)
- [插件安装说明](./docs/PLUGIN_INSTALL.md)
- [外部智能体接入](./docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md)
- [跨机器部署说明](./docs/AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md)

---

## 当前状态

- 当前推荐主线插件：`Agent影视助手`
- 当前插件版本：`0.2.68`
- 当前 skill helper 版本：`0.1.42`
- 当前仓库许可证：`GPL-3.0`
- 当前发布页：[v0.2.68](https://github.com/liuyuexi1987/MoviePilot-Plugins/releases/tag/v0.2.68)

## 许可证

本仓库当前使用 `GPL-3.0`。
