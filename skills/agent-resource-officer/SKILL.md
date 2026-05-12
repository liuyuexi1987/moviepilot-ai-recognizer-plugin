---
name: agent-resource-officer
description: Control AgentResourceOfficer, the MoviePilot resource workflow hub, from an external agent. Use when an agent should route title-based resource commands including PanSou, HDHive, 115, Quark, MP/PT search, downloads, update checks, numbered choices, paging, cookie repair, startup/recovery state, request templates, or saved plans through AgentResourceOfficer instead of calling MoviePilot MCP search tools, TMDB, HDHive, 115, Quark, or PanSou APIs directly.
---

# AgentResourceOfficer Skill

Use this skill when the user wants an external agent to operate MoviePilot title-based resource workflows through `AgentResourceOfficer`, including PanSou, HDHive, 115, Quark, MP/PT search, download, update-check, numbered picking, paging, and repair flows.

The plugin is the capability layer. The agent should orchestrate, display choices, ask for confirmation when required, and call the stable assistant endpoints.

## Configuration

Public repository:

```text
https://github.com/liuyuexi1987/MoviePilot-Plugins
```

Install this skill on the machine running the external agent:

```bash
git clone https://github.com/liuyuexi1987/MoviePilot-Plugins.git
cd MoviePilot-Plugins
bash skills/agent-resource-officer/install.sh --dry-run
bash skills/agent-resource-officer/install.sh
```

Preferred config file:

```text
~/.config/agent-resource-officer/config
```

Format:

```text
ARO_BASE_URL=http://127.0.0.1:3000
ARO_API_KEY=your_moviepilot_api_token
```

Rules:

- `ARO_BASE_URL` must be the MoviePilot address reachable from the machine running the external agent.
- Use `127.0.0.1` only when MoviePilot is on the same machine.
- If the user has multiple MoviePilot instances, `ARO_BASE_URL` decides which one receives `下载` / `MP搜索` / `PT搜索` / `转存`.
- `下载` / `MP搜索` / `PT搜索` use the downloader configured inside that MoviePilot instance, so do not assume "local MP" means "local download".
- If the target MoviePilot is only for cloud-drive/STRM workflows, do not confirm PT downloads through it.
- If the server plugin sets `mp_download_save_path`, treat it as a server-side safety setting. Never invent that path in chat.

## Routing Boundary

Use MoviePilot MCP only when it is truly connected in the current client and the corresponding MCP tools are visible in the active tool list.

Default boundary:

- MoviePilot native read-only or light management queries may prefer MCP when MCP is really available.
- Title-based resource workflows stay on `agent-resource-officer`.
- If MCP is not explicitly available, continue to use helper/HTTP route flow and do not pretend MCP exists.

Resource commands that must go straight to `route` / `pick`:

- `搜索` / `找`
- `盘搜` / `盘搜搜索`
- `影巢` / `影巢搜索`
- `MP搜索` / `PT搜索`
- `转存` / `115转存` / `夸克转存`
- `下载`
- `更新` / `更新检查` / `检查`
- `盘搜更新检查` / `影巢更新检查`
- `选择` / `详情` / `n` / `下一页`
- numbered follow-ups

Episode-aware plain searches such as `搜索 第 3 集`, `搜索 E03`, or `搜索 更新至 第 10 集` should also be treated as explicit MP/PT searches and must not fall back to cloud search.
Cloud update checks must carry a source prefix: use `盘搜更新检查 <片名>` or `影巢更新检查 <片名>`. Bare `更新检查 xx 剧` / `检查 xx 剧` should be treated as MP/PT search intent.

Core rules:

- `转存 <片名>` means `115转存 <片名>` by default; only explicit `夸克转存` should use Quark.
- `下载 <片名>` means MoviePilot/PT only. Never rewrite it into cloud search or cloud transfer.
- Ambiguous write-intent titles such as `下载 蜘蛛侠` or `转存 蜘蛛侠` must first resolve MoviePilot/TMDB candidates, then continue with the exact chosen title and year.
- `下载1` generates or selects the current PT download plan. It is not confirmation for an older saved plan.
- In PT result lists, plain `1` / `选择 1` directly downloads the selected PT result. Do not turn it into a detail/review step.
- Cloud-drive and HDHive resource lists still support read-only detail cards via `选择 1 详情` or `详情 1`.
- Before confirming PT download execution, make sure the connected MoviePilot is the real download instance, not a cloud-drive/STRM-only instance.
- If the user says `校准影视技能`, first check the local `MoviePilot-Plugins` checkout for GitHub updates: run `git fetch origin --prune`, then run `git pull --ff-only origin <current-branch>` only when the working tree is clean. If local changes or a non-fast-forward state block the pull, report that and continue calibration without overwriting anything. Then run `python3 scripts/aro_request.py calibrate` or `python3 scripts/aro_request.py route "校准影视技能"`, apply the returned hard rules to the current session, and reply with the repository update status plus `影视技能已校准。`.
- For explicit title searches such as `MP 搜索 罪无可逃`, the first and only initial action is helper `route "<原话>" --session <session>`. Do not pre-call TMDB, MCP search, raw MoviePilot API, or torrent search before that helper route.

Environment overrides:

