# 外部智能体接入 Agent影视助手

当前插件版本：`Agent影视助手 0.2.69`

当前 helper 版本：`agent-resource-officer 0.1.44`

让 `OpenClaw`、`Hermes`、`WorkBuddy` 或其他外部智能体，也能稳定调用 MoviePilot 的搜片、转存、下载、签到和修复能力。

核心思路很简单：外部智能体负责理解你说的话、调用 `Agent影视助手`、展示结果；真正的资源搜索、转存、下载和账号操作，都交给 MoviePilot 里的插件执行。

---

## 一步接入

把下面这段直接发给你的外部智能体：

```text
请从这个仓库安装并使用 agent-resource-officer Skill：
https://github.com/liuyuexi1987/MoviePilot-Plugins

安装步骤：
git clone https://github.com/liuyuexi1987/MoviePilot-Plugins.git
cd MoviePilot-Plugins

请先判断当前客户端的 Skill 目录，再安装到对应位置：

# Codex / 类 Codex 通常可以直接执行
bash skills/agent-resource-officer/install.sh

# OpenClaw 示例
bash skills/agent-resource-officer/install.sh --target ~/.workbuddy/skills/agent-resource-officer

# Hermes 示例
bash skills/agent-resource-officer/install.sh --target ~/Services/Hermes/home/skills/agent-resource-officer

# WorkBuddy 示例
bash skills/agent-resource-officer/install.sh --target ~/.workbuddy/skills/agent-resource-officer

其他客户端：把 --target 指向你的 skills/agent-resource-officer 目录。

确认安装成功：
ls <target>/SKILL.md && echo "安装成功"

安装后先读取：
skills/agent-resource-officer/SKILL.md

连接配置：
请写入 ~/.config/agent-resource-officer/config

ARO_BASE_URL=http://你的MoviePilot地址:3000
ARO_API_KEY=<去 MoviePilot 设置 → 安全设置 → API Token 复制>

如果 MoviePilot 在 NAS，ARO_BASE_URL 必须填 NAS 的实际地址，例如：
ARO_BASE_URL=http://192.168.1.100:3000

运行 readiness 验证：
python3 <target>/scripts/aro_request.py readiness

这里的 <target> 就是上面 install.sh 使用的实际安装目录。

MCP 接入是可选项，不影响 ARO 使用。
只有客户端明确支持远程 HTTP MCP、MoviePilot 的 /api/v1/mcp 可以访问，并且当前会话能看到 mcp__moviepilot__* 工具时，才算 MCP 已接通。
MCP 适合查插件列表、下载器状态、站点状态、历史记录、订阅管理和工作流。
盘搜、影巢、转存、夸克转存、115转存、下载、更新检查、编号选择、翻页、详情、Cookie 修复，继续走 agent-resource-officer skill / helper。
如果 MCP 工具没有加载，全部走 ARO，不要假装在用 MCP。
```

更细的接入说明再看本文档后续章节。

---

## 连接地址怎么填

先判断 MoviePilot 和智能体是不是在同一台机器。

### 跨机器部署

如果 MoviePilot 在 NAS，智能体在 Win / Mac 电脑上，`ARO_BASE_URL` 必须填 NAS 的实际地址：

```bash
ARO_BASE_URL=http://192.168.1.100:3000
ARO_API_KEY=你的 MoviePilot API_TOKEN
```

不要填：

```bash
ARO_BASE_URL=http://127.0.0.1:3000
```

这里的 `127.0.0.1` 只代表智能体自己这台机器，不是 NAS。

如果你有多套 MoviePilot，要特别注意：

- `ARO_BASE_URL` 指向哪套 MoviePilot，`下载 / MP搜索 / PT搜索 / 转存` 就使用哪套 MoviePilot。
- 如果当前 MoviePilot 只用于网盘或 STRM，不要在这套实例里确认 PT 下载。
- 如果 MoviePilot 和 qBittorrent 不在一台机器，可在 Agent影视助手设置里填写 `PT 下载保存路径`，路径要按目标 NAS / qB 的真实下载目录填写。

跨机器部署详细说明见 [AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md](../../docs/AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md)。

### 同机部署

如果 MoviePilot 和智能体在同一台电脑或同一个容器网络里，可以这样填：

```bash
ARO_BASE_URL=http://127.0.0.1:3000
ARO_API_KEY=你的 MoviePilot API_TOKEN
```

这也是最简单的情况。

---

## 手动添加 MCP

有些智能体不会自动读取或启用 MoviePilot MCP，需要你在智能体的 MCP 设置里手动添加。

填写：

