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

Never print API keys, cookies, or tokens back to the user.

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

Use `config-check` to verify connection settings without printing secrets:

```bash
python3 scripts/aro_request.py config-check
```

Use `readiness` after configuration to run config check, local selftest, and live plugin selfcheck together:

```bash
python3 scripts/aro_request.py readiness
```

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
- `mp_pt` / `mp` / `pt` -> `mp_pt_mainline`
- `recommend` / `热门` / `推荐` -> `mp_recommendation`

Use:

```bash
python3 scripts/aro_request.py templates --recipe plan --policy-only
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

`mp_media_detail` is read-only. Use it before search/download/subscribe when the title is ambiguous or the agent needs to confirm MoviePilot's native media recognition, TMDB/Douban/IMDB IDs, year, and media type.

`mp_search_detail` is read-only. Use it after or together with MP native search when the user wants to inspect a numbered PT candidate. It shows seeders, promotion, size, score reasons, and risks. Do not download from this detail step; ask for confirmation or generate a plan before downloading.

`mp_search_best` is read-only and token-efficient. Use it when the user asks the agent to recommend the best PT candidate after MP native search. It searches, ranks by the plugin-owned score, and returns the best candidate detail. It still does not download.

After an MP search session, `下载最佳` generates a saved download plan for the current highest-scoring PT candidate. It does not download immediately; after user confirmation, execute the returned `plan_id` with `plan-execute` or route the natural text `执行计划` / `执行 plan-...`. Then prefer `followup` so the plugin itself can decide whether the best next read is download history, lifecycle, subscribes, or transfer history.

Even if a PT candidate scores high, the current default interaction policy is still `plan_id` first. Treat `can_auto_execute` as a score signal for explanation only; do not assume `下载1` or `下载最佳` will bypass confirmation.

For cloud-drive result sessions, `最佳片源` is read-only. It returns the highest-scoring PanSou or HDHive resource detail and must not transfer or unlock by itself. `选择 N 详情` is also read-only. Prefer `计划选择 N` for PanSou transfer or HDHive unlock when an external agent is acting for the user; it returns a saved `plan_id` and performs no write action until the plan is executed. Use direct `选择 N` only after the user explicitly confirms immediate transfer/unlock.

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
下载历史
下载历史 蜘蛛侠
追踪 蜘蛛侠
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