- `ARO_BASE_URL`
- `MP_BASE_URL`
- `MOVIEPILOT_URL`
- `ARO_API_KEY`
- `MP_API_TOKEN`
- `ARO_HDHIVE_COOKIE_EXPORT_DIR`
- `ARO_HDHIVE_COOKIE_EXPORT_PYTHON`
- `ARO_HDHIVE_COOKIE_BROWSER`
- `ARO_HDHIVE_COOKIE_SITE_URL`
- `ARO_HDHIVE_COOKIE_RESTART_CONTAINER`
- `ARO_QUARK_COOKIE_EXPORT_DIR`
- `ARO_QUARK_COOKIE_EXPORT_PYTHON`
- `ARO_QUARK_COOKIE_BROWSER`
- `ARO_QUARK_COOKIE_SITE_URL`
- `ARO_QUARK_COOKIE_RESTART_CONTAINER`

Never print API keys, cookies, or tokens back to the user.

If this skill is installed from the `MoviePilot-Plugins` repository checkout, the helper will first try the bundled cookie export tools in:

- `tools/hdhive-cookie-export/`
- `tools/quark-cookie-export/`

The install helper copies these tools into the installed skill directory as `tools/...`, so a standalone installed skill can call `hdhive-cookie-refresh`, `hdhive-checkin-repair`, `quark-cookie-refresh`, and `quark-transfer-repair` directly. You can still override them with `ARO_HDHIVE_COOKIE_EXPORT_DIR` and `ARO_QUARK_COOKIE_EXPORT_DIR`.

Optional install helper:

```bash
bash install.sh --dry-run
bash install.sh
bash install.sh --target /path/to/skills/agent-resource-officer
```

## Request Helper

Prefer the bundled helper:

```bash
python3 scripts/aro_request.py startup
python3 scripts/aro_request.py auto
python3 scripts/aro_request.py auto --summary-only
python3 scripts/aro_request.py decide --summary-only
python3 scripts/aro_request.py decide --command-only
python3 scripts/aro_request.py doctor --limit 5
python3 scripts/aro_request.py doctor --limit 5 --summary-only
python3 scripts/aro_request.py feishu-health
python3 scripts/aro_request.py recover --summary-only
python3 scripts/aro_request.py version
python3 scripts/aro_request.py selftest
python3 scripts/aro_request.py hdhive-cookie-refresh
python3 scripts/aro_request.py hdhive-checkin-repair
python3 scripts/aro_request.py quark-cookie-refresh
python3 scripts/aro_request.py quark-transfer-repair
python3 scripts/aro_request.py commands
python3 scripts/aro_request.py external-agent
python3 scripts/aro_request.py external-agent --full
python3 scripts/aro_request.py config-check
python3 scripts/aro_request.py readiness
python3 scripts/aro_request.py selfcheck
python3 scripts/aro_request.py sessions
python3 scripts/aro_request.py sessions --kind assistant_hdhive --limit 5
python3 scripts/aro_request.py session-clear default
python3 scripts/aro_request.py sessions-clear --has-pending-p115 --limit 10
python3 scripts/aro_request.py templates --recipe bootstrap
python3 scripts/aro_request.py route "盘搜搜索 大君夫人"
python3 scripts/aro_request.py pick 1
```

The helper uses `?apikey=...`, which is the recommended HTTP auth mode for plugin assistant endpoints.

Use `selftest` to validate local helper logic without connecting to MoviePilot:

```bash
python3 scripts/aro_request.py selftest
```

Use `version` to print the local helper version:

```bash
python3 scripts/aro_request.py version
```

Use `commands` when an external agent needs the local helper command catalog:

```bash
python3 scripts/aro_request.py commands
```

The command catalog uses `schema_version=commands.v1`; `writes` is always boolean and details live in `write_condition`.

Use `external-agent` when handing this Skill to WorkBuddy, Hermes, OpenClaw（小龙虾）, a WeChat-side agent, or another external agent:

```bash
python3 scripts/aro_request.py external-agent
python3 scripts/aro_request.py external-agent --full
python3 scripts/aro_request.py calibrate
```

`external-agent` prints the compact prompt and minimal tool contract. `external-agent --full` prints the full bundled handoff guide. `workbuddy` remains a compatibility alias only; new integrations should use `external-agent`.

`calibrate` prints a compact calibration card for long-lived external-agent threads. Use it when a WeChat/WorkBuddy/Claw/Hermes/OpenClaw session has been compressed or starts rewriting commands incorrectly, for example changing `下载 <片名>` into cloud transfer, treating cloud detail as execution, or treating PT numbered downloads as detail review.

When a user says plain `搜索 <片名>` or `找 <片名>`, pass that text through to `route` first. Do not guess that the user meant HDHive, and do not continue an old result session by sending `选择 1` unless the user actually chose an item in the current round. Default plain search should start from MoviePilot native/PT search; only if MP/PT is disabled should the plugin fall back to other enabled search sources.

When the user clearly refers to a previously shown numbered result, for example `刚才那个 22`、`上次的 #22`、`把原来的 22 转存`、`下载 10`、`选择 14`, do not restart search first. Reuse the current session, or recover the latest matching session with `decide --summary-only` / `sessions` / `session`, then continue with `pick`. Only restart the search when the old session is truly gone and cannot be recovered.

When a user says `转存 <片名>`, route that text directly first. Treat it as a 115-transfer intent, equivalent to `115转存 <片名>`: prefer PanSou + HDHive 115 resources, and let AgentResourceOfficer execute the one-stop transfer flow instead of rewriting it into a PT download request. Only use Quark when the user explicitly says `夸克转存`.

