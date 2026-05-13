# AgentResourceOfficer Prompt Examples

## Startup

```text
使用 agent-resource-officer skill，先调用 auto，自动读取 startup 和推荐 request_templates。
```

## MCP Guardrail

```text
如果当前客户端没有明确接入 MoviePilot 官方 MCP，或者当前会话里看不到 MoviePilot MCP 工具，就不要声称自己在用 MCP。此时继续使用 agent-resource-officer skill/helper。MCP 只优先用于插件列表、下载器状态、站点状态、历史记录这类管理查询；片名资源流不走 MCP 优先。资源工作流、编号选择、分页、Cookie 修复仍优先走 agent-resource-officer。
```

```text
如果当前会话已经存在对应的 mcp__moviepilot__* 工具，而用户要查的是 MoviePilot 管理信息（例如插件列表、下载器状态、站点状态、下载历史、入库历史、工作流、调度器），就直接调用 MCP，不要先绕回 agent-resource-officer raw GET，也不要先试 curl。
```

```text
如果用户命令明显是资源流，例如“盘搜搜索/影巢搜索/MP搜索/PT搜索/转存/夸克转存/115转存/下载/更新/更新检查/检查/选择/详情/n/下一页/编号”，不要先调用 MCP、tool_search、curl 或 raw API 探测，直接使用 agent-resource-officer helper 的 route/pick。带“第 3 集 / E03 / 更新至”等集数线索的“搜索”也要直接按 MP/PT 处理，不要回退云盘。注意：标题级“转存/115转存/夸克转存 + 片名”已经取消，route 后只会返回引导用户先搜索的提示。
```

```text
如果用户明确说“MP搜索 / MP 搜索 / PT搜索 / PT 搜索 + 片名”，必须原样调用 route，不要改写成“搜索/盘搜搜索/影巢搜索/智能搜索”。这是用户指定 MoviePilot 原生/PT 搜索，不是普通盘搜。
```

```text
如果当前客户端没有 MoviePilot MCP 工具，处理“MP搜索 / MP 搜索 / PT搜索 / PT 搜索”时不要输出“MCP 不可用所以改走盘搜”。正确做法是直接执行 agent-resource-officer helper：route "<用户原话>"，并原样转发返回结果。
```

```text
处理“MP 搜索 罪无可逃”这类片名资源命令时，第一步只能是运行：python3 scripts/aro_request.py route "MP 搜索 罪无可逃" --session <session>。不要先调用 search_media、search_torrents、TMDB、MoviePilot raw API 或 MCP。
```

## Low Token Auto

```text
使用 agent-resource-officer skill，先调用 auto --summary-only，只返回自动启动流的最小决策摘要。
```

## Decide

```text
使用 agent-resource-officer skill，先调用 decide --summary-only，告诉我现在应该继续旧会话还是按推荐 recipe 开始新流程。
```

## Command Only Decide

```text
使用 agent-resource-officer skill，调用 decide --command-only，只返回下一步 helper 命令。
```

## Confirmed Command

```text
使用 agent-resource-officer skill，在我已经确认执行后，调用 decide --command-only --confirmed，只返回执行用 helper 命令。
```

## Manual Startup

```text
使用 agent-resource-officer skill，先调用 startup，读取 recommended_request_templates，然后按推荐 recipe 获取低 token 请求模板。
```

## PanSou Search

```text
使用 agent-resource-officer skill，盘搜搜索“大君夫人”，分别展示 115 和夸克结果，让我选择编号。不要直接转存，等我确认编号。
```

## Generic Search

```text
使用 agent-resource-officer skill，搜索“大君夫人”。注意：普通“搜索/找片”默认先走盘搜，不要先脑补成影巢候选或 MP 搜索。
```

```text
使用 agent-resource-officer skill，执行普通“搜索/找片”后，优先原样转述 route 返回的条目列表。不要把结果二次改写成“资源状态 / 推荐清单 / 要现在下载吗”这类摘要；不要额外补“费用、评分、推荐星级”表述。只保留资源官已经给出的编号、网盘、来源、提取码、摘要、链接和下一步提示。
```

```text
使用 agent-resource-officer skill，执行“转存 / 115转存 / 夸克转存”后，如果插件返回“命令已取消”“暂无结果”“盘搜无结果，可继续试：影巢搜索 片名”“当前不会自动降级执行影巢转存”这类提示，必须原样转发。不要自己追加“要不要试夸克转存”“可以重新盘搜”“可能是缓存清空”这类分析，也不要把无结果改写成新的推荐动作。
```

