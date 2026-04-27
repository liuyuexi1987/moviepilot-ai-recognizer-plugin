# agent-resource-officer changelog

## 0.1.0

- Bumped helper script to `0.1.1`.
- Completed the `commands` catalog so every helper subcommand is represented.
- Marked `workflow` as a dry-run plan write in the command catalog.
- Added `version` command and `helper_version` in command catalog/readiness output.
- Added `install.sh` with dry-run and custom target support for installing the skill into Codex skill paths.
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
