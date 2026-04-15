# MoviePilot-Plugins

这个仓库现在主要维护 3 个 MoviePilot 插件：

1. `AIRecoginzerForwarder`
2. `FeishuCommandBridgeLong`
3. `HdhiveOpenApi`

如果你是第一次打开这个仓库，直接先看这段就够了：

- 想做“原生识别失败后的 AI 兜底”：
  用 `AIRecoginzerForwarder`
- 想在飞书里直接操作 MoviePilot / 115 / STRM：
  用 `FeishuCommandBridgeLong`
- 想把影巢资源搜索、解锁、签到、115 转存整合进 MoviePilot：
  用 `HdhiveOpenApi`

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

---

## 仓库结构

```text
package.json
package.v2.json
icons/
plugins/
plugins.v2/
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
