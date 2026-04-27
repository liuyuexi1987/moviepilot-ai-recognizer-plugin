#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

python3 - <<'PY'
from hashlib import sha256
import json
from pathlib import Path

dist_dir = Path("dist")
package = json.loads(Path("package.json").read_text(encoding="utf-8"))
zip_files = sorted(dist_dir.glob("*.zip"))
if not zip_files:
    print("dist 目录没有生成 ZIP 文件")
    raise SystemExit(1)

lines = []
plugins = []
for zip_file in zip_files:
    plugin_id = zip_file.name.rsplit("-", 1)[0]
    meta = package.get(plugin_id) or {}
    digest = sha256(zip_file.read_bytes()).hexdigest()
    lines.append(f"{digest}  {zip_file.name}")
    plugins.append(
        {
            "id": plugin_id,
            "name": meta.get("name") or plugin_id,
            "version": meta.get("version") or "unknown",
            "zip": zip_file.name,
            "sha256": digest,
            "size": zip_file.stat().st_size,
        }
    )
(dist_dir / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
(dist_dir / "MANIFEST.json").write_text(
    json.dumps({"plugins": plugins}, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(f"sha256_manifest_ok files={len(zip_files)}")
PY