```text
使用 agent-resource-officer skill，执行“转存 / 115转存 / 夸克转存”时，route 原话一次以后就停在这条链路上。即使命令已取消或结果为空，也不要再自动补跑“MP搜索 / PT搜索 / 搜索 / raw API / 第二次 route”去替用户找下载方案。转存命令的下一步只能是原样回插件提示；除非用户明确改口，否则不要替用户续跑别的链路。
```

## Cloud Search

```text
使用 agent-resource-officer skill，盘搜搜索“蜘蛛侠”或影巢搜索“蜘蛛侠”。这两条入口只在盘搜和影巢之间补查，不进入 MP/PT。
```

```text
使用 agent-resource-officer skill，执行“盘搜搜索 大君夫人”或“影巢搜索 大君夫人”时，必须直接调用 route 对应原话。不要先自己做网页搜索，也不要先把结果加工成“推荐资源/分析结论”。优先原样展示插件返回的 `盘搜结果` 和 `影巢结果` 两段、原始编号、原始链接和下一步提示。
```

```text
使用 agent-resource-officer skill，执行“盘搜搜索 大君夫人”或“影巢搜索 大君夫人”后，不要把返回改写成自己的表格摘要，不要把 115 和夸克各自重新从 1 开始编号，也不要只摘“亮点”。如果插件返回了全局编号和 `影巢结果` 段落，就原样保留；如果插件提示“影巢候选未自动展开”，也原样保留这句。
```

```text
使用 agent-resource-officer skill，夸克转存失败后，如果插件只返回“夸克转存失败：无法转存到 /飞书”，不要自行追加“默认转存目录不存在”“换 path=/ 试试”这类路径猜测。除非插件明确指出路径问题，否则只说明“原因未明，先不要擅自推断路径问题”。
```

## Update Check