When a user says `下载 <片名>`, route that text directly first. Treat it as an MP/PT search-and-download intent, not a browsing/listing intent. If the title is ambiguous, show MoviePilot/TMDB title candidates first. Once the title is unambiguous, the plugin should search PT internally and directly return up to three pending download plans for the best PT candidates instead of showing the full PT list. It must not auto-submit a real download from the title command. Only after the plugin has returned pending plans may the user confirm by replying the displayed方案编号 such as `1`, `2`, or `3`, or `执行计划`; route that reply as-is so the plugin can execute the matching pending plan. `下载1` means "generate/select download plan for result 1", not confirmation for an older saved plan. If there is no pending plan in the current session, a bare number must be treated as the current result-list continuation.

When a user says `MP搜索 <片名>`, `MP 搜索 <片名>`, `PT搜索 <片名>`, or `PT 搜索 <片名>`, route that exact text directly first. Treat it as an explicit MoviePilot native/PT search request. Do not rewrite it into `搜索 <片名>`, `盘搜搜索 <片名>`, `影巢搜索 <片名>`, or smart search.

If the same command includes a natural-language latest-episode intent such as `给我最新集`, `最新集`, or `最新一集`, still route the original text directly. AgentResourceOfficer will strip that suffix from the title, detect the highest episode in PT results, and show only candidates containing that latest episode. Do not add older episode batches back into the summary unless the user asks for all results.

If the same command includes a clear episode filter such as `第4集`, `第四集`, `E04`, or `S01E04`, still route the original text directly. AgentResourceOfficer will strip the episode suffix from the title and show only candidates containing that target episode, then renumber the filtered list safely. Do not remove this intent or rewrite it as a generic title search.

For `下载 <片名>` results, relay the plugin's returned message exactly like `MP搜索` / `PT搜索`. If the plugin returns a PT resource list, show the numbered resources, score lines, recommendation, and next-step hints. Never replace the list with a one-line summary such as `PT资源已列出，回编号选详情或下载`. In PT result lists, keep the distinction clear: plain `N` / `选择 N` directly downloads the selected PT result; `下载N` generates a pending download plan; PT result rows do not expose a chat detail card.

If `MP搜索` / `PT搜索` returns a MoviePilot media candidate list, do not choose for the user. Show the candidates, ask the user to reply with a number, then call `pick <number>` to continue the PT search. For ambiguous titles such as `蜘蛛侠`, this candidate step is expected and safer than assuming the 2002 movie.

If the original `MP搜索` / `PT搜索` command included `最新集` / `给我最新集` and then returned a media candidate list, the user's numeric reply must be routed in the same helper session. Do not run a fresh bare `route "1"` in another/default session, and do not summarize older episode batches as latest results. The plugin will preserve the latest-episode filter after the candidate is selected; relay that returned message as-is.

After `下载 <片名>` returns a title candidate list, preserve the same helper session and route the user's numeric reply exactly as the reply text, for example `python3 scripts/aro_request.py route "5" --session <same-session>`. Do not reconstruct it as `下载 <候选标题 年份>`, because that loses the candidate session and can change behavior. If the selected title has no PT resources, say that MP/PT currently has no downloadable result; do not silently fall back to PanSou, HDHive, Quark, 115, or cloud transfer. Cloud resources require an explicit `盘搜搜索` / `影巢搜索` / `转存` / `夸克转存` / `115转存` command.

For `MP搜索` / `PT搜索` results, relay the plugin's returned message exactly. Do not compress it into a new custom list such as `PT 资源共 N 条`, and do not rewrite release titles. Preserve the plugin's emoji markers (`🧲`, `🌱`, `🎁`, `💾`, `⭐`, etc.) and invisible breaks in dotted release names; they are intentional for WeChat/mobile readability.

Do not renumber MP/PT result lists. If the plugin returns visible item numbers like `2, 4, 21, 29`, keep those exact numbers in the user-facing reply and in follow-up commands such as `选择 2` or `下载2`. Never rewrite them to `1, 2, 3, 4`, because MP/PT download actions are keyed to the plugin's visible numbers. Do not append your own “当前最高分候选” or “回复选择 N” footer when the plugin message already includes recommendation and next-step hints.

When the current client has no MoviePilot MCP tools, do not announce an MCP fallback for `MP搜索` / `PT搜索`. Just call `python3 scripts/aro_request.py route "<原始用户命令>" --session <session>` and relay the returned message.

`云盘搜索` is deprecated. If a user still says `云盘搜索 <片名>`, do not invent your own combined search. Let the plugin return its deprecation hint, then guide the user toward `盘搜搜索 <片名>` or `影巢搜索 <片名>`.

When a user says `更新 <片名>`, `更新检查 <片名>`, `查更新 <片名>`, `检查 <片名>`, or a glued form like `检查大君夫人`, route that text directly first and treat it as the update-check entry unless the query carries explicit episode/series-search intent such as `第 3 集`, `E03`, or a trailing `剧`; those should remain MP/PT searches. Do not clear the session first, do not guess that the user meant HDHive candidate search, and do not replace it with a generic search flow. Cloud-side update checks must use `盘搜更新检查 <片名>` or `影巢更新检查 <片名>`. `检查115登录` remains a login-check command, not an update-check command.

For update-check results, relay the plugin's returned message exactly. Preserve the emoji sections and item lines such as `🟨 盘搜结果`, `🟦 影巢结果`, `🗄 #25 夸克`, `📺 #1 115`, `🕒05/02`, and `📌 E01-E09`. Do not transform them into field-table prose like `#: ... 来源: ... 详情: ... 日期: ...`, and do not replace the list with a summary.

