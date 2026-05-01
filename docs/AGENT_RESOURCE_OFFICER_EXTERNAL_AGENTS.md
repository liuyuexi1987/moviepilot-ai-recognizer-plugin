# 外部智能体接入 Agent影视助手

目标：给 WorkBuddy、Hermes、OpenClaw（小龙虾）、微信侧智能体或其他外部智能体一套统一接入范式。`Agent影视助手 / AgentResourceOfficer` 负责服务端能力执行；外部智能体只做客户端理解、调度和展示，115 云盘、夸克云盘等云盘资源搜索、解锁、转存、115 登录状态全部交给插件完成。

公开仓库地址：

```text
https://github.com/liuyuexi1987/MoviePilot-Plugins
```

## 当前接入状态

- 当前插件版本：`Agent影视助手 0.2.67`
- 当前 helper 版本：`agent-resource-officer 0.1.40`
- 当前最小循环：`startup -> decide --summary-only -> route --summary-only -> followup --summary-only`
- 当前优先读取字段：`recommended_agent_behavior`、`auto_run_command`、`confirm_command`、`display_command`

给其他机器或其他智能体复现时，优先让它阅读这三个文件：

- `docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md`
- `skills/agent-resource-officer/SKILL.md`
- `skills/agent-resource-officer/EXTERNAL_AGENTS.md`

## 接入原则

- 不让外部智能体直接调用影巢、115、夸克、盘搜底层 API。
- 不把 Cookie、Token、API Key 写进提示词正文。
- 所有调用都走 `AgentResourceOfficer` 的标准 `assistant` 接口。
- 同一个用户或群聊固定使用同一个 `session`，例如 `agent:${chat_id}`。
- 搜索和展示是读操作；选择编号、转存、解锁、执行计划是写操作，需要用户明确输入编号或链接。
- 首次接入建议先读取 `assistant/preferences`。如果未初始化，先询问用户片源偏好，再保存为偏好画像。
- 云盘资源和 PT 资源分开评分：云盘看清晰度、字幕、完整度、网盘类型和影巢积分；PT 看做种数、免费/促销、下载折算、清晰度、字幕和匹配度。
- 如果 helper 的 `summary-only` 返回 `recommended_agent_behavior=auto_continue` 或 `auto_continue_then_wait_confirmation`，可以直接执行 `auto_run_command`；其他结果先停下来展示或确认。

推荐把外部智能体自身的执行分支固定成 5 类：

- `auto_continue`
- `auto_continue_then_wait_confirmation`
- `wait_user_confirmation`
- `show_only`
- `stop`

不要在接入层再定义第三套状态机，直接复用 helper 返回值。

推荐的最小接入循环：

1. 调 `startup`
2. 调 `decide --summary-only`
3. 用户发自然语言后，调 `route --summary-only`
4. 读取 `recommended_agent_behavior`
5. 如果执行过计划，再调 `followup --summary-only`

如果场景是“只给片名，让智能体自己比较多个来源”，优先使用统一搜索决策入口：

- `route "智能搜索 <片名>" --summary-only`
- `route "资源决策 <片名>" --summary-only`
- 如果用户已经明确要计划或直接执行，也可以直接发：
  - `route "资源决策 <片名> 计划" --summary-only`
  - `route "资源决策 <片名> 直接执行" --summary-only`
- 如果已经进入同一资源决策会话，还可以直接发：
  - `route "先计划" --summary-only`
  - `route "确认执行" --summary-only`
  - `route "先看详情" --summary-only`
- 或者先读模板：`templates --recipe smart_search --compact`
- 或先读模板：`templates --recipe smart_decision --compact`
- 如果希望一步拿到待确认计划，用：`route "智能计划 <片名>" --summary-only`
- 或先读模板：`templates --recipe smart_search_plan --compact`
- 如果用户已经明确要求立即执行，用：`route "智能执行 <片名>" --summary-only`
- 或先读模板：`templates --recipe smart_search_execute --compact`

这条入口会统一按 `盘搜 -> 影巢 -> MP/PT` 搜索，并自动读取当前会话偏好中的：

- 可用源：`enable_pansou / enable_hdhive / enable_mp_pt`
- 可用云盘：`has_115 / has_quark`

所以如果用户提前说明“只有夸克”“没有 115”“不用盘搜”“只用 MP/PT”，外部智能体无需自己再维护一套分支判断，直接先保存偏好，再调用 `智能搜索` 即可。

如果已经跑过一次 `智能搜索`，还可以在同一 session 里直接发：

- `计划最佳`
- `执行最佳`
- `继续推荐`
- `换影巢`
- `换盘搜`
- `换PT`
- `保守一点`
- `激进一点`

这会按当前首选自动生成待确认 `plan_id`，但仍然需要后续 `执行计划` 才会真正写入。
而 `执行最佳` / `智能执行` 会直接走写入链，只适用于用户已经明确要求立即执行的场景。

三类入口都复用这一套 assistant 协议：

- 外部智能体：优先用 Skill/helper，按 `startup -> decide -> route -> followup` 跑。
- MP 内置智能体：优先用 Agent Tool / `request_templates`，不要让模型自己拼底层 API。
- 飞书入口：把消息送进插件内置 Channel，底层仍然走 `route / pick / followup`。

最低 token 接入时，优先读取 `assistant/request_templates` 返回里的：