```text
使用 agent-resource-officer skill，更新检查“大君夫人”或“检查大君夫人”。这条入口必须先直接调用 route 对应原话，不要先清空会话，不要先网页搜索，不要先走影巢候选。云盘侧更新检查必须显式写成“盘搜更新检查 大君夫人”或“影巢更新检查 大君夫人”。如果原话是“更新检查 xx 剧 / 检查 xx 剧 / 搜索 xx 第 3 集”，按 MP/PT 搜索语义处理，不要回退云盘。`检查115登录` 仍然是 115 登录检查，不算更新检查。
更新检查返回后必须原样保留插件 message 的 emoji 分区和条目行，例如 `🟨 盘搜结果`、`🟦 影巢结果`、`🗄 #25 夸克`、`📺 #1 115`、`🕒05/02`、`📌 E01-E09`。不要改写成 `#: ... 来源: ... 详情: ... 日期: ...` 这种字段表，也不要把条目压缩成总结。
```

```text
使用 agent-resource-officer skill，刷新影巢Cookie。不要 route 这句话，直接运行 hdhive-cookie-refresh，把本机浏览器里的 hdhive.com 完整 Cookie 写回 MoviePilot 和 AgentResourceOfficer。
```

```text
使用 agent-resource-officer skill，修复影巢签到。不要 route 这句话，直接运行 hdhive-checkin-repair：先从本机浏览器刷新影巢 Cookie，再自动重试一次影巢签到，并把最终结果回给我。
```

```text
使用 agent-resource-officer skill，刷新夸克Cookie。不要 route 这句话，直接运行 quark-cookie-refresh，把本机浏览器里的 pan.quark.cn 完整 Cookie 写回 MoviePilot 和 AgentResourceOfficer。
```

```text
使用 agent-resource-officer skill，修复夸克转存。如果刚才的失败明确是登录态问题，直接运行 quark-transfer-repair；如果你还保留着刚才失败的原始命令（例如“选择 7”或“夸克转存 21世纪大君夫人”），优先运行 quark-transfer-repair --retry-text "<原命令>"，刷新完 Cookie 后自动再试一次。
```

```text
使用 agent-resource-officer skill，执行“检查 大君夫人”或“检查大君夫人”时，把它当成“更新检查 大君夫人”的简写。不要把它当成普通搜索，也不要走影巢候选；但 `检查115登录` 仍然保持登录检查。
```

```text
使用 agent-resource-officer skill，执行“更新 大君夫人”时，先把它等价成“更新检查 大君夫人”。如果返回里已经列出盘搜/影巢最新集资源，不要再改写成“你要更新的是不是选项1”。只有在更新检查明确要求继续 PT 搜索时，才提示我是否执行 PT搜索。
```

```text
使用 agent-resource-officer skill，处理普通“搜索/找片/更新检查”时，不要先调用 `session-clear default`。只有用户明确要求“清空会话/重置会话”时，才允许先清会话。
```

```text
使用 agent-resource-officer skill，用户明确发出新的带片名入口命令，例如“搜索低智商犯罪”“搜索 低智商犯罪”“MP搜索 片名”“PT搜索 片名”“下载 片名”“转存 片名”“更新检查 片名”时，必须先 route 原话。即使 route 返回 500、提示有活跃会话或发现旧候选列表，也不能自动 `pick 1` / `选择 1` / 提交下载或转存。只能重试同一原话、用同一原话换新 session，或把错误报告给用户。只有用户本轮明确说“选择 14 / 14详情 / 下载10 / 执行计划 / 刚才那个 / 上次的 / 原来的”这类旧会话续接意图，才允许恢复旧会话并 pick。
```

```text
使用 agent-resource-officer skill，如果“影巢签到”或“影巢签到日志”明确提示网页登录态失效、Cookie 失效、require login 或自动登录拿不到有效 Cookie，先提醒我确认已在 Edge 登录 https://hdhive.com，然后自动执行 hdhive-checkin-repair，再把新的签到结果发给我。不要先让我手工复制 Cookie。
```

```text
使用 agent-resource-officer skill，如果夸克转存失败里明确出现“require login [guest]”“夸克登录态已过期”“当前夸克登录态不足”，先提醒我确认已在 Edge 登录 https://pan.quark.cn，然后自动执行 quark-transfer-repair；如果能拿到刚才失败的原始转存命令，就带上 --retry-text 直接重试一次。不要对 41031、分享受限、分享者封禁这类错误误触发 Cookie 修复。
```

```text
使用 agent-resource-officer skill，执行“清空夸克默认转存目录”或“清空夸克默认目录”时，直接原样透传给 route。不要改写成 115 清理，不要先做搜索，不要先做更新检查。
不要先 grep `aro_request.py` 或自己判断 helper 是否“内置支持”这个命令；这类清空命令本来就是通过 `route "<原话>"` 进入插件路由，不是 helper 的独立子命令。
```

```text
使用 agent-resource-officer skill，执行“清空115转存目录”“清空115默认转存目录”或“清空115默认目录”时，直接原样透传给 route。不要改写成夸克清理，不要先做搜索，不要先做更新检查。
不要先 grep `aro_request.py` 或自己判断 helper 是否“内置支持”这个命令；这类清空命令本来就是通过 `route "<原话>"` 进入插件路由，不是 helper 的独立子命令。
```

```text
使用 agent-resource-officer skill，返回盘搜/影巢/更新检查的资源列表时，必须保留插件原始编号。不要把 `7/8/9/14` 这类编号改写成无编号段落，也不要只在总结里提编号。用户后续需要直接回复编号执行。
```

```text
使用 agent-resource-officer skill，普通 route/pick 命令默认已经输出适合聊天展示的纯文本 message。请优先原样转发这段输出，不要重新解析后再自己生成资源列表。只有需要读取结构化字段时，才给命令加 --json-output。
```

```text
使用 agent-resource-officer skill，展示盘搜结果时，保留“🟦 115 结果 / 🟨 夸克结果”分组标题，但每条资源不要再写 `[115]` 或 `[quark]`。条目格式用“编号. 📺 标题”或“编号. 🗄 标题”，日期保留时钟标记，例如“— 🕒05/07”或插件返回的 display_datetime。如果当前聊天前端会把换行折叠成一段，请把资源列表放进 text 代码块，或至少在分组标题后保留一个空行，确保夸克结果逐条换行显示。
```

```text
使用 agent-resource-officer skill，搜索结果列表不要展示 115/夸克原始分享链接。链接只在“选择 编号 详情”的复制友好详情卡片里展示。