For update-check results, relay the plugin's returned message exactly. Preserve the emoji sections and item lines such as `🟨 盘搜结果`, `🟦 影巢结果`, `🗄 #25 夸克`, `📺 #1 115`, `🕒05/02`, and `📌 E01-E09`. Do not transform them into field-table prose like `#: ... 来源: ... 详情: ... 日期: ...`, and do not replace the list with a summary.

When a user says `刷新影巢Cookie`, do not route that phrase into AgentResourceOfficer. Treat it as a host-side repair action and run:

```bash
python3 scripts/aro_request.py hdhive-cookie-refresh
```

This command exports the current HDHive webpage cookie from the local browser, writes it back into MoviePilot and AgentResourceOfficer, and restarts `moviepilot-v2`.

When a user says `修复影巢签到`, do not route that phrase directly. Run:

```bash
python3 scripts/aro_request.py hdhive-checkin-repair
```

This command refreshes the HDHive webpage cookie from the local browser export tool, restarts `moviepilot-v2`, then retries one HDHive sign-in through AgentResourceOfficer.

When `影巢签到` or `影巢签到日志` clearly shows cookie/login failure, prefer the automatic repair flow instead of asking the user to hand-copy cookies. First remind the user to ensure they are logged into `https://hdhive.com` in Edge, then run `hdhive-checkin-repair`, and finally show the new sign-in result.

When a user says `刷新夸克Cookie`, do not route that phrase into AgentResourceOfficer. Treat it as a host-side repair action and run:

```bash
python3 scripts/aro_request.py quark-cookie-refresh
```

This command exports the current Quark webpage cookie from the local browser, writes it back into MoviePilot and AgentResourceOfficer, and restarts `moviepilot-v2`.

When a user says `修复夸克转存`, do not route that phrase directly. Prefer:

```bash
python3 scripts/aro_request.py quark-transfer-repair --retry-text "<刚才失败的原始转存命令>"
```

If there is no safe transfer command to retry, run `python3 scripts/aro_request.py quark-transfer-repair` first to refresh the cookie and verify Quark health, then ask the user to retry the original transfer.

Only use the Quark automatic repair flow when the failure clearly points to login/cookie problems, for example `require login [guest]`, `夸克登录态已过期`, or `当前夸克登录态不足`. Do not trigger it for share-link restrictions, deleted links, or ordinary 403/41031 share bans.

For ordinary search, cloud search, HDHive resource lists, and update-check lists, preserve the plugin's original numbering exactly. Do not reformat a numbered resource list into unnumbered prose, do not collapse numbered items into a separate summary, and do not move the actionable numbers only into a later recommendation paragraph. Smart recommendations are welcome after the original list, and can be as detailed as useful, as long as they reference the original item numbers and do not replace the list.

The helper's default `route` and `pick` commands print a chat-friendly plain text `message`. Relay that output directly to the user. If you need to parse structured fields programmatically, add `--json-output`; do not parse the plain display text and then reconstruct your own resource list.

For cloud-drive or HDHive numbered detail follow-ups, keep the detail action. `选择 15 详情`, `我要看看 15 的详情`, and `详情十六` are read-only detail requests. They must not be changed into `选择 15` or a direct transfer command. PT result lists do not expose detail cards; plain numbers download PT results.

For PanSou result lists, keep the source section headings (`🟦 115 结果`, `🟨 夸克结果`) and do not repeat provider tags inside every item. Display items as `编号. emoji 标题` rather than `编号. [115] ...` or `编号. [quark] ...`. Dates should keep the clock marker, for example `— 🕒05/07` or the returned `display_datetime`. Preserve physical line breaks between the source heading and each numbered item; if the chat frontend renders Markdown and may collapse normal line breaks, wrap the resource list itself in a fenced `text` block or insert real blank lines after each source heading so Quark items do not collapse into one paragraph.

Do not show raw 115/Quark share links in search result lists. Links belong in the copy-friendly detail card returned by `选择 编号 详情`.

For HDHive/影巢 resource lists, use the same source grouping style: `🟦 115 结果` and `🟨 夸克结果`. Keep each resource as plain numbered items like `1. emoji 标题 · 积分 · 大小 · 集数 · 规格`, not `#1`. Put a real blank line between resource items in Markdown-like chat frontends so WorkBuddy does not collapse the list into one paragraph. A recommendation section is allowed at the end, but keep it after the original list and reference original numbers. If the user needs a shareable link or full metadata, tell them to use `选择 编号 详情`; the detail card is the copy-friendly view.

After displaying a resource list, add or preserve a `智能建议` section when the data is enough to compare quality. Do not over-constrain the recommendation length; explain the tradeoffs naturally around common viewing and storage decisions such as picture quality, episode completeness, subtitle clarity, file size, source reliability, and whether the user explicitly wants 115 or Quark. Do not expose raw score formulas such as `4K +25` as the main explanation. The only hard rule is that recommendations must reference the original item numbers and must not replace or renumber the original list.

For cloud search results, prefer the plugin's raw combined layout: keep the `盘搜结果` section, keep the `影巢结果` section, and keep raw links when the plugin returned them. Do not hide the source-specific sections behind your own summary. A short recommendation is allowed only after the raw list and next-step hint.

