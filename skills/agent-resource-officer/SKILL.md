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
python3 scripts/aro_request.py session-clear --session default
python3 scripts/aro_request.py sessions-clear --has-pending-p115 --limit 10
python3 scripts/aro_request.py templates --recipe bootstrap
python3 scripts/aro_request.py route --text "盘搜搜索 大君夫人"
python3 scripts/aro_request.py pick --choice 1
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

`--command-only` prints an inspect command when the next action requires confirmation. Add `--confirmed` only after the user has approved the write-side-effect step.

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

Use:

```bash
python3 scripts/aro_request.py templates --recipe plan --policy-only
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

For numbered continuation, use `pick`:

```bash
python3 scripts/aro_request.py pick --choice 1
python3 scripts/aro_request.py pick --choice 11 --path /飞书
python3 scripts/aro_request.py pick --action 详情
python3 scripts/aro_request.py pick --action 下一页
```

For session inspection and recovery:

```bash
python3 scripts/aro_request.py sessions
python3 scripts/aro_request.py session --session default
python3 scripts/aro_request.py session-clear --session default
python3 scripts/aro_request.py sessions-clear --has-pending-p115 --limit 10
python3 scripts/aro_request.py recover
python3 scripts/aro_request.py recover --execute
python3 scripts/aro_request.py history --limit 10
python3 scripts/aro_request.py plans --limit 10
python3 scripts/aro_request.py plans --plan-id plan-xxx
python3 scripts/aro_request.py plans --executed --include-actions --limit 5
python3 scripts/aro_request.py plan-execute --plan-id plan-xxx
python3 scripts/aro_request.py plans-clear --plan-id plan-xxx
```

Notes:

- `sessions`, `history`, `plans`, and `recover` no longer force `session=default` when you do not pass `--session`.
- Use `--session` or `--session-id` only when you want to narrow to one conversation.
- Use `sessions --kind ...` or `sessions --has-pending-p115` when you want recovery-oriented filtering.
- Use `session-clear` or `sessions-clear` to clear abandoned assistant state after user confirmation.
- Use `plans-clear --plan-id ...` for exact saved-plan cleanup. Treat bulk cleanup flags as write-side-effect operations requiring confirmation.

## Preferences And Scoring

Before the first automated resource task in a new user profile, check preferences:

```bash
python3 scripts/aro_request.py preferences --session agent:<用户ID>
```

Most assistant responses also include compact `preference_status`. If `preference_status.needs_onboarding=true`, pause automation, ask the user for preferences, then save them before choosing downloads, unlocks, or transfers.

If `needs_onboarding=true`, ask the user for a compact preference profile and save it:

```bash
python3 scripts/aro_request.py preferences --session agent:<用户ID> --preferences-json '{"prefer_resolution":"4K","prefer_dolby_vision":true,"prefer_hdr":true,"prefer_chinese_subtitle":true,"prefer_complete_series":true,"prefer_cloud_provider":"115","pt_require_free":false,"pt_min_seeders":3,"hdhive_max_unlock_points":20,"p115_default_path":"/待整理","quark_default_path":"/飞书","auto_ingest_enabled":false,"auto_ingest_score_threshold":90}'
```

Scoring rules are source-specific:

- Cloud resources: HDHive, PanSou 115, PanSou Quark, direct 115/Quark links. Score quality, Dolby Vision/HDR, subtitles, completeness, file size, drive preference, and target directory. HDHive also checks point cost.
- PT resources: MoviePilot native site search/download/subscribe. Score seeders, free/promo status, volume factor, resolution, Dolby Vision/HDR, subtitles, release group/site, size, and title match.
- PT seeders are a hard gate. Default minimum is `3`; seeders `0` means never auto-download.
- HDHive point cost is a hard gate. Default max is `20`; unknown points cannot auto-unlock.
- Auto ingest is off by default. Only auto-execute when `auto_ingest_enabled=true`, `score >= 90`, and there are no hard risks.

For MP native workflows:

```bash
python3 scripts/aro_request.py workflow --workflow mp_search --keyword "蜘蛛侠"
python3 scripts/aro_request.py workflow --workflow mp_search_download --keyword "蜘蛛侠" --choice 1
python3 scripts/aro_request.py workflow --workflow mp_subscribe --keyword "蜘蛛侠"
python3 scripts/aro_request.py workflow --workflow mp_recommend --source tmdb_trending --media-type all --limit 20
```

`mp_search_download`, `mp_subscribe`, and `mp_subscribe_and_search` are write-side-effect workflows. They should return a saved `plan_id` first; execute with `plan-execute` only after the user confirms.

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
