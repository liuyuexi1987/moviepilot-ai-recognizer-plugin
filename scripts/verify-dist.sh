#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

python3 - <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import zipfile

dist_dir = Path("dist")
manifest = dist_dir / "SHA256SUMS.txt"
json_manifest = dist_dir / "MANIFEST.json"
if not dist_dir.exists():
    print("dist 目录不存在")
    raise SystemExit(1)
if not manifest.exists():
    print("dist/SHA256SUMS.txt 不存在")
    raise SystemExit(1)
if not json_manifest.exists():
    print("dist/MANIFEST.json 不存在")
    raise SystemExit(1)

zip_files = sorted(dist_dir.glob("*.zip"))
if not zip_files:
    print("dist 目录没有 ZIP 文件")
    raise SystemExit(1)

expected = {}
for line in manifest.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    try:
        digest, filename = line.split(None, 1)
    except ValueError:
        print(f"SHA256SUMS.txt 行格式错误: {line}")
        raise SystemExit(1)
    expected[filename.strip()] = digest.strip()

zip_names = {path.name for path in zip_files}
manifest_names = set(expected)
missing = sorted(zip_names - manifest_names)
extra = sorted(manifest_names - zip_names)
if missing or extra:
    if missing:
        print("SHA256SUMS.txt 缺少 ZIP:")
        print("\n".join(missing))
    if extra:
        print("SHA256SUMS.txt 包含不存在的 ZIP:")
        print("\n".join(extra))
    raise SystemExit(1)

manifest_data = json.loads(json_manifest.read_text(encoding="utf-8"))
manifest_plugins = manifest_data.get("plugins")
if not isinstance(manifest_plugins, list):
    print("MANIFEST.json 缺少 plugins 列表")
    raise SystemExit(1)
manifest_by_zip = {}
for item in manifest_plugins:
    if not isinstance(item, dict) or not item.get("zip"):
        print("MANIFEST.json 插件条目格式错误")
        raise SystemExit(1)
    manifest_by_zip[item["zip"]] = item
missing_json = sorted(zip_names - set(manifest_by_zip))
extra_json = sorted(set(manifest_by_zip) - zip_names)
if missing_json or extra_json:
    if missing_json:
        print("MANIFEST.json 缺少 ZIP:")
        print("\n".join(missing_json))
    if extra_json:
        print("MANIFEST.json 包含不存在的 ZIP:")
        print("\n".join(extra_json))
    raise SystemExit(1)

for zip_file in zip_files:
    actual = sha256(zip_file.read_bytes()).hexdigest()
    if expected[zip_file.name] != actual:
        print(f"{zip_file} SHA256 不匹配")
        raise SystemExit(1)
    manifest_item = manifest_by_zip[zip_file.name]
    if manifest_item.get("sha256") != actual:
        print(f"{zip_file} MANIFEST.json SHA256 不匹配")
        raise SystemExit(1)
    if manifest_item.get("size") != zip_file.stat().st_size:
        print(f"{zip_file} MANIFEST.json size 不匹配")
        raise SystemExit(1)
    plugin_name = zip_file.name.rsplit("-", 1)[0]
    required_readme = f"{plugin_name}/README.md"
    required_init = f"{plugin_name}/__init__.py"
    with zipfile.ZipFile(zip_file) as zip_obj:
        names = set(zip_obj.namelist())
        bad_entries = [
            name
            for name in names
            if "__pycache__" in name or name.endswith((".pyc", ".pyo", ".DS_Store"))
        ]
    if required_readme not in names:
        print(f"{zip_file} 缺少 {required_readme}")
        raise SystemExit(1)
    if required_init not in names:
        print(f"{zip_file} 缺少 {required_init}")
        raise SystemExit(1)
    if bad_entries:
        print(f"{zip_file} 包含不应发布的生成文件:")
        print("\n".join(sorted(bad_entries)))
        raise SystemExit(1)

print(f"dist_verify_ok files={len(zip_files)}")
PY
