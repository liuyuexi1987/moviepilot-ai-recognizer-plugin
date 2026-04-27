#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

python3 - <<'PY'
from hashlib import sha256
from pathlib import Path

dist_dir = Path("dist")
zip_files = sorted(dist_dir.glob("*.zip"))
if not zip_files:
    print("dist 目录没有生成 ZIP 文件")
    raise SystemExit(1)

lines = [
    f"{sha256(zip_file.read_bytes()).hexdigest()}  {zip_file.name}"
    for zip_file in zip_files
]
(dist_dir / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"sha256_manifest_ok files={len(zip_files)}")
PY
