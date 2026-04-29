# agent-resource-officer changelog

## 0.1.13

- Added `preferences` helper command to read, save, or reset source preferences for external agents.
- Documented cloud/PT source-specific scoring and MP native search/download/subscribe/recommend workflows.
- Updated the external-agent handoff prompt to check preferences before automated resource tasks.

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