使用 agent-resource-officer skill，盘搜翻页时必须保留插件返回的“展示全局编号 11-20 / 21-30”这类提示，并按全局编号继续。不要把第二页重新改写成“1-10”，也不要把“回复 11”改写成“回复 1”。
```

```text
使用 agent-resource-officer skill，用户说“15详情”“15 的详情”“我要看看 15 的详情”“看十六详情”“详情十六”这类话时，必须当成继续当前编号会话并查看详情，不要执行转存/下载。优先原样调用 route/pick；如果你需要改写命令，只能改写成“选择 15 详情”这一类保留“详情”的命令，绝对不要改成“选择 15”或单独数字。
```

```text
使用 agent-resource-officer skill，用户说“下载 蜘蛛侠”“转存 蜘蛛侠”“夸克转存 蜘蛛侠”“115转存 蜘蛛侠”这类写入命令时，必须保留原话交给 route。现在“下载”仍是有效主线；标题级“转存/115转存/夸克转存”会由插件直接返回“命令已取消”，并引导先做 `盘搜搜索` / `影巢搜索` / `PT搜索`。不要把这些命令改写成“智能执行 蜘蛛侠”，也不要跳过影片确认。
```

```text
使用 agent-resource-officer skill，如果用户有多套 MoviePilot，`ARO_BASE_URL` 指向哪一套，资源命令就会发给哪一套。`下载` / `MP搜索` / `PT搜索` 使用目标 MoviePilot 里配置的下载器；本机 Mac/Win MoviePilot 也可能远程控制 NAS qBittorrent。若当前连接的是网盘/STRM 专用 MoviePilot，或它的 `/待整理` 只是云盘整理目录，不要在这套实例里确认 PT 下载，应先让用户把 `ARO_BASE_URL` 切到 NAS 上负责正常下载的 MoviePilot。
```

```text
使用 agent-resource-officer skill，如果 Agent影视助手插件设置了 `mp_download_save_path`，PT 下载会显式使用这个 MoviePilot `save_path`。不要在聊天里临时猜路径；这个值必须按目标 MoviePilot/NAS 的真实存储映射配置，例如有效的 `local:/...` 或其他 MoviePilot 支持的存储前缀。
```

```text
使用 agent-resource-officer skill，执行“下载 片名”返回 PT 资源列表时，必须原样展示插件 message 里的完整编号列表、做种、体积、评分、建议和下一步提示。不要把结果压缩成“PT资源已列出，回编号选详情或下载”这类一句话摘要。
```

```text
使用 agent-resource-officer skill，在 PT 结果列表里，裸编号“1”、`下载1`，以及用户误发的“计划1/生成计划1”，都按直接下载当前第 1 条 PT 结果处理；“1详情”不是普通聊天入口。只有插件已经返回“PT 下载计划已生成”之后，用户再回复裸编号“1”或“执行计划”才是确认执行。不要把“下载1”当成旧计划确认，也不要把插件的“回复编号直接下载”改写成“查看详情或生成下载计划”。
```

```text
使用 agent-resource-officer skill，用户说“校准影视技能”时，先定位 MoviePilot-Plugins 仓库并检查更新：执行 git fetch origin --prune；如果工作区干净，再执行 git pull --ff-only origin 当前分支。若当前 skill 是 WorkBuddy 这类 standalone 安装副本，拉取后还要从仓库 skill 目录同步当前 skill。若有本地未提交改动或无法快进，只报告原因并继续校准，不要覆盖本地改动。随后运行 python3 scripts/aro_request.py calibrate 或 route "校准影视技能"；无论 pull 是否跳过，都必须重新读取本地 SKILL.md 和 EXTERNAL_AGENTS.md，把返回的硬规则覆盖到当前会话，然后回复仓库更新/同步状态和“影视技能已校准。”。这个命令用于长线程、微信线程或会话压缩后重新校准资源流语义，避免把“下载”改成云盘转存、把“详情”改成执行。
```

```text
使用 agent-resource-officer skill，展示影巢资源结果时，也按“🟦 115 结果 / 🟨 夸克结果”分组展示。每条资源用纯数字编号，格式类似“1. 📺/🗄 标题 · 免费/积分 · 大小 · 集数 · 规格”，不要写成“#1”。在 WorkBuddy 这类 Markdown 前端，每条资源之间保留一个空行，避免压成一个长段落。可以在列表后追加“智能建议”，但必须引用原编号，不能替代列表；需要复制链接或完整信息时，引导使用“选择 编号 详情”。
```

```text
使用 agent-resource-officer skill，资源列表后可以保留或追加“智能建议”。顺序必须是：先完整展示原始编号列表，再单独写“智能建议：”。智能建议不限制长短，可以自然分析取舍，但必须引用原编号；不要用建议替代列表，不要重新编号。建议口吻要像真人帮用户挑资源，重点讲画质、集数完整度、字幕、体积、来源可靠性、115/夸克明确偏好；不要把评分公式或“4K +25”这类加分项当成主要理由。
```

```text
使用 agent-resource-officer skill，如果我说“把刚才那个 22 转存”“原来的 #22”“下载 10”“选择 14”这类话，先把它当成继续上一轮编号会话，不要先重新搜索。优先复用当前 session，或用 decide / sessions / session 恢复最近一轮匹配会话，然后直接 pick 对应编号。只有会话真的不存在时，才允许重搜，并明确告诉我编号已经重建。
```

```text
使用 agent-resource-officer skill，如果“影巢搜索”因为暂无结果而自动补查盘搜，或“盘搜搜索”里的影巢段没有展开，优先原样展示插件返回。不要把它改写成只剩“有新集了”“现在两边都有了”“最高分如下”这类摘要；必须保留原始编号、原始链接和下一步提示。可以在列表后追加智能建议，建议不限制长短。
```

## PT Search

```text
使用 agent-resource-officer skill，PT搜索“蜘蛛侠”。这条入口等同于 MP搜索，走 MoviePilot 原生 PT 搜索和评分。
如果插件先返回 MP/TMDB 候选列表，不要替用户默认选第一项；把候选列表展示出来，让我回复编号后再继续搜索 PT 资源。
展示 PT 结果时必须原样保留插件返回的 message，不要重新压缩成自己的列表，不要改写英文发布标题；插件标题里有防止微信误识别链接的隐藏断点，也有为手机微信阅读准备的 emoji 标记，必须保留。
```

## HDHive Search

```text
使用 agent-resource-officer skill，影巢搜索“蜘蛛侠”。如果有多个候选影片，先让我选择影片；再展示资源列表。
```

## Direct Share Link

```text
使用 agent-resource-officer skill，处理这个分享链接并转存到默认目录：https://pan.quark.cn/s/xxxx
```

## Custom Path

```text
使用 agent-resource-officer skill，把这个夸克链接转存到 /飞书：链接 https://pan.quark.cn/s/xxxx path=/飞书

