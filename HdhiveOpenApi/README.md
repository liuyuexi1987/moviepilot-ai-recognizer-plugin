# HdhiveOpenApi

MoviePilot 影巢 OpenAPI 插件。

这个插件的目标很明确：

把影巢的核心能力直接接进 MoviePilot，包括：

- 用户信息查询
- 每日签到
- 资源搜索
- 资源解锁
- 115 自动转存
- 分享管理
- 用量与配额查询

---

## 当前版本重点

当前版本已经覆盖这些核心能力：

1. 用户信息查询
2. 每日签到
3. 资源查询与解锁
4. 分享管理
5. 用量与配额
6. 115 自动转存

其中“资源查询与解锁”这条链路是当前最重要的部分。

---

## 公开 Skill 模板

如果你想把这套能力交给 AI 智能体，仓库里已经提供了一份可以直接复用的公开 Skill 模板：

- [skills/hdhive-search-unlock-to-115/README.md](../skills/hdhive-search-unlock-to-115/README.md)
- [skills/hdhive-search-unlock-to-115/SKILL.md](../skills/hdhive-search-unlock-to-115/SKILL.md)
- [skills/hdhive-search-unlock-to-115/PROMPTS.md](../skills/hdhive-search-unlock-to-115/PROMPTS.md)

适合场景：

- 让别的机器快速复现
- 让别的智能体直接调用统一流程
- 让搜索、确认、解锁、115 落地形成固定工作流

推荐搭配支持技能和工作流编排的智能体工作台使用，例如腾讯 WorkBuddy，或其它兼容 Skill 工作流的客户端。

---

## 资源搜索方式

这个插件支持两种搜索方式：

### 1. 按 TMDB ID 搜索

适合已经知道 TMDB ID 的场景。

示例：

```text
GET /api/v1/plugin/HdhiveOpenApi/resources/search?type=movie&tmdb_id=550
```

### 2. 按关键词搜索

这是当前更推荐的方式。

插件会先借助 MoviePilot 的媒体搜索能力，把片名转换成 TMDB 候选，再去影巢查资源。

示例：

```text
GET /api/v1/plugin/HdhiveOpenApi/resources/search?type=movie&keyword=超级马里奥兄弟大电影
```

支持附加参数：

- `year=2023`
- `candidate_limit=5`
- `limit=10`

---

## 资源解锁

按 `slug` 解锁资源：

```text
POST /api/v1/plugin/HdhiveOpenApi/resources/unlock
{
  "slug": "资源slug"
}
```

如果是 115 资源，还可以在解锁时直接要求自动转存：

```text
POST /api/v1/plugin/HdhiveOpenApi/resources/unlock
{
  "slug": "资源slug",
  "transfer_115": true,
  "path": "/待整理"
}
```

---

## 115 自动转存

插件已经支持把解锁得到的 115 分享链接直接交给 `P115StrmHelper`。

默认思路是：

- 解锁资源
- 如果解锁结果是 115 链接
- 自动转存到 `/待整理`

所以这条链路现在可以变成：

`搜索 -> 选择资源 -> 解锁 -> 自动落到 115 /待整理`

前提：

- `P115StrmHelper` 已安装
- 115 已登录
- `/待整理` 目录有效

---

## 非 Premium 账号说明

当前实测结论：

- 非 Premium 账号也可以正常搜索资源
- 部分接口是 Premium 限制的

常见情况：

- `/account` 可能提示 Premium 限制
- `/vip/weekly-free-quota` 可能提示 Premium 限制
- 但 `resources/search` 依然可以使用

所以对大部分“搜资源 / 解锁资源”的实际需求来说，非 Premium 用户仍然有使用价值。

---

## 智能体最佳实践

如果你想把这套能力交给 AI 智能体，仓库里更适合写“解决问题的思路”，而不是绑定某个本地 Skill 或脚本实现。

推荐思路：

`插件做能力，智能体做调度`

也就是把流程拆成下面几步：

1. 智能体接收用户输入的片名或 TMDB ID
2. 优先调用插件已经暴露的稳定接口，不直接拼影巢原始 API
3. 如果是片名搜索：
   - 先让插件完成关键词到候选影片的解析
   - 如果候选存在歧义，再补充 1 到 2 个主演名帮助用户确认版本
4. 向用户展示前 10 个资源候选
5. 等用户按编号选择后，再执行解锁
6. 如果结果是 115 资源，再继续自动转存到目标目录
7. 如果资源需要积分，必须先征求用户确认，再继续解锁

这样做的好处是：

- 更省 token
- 更稳定
- 更容易复现
- 更容易复用到别的机器和智能体环境

不推荐的做法：

- 让智能体现场拼影巢原始 API
- 让智能体自己维护 `slug`、Cookie 或其它运行时状态
- 为了区分同名影片而临时做网页登录、网页搜索或人工拼接流程

如果需要，你也可以直接从仓库里的公开模板开始：

- [skills/hdhive-search-unlock-to-115/README.md](../skills/hdhive-search-unlock-to-115/README.md)

---

## 已包含的插件目录

仓库里已经包含：

```text
plugins/hdhiveopenapi/__init__.py
plugins.v2/hdhiveopenapi/__init__.py
icons/hdhive.ico
```

并且已在：

```text
package.json
package.v2.json
```

中注册。

---

## 适合谁用

这个插件最适合下面这类用户：

- 已经在用 MoviePilot
- 手里有影巢 Open API Key
- 想在 MoviePilot 内直接完成资源搜索与解锁
- 想把 115 资源自动放进 `/待整理`
- 想给 AI 智能体一个稳定的影巢入口
