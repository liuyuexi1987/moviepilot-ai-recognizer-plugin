# 外部智能体接入 Agent影视助手

让 `OpenClaw`、`Hermes`、`WorkBuddy` 或其他外部智能体，也能稳定调用 MoviePilot 的搜片、转存、下载、签到和修复能力。

核心思路很简单：外部智能体负责理解你说的话、调用 `Agent影视助手`、展示结果；真正的资源搜索、转存、下载和账号操作，都交给 MoviePilot 里的插件执行。

---

## 一步接入

把下面这段直接发给你的外部智能体：

```text
请从这个仓库创建并使用 agent-resource-officer Skill：
https://github.com/liuyuexi1987/MoviePilot-Plugins

创建后请依次读取：
1. skills/agent-resource-officer/SKILL.md
2. skills/agent-resource-officer/EXTERNAL_AGENTS.md
3. docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md

连接配置：
ARO_BASE_URL=http://MoviePilot地址:3000
ARO_API_KEY=你的 MoviePilot API_TOKEN

如果你的客户端支持 MoviePilot 官方 MCP，也请同时接入：
MCP 地址：http://MoviePilot地址:3000/api/v1/mcp
认证头：X-API-KEY=你的 MoviePilot API_TOKEN

分工规则：
1. 插件列表、下载器状态、站点状态、历史记录、工作流、调度器等 MoviePilot 管理查询，可以优先用 MCP。
2. 云盘搜索、盘搜、影巢、转存、夸克转存、115转存、下载、更新检查、编号选择、翻页、详情、Cookie 修复，继续优先用 agent-resource-officer skill / helper。
3. 只有当前会话真的加载出 mcp__moviepilot__* 工具，才算 MCP 已接通；没接通时不要假装在用 MCP。

请把配置写入 ~/.config/agent-resource-officer/config。
然后运行 readiness 验证连接，成功后按文档规则接入。
```

`ARO_API_KEY` 在 MoviePilot 管理后台的系统设置 / 安全设置里找。

---

## 连接地址怎么填

先判断 MoviePilot 和智能体是不是在同一台机器。

### 同机部署

如果 MoviePilot 和智能体在同一台电脑或同一个容器网络里，可以这样填：

```bash
ARO_BASE_URL=http://127.0.0.1:3000
ARO_API_KEY=你的 MoviePilot API_TOKEN
```

这也是最简单的情况。

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

跨机器部署详细说明见 [AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md](./AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md)。

---

## 手动安装

如果智能体不能自动安装，在智能体所在机器执行：

```bash
git clone https://github.com/liuyuexi1987/MoviePilot-Plugins.git
cd MoviePilot-Plugins
bash skills/agent-resource-officer/install.sh --dry-run
bash skills/agent-resource-officer/install.sh
```

然后创建配置：

```bash
mkdir -p ~/.config/agent-resource-officer
cat > ~/.config/agent-resource-officer/config <<'EOF'
ARO_BASE_URL=http://你的MoviePilot地址:3000
ARO_API_KEY=你的MoviePilot_API_TOKEN
EOF
```

验证连接：

```bash
python3 ~/.codex/skills/agent-resource-officer/scripts/aro_request.py readiness
```

如果你的 Skill 不在 `~/.codex`，把路径换成实际安装位置。

常见位置：

| 环境 | 常见位置 |
|---|---|
| Codex / 类 Codex | `~/.codex/skills/agent-resource-officer/` |
| WorkBuddy / 类 Claw | `~/.workbuddy/skills/agent-resource-officer/` |
| 仓库内调试 | `skills/agent-resource-officer/` |

---

## 怎么用

接入完成后，直接对智能体说：

| 命令 | 作用 |
|---|---|
| `搜索 蜘蛛侠` | 搜索云盘资源，默认走盘搜 |
| `云盘搜索 蜘蛛侠` | 盘搜 + 影巢一起搜 |
| `MP搜索 蜘蛛侠` / `PT搜索 蜘蛛侠` | 走 MoviePilot 原生 PT 搜索 |
| `转存 蜘蛛侠` | 默认等同 `115转存 蜘蛛侠` |
| `115转存 蜘蛛侠` | 搜索后转存到 115 |
| `夸克转存 蜘蛛侠` | 搜索后转存到夸克 |
| `下载 蜘蛛侠` | 搜索并生成 PT 下载计划 |
| `更新检查 蜘蛛侠` | 检查是否有新资源 |
| `115登录` | 扫码登录 115 |
| `影巢签到` | 执行影巢签到 |

完整命令列表见 [ALL_COMMANDS.md](./ALL_COMMANDS.md)。

---

## MCP 要不要接

MoviePilot 官方 MCP 可以接，但它和 `agent-resource-officer skill / helper` 的定位不同。

推荐这样分工：

| 场景 | 推荐入口 |
|---|---|
| 插件列表、下载器状态、站点状态、历史记录、工作流、调度器等 MoviePilot 管理查询 | 官方 MCP |
| 盘搜、影巢、云盘搜索、115/夸克转存、编号选择、翻页、详情、Cookie 修复 | `agent-resource-officer skill / helper` |
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

这条命令会让智能体重新加载影视助手的关键规则。不要在普通 `搜索 / 更新检查 / 检查` 前主动清会话，否则会破坏正常编号续接。

---

## 相关文档

- [全部命令一览](./ALL_COMMANDS.md)
- [跨机器部署](./AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md)
- [Skill 说明](../skills/agent-resource-officer/SKILL.md)
- [外部智能体详细规范](../skills/agent-resource-officer/EXTERNAL_AGENTS.md)