---

如果用户直接发来夸克或 115 分享链接，不要改写成“夸克转存 关键词”或“盘搜搜索 关键词”。这是直链转存场景，不是影视标题搜索场景。请直接使用 agent-resource-officer skill，原样 route 这条带链接的话，或直接走 share-link 路由。
```

## Continue Choice

```text
使用 agent-resource-officer skill，继续当前会话，选择 1。如果返回 confirmation_message，先给我确认提示。
```

## Health Check

```text
使用 agent-resource-officer skill，执行 selfcheck，确认 AgentResourceOfficer 协议和请求模板都正常。
```

## Local Selftest

```text
使用 agent-resource-officer skill，先运行 selftest，验证本地 helper 的命令生成逻辑。
```

## Command Catalog

```text
使用 agent-resource-officer skill，运行 commands，查看 helper 支持的命令、联网需求和写入风险。
```

## Helper Version

```text
使用 agent-resource-officer skill，运行 version，确认当前 helper 版本。
```

## Config Check

```text
使用 agent-resource-officer skill，运行 config-check，确认连接配置存在，但不要输出 API Key。
```

## External Agent

```text
你是 MoviePilot Agent影视助手的外部智能体入口。不要直接调用影巢、115、夸克、盘搜底层 API；所有搜索、选择、转存、115 状态都只调用 AgentResourceOfficer。每个用户或群聊固定使用 session=agent:会话ID。新会话先 startup；用户发搜索/链接时调用 route；用户发选择/详情/下一页时调用 pick。不要输出 API Key、Cookie、Token。
展示资源列表时，不要压缩掉关键字段：网盘、解锁分、大小、清晰度、来源、集数/更新信息、字幕、详情摘要都要尽量保留。
用户只说“搜索/找 某片”时，先原样透传给 route，不要擅自续跑旧 session，也不要先脑补成影巢候选选择。默认搜索应先走盘搜；只有用户明确说“影巢搜索”才进影巢，明确说“MP搜索/PT搜索”才进 MP/PT。
用户明确说“MP搜索 / MP 搜索 / PT搜索 / PT 搜索 某片”时，必须保持原命令进入 route，不要改写为“搜索/盘搜搜索/影巢搜索/智能搜索”。
“推荐 / 热门推荐 / 智能发现 / 热门发现 / 资源决策 / 智能决策”这组高级入口已经下线。不要再主动建议用户使用它们，也不要把普通明确来源命令自动升级成智能决策。
用户只说“更新/查更新/检查 某片”时，先原样透传给 route，并优先走“更新检查 某片”或“检查 某片”；不要先清空会话，不要先影巢候选，不要先网页搜索。更新检查的职责是直接列出TMDB 参考进度、盘搜最新集资源、影巢最新集资源，让用户自己判断和选择编号。
```

## External Agent Helper

```text
使用 agent-resource-officer skill，运行 external-agent，输出可交给 WorkBuddy、Hermes、OpenClaw（小龙虾）、微信侧智能体或其他外部智能体的紧凑提示词和最小工具约定。需要完整说明时运行 external-agent --full。
```

## Ask Another Agent To Create Skill

```text
请阅读 https://github.com/liuyuexi1987/MoviePilot-Plugins ，重点阅读 docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md、skills/agent-resource-officer/SKILL.md、skills/agent-resource-officer/EXTERNAL_AGENTS.md。然后在你的环境里创建或安装 agent-resource-officer Skill。Skill 里只固化通用流程、工具调用方式、session 规则和错误处理，不要写入 API Key、Cookie、Token。

