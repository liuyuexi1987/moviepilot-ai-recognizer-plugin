# MoviePilot-Plugins

[![CI](https://github.com/liuyuexi1987/MoviePilot-Plugins/actions/workflows/ci.yml/badge.svg)](https://github.com/liuyuexi1987/MoviePilot-Plugins/actions/workflows/ci.yml)

这个仓库现在的方向不是“插件越多越好”，而是把关键能力收拢成更清楚的两条线：

- `MoviePilot` 负责搜索、订阅、整理、入库
- `P115StrmHelper` 负责 115 落地、整理目录、STRM 等底层能力
- 这个仓库里的插件负责把影巢、飞书、夸克转存、AI 识别、极影视刷新这些能力接进现有流程
- 智能体负责调用稳定入口，不直接硬拼站点接口

如果你只想先理解“这几个插件分别干什么、怎么配合”，先看下面这段就够了。

## 重构状态

这个仓库已经进入下一阶段重构：

- 旧插件目录继续保留，作为当前可运行版本
- 新能力逐步收拢到两套新插件
  - `Agent资源官`
  - `AI识别增强`
- 重构说明见：
  [docs/REBUILD_AGENT_SUITE.md](./docs/REBUILD_AGENT_SUITE.md)

当前已经进入第一阶段可用状态的新插件是：

- `Agent资源官`
  - 已支持影巢搜索、盘搜搜索、115 直链、夸克直链统一入口
  - 已支持影巢解锁后自动路由到 115 / 夸克执行层
  - 已支持原生 Agent Tool、插件 API、智能体会话式调用和可选内置飞书入口
- `FeishuCommandBridgeLong`
  - 继续保留，不删除
  - 当前定位为兼容/备份插件
  - 新用户优先使用 `Agent资源官` 内置飞书入口，避免同一个飞书机器人被两个插件同时监听

`AI识别增强` 已进入第一版可用阶段，方向是逐步替代旧版 AI Gateway 转发链路。

当前发布版本：

- `AIRecoginzerForwarder`（AI 识别转发）：`2.0.1`
- `AIRecognizerEnhancer`（AI识别增强）：`0.1.11`
- `AgentResourceOfficer`：`0.1.112`
- `FeishuCommandBridgeLong`（飞书命令桥接）：`0.5.26`
- `HdhiveOpenApi`（影巢 OpenAPI）：`0.3.0`
- `HDHiveDailySign`（HDHive Daily Sign）：`1.0.0`
- `QuarkShareSaver`（夸克分享转存）：`0.1.0`
- `ZspaceMediaFreshMix`（极影视刷新（自用魔改））：`1.0.0`

## 插件分工

当前线上主插件仍然是这些：

1. `AIRecoginzerForwarder`：AI 识别转发
2. `AIRecognizerEnhancer`：AI识别增强
3. `AgentResourceOfficer`：Agent资源官
4. `FeishuCommandBridgeLong`：飞书命令桥接
5. `HdhiveOpenApi`：影巢 OpenAPI
6. `HDHiveDailySign`：HDHive Daily Sign
7. `QuarkShareSaver`：夸克分享转存
8. `ZspaceMediaFreshMix`：极影视刷新（自用魔改）

其中 `AIRecognizerEnhancer` 是新识别线的固定落点，当前已经能接住 `NameRecognize` 并回写结构化识别结果；旧 `AIRecoginzerForwarder` 暂时继续保留。

它们各自更像这样：

- 想做“原生识别失败后的 AI 兜底”：
  用 `AIRecoginzerForwarder`
- 想给智能体、原生 Agent Tool、飞书入口统一一个资源执行主线：
  用 `AgentResourceOfficer`
- 老环境想继续使用独立飞书桥接：
  用 `FeishuCommandBridgeLong`
- 想把影巢资源搜索、解锁、签到、115 转存整合进 MoviePilot：
  用 `HdhiveOpenApi`
- 想只保留一个更轻量的影巢签到插件：
  用 `HDHiveDailySign`
  `HdhiveOpenApi` 里的 OpenAPI 签到需要付费用户时，这个轻量签到插件会更合适
- 想把夸克分享链接直接转存到自己的夸克网盘目录：
  用 `QuarkShareSaver`
- 想让极影视按 MP 最近入库自动刷新，而且电影/电视剧共用一个分类：
  用 `ZspaceMediaFreshMix`

## 和 115 的关系

这几个插件里，和 `115` 关系最直接的是四块：

- `AgentResourceOfficer`
  负责“统一接住智能体 / Agent Tool / API 的资源请求 -> 分流到影巢、115、夸克执行层”
  影巢候选已支持分页，以及按需 `详情` / `审查` 补主演
- `FeishuCommandBridgeLong`
  作为旧飞书桥接兼容入口保留；新飞书入口建议直接开启 `AgentResourceOfficer` 内置 Channel
- `HdhiveOpenApi`
  负责“搜索影巢资源 -> 解锁 -> 判断是不是 115 分享链接 -> 调用 115 转存”
- `QuarkShareSaver`
  负责“把夸克分享链接稳定转存到自己的夸克目录”

但真正落到 `115` 目录、`/待整理`、STRM 生成这层，通常还是依赖你现有环境里的：

- `P115StrmHelper`

可以把它理解成：

- `AgentResourceOfficer` 是新的资源中枢入口
- `AgentResourceOfficer` 内置飞书 Channel 是新的远程操作入口
- `FeishuCommandBridgeLong` 是旧飞书兼容/备份入口
- `HdhiveOpenApi` 是旧影巢能力入口
- `QuarkShareSaver` 是夸克分享落盘入口
- `P115StrmHelper` 是 115 文件落地和整理能力

也就是说，这个仓库不是替代 `P115StrmHelper`，而是和它配合。

当前 `AgentResourceOfficer 0.1.112` 已经具备 115 分享链接轻量直转层，并接入和 `P115StrmHelper` 同款的扫码登录能力：可以优先使用扫码得到的客户端会话，也可以复用当前已加载的 115 客户端，直转失败时再回退 `P115StrmHelper`。但 STRM 生成、302、全量/增量同步和媒体库整理仍建议继续由 `P115StrmHelper` 负责。

如果升级 MoviePilot 后 `P115StrmHelper` 因旧事件导入失败无法加载，可以使用仓库里的兼容脚本恢复：

```bash
MP_CONTAINER=moviepilot-v2 ./scripts/patch-p115strmhelper-mp-compat.sh
```

## 和智能体怎么配合

这套仓库现在更推荐的做法不是让智能体自己写临时脚本、自己拼接口，而是：

- 插件做能力
- 智能体做调度

最典型的一条链路是：

1. 智能体把自然语言、片名或分享链接发给 `AgentResourceOfficer`
2. `AgentResourceOfficer` 负责判断是影巢搜索、盘搜搜索，还是 115 / 夸克直链路由
3. 智能体只展示前几条结果，让用户按编号选
4. 插件执行解锁或转存
5. 如果返回的是 `115` 分享链接，再交给现有 115 流程落到 `/待整理`
6. 后续 MoviePilot / `P115StrmHelper` 继续整理、生成 STRM 或补充操作

飞书链路现在推荐直接走资源官内置 Channel：

1. 智能体在飞书侧接收自然语言或命令
2. `AgentResourceOfficer` 内置飞书入口把消息转成统一 `assistant/route` 或 `assistant/pick`
3. 资源官判断是影巢、盘搜、115、夸克、MP 搜索还是 STRM 调度
4. 插件执行后把结果回到飞书
5. 老 `FeishuCommandBridgeLong` 只作为兼容/备份入口保留

所以这几个插件不是平铺的独立小工具，更像一套配合关系：

- `AgentResourceOfficer` 解决智能体 / Agent Tool 的统一资源入口
- `AgentResourceOfficer` 内置飞书 Channel 解决新远程控制入口
- `FeishuCommandBridgeLong` 保留旧远程控制兼容入口
- `HdhiveOpenApi` 继续保留旧影巢 OpenAPI 入口
- `QuarkShareSaver` 解决夸克分享转存入口
- `AIRecoginzerForwarder` 解决识别失败后的补救
- `ZspaceMediaFreshMix` 解决入库后的极影视刷新
- `HDHiveDailySign` 解决签到这种独立轻量任务

---

## 智能体 Skill 模板

GitHub Actions artifact 和正式 Release 附件会同时附带公开 Skill ZIP：

- `agent-resource-officer-<version>.zip`
- `hdhive-search-unlock-to-115-<version>.zip`

如果你从源码仓库安装，也可以直接运行下面的 `install.sh`。

如果你是为了让外部智能体直接控制 `AgentResourceOfficer` 这条新主线，优先看这里：

- AgentResourceOfficer Skill 模板：
  [skills/agent-resource-officer/README.md](./skills/agent-resource-officer/README.md)
- Skill 主说明：
  [skills/agent-resource-officer/SKILL.md](./skills/agent-resource-officer/SKILL.md)
- 推荐提示词：
  [skills/agent-resource-officer/PROMPTS.md](./skills/agent-resource-officer/PROMPTS.md)

外部智能体优先从这几个 helper 命令开始：

```bash
bash skills/agent-resource-officer/install.sh --dry-run
bash skills/agent-resource-officer/install.sh
python3 ~/.codex/skills/agent-resource-officer/scripts/aro_request.py readiness
python3 ~/.codex/skills/agent-resource-officer/scripts/aro_request.py decide --summary-only
python3 ~/.codex/skills/agent-resource-officer/scripts/aro_request.py decide --command-only
python3 ~/.codex/skills/agent-resource-officer/scripts/aro_request.py decide --command-only --confirmed
```

其中 `readiness` 用来确认配置、本地 helper 和插件接口都正常；`decide --summary-only` 用来判断继续旧会话还是开始新流程；`--command-only` 只输出下一步 helper 命令，遇到需要确认的动作时，只有加 `--confirmed` 才会输出执行命令。

如果你是为了“把影巢搜索 -> 选择 -> 解锁 -> 115 落地”这条链路交给 AI 智能体，直接看这里：

- 公开版 Skill 模板：
  [skills/hdhive-search-unlock-to-115/README.md](./skills/hdhive-search-unlock-to-115/README.md)
- Skill 主说明：
  [skills/hdhive-search-unlock-to-115/SKILL.md](./skills/hdhive-search-unlock-to-115/SKILL.md)
- 推荐提示词：
  [skills/hdhive-search-unlock-to-115/PROMPTS.md](./skills/hdhive-search-unlock-to-115/PROMPTS.md)
- 推荐搭配支持技能和工作流调度的智能体工作台使用，例如腾讯 WorkBuddy 或兼容 Codex Skill 工作流的客户端。
- 如果你已经接入 MP 原生 Agent / MCP，更推荐直接调用 `AgentResourceOfficer` 的统一 API / Agent Tool，而不是让智能体自己拼影巢或夸克接口。

快速安装和本地验证：

```bash
bash skills/hdhive-search-unlock-to-115/install.sh --dry-run
bash skills/hdhive-search-unlock-to-115/install.sh
python3 ~/.codex/skills/hdhive-search-unlock-to-115/scripts/hdhive_agent_tool.py version
python3 ~/.codex/skills/hdhive-search-unlock-to-115/scripts/hdhive_agent_tool.py selftest
```

---

## 1. AI 识别转发

插件名：

- `AIRecoginzerForwarder`

作用：

- MoviePilot 原生 TMDB 识别失败
- 插件把标题和路径转发给 AI Gateway
- Gateway 识别完成后回调 MoviePilot
- 插件继续触发二次整理

适合场景：

- PT / 网盘资源命名很乱
- 115 挂载文件名不规范
- 原生识别失败率比较高

相关说明：

- [AIRecoginzerForwarder/README.md](./AIRecoginzerForwarder/README.md)
- 配套网关仓库：[moviepilot-ai-recognizer-gateway](https://github.com/liuyuexi1987/moviepilot-ai-recognizer-gateway)

---

## 1.1 AI 识别增强

插件名：

- `AIRecognizerEnhancer`

作用：

- MoviePilot 原生识别失败时，在本机直接复用当前已启用的 LLM 配置
- 结构化推断作品名、年份、类型、季集
- 把结果回写给 MoviePilot，继续原生二次识别

适合场景：

- 不想再维护额外 AI Gateway
- 想先把 AI 识别增强收口到 MP 容器内
- 想逐步替代旧版外部回调链路

当前状态：

- `0.1.11` 已可用
- 已提供健康检查、手动识别、失败样本摘要、失败样本洞察、失败样本精简摘要、失败样本查看、按样本移除、按样本复查、批量复查、批量建议、批量写入、识别词建议、按样本直出建议和按样本直写规则 API，并在建议模型退化时自动走精确规则兜底
- 后续继续补提示词、失败样本分析与自定义识别词建议质量

---

## 2. 飞书命令桥接

插件名：

- `FeishuCommandBridgeLong`

作用：

- 作为旧飞书长连接桥接的兼容/备份入口
- 保留老环境里已经习惯的飞书命令体验
- 新资源动作建议逐步切到 `AgentResourceOfficer` 内置飞书入口

适合场景：

- 已经装好旧飞书桥接，暂时不想迁移
- 只需要旧命令快路径，例如 `刮削`、`生成STRM`、`全量STRM`、`版本`
- 需要保留一个和 `AgentResourceOfficer` 内置飞书入口相互独立的备份入口
- 不想折腾公网 webhook 和 HTTPS 回调

新用户如果只想装一个入口，优先开启 `AgentResourceOfficer` 内置飞书 Channel；同一个飞书 App 不建议同时开启两个长连接入口。

---

## 3. 影巢 OpenAPI

插件名：

- `HdhiveOpenApi`

作用：

- 对接影巢 Open API
- 在 MoviePilot 内完成签到、用户信息、资源搜索、资源解锁、115 转存、分享管理、用量与配额查询

当前版本重点能力：

- 通过关键词或 TMDB ID 搜索资源
- 自动走 MoviePilot 媒体搜索，把片名转换成影巢可用的 TMDB 候选
- 解锁资源
- 解锁 115 资源后自动转存到 `/待整理`
- 支持分享创建、更新、删除、详情和列表
- 支持普通签到 / 赌狗签到
- 支持查询配额和今日用量

适合场景：

- 想在 MoviePilot 里直接用影巢 OpenAPI
- 想做“搜索 -> 选资源 -> 解锁 -> 落 115 `/待整理`”这条链路
- 想给 AI 智能体一个稳定入口，不让它自己拼影巢 API

详细说明：

- [HdhiveOpenApi/README.md](./HdhiveOpenApi/README.md)
- 对应的公开智能体 Skill 模板：
  [skills/hdhive-search-unlock-to-115/README.md](./skills/hdhive-search-unlock-to-115/README.md)

---

## 4. 影巢签到

插件名：

- `HDHiveDailySign`

作用：

- 自动完成影巢每日签到
- 支持普通签到 / 赌狗签到
- 支持失败重试、自动登录和历史记录

说明：

- 这是基于原作者 `madrays` 的影巢签到插件整理出来的自用魔改版
- 如果你更想跟进原版更新，推荐优先关注原作者仓库：
  [madrays/MoviePilot-Plugins](https://github.com/madrays/MoviePilot-Plugins)

适合场景：

- 只想做影巢签到
- 不需要资源搜索和解锁
- 想保留一个更轻量的独立插件

详细说明：

- [HDHiveDailySign/README.md](./HDHiveDailySign/README.md)

---

## 5. 夸克分享转存

插件名：

- `QuarkShareSaver`

作用：

- 把夸克分享链接直接转存到自己的夸克网盘目录
- 目录不存在时自动创建
- 提供稳定 API 给智能体和飞书桥接调用

适合场景：

- 智能体拿到夸克分享链接后，需要一个稳定落盘入口
- 想把“搜索”和“转存”拆开，避免智能体自己硬拼夸克接口
- 想在飞书里直接发命令完成夸克转存

详细说明：

- [QuarkShareSaver/README.md](./QuarkShareSaver/README.md)

---

## 6. 极影视刷新（自用魔改）

插件名：

- `ZspaceMediaFreshMix`

作用：

- 按 MoviePilot 最近入库记录刷新极影视分类
- 兼容电影和电视剧共用一个极影视分类
- 兼容新版极空间 Cookie 字段

说明：

- 这是基于原作者 `gxterry` 刷新极影视插件整理出来的自用魔改版
- 如果你更想跟进原版更新，推荐优先关注原作者仓库：
  [gxterry/MoviePilot-Plugins](https://github.com/gxterry/MoviePilot-Plugins)

适合场景：

- 极影视里电影和电视剧混放在同一个分类
- 官方原版在你当前极空间 Cookie 形态下无法直接工作
- 想保留一个独立插件身份，避免和原版配置、统计互相影响

详细说明：

- [ZspaceMediaFreshMix/README.md](./ZspaceMediaFreshMix/README.md)

---

## 安装方式

这个仓库已经补齐 MoviePilot 自定义仓库所需结构：

- `package.json`
- `package.v2.json`
- `plugins/...`
- `plugins.v2/...`

也就是说，既可以走自定义插件仓库，也可以按目录本地安装。

最新正式 Release 下载：

- [v2026.04.28.2](https://github.com/liuyuexi1987/MoviePilot-Plugins/releases/tag/v2026.04.28.2)

发布和本地打包相关文档：

- [插件安装说明](./docs/PLUGIN_INSTALL.md)
- [GitHub 发布说明](./docs/GITHUB_PUBLISH.md)
- [Release Checklist](./docs/RELEASE_CHECKLIST.md)
- [ZIP 打包说明](./docs/PACKAGING.md)

当前已经包含：

- `plugins/airecoginzerforwarder`
- `plugins.v2/airecoginzerforwarder`
- `plugins/airecognizerenhancer`
- `plugins.v2/airecognizerenhancer`
- `plugins/agentresourceofficer`
- `plugins.v2/agentresourceofficer`
- `plugins/feishucommandbridgelong`
- `plugins.v2/feishucommandbridgelong`
- `plugins/hdhiveopenapi`
- `plugins.v2/hdhiveopenapi`
- `plugins/hdhivedailysign`
- `plugins.v2/hdhivedailysign`
- `plugins/quarksharesaver`
- `plugins.v2/quarksharesaver`
- `plugins/zspacemediafreshmix`
- `plugins.v2/zspacemediafreshmix`

---

## 仓库结构

```text
package.json
package.v2.json
icons/
plugins/
plugins.v2/
skills/
AIRecoginzerForwarder/
AIRecognizerEnhancer/
AgentResourceOfficer/
FeishuCommandBridgeLong/
HdhiveOpenApi/
HDHiveDailySign/
QuarkShareSaver/
ZspaceMediaFreshMix/
docs/
```

其中：

- `plugins` 和 `plugins.v2` 是 MoviePilot 实际读取的插件目录
- 根目录下的同名插件目录主要放主源码、README 和补充说明；部分旧插件代码仍以 `plugins/`、`plugins.v2/` 为准

---

## 当前推荐理解

如果你只记一句话，可以记这个：

- `AIRecoginzerForwarder` 解决“识别失败后的兜底”
- `AIRecognizerEnhancer` 解决“新识别增强线的结构化识别”
- `AgentResourceOfficer` 解决“智能体统一资源入口和执行编排”
- `FeishuCommandBridgeLong` 解决“旧飞书远程控制兼容/备份”
- `HdhiveOpenApi` 解决“影巢资源搜索、解锁和 115 落地”
- `HDHiveDailySign` 解决“影巢每日签到”
- `QuarkShareSaver` 解决“夸克分享链接稳定转存”
- `ZspaceMediaFreshMix` 解决“极影视混合分类刷新不稳定”
