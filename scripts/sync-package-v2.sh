#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

show_help() {
  cat <<'EOF'
Usage:
  bash scripts/sync-package-v2.sh

Syncs package.v2.json from package.json by dropping per-plugin "v2" flags
and keeping the current plugin metadata layout used by the repository.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  show_help
  exit 0
fi

python3 - <<'PY'
import json
from pathlib import Path

package_path = Path("package.json")
package_v2_path = Path("package.v2.json")

package = json.loads(package_path.read_text(encoding="utf-8"))
package_v2 = {
    plugin_id: {key: value for key, value in meta.items() if key != "v2"}
    for plugin_id, meta in package.items()
}

package_v2_path.write_text(
    json.dumps(package_v2, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(f"已同步 {package_v2_path}")
PY