- `orchestration_contract`
- `entry_patterns`
- `entry_playbooks`
- `recommended_recipe_detail`

## 必要配置

把下面两个变量配置到外部智能体的安全变量区或工具配置区：

```text
BASE_URL=https://你的 MoviePilot 可访问地址
MP_API_TOKEN=你的 MoviePilot API_TOKEN
```

`BASE_URL` 按实际部署填写：

```text
同机调用示例：BASE_URL=http://127.0.0.1:3000
局域网调用示例：BASE_URL=http://你的局域网IP:3000
公网反代示例：BASE_URL=https://你的 MoviePilot 域名
```

不要把 `MP_API_TOKEN` 写进提示词正文，只放在外部智能体的安全变量、工具密钥或私有配置里。

如果 `MoviePilot` 不在当前机器，而是在 NAS、Windows 或另一台 Docker 主机，请同时阅读：

- `docs/AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md`

跨机器时，外部智能体的用法不变，主要变化只是 `BASE_URL` 和旁路服务地址的可达性配置。

如果你只想最低成本接入，不要先读完整说明，先执行：

```bash
python3 <SKILL_HOME>/agent-resource-officer/scripts/aro_request.py readiness
python3 <SKILL_HOME>/agent-resource-officer/scripts/aro_request.py external-agent
```

然后按 `external-agent` 输出里的 `execution_policy_contract`、`execution_loop_contract`、`entry_playbooks` 和 `deprecated_aliases` 接入。

## 从仓库复现 Skill

在需要接入的机器上：

```bash
git clone https://github.com/liuyuexi1987/MoviePilot-Plugins.git
cd MoviePilot-Plugins
bash skills/agent-resource-officer/install.sh --dry-run
bash skills/agent-resource-officer/install.sh
```

然后创建连接配置：

```bash
mkdir -p ~/.config/agent-resource-officer
cat > ~/.config/agent-resource-officer/config <<'EOF'
ARO_BASE_URL=https://你的 MoviePilot 可访问地址
ARO_API_KEY=你的 MoviePilot API_TOKEN
EOF
```

验证：

```bash
python3 <SKILL_HOME>/agent-resource-officer/scripts/aro_request.py readiness
python3 <SKILL_HOME>/agent-resource-officer/scripts/aro_request.py external-agent
```

## 快速生成提示词

如果已经安装仓库里的 `agent-resource-officer` Skill，可以直接让 helper 输出可复制的提示词和最小工具约定：

```bash
python3 <SKILL_HOME>/agent-resource-officer/scripts/aro_request.py external-agent
python3 <SKILL_HOME>/agent-resource-officer/scripts/aro_request.py external-agent --full
```

这里的 `<SKILL_HOME>` 指你的智能体 Skill 根目录，例如某些客户端会使用自己的 `skills/` 目录；不要把个人机器路径写进公开 Skill。

`external-agent` 输出紧凑 JSON，适合直接喂给外部智能体；`external-agent --full` 输出完整说明。旧命令 `workbuddy` 仍保留为兼容别名，但已标记为 deprecated。

## 让外部智能体创建自己的 Skill

如果外部智能体支持 Skill、项目能力或本地工具目录，推荐让它读完仓库后先创建或安装自己的 `agent-resource-officer` Skill。这样比只发普通聊天提示更稳，换会话后也不容易失去操作记忆。

可以直接给外部智能体这段任务：

```text
请阅读 https://github.com/liuyuexi1987/MoviePilot-Plugins ，重点阅读 docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md、skills/agent-resource-officer/SKILL.md、skills/agent-resource-officer/EXTERNAL_AGENTS.md。然后在你的环境里创建或安装 agent-resource-officer Skill，用于调用 MoviePilot Agent影视助手。

要求：
1. 只把通用流程、工具调用方式、会话规则和错误处理写进 Skill。
2. 不要把 API Key、Cookie、Token、个人路径写进 Skill。
3. 所有资源搜索、影巢解锁、115/夸克转存、115 登录状态都必须调用 Agent影视助手。
4. 不要直接调用影巢、盘搜、115、夸克底层 API。
5. Skill 至少包含 startup、route、pick 三个核心入口。
6. 增加 preferences 入口。第一次接入用户时先读取偏好，未初始化就询问并保存。
7. 同一个用户或群聊固定使用 session=agent:会话ID。
8. 搜索结果只展示 Agent影视助手返回的内容，编号选择继续调用 pick。
9. 写入类动作必须等用户明确选择编号或给出链接后再执行；下载、订阅、影巢解锁和网盘转存优先生成 plan_id。
10. 创建后请运行 external-agent 或等价自检，确认 schema_version=external_agent.v1。
```

创建完成后，用这两句检查它是否真正理解：

```text
如果我说“盘搜搜索 大君夫人”，你会调用哪个入口？
如果我再说“选择 3”，你会如何沿用 session 继续？
```

合格回答应该是：先用 `route` 处理搜索，再用同一个 `agent:会话ID` 调用 `pick` 继续编号选择。

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
    "recipe": "external_agent",
    "include_templates": false
  }
}
```

## 外部智能体系统提示词

```text
你是 MoviePilot Agent影视助手的外部智能体入口。

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

## 推荐测试

```text
115状态
MP搜索 蜘蛛侠
1大君夫人
2蜘蛛侠
链接 https://pan.quark.cn/s/xxxx path=/飞书
```
