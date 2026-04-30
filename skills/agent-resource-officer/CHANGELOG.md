# agent-resource-officer changelog

## 0.1.24

- Added positional argument support for `workflow`, so `python3 scripts/aro_request.py workflow mp_media_detail 蜘蛛侠` works without `--workflow` and `--keyword`.
- Added positional session support for `session`, `session-clear`, and `history`, so `python3 scripts/aro_request.py session default` and `python3 scripts/aro_request.py history agent:demo` work without `--session`.
- Added positional `plan-xxx` support for `plans` and `plans-clear`.

## 0.1.23

- Added positional argument support for `pick`, so `python3 scripts/aro_request.py pick 1` and `python3 scripts/aro_request.py pick 1 详情` work without `--choice` or `--action`.
- Added positional plan support for `plan-execute`, so `python3 scripts/aro_request.py plan-execute plan-xxx` works without `--plan-id`.
- Updated the external-agent handoff payload to prefer the shorter positional `pick` command.

## 0.1.22

- Added positional text support for `route`, so `python3 scripts/aro_request.py route "盘搜搜索 大君夫人"` works without `--text`.
- Kept the old `--text` form for compatibility.

## 0.1.21

- Added direct `--command-only` helper output for the `mp_pt` and `recommend` recipes.
- Changed recipe command selection to execute the first safe read step directly even when later recipe steps require confirmation.

## 0.1.20

- Added `mp_pt_recipe_command` and `mp_recommend_recipe_command` to the external-agent handoff payload.
- Documented `mp_pt` and `recommend` request-template recipes for MP native PT and recommendation flows.

## 0.1.19

- Added workflow helper flags for MP download task management: `--status`, `--hash`, `--target`, `--control`, `--downloader`, and `--delete-files`.
- Added examples for querying, pausing, resuming, and deleting MP download tasks through AgentResourceOfficer.

## 0.1.18

- Added `--mode` to the workflow helper so `mp_recommend_search` can continue a recommended title into MP, HDHive, or PanSou.
- Documented the recommendation-to-search chain for external agents.

## 0.1.17

- Changed HDHive search helper default to `media_type=auto`, so uncertain titles are not filtered as movies before TV candidates can be found.

## 0.1.16

- Added `scoring-policy` helper command so external agents can explain plugin-owned scoring rules without re-scoring.

## 0.1.15

- Documented compact `score_summary` for choosing scored cloud/PT results without parsing long messages.

## 0.1.14

- Added compact `preference_status` to assistant responses so external agents can detect onboarding without a separate verbose call.

## 0.1.13

- Added `preferences` helper command to read, save, or reset source preferences for external agents.
- Documented cloud/PT source-specific scoring and MP native search/download/subscribe/recommend workflows.
- Updated the external-agent handoff prompt to check preferences before automated resource tasks.
- Changed `workflow` helper behavior so read-only workflows execute directly while write workflows still generate a dry-run plan by default.

## 0.1.12

- Added `external-agent` helper command to print a compact external-agent prompt and minimal tool contract.
- Added `external-agent --full` to print the bundled external-agent handoff guide directly from the Skill package.
- Kept `workbuddy` as a compatibility alias for existing setups.

## 0.1.11

- Compact output now preserves Feishu migration fields such as `ready_to_start`, `safe_to_enable`, `missing_requirements`, and `migration_hint`.

## 0.1.10

- Compact output now preserves service health fields, warnings, defaults, and Quark/P115 readiness fields for lower-token diagnostics.

## 0.1.9

- Added `session-clear` and `sessions-clear` helper commands so agents can clear abandoned assistant sessions and pending 115 recovery state.

## 0.1.8

- Added `--compact` as a compatibility no-op because compact output is already the default.

## 0.1.7

- Compact `feishu-health` output now preserves key status fields such as `plugin_version`, `running`, `legacy_bridge_running`, and `conflict_warning`.

## 0.1.6

- Added `feishu-health` for checking the built-in AgentResourceOfficer Feishu Channel status.
- Documented the matching MoviePilot Agent Tool `agent_resource_officer_feishu_health`.

## 0.1.5

- Expanded local `selftest` coverage for maintain command generation and request-template summary parsing.

## 0.1.4

- `maintain` preview now sends a clean GET dry-run request without `execute=true`.

## 0.1.3

- Bumped helper script to `0.1.3`.
- Added `plans-clear` for exact saved-plan cleanup and bulk cleanup filters.

## 0.1.2

- Bumped helper script to `0.1.2`.
- Added `--plan-id` support for exact `plans` inspection and `plan-execute`.
- Recovery helper commands now preserve `plan_id` when the plugin recommends executing a saved plan.
- Compact helper output now preserves `plan_id` and `execute_plan_body` from dry-run workflow responses.

## 0.1.1

- Bumped helper script to `0.1.1`.
- Completed the `commands` catalog so every helper subcommand is represented.
- Marked `workflow` as a dry-run plan write in the command catalog.
- Added `version` command and `helper_version` in command catalog/readiness output.

## 0.1.0

- Added `install.sh` with dry-run and custom target support for installing the skill into configurable skill paths.
- Added installer target guards to prevent accidental overwrites of unsafe or non-skill directories.
- Added `commands` catalog with stable `commands.v1` schema.
- Added `readiness` for config, local selftest, and live plugin selfcheck.
- Added `config-check` without printing secrets or expanded local paths.
- Added `selftest` for helper command-generation logic.
- Added low-token decision helpers:
  - `decide --summary-only`
  - `doctor --summary-only`
  - `auto --summary-only`
  - `recover --summary-only`
- Added `--command-only` and `--confirmed` for safer machine execution.
