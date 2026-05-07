# Agent影视助手

`Agent影视助手` 是这个仓库当前最重要的主线插件。

如果你是第一次接触这个仓库，优先看这个插件就够了。

## 适合谁

适合这些场景：

- 你想把 `飞书` 当成和 `TG / 企业微信` 类似的命令入口，用长连接直接控制 `MoviePilot`，不依赖特殊网络环境和公网暴露
- 你想统一处理“找资源 -> 选资源 -> 转存到网盘”的流程
- 你也想把 `MoviePilot` 原生搜索、`PT` 下载、订阅、下载任务这些能力收进同一套命令入口
- 你既用 `115`，也用 `夸克`
- 你会同时用 `盘搜`、`影巢`、`MP/PT`
- 你希望外部智能体不要乱发挥，而是按固定命令稳定执行

## 两种用法

### 1. 飞书用法

- 直接把飞书当成一个资源命令入口
- 不依赖 `OpenClaw`、`Hermes`、`WorkBuddy`
- 更像 `TG / 企业微信` 机器人命令入口
- 适合：
  - 搜资源
  - 选资源
  - 转存
  - 登录 115
  - 查更新
  - 触发影巢签到
- 也能顺手接住一部分 `MoviePilot` 原生能力，比如搜索、下载、订阅和状态查询

飞书常用命令和接入方式，直接看：

- [`PLUGIN_INSTALL.md`](../docs/PLUGIN_INSTALL.md)
- [`AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md`](../docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md)

### 2. 外部智能体用法

- 通过 `skill / helper` 调 `Agent影视助手`
- 由 `OpenClaw`、`Hermes`、`WorkBuddy` 承接会话和执行
- 更适合：
  - 会话续接
  - 计划确认
  - 自动修复
  - 复杂工作流
- 会把 `盘搜`、`影巢`、`115`、`夸克`、`MoviePilot 原生搜索/PT` 这些能力收进同一条统一工作流
- 如果你要这样用，第一步就是安装 `agent-resource-officer` 的 `skill / helper`

最短接入思路是：

1. `NAS / 本机 MoviePilot` 安装并启用本插件
2. 智能体所在机器安装 `agent-resource-officer skill / helper`
3. 配好 `ARO_BASE_URL` 和 `ARO_API_KEY`
4. 让智能体优先使用固定命令，不要自由改写

优先阅读：

- [`agent-resource-officer/SKILL.md`](../skills/agent-resource-officer/SKILL.md)
- [`AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md`](../docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md)
- [`AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md`](../docs/AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md)

下面这部分说明，默认都按**外部智能体用法**理解。

### 资源搜索

- 这是最核心的用户命令层
- 飞书也能直接发同名命令，但这里只展开外部智能体场景

- `搜索 <片名>`：普通搜索，默认先盘搜
- `盘搜搜索 <片名>`：只看盘搜
- `影巢搜索 <片名>`：只看影巢
- `云盘搜索 <片名>`：盘搜 + 影巢
- `MP搜索 <片名>` / `PT搜索 <片名>`：走 MoviePilot 原生搜索/PT

### 资源执行

- 这一组命令用于云盘转存和 PT 下载主线
- 飞书也能直接发同名命令，但这里只展开外部智能体场景
- 执行前会结合智能评分系统自动择优：
  - 云盘更看清晰度、HDR/DV、字幕、更新集数、完整度、目录和影巢积分
  - PT 更看做种数、免费/促销、下载热度、清晰度、字幕和匹配度
- 如果结果明显够好，会直接走一条龙执行
- 如果整体质量不够稳，会优先给出候选编号让用户自己选

- `转存 <片名>`：云盘资源一条龙转存
- `夸克转存 <片名>`：优先选夸克资源并转存到夸克
- `115转存 <片名>`：优先选 115 资源并转存到 115
- `下载 <片名>`：走 MP/PT 下载链

### 更新与检查

- 这组命令适合更新判断、签到和状态检查

- `更新检查 <片名>` / `检查 <片名>`
- `影巢签到`
- `影巢签到日志`

### 维护与修复

- 这一组更偏外部智能体和本机修复链
- 其中 `刷新影巢Cookie`、`修复影巢签到`、`刷新夸克Cookie`、`修复夸克转存` 会牵涉本机浏览器 Cookie 导出工具

- `115登录`
- `115状态`
- `清空115转存目录`
- `清空夸克转存目录`
- `刷新影巢Cookie`
- `修复影巢签到`
- `刷新夸克Cookie`
- `修复夸克转存`

### MoviePilot 原生能力接入

除了云盘资源链，这个插件也已经接进了 `MoviePilot` 原生能力：

- 原生搜索
- PT 下载
- 订阅
- 下载任务
- 下载历史
- 入库历史
- 站点状态 / 下载器状态
- 热门探索 / 推荐

## 命令文档

如果你想直接查看完整命令，而不是继续读说明，优先看：

- [`AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md`](../docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md)
- [`PLUGIN_INSTALL.md`](../docs/PLUGIN_INSTALL.md)

## 和旧插件的关系

这个插件的定位是：**把旧的分散能力收成主线。**

常见旧插件和用途可以简单理解成这样：

| 旧插件 | 主要用途 |
| --- | --- |
| `FeishuCommandBridgeLong` | 旧的飞书命令桥接入口 |
| `HdhiveOpenApi` | 影巢搜索、解锁、账号与配额相关能力 |
| `QuarkShareSaver` | 夸克分享转存 |
| `HDHiveDailySign` | 旧的影巢签到与网页 Cookie 兜底 |

这几个旧插件常见的依存关系是：

- `FeishuCommandBridgeLong` 负责接收飞书命令
- `HdhiveOpenApi` 负责影巢搜索、解锁和影巢用户态能力
- `QuarkShareSaver` 负责夸克分享转存
- `HDHiveDailySign` 负责旧的影巢签到兜底

也就是说，旧方案通常是：

- 用一个插件收消息
- 再分别调用不同插件完成影巢、夸克和签到兜底的具体动作

这套旧组合仍然能用，但更适合兼容老环境，不适合作为后续主线继续扩展。

## 新手最容易踩的坑

### 1. 外部智能体喜欢乱改命令

例如：

- 把 `云盘搜索` 偷换成 `盘搜搜索`
- 把 `更新检查` 改成普通搜索
- 把原始结果改写成“推荐资源 / 分析结论”

如果你接外部智能体，优先看：

- [`AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md`](../docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md)

### 2. 影巢 Cookie 不建议手工抄

如果影巢签到失效，不建议手工找 Cookie。

更稳的方式是：

- 在浏览器登录 `https://hdhive.com`
- 然后运行仓库里的本机导出工具：`tools/hdhive-cookie-export/`

### 3. 夸克失败不一定是 Cookie 失效

这些情况不要误判成 Cookie 问题：

- 分享受限
- `41031`
- 分享者封禁

只有明确出现：

- `require login [guest]`
- `夸克登录态已过期`
- `当前夸克登录态不足`

才优先走夸克 Cookie 修复。

## 进一步阅读

如果你只是新手用户，到这里已经够用了。

如果你还想继续看更细的安装、接入和远程用法，再看这些文档：

- [`PLUGIN_INSTALL.md`](../docs/PLUGIN_INSTALL.md)
- [`AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md`](../docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md)
- [`AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md`](../docs/AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md)
- [`AI识别增强 README`](../AIRecognizerEnhancer/README.md)

## 当前状态

- 当前版本：`0.2.68`
- 当前 helper 版本：`0.1.42`
- 当前发布页：<https://github.com/liuyuexi1987/MoviePilot-Plugins/releases/tag/v0.2.68>
