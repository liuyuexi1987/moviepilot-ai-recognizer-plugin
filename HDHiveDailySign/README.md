# HDHiveDailySign

MoviePilot 影巢签到插件。

这是一份基于原作者 `madrays` 的影巢签到插件整理出来的自用魔改版，主要按我自己的 MoviePilot 环境和使用习惯做了兼容、修补和页面调整。

如果你只是想用一个更通用、跟进更及时的原版实现，优先建议关注原作者仓库：

- 原作者：`madrays`
- 原始仓库：[madrays/MoviePilot-Plugins](https://github.com/madrays/MoviePilot-Plugins)

这个分支专门解决一件事：

`自动完成影巢(HDHive)每日签到`

---

## 当前版本

- 插件名：`HDHive Daily Sign`
- 版本：`1.0.0`
- 作者：`liuyuexi1987`

---

## 来源说明

这不是从零开始写的新插件，而是：

- 基于原作者 `madrays` 的影巢签到插件继续调整
- 按我自己的 MoviePilot 环境做兼容和修补
- 增加一些更偏自用的日志、页面和兜底细节

如果你后续需要：

- 更标准地跟进原版演进
- 第一时间获取原作者后续修复
- 尽量减少分支差异

更推荐直接关注原作者仓库。

---

## 功能说明

当前版本支持：

- 每日自动签到
- 普通签到
- 赌狗签到
- 失败重试
- 签到历史记录
- 自动登录获取 Cookie
- 兼容旧接口与 Next Server Action 两条签到链路

---

## 适合场景

适合下面这种需求：

- 只想做影巢签到
- 不需要资源搜索和解锁
- 不需要 115 自动转存
- 想保留一个更轻量的影巢插件

如果你要的是：

- 资源搜索
- 资源解锁
- 115 自动转存
- 分享管理

那更适合用：

- `HdhiveOpenApi`

---

## 当前仓库内的位置

这个插件已经同步到：

```text
plugins.v2/hdhivedailysign/__init__.py
plugins/hdhivedailysign/__init__.py
icons/hdhive.ico
```

并已写入：

```text
package.json
package.v2.json
```

---

## 与 HdhiveOpenApi 的关系

可以简单这样理解：

- `HDHiveDailySign`：更轻，只管签到
- `HdhiveOpenApi`：更完整，管签到、搜索、解锁、115 转存、分享管理

如果你只想保留一个插件，通常更推荐：

- `HdhiveOpenApi`

如果你想保留一个更轻量、单功能的签到插件，也可以继续发布：

- `HDHiveDailySign`
