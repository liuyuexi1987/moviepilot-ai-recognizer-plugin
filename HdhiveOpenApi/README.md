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

如果你想把这套能力交给 AI 智能体，最推荐的方式不是让智能体自己拼影巢 API，而是：

`插件做能力，智能体做调度`

也就是：

- 插件负责搜索、解锁、115 转存
- 智能体只负责调用稳定接口、展示结果、让用户选编号

本机已经配套了一套 Skill，专门给智能体使用：

```text
~/.codex/skills/hdhive-search-unlock-to-115
```

最推荐的单入口脚本是：

```text
~/.codex/skills/hdhive-search-unlock-to-115/scripts/hdhive_agent_tool.py
```

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
