---
name: agent-resource-officer
description: Control AgentResourceOfficer, the MoviePilot cloud-drive resource workflow hub, from an external agent. Use when an agent should route natural-language 115/Quark cloud-drive resource requests, inspect startup/recovery state, fetch low-token request templates by recipe, continue numbered choices, or execute saved plans through AgentResourceOfficer instead of calling HDHive, 115, Quark, or PanSou APIs directly.
---

# AgentResourceOfficer Skill

Use this skill when the user wants an external agent to operate the MoviePilot 115/Quark cloud-drive resource workflow through `AgentResourceOfficer`.

The plugin is the capability layer. The agent should orchestrate, display choices, ask for confirmation when required, and call the stable assistant endpoints.

## Configuration

Public repository:

```text
https://github.com/liuyuexi1987/MoviePilot-Plugins
```

To reproduce this skill on another machine, clone the repository and install the bundled skill:

```bash
git clone https://github.com/liuyuexi1987/MoviePilot-Plugins.git
cd MoviePilot-Plugins
bash skills/agent-resource-officer/install.sh --dry-run
bash skills/agent-resource-officer/install.sh
```

Preferred local config:

```text
~/.config/agent-resource-officer/config
```

Format:

```text
ARO_BASE_URL=http://127.0.0.1:3000
ARO_API_KEY=your_moviepilot_api_token
```

Set `ARO_BASE_URL` to the MoviePilot address reachable from the machine running the external agent. Use `http://127.0.0.1:3000` only when MoviePilot is on the same machine.

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

You can still override them with `ARO_HDHIVE_COOKIE_EXPORT_DIR` and `ARO_QUARK_COOKIE_EXPORT_DIR`.

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
```

`external-agent` prints the compact prompt and minimal tool contract. `external-agent --full` prints the full bundled handoff guide. `workbuddy` remains a compatibility alias only; new integrations should use `external-agent`.

When a user says plain `搜索 <片名>` or `找 <片名>`, pass that text through to `route` first. Do not guess that the user meant HDHive, and do not continue an old result session by sending `选择 1` unless the user actually chose an item in the current round. Default plain search should start from PanSou.

When a user says `转存 <片名>`, route that text directly first. Treat it as a cloud-transfer intent: prefer PanSou + HDHive, and let AgentResourceOfficer execute the one-stop transfer flow instead of rewriting it into a PT download request.

When a user says `下载 <片名>`, route that text directly first. Treat it as an MP/PT direct-download intent: prefer MoviePilot native PT search/download, and do not silently rewrite it into a cloud-drive transfer request.

When a user says `云盘搜索 <片名>`, route that exact text first. Do not silently replace it with `盘搜搜索 <片名>`. Cloud search is a distinct entry that should compare PanSou and HDHive together; if HDHive stays ambiguous, preserve the plugin's own `影巢结果` hint instead of collapsing everything into a PanSou-only recommendation.

When a user says `更新 <片名>`, `更新检查 <片名>`, `查更新 <片名>`, or `检查 <片名>`, route that text directly first and treat it as the update-check entry. Do not clear the session first, do not guess that the user meant HDHive candidate search, and do not replace it with a generic search flow. The update flow should first show official reference progress plus PanSou and HDHive latest-episode resources, then let the user choose a numbered resource if needed.

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

For ordinary search, cloud search, HDHive resource lists, and update-check lists, preserve the plugin's original numbering exactly. Do not reformat a numbered resource list into unnumbered prose, do not collapse numbered items into a separate summary, and do not move the actionable numbers only into a later recommendation paragraph.

For cloud search results, prefer the plugin's raw combined layout: keep the `盘搜结果` section, keep the `影巢结果` section, and keep raw links when the plugin returned them. Do not rewrite the answer into a guide like “最佳选择/推荐资源/分析结论/要不要我帮你下载”, and do not hide the source-specific sections behind your own summary.

For cloud search, never renumber items per source in your own prose. If the plugin returned global numbering like `1..16` plus `17..24`, preserve that exact numbering. Do not convert it into separate `115 1..6 / 夸克 1..10` local indices, and do not collapse the response into a custom “标题/画质/日期/链接” table that drops the plugin's next-step instructions.

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
- Auto ingest is off by default. Even when `can_auto_execute=true`, the current PT interaction policy should still prefer `plan_id` first unless an internal system path explicitly executes the saved plan.

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

`mp_search_detail` is read-only. Use it after or together with MP native search when the user wants to inspect a numbered PT candidate. It shows seeders, promotion, size, score reasons, and risks. Do not download from this detail step; ask for confirmation or generate a plan before downloading.

`mp_search_best` is read-only and token-efficient. Use it when the user asks the agent to recommend the best PT candidate after MP native search. It searches, ranks by the plugin-owned score, and returns the best candidate detail. It still does not download.

After an MP search session, `下载最佳` generates a saved download plan for the current highest-scoring PT candidate. It does not download immediately; after user confirmation, execute the returned `plan_id` with `plan-execute` or route the natural text `执行计划` / `执行 plan-...`. Then prefer `followup` so the plugin itself can decide whether the best next read is download history, lifecycle, subscribes, or transfer history.

Even if a PT candidate scores high, the current default interaction policy is still `plan_id` first. Treat `can_auto_execute` as a score signal for explanation only; do not assume `下载1` or `下载最佳` will bypass confirmation.

For cloud-drive result sessions, `最佳片源` is read-only. It returns the highest-scoring PanSou or HDHive resource detail and must not transfer or unlock by itself. `选择 N 详情` is also read-only. For ordinary `搜索/找 <片名>` sessions, prefer direct numbered picks first and use `计划选择 N` only when the user explicitly wants a saved confirmation plan. Use direct `选择 N` for immediate transfer/unlock after the user confirms that intent.

For ordinary `搜索/找 <片名>` sessions, do not re-summarize the returned list into your own “resource status”, “recommended shortlist”, “费用/评分/推荐星级”, or “要现在下载吗？” style output. Prefer relaying the plugin's original numbered list and next-step hints. If you must add one short sentence, keep it to a plain observation such as “夸克前几条已经更新到 E08” and do not replace the original list body.

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