```text
MCP 地址：http://你的MP地址:3000/api/v1/mcp
认证头：X-API-KEY=你的 MoviePilot API_TOKEN
```

如果 MoviePilot 在 NAS，地址要写 NAS 的实际地址：

```text
MCP 地址：http://你的NAS地址:3000/api/v1/mcp
```

添加后，需要在智能体里确认 MCP 已启用，并且当前会话能看到类似 `mcp__moviepilot__*` 的工具。

如果看不到这些工具，就说明 MCP 没有真正加载成功。此时不要让智能体假装在用 MCP，资源流继续走 `agent-resource-officer skill / helper`。

---

## 怎么用

接入完成后，直接对智能体说：

| 命令 | 作用 |
|---|---|
| `搜索 蜘蛛侠` | 默认优先走 MP/PT 搜索；如果 MP/PT 已关闭，再按当前启用源回退 |
| `盘搜搜索 蜘蛛侠` | 先查盘搜；盘搜没结果时按开关补查影巢 |
| `影巢搜索 蜘蛛侠` | 先查影巢；影巢没结果时按开关补查盘搜 |
| `MP搜索 蜘蛛侠` / `PT搜索 蜘蛛侠` | 走 MoviePilot 原生 PT 搜索 |
| `转存 蜘蛛侠` | 默认等同 `115转存 蜘蛛侠` |
| `115转存 蜘蛛侠` | 搜索后转存到 115 |
| `夸克转存 蜘蛛侠` | 搜索后转存到夸克 |
| `下载 蜘蛛侠` | 搜索并生成 PT 下载计划 |
| `更新检查 蜘蛛侠` | 检查是否有新资源 |
| `115登录` | 扫码登录 115 |
| `影巢签到` | 执行影巢签到 |

完整命令列表见 [ALL_COMMANDS.md](../../docs/ALL_COMMANDS.md)。

补充说明：

- `盘搜搜索` / `影巢搜索` / `转存` 只会使用当前还开启的网盘源，不会偷偷改成 `MP搜索`。
- `云盘搜索` 已废弃；如果用户仍然发送，插件只返回改用 `盘搜搜索` / `影巢搜索` / `PT搜索` 的提示。
- `115登录` / `115转存` 现在不再强依赖 `P115StrmHelper`；有它更适合做 115 整理、STRM 和旧登录态复用，没有它也可以直接扫码后完成 115 转存。
- `刷新影巢Cookie` / `刷新夸克Cookie` 读取的是智能体所在电脑浏览器里的登录态，再写回 `MoviePilot`。

---

## MCP 要不要接

MoviePilot 官方 MCP 可以接，但它和 `agent-resource-officer skill / helper` 的定位不同。

推荐这样分工：

| 场景 | 推荐入口 |
|---|---|
| 插件列表、下载器状态、站点状态、历史记录、工作流、调度器等 MoviePilot 管理查询 | 官方 MCP |
| 盘搜、影巢、115/夸克转存、编号选择、翻页、详情、Cookie 修复 | `agent-resource-officer skill / helper` |
| `MP搜索 / PT搜索 / 下载 / 更新检查` 这类片名资源流 | 优先 `agent-resource-officer skill / helper` |

MCP 地址通常是：

```text
http://你的MP地址:3000/api/v1/mcp
```

认证头：

```text
X-API-KEY=你的 MoviePilot API_TOKEN
```

注意：只有当前智能体客户端真的加载出了 `mcp__moviepilot__*` 工具，才算 MCP 已接通。没有接通时，不要让智能体假装在用 MCP；资源流继续走 `agent-resource-officer`。

---

## 给智能体看的执行规则

这部分规则已经写在 `agent-resource-officer` Skill 里，普通用户不用背。

接入时只要让外部智能体读取本仓库里的 Skill，它就会知道哪些命令必须走 `route / pick`、哪些动作需要确认、哪些结果不能重排编号。

---

## 长线程维护

微信、飞书、WorkBuddy、Claw 这类长线程用久后，可能会出现：

- `15详情` 被误解成 `选择 15`
- 编号续接到旧搜索结果
- 一直套用旧格式或旧规则

这时直接对智能体说：

```text
校准影视技能
```

这条命令会让智能体先检查并拉取 `MoviePilot-Plugins` 仓库最新版，再重新加载影视助手的关键规则。不要在普通 `搜索 / 更新检查 / 检查` 前主动清会话，否则会破坏正常编号续接。

---

## 相关文档

- [全部命令一览](../../docs/ALL_COMMANDS.md)
- [跨机器部署](../../docs/AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md)
- [Skill 说明](./SKILL.md)
- [外部智能体详细规范](./EXTERNAL_AGENTS.md)