创建的 Skill 必须写入这些硬规则：
1. 资源流命令直接走 agent-resource-officer 的 route/pick，不要先走 MCP、tool_search、curl 或 raw API。当前主线包括：盘搜搜索、影巢搜索、MP搜索、PT搜索、下载、更新、更新检查、检查、选择、详情、n、下一页和编号续选。标题级“转存/115转存/夸克转存”仅用于返回插件的取消提示，不再是实际执行入口。
2. route/pick 默认输出就是适合聊天展示的纯文本 message，请优先原样转发，不要重新改写资源列表；只有需要程序化读取字段时才加 --json-output。
3. 如果原始输出里有“智能建议”，必须保留；如果没有，也可以在原始列表后追加智能建议。智能建议不限制长短，但必须引用原始编号，不能替代列表、不能重新编号；建议要围绕画质、集数完整度、字幕、体积、来源可靠性、115/夸克明确偏好来写，不要把评分公式或加分项原样展示成理由。
4. 如果用户有多套 MoviePilot，先确认 `ARO_BASE_URL` 当前指向哪一套。`下载` / `MP搜索` / `PT搜索` 的下载器和保存路径由目标 MoviePilot/qBittorrent 决定；网盘/STRM 专用实例不要用于确认 PT 下载，PT 下载应切到 NAS 上负责正常下载的 MoviePilot。
5. 如果插件配置了 `mp_download_save_path`，它会作为 PT 下载的显式保存路径；不要自行猜测或覆盖这个路径。

创建后请用 external-agent 输出接入信息，并自测：用户说“盘搜搜索 大君夫人”时走 route；用户再说“选择 3”时沿用同一个 agent:会话ID 走 pick。
```

## Readiness

```text
使用 agent-resource-officer skill，运行 readiness，确认配置、本地 helper 和 MoviePilot 插件接口都可用。
```

## Doctor

```text
使用 agent-resource-officer skill，先调用 doctor，给我一个只读的启动/健康/会话/恢复总览，再决定是否继续旧会话。
```

## Low Token Doctor

```text
使用 agent-resource-officer skill，先调用 doctor --summary-only，只返回最省 token 的决策摘要和下一步命令建议。
```

## Recovery

```text
使用 agent-resource-officer skill，先调用 sessions 和 recover，告诉我当前最值得继续的会话；如果需要继续执行，先展示 confirmation_message。
```

## Low Token Recovery

```text
使用 agent-resource-officer skill，先调用 recover --summary-only，只返回恢复决策摘要和下一步命令建议。
```

## Plan Audit

```text
使用 agent-resource-officer skill，先看最近 plans 和 history，不要默认只看 default 会话；如果发现未执行计划，再告诉我是否值得继续。
```

## Execute Exact Plan

```text
使用 agent-resource-officer skill，精确执行这个 dry-run 计划：plan-execute --plan-id plan-xxx。执行前先确认这是我要的 plan_id。
```

## Clear Exact Plan

```text
使用 agent-resource-officer skill，清理这个已确认不需要的 dry-run 计划：plans-clear --plan-id plan-xxx。不要批量清理其他计划。
```
