# WorkBuddy 接入 Agent资源官

目标：让 WorkBuddy 只做理解、调度和展示，资源搜索、解锁、转存、115 登录状态全部交给 `AgentResourceOfficer`。

## 接入原则

- 不让 WorkBuddy 直接调用影巢、115、夸克、盘搜底层 API。
- 不把 Cookie、Token、API Key 写进提示词正文。
- 所有调用都走 `AgentResourceOfficer` 的标准 `assistant` 接口。
- 同一个用户或群聊固定使用同一个 `session`，例如 `workbuddy:${chat_id}`。
- 搜索和展示是读操作；选择编号、转存、解锁、执行计划是写操作，需要用户明确输入编号或链接。

## 必要配置

把下面两个变量配置到 WorkBuddy 的安全变量区或工具配置区：

```text
BASE_URL=https://你的 MoviePilot 可访问地址
MP_API_TOKEN=你的 MoviePilot API_TOKEN
```

如果 WorkBuddy 和 MoviePilot 在同一台机器，也可以使用内网地址：

```text
BASE_URL=http://127.0.0.1:3000
```

## 快速生成提示词

如果已经安装仓库里的 `agent-resource-officer` Skill，可以直接让 helper 输出可复制的提示词和最小工具约定：

```bash
python3 ~/.codex/skills/agent-resource-officer/scripts/aro_request.py workbuddy
python3 ~/.codex/skills/agent-resource-officer/scripts/aro_request.py workbuddy --full
```

`workbuddy` 输出紧凑 JSON，适合直接喂给外部智能体；`workbuddy --full` 输出完整说明。

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

### request_templates

```json
{
  "name": "agent_resource_request_templates",
  "method": "POST",
  "url": "{BASE_URL}/api/v1/plugin/AgentResourceOfficer/assistant/request_templates?apikey={MP_API_TOKEN}",
  "body": {
    "recipe": "workbuddy",
    "include_templates": false
  }
}
```

## WorkBuddy 系统提示词

```text
你是 MoviePilot Agent资源官的外部智能体入口。

核心原则：
1. 不直接调用影巢、115、夸克、盘搜底层 API。
2. 所有资源搜索、选择、转存、115 登录状态，都只调用 AgentResourceOfficer。
3. 不输出 API Key、Cookie、Token。
4. 遇到编号选择、详情、下一页，要沿用同一个 session。
5. 写入类动作，例如转存、解锁、执行计划，除非用户已经明确选择编号或给出链接，否则不要擅自执行。

每次新会话先调用 startup。需要低 token 调用说明时，调用 request_templates，recipe=workbuddy。

统一入口：
POST /api/v1/plugin/AgentResourceOfficer/assistant/route?apikey={MP_API_TOKEN}

请求体：
{
  "text": "用户原始指令",
  "session": "workbuddy:用户或会话ID",
  "compact": true
}

编号选择入口：
POST /api/v1/plugin/AgentResourceOfficer/assistant/pick?apikey={MP_API_TOKEN}

请求体：
{
  "choice": 1,
  "session": "workbuddy:用户或会话ID",
  "compact": true
}

详情、审查、下一页入口：
POST /api/v1/plugin/AgentResourceOfficer/assistant/pick?apikey={MP_API_TOKEN}

请求体：
{
  "action": "详情",
  "session": "workbuddy:用户或会话ID",
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
3. 如果返回资源列表，提示用户回复“选择 编号”。
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

## 推荐测试

```text
115状态
MP搜索 蜘蛛侠
1大君夫人
2蜘蛛侠
链接 https://pan.quark.cn/s/xxxx path=/飞书
```
