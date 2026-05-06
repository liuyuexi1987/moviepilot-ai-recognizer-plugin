# 重构计划：Agent Suite

> 这是历史重构规划文档，主要用于回看设计演进。
> 当前安装、接入、发布请优先看 `README.md`、`docs/INDEX.md`、`docs/PLUGIN_INSTALL.md`、`docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md`。

这个仓库接下来不再继续沿着“功能越分越散”的方向增长，而是进入一次有边界的重构：

- 保留旧插件作为可运行的 `legacy` 参考
- 在新分支上并行重建两套新插件
- 等新插件链路跑稳后，再逐步归档旧插件

当前重构分工如下：

## 目标插件

### 1. Agent影视助手

定位：

- 智能体友好的资源工作流主插件
- 对外统一承接搜索、选择、解锁、转存、签到、远程消息入口

计划整合的现有能力：

- `FeishuCommandBridgeLong`
- `HdhiveOpenApi`
- `HDHiveDailySign`
- `QuarkShareSaver`

首期能力边界：

- 盘搜 / 影巢搜索与候选选择
- 影巢资源解锁
- 115 / 夸克自动转存
- 通用分享链接路由
- MP 原生 Agent Tool / 插件 API / 智能体会话入口
- 飞书桥接后续按需委托

### 2. AI识别增强

定位：

- MoviePilot 原生识别失败后的本地 AI 识别增强插件
- 不再依赖外部 AI Gateway 作为必经链路

计划承接的现有能力：

- 已全部收敛到 `AIRecognizerEnhancer`

首期能力边界：

- 识别失败事件兜底
- 直接调用 MP 内置 LLM 配置进行结构化识别
- 自动二次整理
- 为后续“自定义识别词建议”预留扩展点

## 旧插件处理原则

重构期间，以下目录优先保留；自用魔改和旧签到插件可逐步从公开仓库下架：

- `FeishuCommandBridgeLong`
- `HdhiveOpenApi`
- `QuarkShareSaver`

处理原则：

- 旧插件继续作为线上可运行版本
- `FeishuCommandBridgeLong` 当前继续保留为兼容飞书入口，不做删除
- `HDHiveDailySign`、`ZspaceMediaFreshMix` 更适合本地自用，不再作为公开主线插件继续发布
- 新功能尽量优先落到新插件设计里
- 旧插件只做必要修复，不再继续扩张边界

## 迁移顺序

建议按下面顺序逐步迁移，避免同时重写太多链路：

1. `Agent影视助手` 先完成目录骨架、配置模型和入口设计
2. 先搬入 `QuarkShareSaver` 的稳定执行能力
3. 再搬入 `HdhiveOpenApi` 的搜索、解锁、转存能力
4. 接入原生 Agent Tool 与统一 API
5. 最后把 `FeishuCommandBridgeLong` 收缩为消息入口和会话层
6. 单独重写 `AI识别增强`

## 为什么不是一个插件

这次明确不做“超级大插件”，原因很实际：

- 搜索/转存/签到属于资源工作流
- 识别失败兜底属于整理工作流
- 两类逻辑耦合过深后，配置、排障和升级成本都会显著升高

最终目标是：

- 对外看起来像一套统一产品
- 仓库内部保留两个清晰边界

## 分支与备份

本次重构采用：

- 备份归档后再开新分支
- 在 `codex/rebuild-agent-suite` 上推进

仓库外备份文件已单独存放，作为重构前快照。

## 当前状态

当前已完成：

- 仓库快照备份
- 重构分支创建
- `Agent影视助手` 目录、配置模型、执行层、统一 API 已落地
- `Agent影视助手` 已接通影巢搜索/解锁、115 转存、夸克转存、盘搜搜索与直链路由
- `Agent影视助手` 已接通原生 Agent Tool 和智能体会话式 API
- `Agent影视助手` 已补齐影巢候选分页与 `详情` / `审查` 按需补主演，飞书新主线不再缺这段交互
- `Agent影视助手` 已补齐 `P115StrmHelper` 新版 MoviePilot 兼容补丁脚本，115 健康检查已验证 `p115_ready=true`
- `Agent影视助手` 已新增 115 轻量直转层，分享链接落盘可优先不走 `P115StrmHelper.sharetransferhelper`，失败时再回退旧执行层
- `FeishuCommandBridgeLong` 保持线上可运行，默认继续走 `legacy` 快路径
- `FeishuCommandBridgeLong` 已支持切换到 `auto`，把智能入口委托给 `Agent影视助手`
- 运行环境已完成双链路验证：`legacy` 日常可用，`auto` 可接手统一资源工作流
- `AIRecognizerEnhancer` 已进入 `0.1.11` 阶段，可直接复用 MoviePilot 当前 LLM 配置，在 `NameRecognize` 阶段做本地结构化兜底，并支持失败样本维护、样本洞察、精简摘要、直接转建议、批量建议、写入动作、样本出队、样本复查和批量复查；当识别词建议模型退化时会自动切到精确规则兜底

下一步重点：

1. 继续把影巢签到、用户态、配额态能力评估是否并入 `Agent影视助手`
2. 继续打磨 `AIRecognizerEnhancer` 的提示词、失败样本洞察和识别词建议质量
3. 继续完善 `AgentResourceOfficer` Skill 与外部智能体的低 token、可恢复、可审计调用链路
