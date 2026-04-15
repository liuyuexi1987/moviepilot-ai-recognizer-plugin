# HdhiveSign

MoviePilot 影巢签到插件。

这个插件专门解决一件事：

`自动完成影巢(HDHive)每日签到`

相比只保留一个简单 Cookie 的早期版本，这一版已经补充了更多兜底能力。

---

## 当前版本

- 插件名：`影巢签到`
- 版本：`1.4.6`
- 作者：`madrays`

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
plugins.v2/hdhivesign/__init__.py
plugins/hdhivesign/__init__.py
icons/hdhive.ico
```

并已写入：

```text
package.json
package.v2.json
```

---

## 隐私注意

这个插件本身会在运行时读取：

- Cookie
- 用户名
- 密码

但这些都属于运行时配置，不应该写死进仓库。

当前同步到 GitHub 的版本已经检查过：

- 没有明文 Cookie
- 没有明文用户名密码
- 没有本机绝对路径

---

## 与 HdhiveOpenApi 的关系

可以简单这样理解：

- `HdhiveSign`：更轻，只管签到
- `HdhiveOpenApi`：更完整，管签到、搜索、解锁、115 转存、分享管理

如果你只想保留一个插件，通常更推荐：

- `HdhiveOpenApi`

如果你想保留一个更轻量、单功能的签到插件，也可以继续发布：

- `HdhiveSign`
