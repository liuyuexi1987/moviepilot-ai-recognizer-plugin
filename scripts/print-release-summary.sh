#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

python3 - <<'PY'
import json
from pathlib import Path

manifest_file = Path("dist/MANIFEST.json")
if not manifest_file.exists():
    print("dist/MANIFEST.json 不存在，请先运行 bash scripts/package-plugin.sh --all")
    raise SystemExit(1)

manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
plugins = manifest.get("plugins")
if not isinstance(plugins, list) or not plugins:
    print("dist/MANIFEST.json 缺少 plugins 列表")
    raise SystemExit(1)

print("## MoviePilot 插件 ZIP")
print()
print("| Plugin | Name | Version | ZIP | Size | SHA256 |")
print("| --- | --- | --- | --- | ---: | --- |")
for item in plugins:
    size_kib = int(round(int(item.get("size") or 0) / 1024))
    print(
        "| {id} | {name} | {version} | {zip} | {size_kib} KiB | `{sha256}` |".format(
            id=item.get("id", ""),
            name=item.get("name", ""),
            version=item.get("version", ""),
            zip=item.get("zip", ""),
            size_kib=size_kib,
            sha256=item.get("sha256", ""),
        )
    )
PY
