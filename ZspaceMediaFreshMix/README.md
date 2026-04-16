# ZspaceMediaFreshMix

MoviePilot 极影视刷新插件。

这是一份基于原作者 `gxterry` 的“刷新极影视”插件整理出来的自用魔改版，主要按我自己的 MoviePilot、极影视分类方式和极空间 Cookie 形态做了兼容和修补。

如果你更想跟进原版更新，优先建议关注原作者仓库：

- 原作者：`gxterry`
- 原始仓库：[gxterry/MoviePilot-Plugins](https://github.com/gxterry/MoviePilot-Plugins)

这个分支专门解决一件事：

`按 MoviePilot 最近入库记录刷新极影视分类`

---

## 当前版本

- 插件名：`极影视刷新（自用魔改）`
- 插件 ID：`ZspaceMediaFreshMix`
- 版本：`1.0.0`
- 作者：`liuyuexi1987`

---

## 来源说明

这不是从零开始写的新插件，而是：

- 基于原作者 `gxterry` 的极影视刷新插件继续调整
- 按我自己的 MoviePilot 环境做兼容和修补
- 增加一些更偏自用的分类处理和 Cookie 兼容逻辑

如果你后续需要：

- 更标准地跟进原版演进
- 第一时间获取原作者后续修复
- 尽量减少分支差异

更推荐直接关注原作者仓库。

---

## 这个自用版额外处理了什么

当前版本主要补了这几件事：

- 支持电影和电视剧共用同一个极影视分类
- 只填电影分类名或电视剧分类名其中一项时，另一边自动复用
- 增加本地 Cookie 解析函数，不再依赖当前环境缺失的 `RequestUtils.cookie_parse`
- 同时兼容 `token` 和 `zenithtoken`
- 请求极影视接口时使用解析后的 Cookie 字典，避免多行 Cookie 值导致请求失败

---

## 适合场景

适合下面这种需求：

- 极影视中电影和电视剧混放在一个分类
- MoviePilot 最近入库后，希望自动触发极影视分类刷新
- 原版插件在你当前环境里无法直接跑通

---

## 当前仓库内的位置

这个插件已经同步到：

```text
plugins.v2/zspacemediafreshmix/__init__.py
plugins/zspacemediafreshmix/__init__.py
icons/zspacemediafreshmix.png
```

并已写入：

```text
package.json
package.v2.json
```

---

## 使用建议

- 如果电影和电视剧共用一个极影视分类，只填 `电影分类名` 或 `电视剧分类名` 其中一项即可
- 如果你更看重和原版一致的更新节奏，优先用原作者插件
- 如果你更看重当前这套环境已经实测跑通，适合直接用这份自用魔改版
