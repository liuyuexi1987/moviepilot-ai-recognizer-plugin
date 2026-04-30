#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "warning: scripts/verify-ci-artifact.sh 已弃用，请改用 scripts/verify-release-preflight-artifact.sh" >&2
exec bash scripts/verify-release-preflight-artifact.sh "$@"
