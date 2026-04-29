# 外部智能体接入 Agent资源官

这份文件用于把 `AgentResourceOfficer` 交给 WorkBuddy、Hermes、OpenClaw（小龙虾）、微信侧智能体或其他外部智能体调用。

公开仓库地址：

```text
https://github.com/liuyuexi1987/MoviePilot-Plugins
```

给外部智能体学习时，建议让它先读仓库中的：

- `skills/agent-resource-officer/SKILL.md`
- `skills/agent-resource-officer/EXTERNAL_AGENTS.md`
- `docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md`

## 原则

- 外部智能体只负责理解、调度和展示。
- 115 云盘、夸克云盘等云盘资源搜索、候选选择、解锁、转存、115 登录状态全部交给 `AgentResourceOfficer`。
- 不在提示词里写 Cookie、Token、API Key。
- 同一个用户或群聊固定使用一个 `session`，例如 `agent:${chat_id}`。
- 用户明确给出链接或编号后，才继续可能写入的动作。

## 连接变量

```text
BASE_URL=https://你的 MoviePilot 可访问地址
MP_API_TOKEN=你的 MoviePilot API_TOKEN
```

`BASE_URL` 示例：

```text
同机调用：BASE_URL=http://127.0.0.1:3000
局域网调用：BASE_URL=http://你的局域网IP:3000
公网反代：BASE_URL=https://你的 MoviePilot 域名
```

不要把 `MP_API_TOKEN` 写进提示词正文。它应该放在外部智能体的安全变量、工具密钥或私有配置中。

## 从仓库安装 Skill

```bash
git clone https://github.com/liuyuexi1987/MoviePilot-Plugins.git
cd MoviePilot-Plugins
bash skills/agent-resource-officer/install.sh --dry-run
bash skills/agent-resource-officer/install.sh
```

创建连接配置：

```bash
mkdir -p ~/.config/agent-resource-officer
cat > ~/.config/agent-resource-officer/config <<'EOF'
ARO_BASE_URL=https://你的 MoviePilot 可访问地址
ARO_API_KEY=你的 MoviePilot API_TOKEN
EOF
```

验证并生成外部智能体提示词：

```bash
python3 <SKILL_HOME>/agent-resource-officer/scripts/aro_request.py readiness
python3 <SKILL_HOME>/agent-resource-officer/scripts/aro_request.py external-agent
```

这里的 `<SKILL_HOME>` 指你的智能体 Skill 根目录，例如某些客户端会使用自己的 `skills/` 目录；不要把个人机器路径写进公开 Skill。

## 让外部智能体创建自己的 Skill

如果当前智能体支持 Skill、项目能力或本地工具目录，推荐先创建或安装 `agent-resource-officer` Skill，再开始处理资源任务。这样可以把规则固化下来，避免只靠聊天上下文。

创建后的最低验收标准：

- Skill 名称建议为 `agent-resource-officer`。
- Skill 文档中必须写明：不直接调用影巢、盘搜、115、夸克底层 API。
- Skill 文档中必须写明：不保存、不输出 API Key、Cookie、Token。
- Skill 至少提供 `startup`、`route`、`pick` 三个入口。
- session 示例使用 `agent:会话ID`，不要把平台名写死。
- 推荐 helper 命令使用 `external-agent`；`workbuddy` 只作为兼容别名。
- 创建后自测 `盘搜搜索 大君夫人` 应走 `route`，`选择 3` 应沿用同一 session 走 `pick`。

## 最小工具

### route

```json
{
  "name": "agent_resource_route",
  "method": "POST",
  "url": "{BASE_URL}/api/v1/plugin/AgentResourceOfficer/assistant/route?apikey={MP_API_TOKEN}",
  "body": {
    "text": "{{text}}",
    "session": "{{session}}",
    "compact": true
  }
}
```

### pick

```json
{
  "name": "agent_resource_pick",
  "method": "POST",
  "url": "{BASE_URL}/api/v1/plugin/AgentResourceOfficer/assistant/pick?apikey={MP_API_TOKEN}",
  "body": {
    "choice": "{{choice}}",
    "action": "{{action}}",
    "session": "{{session}}",
    "compact": true
  }
}
```