For cloud search, never renumber items per source in your own prose. If the plugin returned global numbering like `1..16` plus `17..24`, preserve that exact numbering. Do not convert it into separate `115 1..6 / 夸克 1..10` local indices, and do not collapse the response into a custom “标题/画质/日期/链接” table that drops the plugin's next-step instructions.

When `影巢搜索` falls back to PanSou because HDHive returned no usable result, keep the plugin's original fallback text and numbered resource list. Do not rewrite it into your own progress bulletin like “有新集了”“现在两边都有了” or a custom compact table that hides links, numbering, or next-step hints.

When a Quark transfer fails, do not invent a path diagnosis unless the plugin explicitly said so. If the plugin only returned `夸克转存失败：无法转存到 /飞书`, treat the cause as unknown and do not add guesses like “默认转存目录不存在” or “换成 path=/ 试试” on your own. Only recommend a different path when the plugin itself clearly pointed to a path problem or the user explicitly asked to try another path.

Use `config-check` to verify connection settings without printing secrets:

```bash
python3 scripts/aro_request.py config-check
```

Use `readiness` after configuration to run config check, local selftest, and live plugin selfcheck together:

```bash
python3 scripts/aro_request.py readiness
```

Update-check examples:

```bash
python3 scripts/aro_request.py route "更新 大君夫人"
python3 scripts/aro_request.py route "更新检查 大君夫人"
python3 scripts/aro_request.py route "检查 大君夫人"
```

Quark cleanup examples:

```bash
python3 scripts/aro_request.py route "清空夸克默认转存目录"
python3 scripts/aro_request.py route "清空夸克默认目录"
```

Use Quark cleanup only when the user explicitly asked to clear the Quark default transfer directory. Treat it as a destructive cloud-drive write. It targets the current layer entries of the configured Quark default directory: files are deleted directly, and current-layer folders are deleted together with their contents. Do not infer it from vague cleanup requests, do not silently replace it with 115 cleanup, and do not grep helper source to decide whether this command is supported.

115 cleanup examples:

```bash
python3 scripts/aro_request.py route "清空115转存目录"
python3 scripts/aro_request.py route "清空115默认转存目录"
python3 scripts/aro_request.py route "清空115默认目录"
```

Use 115 cleanup only when the user explicitly asked to clear the 115 default transfer directory. Treat it as a destructive cloud-drive write. It targets the current layer entries of the configured 115 default directory: files are deleted directly, and current-layer folders are deleted together with their contents. Do not grep helper source to decide whether this command is supported; route the original phrase directly.

For update requests, do not start with:

```bash
python3 scripts/aro_request.py session-clear default
python3 scripts/aro_request.py route "影巢搜索 大君夫人"
```

unless the user explicitly asked to abandon the current state or explicitly asked for HDHive-only search.

For ordinary search and update requests, do not start with:

```bash
python3 scripts/aro_request.py session-clear default
```

unless the user explicitly asked to clear or reset the session.

Use `feishu-health` only when diagnosing the built-in AgentResourceOfficer Feishu Channel:

```bash
python3 scripts/aro_request.py feishu-health
```

For MoviePilot's built-in Agent, use the native tool `agent_resource_officer_feishu_health` instead of calling the Feishu health API manually.

## Core Startup Flow

Fast path:

```bash
python3 scripts/aro_request.py decide --summary-only
python3 scripts/aro_request.py auto
python3 scripts/aro_request.py auto --summary-only
python3 scripts/aro_request.py doctor --limit 5
```

`auto` calls `startup`, reads `recommended_request_templates`, then fetches the recommended low-token recipe.

`decide` is the single low-token decision entry:

- if there is a resumable session, it returns `decision=continue_session`
- otherwise it returns `decision=start_recipe`

If you want the automatic flow but only need the decision summary, prefer:

```bash
python3 scripts/aro_request.py auto --summary-only
```

`doctor` is the read-only diagnostic entry. It combines:

- `assistant/startup`
- `assistant/selfcheck`
- `assistant/sessions`
- `assistant/recover`

Use it when an external agent needs one compact bootstrap/health/recovery snapshot before deciding whether to start a new task or continue an old one.

It also returns local helper suggestions:

- `helper_commands.inspect_helper_command`
- `helper_commands.execute_helper_command`

For `auto --summary-only` and `decide --summary-only`, the start-recipe branch also returns:

- `inspect_helper_command`
- `execute_helper_command`

If a caller only wants the next helper command, use:

```bash
python3 scripts/aro_request.py decide --command-only
python3 scripts/aro_request.py auto --command-only
python3 scripts/aro_request.py recover --command-only
python3 scripts/aro_request.py decide --command-only --confirmed
```

`--command-only` prints an inspect command only when the next action itself requires confirmation. If the current recipe starts with a safe read step, such as `mp_pt` or `recommend`, it prints that executable read command directly even when later write steps still require confirmation.

If token budget is tight, prefer:

```bash
python3 scripts/aro_request.py doctor --summary-only
python3 scripts/aro_request.py recover --summary-only
```

Manual path:

1. Call startup:

```bash
python3 scripts/aro_request.py startup
```

2. Read `recommended_request_templates`.

3. Fetch templates by the recommended recipe:

```bash
python3 scripts/aro_request.py templates --recipe continue
```

If startup has recoverable state, it may recommend `continue`. Otherwise it normally recommends `bootstrap`.

## Recipes

Supported recipe names and short aliases:

- `bootstrap` -> `safe_bootstrap`
- `plan` -> `plan_then_confirm`
- `maintain` -> `maintenance_cycle`
- `continue` -> `continue_existing_session`
- `preferences` / `prefs` / `片源偏好` / `偏好画像` -> `preferences_onboarding`
- `mp_pt` / `mp` / `pt` -> `mp_pt_mainline`
- `recommend` / `热门` / `推荐` -> `mp_recommendation`
- `local_ingest` / `ingest` / `local` / `本地入库` / `入库诊断` -> `local_ingest`

Use:

```bash
python3 scripts/aro_request.py templates --recipe plan --policy-only
python3 scripts/aro_request.py templates --recipe preferences --policy-only
python3 scripts/aro_request.py templates --recipe mp_pt --policy-only
python3 scripts/aro_request.py templates --recipe recommend --policy-only
```

The response includes:

- `recommended_recipe`
- `recommended_recipe_detail.first_call`
- `recommended_recipe_detail.calls`
- `first_confirmation_template`
- `confirmation_message`
- `auth.mode=query_apikey`
- `url_template`

## Main Interaction Flow

For natural-language resource work, use `route`:

```bash
python3 scripts/aro_request.py route --text "MP搜索 蜘蛛侠"
python3 scripts/aro_request.py route --text "影巢搜索 蜘蛛侠"
python3 scripts/aro_request.py route --text "盘搜搜索 大君夫人"
python3 scripts/aro_request.py route --text "链接 https://pan.quark.cn/s/xxxx path=/飞书"
```

For numbered continuation, use `pick`. Positional and flagged forms are both supported:

```bash
python3 scripts/aro_request.py pick 1
python3 scripts/aro_request.py pick 11 --path /飞书
python3 scripts/aro_request.py pick 1 详情
python3 scripts/aro_request.py pick 详情
python3 scripts/aro_request.py pick 下一页
```

Common diagnostic helpers also support shorter positional forms:

```bash
python3 scripts/aro_request.py workflow mp_media_detail 蜘蛛侠
python3 scripts/aro_request.py session default
python3 scripts/aro_request.py history agent:demo
python3 scripts/aro_request.py plans plan-xxx
python3 scripts/aro_request.py plans-clear plan-xxx
```

For session inspection and recovery:

```bash
python3 scripts/aro_request.py sessions
python3 scripts/aro_request.py session default
python3 scripts/aro_request.py session-clear default
python3 scripts/aro_request.py sessions-clear --has-pending-p115 --limit 10
python3 scripts/aro_request.py recover
python3 scripts/aro_request.py recover --execute
python3 scripts/aro_request.py templates --recipe followup --compact
python3 scripts/aro_request.py history --limit 10
python3 scripts/aro_request.py history agent:demo
python3 scripts/aro_request.py plans --limit 10
python3 scripts/aro_request.py plans plan-xxx
python3 scripts/aro_request.py plans --executed --include-actions --limit 5
python3 scripts/aro_request.py plan-execute plan-xxx
python3 scripts/aro_request.py followup --session agent:<用户ID>
python3 scripts/aro_request.py followup plan-xxx
python3 scripts/aro_request.py plans-clear plan-xxx
```

Notes:

- `sessions`, `history`, `plans`, and `recover` no longer force `session=default` when you do not pass `--session`.
- Use `--session` or `--session-id` only when you want to narrow to one conversation.
- Use `sessions --kind ...` or `sessions --has-pending-p115` when you want recovery-oriented filtering.
- Use `followup` after `plan-execute` when you want the plugin to choose the correct read-only next step automatically.
- Use `session-clear` or `sessions-clear` to clear abandoned assistant state after user confirmation.
- Use `plans-clear --plan-id ...` for exact saved-plan cleanup. Treat bulk cleanup flags as write-side-effect operations requiring confirmation.
- For long-lived WeChat, WorkBuddy, Claw, Hermes, or OpenClaw threads, stale compressed context can cause bad rewrites such as changing cloud detail into direct selection, or changing PT numbered downloads into detail review. When that happens, clear the current ARO session and saved plans, then reload this skill. Do not run session cleanup before ordinary search or update-check commands, because normal numbered follow-up depends on session continuity.

Long-thread cleanup example:

```bash
python3 scripts/aro_request.py session-clear --session default
python3 scripts/aro_request.py plans-clear --session default
```

## Preferences And Scoring

Before the first automated resource task in a new user profile, check preferences:

```bash
python3 scripts/aro_request.py preferences --session agent:<用户ID>
python3 scripts/aro_request.py templates --recipe preferences --compact
python3 scripts/aro_request.py scoring-policy
```

Most assistant responses also include compact `preference_status`. If `preference_status.needs_onboarding=true`, pause automation, ask the user for preferences, then save them before choosing downloads, unlocks, or transfers.

Search responses may include compact `score_summary`. Prefer `score_summary.best` and `score_summary.top_recommendations` over parsing the natural-language message. Treat `hard_risk_reasons` as blocking automation; treat `risk_reasons` as warnings to explain before asking for confirmation. If `score_level=confirm`, explain the reasons and ask the user before executing.

If `needs_onboarding=true`, ask the user for a compact preference profile and save it:

```bash
python3 scripts/aro_request.py preferences --session agent:<用户ID> --preferences-json '{"prefer_resolution":"4K","prefer_dolby_vision":true,"prefer_hdr":true,"prefer_chinese_subtitle":true,"prefer_complete_series":true,"prefer_cloud_provider":"115","pt_require_free":false,"pt_min_seeders":3,"hdhive_max_unlock_points":20,"p115_default_path":"/待整理","quark_default_path":"/飞书","auto_ingest_enabled":false,"auto_ingest_score_threshold":90}'
```

