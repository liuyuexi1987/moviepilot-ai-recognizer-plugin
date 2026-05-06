# MoviePilot-Plugins

[![Release Preflight](https://github.com/liuyuexi1987/MoviePilot-Plugins/actions/workflows/ci.yml/badge.svg)](https://github.com/liuyuexi1987/MoviePilot-Plugins/actions/workflows/ci.yml)

这是一个面向 MoviePilot 的插件仓库。当前主线已经收口成两个核心插件：

- [Agent影视助手](./AgentResourceOfficer/README.md)
- [AI识别增强](./AIRecognizerEnhancer/README.md)

如果你是第一次接触这个仓库，先看这两个就够了。其他插件大多是兼容旧链路、补充能力或自用扩展。

## 主线插件

### [Agent影视助手](./AgentResourceOfficer/README.md)

作用：

- 统一承接 MoviePilot 里和“找资源、选资源、转存、下载、订阅、签到、恢复”相关的主工作流
- 云盘资源能力：
  - `搜索 / 盘搜搜索 / 影巢搜索 / 云盘搜索`
  - `转存 / 夸克转存 / 115转存`
  - 通用分享链接自动路由到 `115 / 夸克`
  - `更新检查 / 检查`
  - 夸克转存后可给出电视剧目录的规范命名建议，并支持用户确认后执行
- 原生 MP / PT 能力：
  - `MP搜索 / PT搜索`
  - `下载`
  - `订阅 / 订阅并搜索`
  - 下载任务、下载历史、订阅列表、站点状态、下载器状态、入库/整理历史查询
  - 热门推荐 / 热门发现 / 原生推荐续接
- 115 / 夸克 / 影巢维护能力：
  - `115登录 / 检查115登录 / 115状态 / 115任务`
  - `清空115转存目录 / 清空夸克转存目录`
  - `影巢签到 / 影巢签到日志`
  - `刷新影巢Cookie / 修复影巢签到`
  - `刷新夸克Cookie / 修复夸克转存`
- 飞书与外部入口能力：
  - 内置飞书长连接入口
  - 可替代大部分旧 `FeishuCommandBridgeLong` 主线能力
  - 兼容 WorkBuddy、OpenClaw、Hermes、CLI、MP 原生 Agent Tool
- 对外部智能体和原生 Tool 友好：
  - 会话续接
  - 编号选择
  - 计划确认
  - 失败恢复
  - 请求模板
  - 原生 Agent Tool / HTTP API 双入口

适合：

- 你想把“搜资源 -> 选资源 -> 转存到固定目录 -> 后续更新 / 签到 / 恢复”这条主线统一起来
- 你想把云盘资源、原生 MP/PT、飞书入口、外部智能体入口收敛到一个插件
- 你想在微信、WorkBuddy、OpenClaw、Hermes 这类智能体里稳定使用 MoviePilot

### [AI识别增强](./AIRecognizerEnhancer/README.md)

作用：

- 在 MoviePilot 原生识别失败后，用当前已启用的 LLM 做本地结构化识别兜底
- 不只补救一次，还会沉淀失败样本，方便长期治理识别问题

它和 MoviePilot 原版“整理失败后智能助手自动接管一次”的区别是：

- MP 原版：偏“一次性自动补救”
- AI识别增强：偏“失败样本治理层”
  - 保存失败样本
  - 生成识别词建议
  - 回放 / 复查 / 批量出队

适合：

- 命名混乱
- 网盘挂载
- 手动整理失败
- 同类资源反复识别错

## 快速开始

先明确一件事：

- 如果你只是在 MoviePilot 里直接使用插件，不接外部智能体，可以只安装插件本体
- 如果你要接 WorkBuddy、OpenClaw、Hermes 或其他外部智能体，请先安装 `agent-resource-officer` skill / helper

外部智能体入口文档：

```text
skills/agent-resource-officer/SKILL.md
docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md
```

可直接复制给智能体的最短提示词：

```text
请安装并使用 agent-resource-officer skill。
先读取：
1. skills/agent-resource-officer/SKILL.md
2. docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md
然后按其中的固定命令和接入规则执行。
```

### 一、同一台机器：智能体和 MoviePilot 在同一设备

这是最简单的使用方式。

1. 在 MoviePilot 插件市场添加本仓库：

```text
https://github.com/liuyuexi1987/MoviePilot-Plugins
```

2. 优先安装这两个插件：

```text
Agent影视助手
AI识别增强
```

3. 在 `Agent影视助手` 里按需填写：

```text
影巢 OpenAPI Key
盘搜 API 地址
115 默认目录
夸克 Cookie 或 CookieCloud
飞书 / 智能体配置（可选）
```

4. 先从这些固定口令开始用：

```text
搜索 <片名>
云盘搜索 <片名>
转存 <片名>
下载 <片名>
更新检查 <片名>
```

5. 如果需要识别兜底，再开启 `AI识别增强`。

详细安装和配置：

- [插件安装说明](./docs/PLUGIN_INSTALL.md)
- [Agent影视助手说明](./AgentResourceOfficer/README.md)
- [AI识别增强说明](./AIRecognizerEnhancer/README.md)

### 二、NAS 环境：MoviePilot 在 NAS，智能体在 Win / Mac

这是当前非常推荐的落地方式：

- `MoviePilot + Agent影视助手` 跑在 NAS
- `WorkBuddy / OpenClaw / 其他智能体` 跑在你的 Win / Mac

使用要点：

1. `MoviePilot`、`Agent影视助手`、`AI识别增强` 装在 NAS 上
2. 智能体所在电脑安装 `agent-resource-officer` skill / helper
3. `ARO_BASE_URL` 填成**Win / Mac 可以访问到的 NAS 上 MP 地址**
4. `盘搜 API 地址` 要按 **MoviePilot 容器视角** 填，不是按你电脑视角填

这一种部署里要特别注意：

- 普通资源命令：
  - 由 Win / Mac 发起
  - 由 NAS 上的 MoviePilot 执行
- Cookie 修复命令：
  - 从 **Win / Mac 本机浏览器** 读取 Cookie
  - 再写回 NAS 上的 MoviePilot

所以如果你要用：

```text
刷新影巢Cookie
修复影巢签到
刷新夸克Cookie
修复夸克转存
```

请先在**本机浏览器**登录对应站点。

详细说明：

- [外部智能体接入](./docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md)
- [跨机器部署说明](./docs/AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md)
- [agent-resource-officer skill](./skills/agent-resource-officer/SKILL.md)

## 全部插件目录

下面是当前仓库里所有主要插件。首页只给一行说明；详细作用、配置和用法请点进去看各自 README。

| 插件 | 主要作用 | 详细说明 |
| --- | --- | --- |
| `AgentResourceOfficer` / Agent影视助手 | 当前主线插件，统一承接盘搜、影巢、115、夸克、更新检查、Cookie 修复和智能体入口 | [查看说明](./AgentResourceOfficer/README.md) |
| `AIRecognizerEnhancer` / AI识别增强 | MoviePilot 原生识别失败后的本地 LLM 兜底和失败样本治理 | [查看说明](./AIRecognizerEnhancer/README.md) |
| `AIRecoginzerForwarder` / AI 识别转发 | 旧的外部 AI Gateway 识别转发链，当前已不再是推荐主线 | [查看说明](./AIRecoginzerForwarder/README.md) |
| `FeishuCommandBridgeLong` / 飞书命令桥接 | 旧飞书长连接兼容/备份入口；新环境优先使用 Agent影视助手 内置入口 | [查看说明](./FeishuCommandBridgeLong/README.md) |
| `HdhiveOpenApi` / 影巢 OpenAPI | 影巢搜索、解锁、签到、配额查询、115 转存的独立 OpenAPI 插件 | [查看说明](./HdhiveOpenApi/README.md) |
| `HDHiveDailySign` / 影巢签到 | 自动影巢每日签到，支持普通/赌狗模式、失败重试、自动登录与历史记录 | [查看说明](./HDHiveDailySign/README.md) |
| `QuarkShareSaver` / 夸克分享转存 | 夸克分享链接直转自己的夸克目录，适合作为轻量执行入口 | [查看说明](./QuarkShareSaver/README.md) |
| `ZspaceMediaFreshMix` / 极影视刷新（自用魔改） | 极空间/极影视媒体刷新与混合分类兼容 | [查看说明](./ZspaceMediaFreshMix/README.md) |

## 文档入口

如果你已经确定要继续深入，再看这些：

- [文档索引](./docs/INDEX.md)
- [插件安装说明](./docs/PLUGIN_INSTALL.md)
- [外部智能体接入](./docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md)
- [跨机器部署说明](./docs/AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md)
- [维护命令速查](./docs/MAINTENANCE_COMMANDS.md)

## 当前状态

- 当前推荐主线插件：`Agent影视助手`
- 当前插件版本：`0.2.68`
- 当前 skill helper 版本：`0.1.42`
- 当前仓库许可证：`GPL-3.0`
- 当前发布页：[v0.2.68](https://github.com/liuyuexi1987/MoviePilot-Plugins/releases/tag/v0.2.68)

## 许可证

本仓库当前使用：

- `GNU General Public License v3.0`（`GPL-3.0`）

也就是说，后续再分发、修改或集成这个仓库代码时，需要按 `GPL-3.0` 的要求处理。