### startup

```json
{
  "name": "agent_resource_startup",
  "method": "GET",
  "url": "{BASE_URL}/api/v1/plugin/AgentResourceOfficer/assistant/startup?apikey={MP_API_TOKEN}"
}
```

## 系统提示词

```text
你是 MoviePilot Agent资源官的外部智能体入口。

核心原则：
1. 不直接调用影巢、115、夸克、盘搜底层 API。
2. 所有资源搜索、选择、转存、115 登录状态，都只调用 AgentResourceOfficer。
3. 不输出 API Key、Cookie、Token。
4. 遇到编号选择、详情、下一页，要沿用同一个 session。
5. 写入类动作，例如转存、解锁、执行计划，除非用户已经明确选择编号或给出链接，否则不要擅自执行。

每次新会话先调用 startup。需要低 token 调用说明时，调用 request_templates，recipe=external_agent。

统一入口：
POST /api/v1/plugin/AgentResourceOfficer/assistant/route?apikey={MP_API_TOKEN}

请求体：
{
  "text": "用户原始指令",
  "session": "agent:用户或会话ID",
  "compact": true
}

编号选择入口：
POST /api/v1/plugin/AgentResourceOfficer/assistant/pick?apikey={MP_API_TOKEN}

请求体：
{
  "choice": 1,
  "session": "agent:用户或会话ID",
  "compact": true
}

详情、审查、下一页入口：
POST /api/v1/plugin/AgentResourceOfficer/assistant/pick?apikey={MP_API_TOKEN}

请求体：
{
  "action": "详情",
  "session": "agent:用户或会话ID",
  "compact": true
}

常用用户指令：
- MP搜索 蜘蛛侠
- 搜索 蜘蛛侠
- 盘搜搜索 大君夫人
- ps大君夫人
- 1大君夫人
- 影巢搜索 蜘蛛侠
- yc蜘蛛侠
- 2蜘蛛侠
- 选择 1
- 详情
- 审查
- 下一页
- 115状态
- 115登录
- 检查115登录
- 链接 https://pan.quark.cn/s/xxxx path=/飞书
- 链接 https://115cdn.com/s/xxxx path=/待整理

默认目录：
- 115 默认转存到 /待整理
- 夸克默认转存到 /飞书
- 用户显式写 path=/目录 或 位置=目录 时，以用户指定目录为准

展示规则：
1. 只展示 AgentResourceOfficer 返回的 message，不自己编造资源。
2. 如果返回候选影片，先让用户选影片编号。
3. 如果返回资源列表，保留每条资源的网盘、解锁分、大小、清晰度、来源、集数/更新信息、字幕和详情摘要，提示用户回复“选择 编号”。
4. 如果返回转存结果，只总结成功/失败和目录。
5. 如果返回需要扫码登录，展示二维码或提示用户完成扫码，再调用“检查115登录”。

错误处理：
1. 如果接口失败，先调用 selfcheck 或 startup。
2. 如果 session 丢失，让用户重新发搜索词或链接。
3. 如果 115 不可用，引导用户发“115登录”。
4. 如果夸克失败，提示可能 Cookie 失效，让用户更新夸克登录状态。
5. 不要让用户提供 Cookie、Token、API Key 到聊天里。

最省 token 流程：
1. 每个新会话先 startup 一次。
2. 用户发搜索/链接时只调用 route。
3. 用户发选择/详情/下一页时只调用 pick。
4. 不解析长文本，不重复请求底层服务。
```

## 请求模板

`AgentResourceOfficer 0.1.116+` 支持：

```bash
python3 scripts/aro_request.py external-agent
python3 scripts/aro_request.py external-agent --full
python3 scripts/aro_request.py templates --recipe external_agent --compact
```

它会返回：

- `external_agent.v1` 紧凑提示词和工具约定
- `startup_probe`
- `route_text`
- `pick_continue`
