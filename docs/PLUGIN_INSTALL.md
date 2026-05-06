# 插件安装说明

这份文档只讲一件事：

- 普通用户该装什么
- 普通用户怎么开始用

如果你只是想把插件装起来，不需要看打包、发布、维护命令。

## 新用户先装什么

优先安装：

- `AgentResourceOfficer`
- `AIRecognizerEnhancer`

这两个就够你先跑通主线：

- 搜资源
- 选资源
- 转存 / 下载
- 更新检查
- 识别失败兜底

## 安装方式

### 方式 1：插件仓库安装

在 MoviePilot 中添加这个自定义插件仓库：

```text
https://github.com/liuyuexi1987/MoviePilot-Plugins
```

然后在插件市场里安装：

- `AgentResourceOfficer`
- `AIRecognizerEnhancer`

这是最推荐的方式。

### 方式 2：本地 ZIP 安装

如果你拿到的是 Release 里的 ZIP 包，也可以在 MoviePilot 插件页直接本地上传安装。

普通用户只需要认这几个包：

- `AgentResourceOfficer-<版本>.zip`
- `AIRecognizerEnhancer-<版本>.zip`
- 如果你确实还要旧兼容入口，再按需装：
  - `FeishuCommandBridgeLong-<版本>.zip`
  - `HdhiveOpenApi-<版本>.zip`
  - `QuarkShareSaver-<版本>.zip`

## 接外部智能体时怎么装

如果你要接：

- WorkBuddy
- OpenClaw
- Hermes
- 其他外部智能体

除了 MoviePilot 里的插件本体，还需要安装：

- `agent-resource-officer` skill / helper

先看这两个文件：

- [skills/agent-resource-officer/SKILL.md](../skills/agent-resource-officer/SKILL.md)
- [AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md](./AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md)

可以直接丢给智能体这段最短提示词：

```text
请安装并使用 agent-resource-officer skill。
先读取：
1. skills/agent-resource-officer/SKILL.md
2. docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md
然后按其中的固定命令和接入规则执行。

额外要求：
- `云盘搜索` 必须原样 route，不要偷换成 `盘搜搜索`
- 不要自己重排编号
- 不要把结果改写成“推荐资源/分析结论”
- 盘搜结果里的链接必须原样保留，不要吞掉 115 或夸克 URL
```

## 推荐安装组合

### 组合 A：当前推荐主线

- `AgentResourceOfficer`
- `AIRecognizerEnhancer`

适合：

- 新用户
- 想少装插件
- 想把搜索、转存、下载、签到、修复尽量统一到一个主入口

### 组合 B：旧兼容组合

如果你还在沿用旧工作流，可以按需补这些插件：

- `FeishuCommandBridgeLong`
- `HdhiveOpenApi`
- `QuarkShareSaver`
- `P115StrmHelper`（这个不在本仓库）

它们组合起来时的大致分工是：

- `FeishuCommandBridgeLong`
  - 负责飞书消息入口
- `HdhiveOpenApi`
  - 负责影巢搜索、解锁、签到、配额
- `QuarkShareSaver`
  - 负责夸克分享直转
- `P115StrmHelper`
  - 负责 115 转存、整理、STRM

也就是说，旧组合是“多插件拼一条链”；现在更推荐把这条链尽量收进：

- `AgentResourceOfficer`

## AI 识别补充说明

`AIRecognizerEnhancer` 不需要额外 Gateway，直接复用 MoviePilot 当前已经启用的 LLM 配置。

## 如果你只是普通用户，到这里就够了

如果你后面真的要自己打包、发布或维护仓库，再去看：

- [MAINTENANCE_COMMANDS.md](./MAINTENANCE_COMMANDS.md)