You may also manage preferences through the main natural-language route:

```bash
python3 scripts/aro_request.py route --text "偏好" --session agent:<用户ID>
python3 scripts/aro_request.py route --text "保存偏好 4K 杜比 HDR 中字 全集 做种>=3 影巢积分20 不自动入库" --session agent:<用户ID>
python3 scripts/aro_request.py route --text "重置偏好" --session agent:<用户ID>
```

Scoring rules are source-specific and plugin-owned. Use `scoring-policy` or `capabilities` to read the current policy when you need to explain the rules to the user. Do not invent a separate score in the agent.

- Cloud resources: HDHive, PanSou 115, PanSou Quark, direct 115/Quark links. Score quality, Dolby Vision/HDR, subtitles, completeness, file size, drive preference, and target directory. HDHive also checks point cost.
- PT resources: MoviePilot native site search/download/subscribe. Score seeders, free/promo status, volume factor, resolution, Dolby Vision/HDR, subtitles, release group/site, size, and title match.
- PT seeders are a hard gate. Default minimum is `3`; seeders `0` means never auto-download.
- HDHive point cost is a hard gate. Default max is `20`; unknown points cannot auto-unlock.
- Auto ingest is off by default. PT result-list numbers are an explicit user selection and download directly; explicit plan commands such as `下载1` / `下载最佳` still use the saved `plan_id` confirmation path.

For MP native workflows:

```bash
python3 scripts/aro_request.py workflow --workflow mp_search --keyword "蜘蛛侠"
python3 scripts/aro_request.py workflow --workflow mp_media_detail --keyword "蜘蛛侠"
python3 scripts/aro_request.py workflow mp_media_detail 蜘蛛侠
python3 scripts/aro_request.py workflow --workflow mp_search_best --keyword "蜘蛛侠"
python3 scripts/aro_request.py workflow --workflow mp_search_detail --keyword "蜘蛛侠" --choice 1
python3 scripts/aro_request.py workflow --workflow mp_search_download --keyword "蜘蛛侠" --choice 1
python3 scripts/aro_request.py workflow --workflow mp_download_history --keyword "蜘蛛侠" --limit 10
python3 scripts/aro_request.py workflow --workflow mp_lifecycle_status --keyword "蜘蛛侠" --limit 5
python3 scripts/aro_request.py workflow --workflow mp_ingest_status --keyword "蜘蛛侠"
python3 scripts/aro_request.py workflow --workflow mp_ingest_failures --keyword "蜘蛛侠" --limit 10
python3 scripts/aro_request.py workflow --workflow mp_recent_activity --limit 10
python3 scripts/aro_request.py workflow --workflow mp_local_diagnose --keyword "蜘蛛侠"
python3 scripts/aro_request.py workflow --workflow mp_subscribe --keyword "蜘蛛侠"
python3 scripts/aro_request.py workflow --workflow mp_transfer_history --keyword "蜘蛛侠" --status all --limit 10
python3 scripts/aro_request.py workflow --workflow mp_recommend --source tmdb_trending --media-type all --limit 20
python3 scripts/aro_request.py workflow --workflow mp_recommend_search --source tmdb_trending --media-type all --choice 1 --mode mp
python3 scripts/aro_request.py workflow --workflow mp_recommend_search --source tmdb_trending --media-type all --choice 1 --mode pansou
```

`mp_search_download`, `mp_subscribe`, and `mp_subscribe_and_search` are write-side-effect workflows. They should return a saved `plan_id` first; execute with `plan-execute` only after the user confirms.

`mp_transfer_history` is read-only. Use it after downloads or transfers to check whether MoviePilot has already organized the media into the library. Prefer the structured `items` fields and path previews; do not ask for full local paths unless the user explicitly needs troubleshooting detail.

`mp_download_history` is read-only. Use it before `mp_transfer_history` when the user asks whether a PT/native MP resource was ever submitted for download. It also reports a compact transfer status when the download hash can be linked to MoviePilot transfer history.

`mp_lifecycle_status` is read-only and should be the default troubleshooting query for “where is this resource now?”. It combines active download tasks, download history, and transfer/import history in one call.

`mp_ingest_status` is read-only and should be the shortest answer path for “has this PT/local resource entered the library yet?”. It returns a structured `diagnosis_summary` with `stage`, `confidence`, `evidence`, `risk_reasons`, `recommended_action`, and `follow_up_hint`.

`mp_ingest_failures` is read-only and focuses on transfer/import failures. Use it when the user asks “why did this fail to ingest?” or wants the recent failed records without reading the full transfer history.

`mp_recent_activity` is read-only and gives a quick view of recent downloads and recent ingest activity. Use it when there is no exact title yet and the user asks what MoviePilot did recently.

`mp_local_diagnose` is read-only and should be the one-stop path for “为什么没入库 / where is it stuck locally?”. Prefer it after `mp_ingest_status` or execution follow-up when the plugin already detected failure clues.

`mp_media_detail` is read-only. Use it before search/download/subscribe when the title is ambiguous or the agent needs to confirm MoviePilot's native media recognition, TMDB/Douban/IMDB IDs, year, and media type.

Normal chat PT result lists do not expose a detail option: plain numbers download directly, and `下载N` generates a pending plan. Do not offer `mp_search_detail` as the next step for ordinary users; reserve low-level PT detail inspection for explicit diagnostic/debug use.

