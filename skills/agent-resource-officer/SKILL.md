---
name: agent-resource-officer
description: Control AgentResourceOfficer, the MoviePilot resource workflow hub, from an external agent. Use when an agent should route natural-language resource requests, inspect startup/recovery state, fetch low-token request templates by recipe, continue numbered choices, or execute saved plans through AgentResourceOfficer instead of calling HDHive, 115, Quark, or PanSou APIs directly.
---

# AgentResourceOfficer Skill

Use this skill when the user wants an external agent to operate the MoviePilot resource workflow through `AgentResourceOfficer`.

The plugin is the capability layer. The agent should orchestrate, display choices, ask for confirmation when required, and call the stable assistant endpoints.

## Configuration

Preferred local config:

```text
~/.config/agent-resource-officer/config
```

Format:

```text
ARO_BASE_URL=http://127.0.0.1:3000
ARO_API_KEY=your_moviepilot_api_token
```

Environment overrides:

- `ARO_BASE_URL`
- `MP_BASE_URL`
- `MOVIEPILOT_URL`
- `ARO_API_KEY`
- `MP_API_TOKEN`

Never print API keys, cookies, or tokens back to the user.

## Request Helper

Prefer the bundled helper:

```bash
python3 scripts/aro_request.py startup
python3 scripts/aro_request.py auto
python3 scripts/aro_request.py doctor --limit 5
python3 scripts/aro_request.py selfcheck
python3 scripts/aro_request.py sessions
python3 scripts/aro_request.py sessions --kind assistant_hdhive --limit 5
python3 scripts/aro_request.py templates --recipe bootstrap
python3 scripts/aro_request.py route --text "盘搜搜索 大君夫人"
python3 scripts/aro_request.py pick --choice 1
```

The helper uses `?apikey=...`, which is the recommended HTTP auth mode for plugin assistant endpoints.

## Core Startup Flow

Fast path:

```bash
python3 scripts/aro_request.py auto
python3 scripts/aro_request.py doctor --limit 5
```

`auto` calls `startup`, reads `recommended_request_templates`, then fetches the recommended low-token recipe.

`doctor` is the read-only diagnostic entry. It combines:

- `assistant/startup`
- `assistant/selfcheck`
- `assistant/sessions`
- `assistant/recover`

Use it when an external agent needs one compact bootstrap/health/recovery snapshot before deciding whether to start a new task or continue an old one.

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
python3 scripts/aro_request.py recover
python3 scripts/aro_request.py recover --execute
python3 scripts/aro_request.py history --limit 10
python3 scripts/aro_request.py plans --limit 10
python3 scripts/aro_request.py plans --executed --include-actions --limit 5
```

Notes:

- `sessions`, `history`, `plans`, and `recover` no longer force `session=default` when you do not pass `--session`.
- Use `--session` or `--session-id` only when you want to narrow to one conversation.
- Use `sessions --kind ...` or `sessions --has-pending-p115` when you want recovery-oriented filtering.

## Confirmation Rules

Do not execute confirmation-required calls silently.

If `recommended_recipe_detail.confirmation_message` says a step needs confirmation, show that message to the user before executing that step.

Common confirmation points:

- `saved_plan_execute`
- `maintain_execute`
- `pick_continue`

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
- Prefer `include_templates=false` for low token startup.
- Use full templates only when parameters are unclear.
- Keep user-facing output short: show options, ask for a number, report result.

## Relationship To MoviePilot-Skill

`MoviePilot-Skill` is useful for MP native API operations such as subscriptions, downloads, sites, storage, and dashboard data.

This skill is for the resource workflow hub:

- HDHive search and unlock
- PanSou search
- 115 and Quark share routing
- 115 login/status/pending tasks
- session recovery
- recipe-guided assistant calls

Use both together when needed, but keep their auth modes separate:

- AgentResourceOfficer plugin endpoints: `?apikey=MP_API_TOKEN`
- MP native API skill: usually `X-API-KEY`
