# MoviePilot-Plugins

这个仓库现在主要维护 5 个 MoviePilot 插件，核心思路不是“插件越多越好”，而是把几个关键环节拆清楚：

- `MoviePilot` 负责搜索、订阅、整理、入库
- `P115StrmHelper` 负责 115 落地、整理目录、STRM 等底层能力
- 这个仓库里的插件负责把影巢、飞书、AI 识别、极影视刷新这些能力接进现有流程
- 智能体负责调用稳定入口，不直接硬拼站点接口

如果你只想先理解“这几个插件分别干什么、怎么配合”，先看下面这段就够了。

## 插件分工

这个仓库里的 5 个插件分别是：

1. `AIRecoginzerForwarder`
2. `FeishuCommandBridgeLong`
3. `HdhiveOpenApi`
4. `HDHiveDailySign`
5. `ZspaceMediaFreshMix`

它们各自更像这样：

- 想做“原生识别失败后的 AI 兜底”：
  用 `AIRecoginzerForwarder`
- 想在飞书里直接操作 MoviePilot / 115 / STRM：
  用 `FeishuCommandBridgeLong`
- 想把影巢资源搜索、解锁、签到、115 转存整合进 MoviePilot：
  用 `HdhiveOpenApi`
- 想只保留一个更轻量的影巢签到插件：
  用 `HDHiveDailySign`
- 想让极影视按 MP 最近入库自动刷新，而且电影/电视剧共用一个分类：
  用 `ZspaceMediaFreshMix`

## 和 115 的关系

这几个插件里，和 `115` 关系最直接的是两块：

- `HdhiveOpenApi`
  负责“搜索影巢资源 -> 解锁 -> 判断是不是 115 分享链接 -> 调用 115 转存”
- `FeishuCommandBridgeLong`
  负责“在飞书里触发 115 整理、STRM 生成、命令桥接”

但真正落到 `115` 目录、`/待整理`、STRM 生成这层，通常还是依赖你现有环境里的：

- `P115StrmHelper`

可以把它理解成：

- `HdhiveOpenApi` 是资源入口
- `FeishuCommandBridgeLong` 是远程操作入口
- `P115StrmHelper` 是 115 文件落地和整理能力

也就是说，这个仓库不是替代 `P115StrmHelper`，而是和它配合。

## 和智能体怎么配合

这套仓库现在更推荐的做法不是让智能体自己写临时脚本、自己拼接口，而是：

- 插件做能力
- 智能体做调度

最典型的一条链路是：

1. 智能体根据片名发起影巢搜索
2. `HdhiveOpenApi` 负责把关键词转换成可搜索的候选并返回资源列表
3. 智能体只展示前几条结果，让用户按编号选
4. 插件执行解锁
5. 如果返回的是 `115` 分享链接，再交给现有 115 流程落到 `/待整理`
6. 后续 MoviePilot / `P115StrmHelper` 继续整理、生成 STRM 或补充操作

另一条常见链路是：

1. 智能体在飞书侧接收自然语言或命令
2. `FeishuCommandBridgeLong` 把命令桥接进 MoviePilot / 115 流程
3. 如果媒体识别失败，再由 `AIRecoginzerForwarder` 做兜底识别

所以这几个插件不是平铺的独立小工具，更像一套配合关系：

- `HdhiveOpenApi` 解决资源搜索、解锁和 115 落地入口
- `FeishuCommandBridgeLong` 解决远程控制入口
- `AIRecoginzerForwarder` 解决识别失败后的补救
- `ZspaceMediaFreshMix` 解决入库后的极影视刷新
- `HDHiveDailySign` 解决签到这种独立轻量任务

---

## 智能体 Skill 模板

如果你是为了“把影巢搜索 -> 选择 -> 解锁 -> 115 落地”这条链路交给 AI 智能体，直接看这里：

- 公开版 Skill 模板：
  [skills/hdhive-search-unlock-to-115/README.md](./skills/hdhive-search-unlock-to-115/README.md)
- Skill 主说明：
  [skills/hdhive-search-unlock-to-115/SKILL.md](./skills/hdhive-search-unlock-to-115/SKILL.md)
- 推荐提示词：
  [skills/hdhive-search-unlock-to-115/PROMPTS.md](./skills/hdhive-search-unlock-to-115/PROMPTS.md)
- 推荐搭配支持技能和工作流调度的智能体工作台使用，例如腾讯 WorkBuddy 或兼容 Codex Skill 工作流的客户端。

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

## 2. 飞书命令桥接

插件名：

- `FeishuCommandBridgeLong`

作用：

- 用飞书长连接接收消息
- 在飞书里直接发命令
- 桥接到 MoviePilot 和 115 / STRM 流程

适合场景：

- 想在飞书里远程操作 MoviePilot
- 想执行 `刮削`、`生成STRM`、`全量STRM`、`版本`
- 不想折腾公网 webhook 和 HTTPS 回调

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

## 5. 极影视刷新（自用魔改）

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

当前已经包含：

- `plugins/hdhiveopenapi`
- `plugins.v2/hdhiveopenapi`
- `plugins/hdhivedailysign`
- `plugins.v2/hdhivedailysign`
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
HdhiveOpenApi/
docs/
```

其中：

- `plugins` 和 `plugins.v2` 是 MoviePilot 实际读取的插件目录
- 根目录下的 `AIRecoginzerForwarder/`、`HdhiveOpenApi/` 主要放 README 和补充说明

---

## 当前推荐理解

如果你只记一句话，可以记这个：

- `AIRecoginzerForwarder` 解决“识别失败后的兜底”
- `FeishuCommandBridgeLong` 解决“飞书远程控制 MoviePilot”
- `HdhiveOpenApi` 解决“影巢资源搜索、解锁和 115 落地”
- `HDHiveDailySign` 解决“影巢每日签到”
- `ZspaceMediaFreshMix` 解决“极影视混合分类刷新不稳定”
