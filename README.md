# MoviePilot-Plugins

[![Release Preflight](https://github.com/liuyuexi1987/MoviePilot-Plugins/actions/workflows/ci.yml/badge.svg)](https://github.com/liuyuexi1987/MoviePilot-Plugins/actions/workflows/ci.yml)

两个插件，解决两个问题：

- **Agent影视助手**：飞书桥接入口 + 搜片、转存、下载、订阅、签到，尽量都从一个入口完成
- **AI识别增强**：文件名识别失败时用 LLM 兜底，并沉淀失败样本与识别词建议

如果你是第一次接触这个仓库，先看这两个就够了。

---

## 第一步：安装插件

MoviePilot -> 插件市场 -> 添加仓库：

```text
https://github.com/liuyuexi1987/MoviePilot-Plugins
```

然后优先安装：

```text
Agent影视助手
AI识别增强
```

其中 `Agent影视助手` 的重点是给外部智能体提供稳定入口，让 `OpenClaw`、`Hermes`、`WorkBuddy` 这类智能体不要自己乱拼影巢、盘搜、115、夸克接口，而是统一交给插件执行。

如果你主要是接外部智能体，装完插件后先看这里：

[外部智能体接入 Agent影视助手](./docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md)

---

## 第二步：填配置

打开 `Agent影视助手` 设置页面，按你要用的功能填写：

| 你想用的功能 | 需要填什么 |
|---|---|
| 盘搜搜索 | `盘搜 API 地址` |
| 影巢搜索 | `影巢 OpenAPI Key` |
| 115 转存 | `115 默认目录`，然后走 `115登录` 扫码 |
| 夸克转存 | `夸克 Cookie` 或 `CookieCloud` |
| 飞书入口 | 飞书应用的 `App ID` / `App Secret` |
| PT 下载 | 一般只要 MoviePilot 原生下载器正常即可；如果 MP 和 qB 不在一台机器，可额外填写 `PT 下载保存路径` |

不用的功能可以不填，插件会自动跳过。

---

## 第三步：直接开始用

装好、填好配置后，直接在 MoviePilot、飞书，或者外部智能体里发这些命令：

### 搜索

```text
MP搜索 流浪地球2
搜索 流浪地球2
影巢搜索 流浪地球2
云盘搜索 流浪地球2
```

- `MP搜索` / `PT搜索`：走 MoviePilot 原生 PT 搜索
- `搜索`：默认走盘搜
- `云盘搜索`：盘搜 + 影巢一起搜

### 转存 / 下载

```text
转存 流浪地球2
115转存 流浪地球2
夸克转存 流浪地球2
下载 流浪地球2
```

- `转存 <片名>` 默认等同 `115转存 <片名>`
- 只有明确发送 `夸克转存 <片名>` 才会走夸克
- `下载 <片名>` 走 MoviePilot 原生 PT 下载链，先找片、再生成下载计划

### 选择与翻页

```text
1
1详情
下载1
n
```

- `1`：继续处理当前第 1 条结果
- `1详情`：查看第 1 条详情
- `下载1`：给第 1 条 PT 结果生成下载计划，不会立刻下载
- `n`：下一页

### 其他常用

```text
订阅 流浪地球2
更新检查 流浪地球2
115登录
影巢签到
```

完整命令见：[全部命令](./docs/ALL_COMMANDS.md)

---

## 飞书怎么用

如果不使用外部智能体，只想用命令功能，也可以只配置飞书入口。

配好飞书后，它就像 TG / 企业微信一样，可以作为 MoviePilot 的资源命令入口。你直接在飞书里发命令，插件会在 MoviePilot 里完成搜索、转存、下载、签到等操作。

| 飞书里发什么 | 会做什么 |
|---|---|
| `MP搜索 流浪地球2` | PT 搜索 |
| `盘搜搜索 流浪地球2` | 盘搜搜索 |
| `影巢搜索 流浪地球2` | 影巢搜索 |
| `云盘搜索 流浪地球2` | 盘搜 + 影巢 |
| `下载资源 1` | 下载第 1 条 PT 结果 |
| `选择 1` | 继续处理第 1 条当前结果 |
| `帮助` | 查看帮助 |

飞书里还有一些快捷别名，但新手直接用完整命令最稳。

---

## AI识别增强是做什么的

MoviePilot 整理文件时，会先识别文件名里的片名、年份、季、集。

如果原生识别失败，`AI识别增强` 会：

1. 用当前 MoviePilot 配置好的 LLM 做一次结构化识别
2. 把识别结果交回 MoviePilot，继续走原生整理链
3. 保存失败样本，方便后续生成自定义识别词

它不会绕过 MoviePilot 原生整理流程，只是在识别环节加了一层兜底。

详细说明见：[AI识别增强](./AIRecognizerEnhancer/README.md)

---

## 外部智能体接入

如果你要让 `OpenClaw`、`Hermes`、`WorkBuddy` 这类外部智能体控制 MoviePilot，再看这一节。

### 同一台机器

MoviePilot 和智能体都在当前电脑：

```text
ARO_BASE_URL=http://127.0.0.1:3000
ARO_API_KEY=你的 MoviePilot API_TOKEN
```

### 不同机器

MoviePilot 在 NAS，智能体在 Win / Mac：

```text
ARO_BASE_URL=http://你的NAS地址:3000
ARO_API_KEY=你的 MoviePilot API_TOKEN
```

如果你的客户端支持官方 MCP，也可以直接接：

```text
http://你的MP地址:3000/api/v1/mcp
X-API-KEY=你的 MoviePilot API_TOKEN
```

MCP 更适合查 MoviePilot 管理信息，例如插件列表、下载器状态、站点状态、历史记录、工作流等。

如果你主要想稳定跑资源流，例如 `云盘搜索 / 盘搜 / 影巢 / 转存 / 夸克转存 / 115转存 / 下载 / 更新检查 / 编号选择 / Cookie 修复`，还是推荐继续用 `agent-resource-officer skill / helper`，避免智能体绕过插件规则。

长时间使用同一个微信、WorkBuddy、OpenClaw 或 Hermes 会话后，如果智能体开始把 `15详情` 当成执行、编号接到旧结果、或者一直套用旧格式，可以直接对它说：

```text
校准影视技能
```

这会让智能体重新加载影视助手的关键规则。

详细步骤见：

- [外部智能体接入](./docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md)
- [跨机器部署](./docs/AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md)
- [Skill 说明](./skills/agent-resource-officer/SKILL.md)

---

## 旧插件还要不要用

下面这些老插件还在仓库里，但新装一般不再推荐优先用它们：

| 旧插件 | 主要用途 | 现在的建议 |
|---|---|---|
| `FeishuCommandBridgeLong` | 旧飞书入口 | 新环境优先用 Agent影视助手内置飞书入口 |
| `HdhiveOpenApi` | 影巢独立能力 | 已被 Agent影视助手主线吸收 |
| `QuarkShareSaver` | 夸克独立转存 | 已被 Agent影视助手主线吸收 |

如果你是老环境兼容，可以继续保留；如果是新装，优先直接用 `Agent影视助手`。

---

## 全部插件

| 插件 | 版本 | 说明 |
|---|---|---|
| Agent影视助手 | `0.2.68` | 当前主线插件，统一承接盘搜、影巢、115、夸克、PT 下载、飞书入口和外部智能体入口 |
| AI识别增强 | `0.1.12` | MoviePilot 原生识别失败后的本地 LLM 兜底和失败样本治理 |
| 飞书命令桥接 | `0.5.26` | 旧飞书长连接入口，更多用于兼容老链路 |
| 影巢 OpenAPI | `0.3.0` | 旧影巢独立插件，主能力已收进 Agent影视助手 |
| 夸克分享转存 | `0.1.0` | 旧夸克独立插件，主能力已收进 Agent影视助手 |

---

## 相关文档

- [全部命令](./docs/ALL_COMMANDS.md)
- [文档索引](./docs/INDEX.md)
- [插件安装说明](./docs/PLUGIN_INSTALL.md)
- [Cookie 导出工具](./tools/README.md)
- [Agent影视助手详细说明](./AgentResourceOfficer/README.md)
- [AI识别增强详细说明](./AIRecognizerEnhancer/README.md)

---

## 许可证

GPL-3.0
