# Agent影视助手：跨机器部署说明

目标：说明 `Agent影视助手 / AgentResourceOfficer` 在 `MoviePilot` 不和外部智能体跑在同一台机器时，应该如何配置和排查。

结论先说：

- 这套交互逻辑仍然成立。
- 关键不在操作系统，而在网络可达性和地址配置。
- 只要外部智能体能访问 `MoviePilot + AgentResourceOfficer`，同样可以走 `startup -> decide -> route -> followup`。

适用场景：

- `MoviePilot` 在 NAS，外部智能体在 Mac / Windows。
- `MoviePilot` 在 Windows，外部智能体在 Mac。
- `MoviePilot` 在另一台 Linux / Docker 主机，外部智能体在本地工作站。

## 架构理解

把当前方案拆成两层理解：

- 服务端：`MoviePilot + Agent影视助手`
- 客户端：`WorkBuddy / Hermes / OpenClaw（小龙虾）/ 其他外部智能体`

`Agent影视助手` 负责：

- 影巢搜索、解锁、签到、配额查询
- 盘搜搜索
- 115 扫码、状态查询、转存
- 夸克转存
- PT 搜索、评分、计划、执行、跟进
- 飞书入口、MP 内置智能体入口、request_templates

外部智能体只负责：

- 理解用户意图
- 调 `startup / request_templates / route / pick / followup`
- 根据 compact 响应决定自动继续、等待确认或停止

所以跨机器时，变化的只是地址，不是协议。

## 外部智能体配置

外部智能体所在机器的 Skill 配置文件：

```text
~/.config/agent-resource-officer/config
```

至少需要：

```text
ARO_BASE_URL=http://你的MoviePilot地址:3000
ARO_API_KEY=你的MoviePilot API_TOKEN
```

典型写法：

```text
同机部署：
ARO_BASE_URL=http://127.0.0.1:3000

局域网部署：
ARO_BASE_URL=http://192.168.x.x:3000

反向代理 / 公网域名：
ARO_BASE_URL=https://mp.example.com
```

规则：

- 只有 `MoviePilot` 和外部智能体在同一台机器时，才用 `127.0.0.1`
- 如果 `MoviePilot` 在 NAS / Windows / 另一台主机，就必须写那台主机对外可达的地址

## 对外部智能体来说，哪些能力不变

下面这些入口跨机器都一样：

- `startup`
- `readiness`
- `request_templates`
- `route`
- `pick`
- `workflow`
- `plan-execute`
- `followup`

也就是说：

- 会话机制不变
- `plan_id` 不变
- `preferred_command / compact_commands` 不变
- `recommended_agent_behavior` 不变

## 真正容易出问题的地方

### 1. 把 `127.0.0.1` 写错位置

最常见的错误是：

- 外部智能体在 Mac
- `MoviePilot` 在 NAS
- 结果 `ARO_BASE_URL` 还写成 `http://127.0.0.1:3000`

这时请求会打到 Mac 自己，不是 NAS。

### 2. 盘搜等旁路服务地址按错视角

例如 `PanSou`：

- 如果它是给 `Agent影视助手` 调用的
- 那么配置里应该填“`MoviePilot` 那台机器能访问到的地址”
- 不是“外部智能体那台机器能访问到的地址”

也就是要区分两种视角：

- 外部智能体看 `ARO_BASE_URL`
- `MoviePilot` 看 `盘搜 API 地址`

### 3. Docker 内部地址和宿主机地址混淆

如果 `MoviePilot` 跑在 Docker：

- `127.0.0.1` 可能是容器自己
- 不是宿主机
- 更不是 NAS 以外的别的机器

这时常见做法是：

- 用宿主机局域网 IP
- 或 `host.docker.internal`
- 或容器网络内的服务名

具体取决于你的部署方式。

### 4. 把本机路径写进公开 Skill

不要把这类内容写进公开 Skill：

```text
/Users/xxx/...
C:\\Users\\...
```

因为真正的落盘目录解释是在 `MoviePilot + Agent影视助手` 那边完成的。

外部智能体只需要知道：

- `/待整理`
- `/飞书`
- `/最新动画`

这类逻辑目录名，而不是你本地磁盘绝对路径。

## 推荐排查顺序

如果跨机器时调用失败，按这个顺序查：

1. 外部智能体机器上能否访问 `ARO_BASE_URL`
2. `ARO_API_KEY` 是否正确
3. `MoviePilot` 插件接口是否正常
4. `request_templates` 是否能返回
5. `route` 是否能处理简单只读命令
6. 再检查盘搜、影巢、115、夸克各自依赖配置

建议最小验证命令：

```bash
python3 scripts/aro_request.py readiness
python3 scripts/aro_request.py startup
python3 scripts/aro_request.py templates --recipe external_agent --compact
python3 scripts/aro_request.py route "115状态" --summary-only
```

如果这些都过了，说明跨机器主链已经通了。

## 三种推荐接法

### 1. 外部智能体

最推荐。

- 外部智能体只需要访问 `ARO_BASE_URL`
- `Agent影视助手` 统一负责服务端能力
- 最适合 WorkBuddy、Hermes、OpenClaw（小龙虾）

### 2. MP 内置智能体

也可以跨机器，但重点不是“跨机器”，而是：

- 你已经把 `MoviePilot` 的消息入口和 LLM 配好了
- 然后由 MP 内部 Agent Tool 调 `Agent影视助手`

### 3. 飞书入口

飞书是消息入口，不是另一套资源协议。

只要 `MoviePilot` 那边的飞书 Channel 正常：

- 消息仍然走 `route / pick / followup`
- 和外部智能体/MP 内置智能体底层一致

## 原则总结

跨机器时，体验目标不应该变：

- 用户还是发自然语言
- 智能体还是调 `Agent影视助手`
- 插件还是统一做搜索、选择、计划、执行、跟进

真正变化的是：

- 地址
- 网络
- 部署视角

不是协议，也不是用户交互模型。