`mp_search_best` is read-only and token-efficient. Use it when the user asks the agent to recommend the best PT candidate after MP native search. It searches, ranks by the plugin-owned score, and returns the best candidate detail. It still does not download.

After an MP search session, `下载最佳` generates a saved download plan for the current highest-scoring PT candidate. It does not download immediately; after user confirmation, execute the returned `plan_id` with `plan-execute`, route the natural text `执行计划` / `执行 plan-...`, or route the same resource number again when the plugin prompt says that number can confirm the pending plan. Then prefer `followup` so the plugin itself can decide whether the best next read is download history, lifecycle, subscribes, or transfer history.

For explicit PT plan commands such as `下载1` or `下载最佳`, keep the `plan_id` confirmation flow. For ordinary PT result lists, a plain number is the direct download action. Treat `can_auto_execute` as a score signal for explanation only.

For cloud-drive result sessions, `最佳片源` is read-only. It returns the highest-scoring PanSou or HDHive resource detail and must not transfer or unlock by itself. `选择 N 详情` is also read-only. For ordinary `搜索/找 <片名>` sessions, prefer direct numbered picks first and use `计划选择 N` only when the user explicitly wants a saved confirmation plan. Use direct `选择 N` for immediate transfer/unlock after the user confirms that intent.

For ordinary `搜索/找 <片名>` sessions, relay the plugin's original numbered list and next-step hints first. You may add a smart recommendation after the list, including a shortlist or tradeoff explanation, but do not replace, renumber, or hide the original list body.

`mp_recommend_search` is the low-token recommendation chain. Without `choice`, it returns a recommendation list and stores the session. With `choice`, it immediately continues the selected title into `mode=mp`, `mode=hdhive`, or `mode=pansou`.

After a recommendation list, natural-language picks are valid:

```text
选择 1
计划选择 1
选择 1 盘搜
选择1影巢
选 2 mp
```

After an MP native search result, natural-language write commands are valid. They still follow the plugin's confirmation/plan rules:

```text
下载1
下载第1个
订阅蜘蛛侠
订阅并搜索蜘蛛侠
```

Download task management also uses the same route. Querying tasks is read-only. Pausing, resuming, and deleting tasks are write actions and should return a saved `plan_id` first:

```text
下载任务
记录
记录 蜘蛛侠
状态 蜘蛛侠
入库 蜘蛛侠
整理失败 蜘蛛侠
最近
最近下载
诊断 蜘蛛侠
后续
跟进
跟进 蜘蛛侠
识别 蜘蛛侠
选择 1
最佳片源
下载最佳
暂停下载 1
恢复下载 1
删除下载 1
```

PT environment diagnostics are read-only and safe. Site results are sanitized and must not expose cookies:

```text
站点状态
下载器状态
```

MP subscription management follows the same rule. Querying subscriptions is read-only; searching, pausing, resuming, and deleting subscriptions are write actions and should return a saved `plan_id` first:

```text
订阅列表
搜索订阅 1
暂停订阅 1
恢复订阅 1
删除订阅 1
```

Transfer/import history is read-only and safe. Use it to answer “did this land in the library?”:

```text
入库历史
入库失败 蜘蛛侠
整理成功 地狱乐
```

Natural-language route examples that should call recommendations:

```text
看看最近有什么热门影视
热门电影
豆瓣热门电影
正在热映
今日番剧
```

## Confirmation Rules

Do not execute confirmation-required calls silently.

If `recommended_recipe_detail.confirmation_message` says a step needs confirmation, show that message to the user before executing that step.

Common confirmation points:

- `saved_plan_execute`
- `maintain_execute`
- `pick_continue`
- `mp_search_download`
- `mp_subscribe`
- `mp_subscribe_and_search`

## Maintenance And Health

Use selfcheck for protocol health:

```bash
python3 scripts/aro_request.py selfcheck
```

Preview maintenance without writing:

```bash
python3 scripts/aro_request.py maintain
```

Execute maintenance only after confirmation:

```bash
python3 scripts/aro_request.py maintain --execute
```

## Guardrails

- Do not call HDHive, 115, Quark, or PanSou raw APIs directly when `AgentResourceOfficer` can handle the workflow.
- Do not unlock paid resources or execute write-side-effect calls without explicit confirmation.
- Respect `hdhive_resource_enabled` and `hdhive_max_unlock_points` returned by readiness/capabilities. The default point limit is 20. If a HDHive resource is above the limit or the plugin cannot confirm its points, tell the user the exact point cost/risk and ask them to raise the limit or set it to 0 before retrying. Do not bypass the guardrail.
- Prefer `include_templates=false` for low token startup.
- Use full templates only when parameters are unclear.
- Keep user-facing output short: show options, ask for a number, report result.

## Relationship To MoviePilot-Skill

`MoviePilot-Skill` is useful for MP native API operations such as subscriptions, downloads, sites, storage, and dashboard data.

This skill is for the resource workflow hub:

- HDHive search and unlock
- PanSou search
- 115 and Quark share routing
- MP native search/download/subscribe/recommendation orchestration
- cloud/PT scoring and preference-aware automation advice
- 115 login/status/pending tasks
- session recovery
- recipe-guided assistant calls

Use both together when needed, but keep their auth modes separate:

- AgentResourceOfficer plugin endpoints: `?apikey=MP_API_TOKEN`
- MP native API skill: usually `X-API-KEY`
