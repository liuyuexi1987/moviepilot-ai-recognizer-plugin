#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist/skills"
cd "$ROOT_DIR"
export PYTHONDONTWRITEBYTECODE=1

show_help() {
  cat <<'EOF'
Usage:
  bash scripts/package-skills.sh
  bash scripts/package-skills.sh --help

Packages public Codex Skill templates into dist/skills.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  show_help
  exit 0
fi

if [[ "$#" -gt 0 ]]; then
  echo "Unknown argument: $1" >&2
  show_help >&2
  exit 2
fi

if ! command -v zip >/dev/null 2>&1; then
  echo "未找到 zip 命令，请先安装 zip。" >&2
  exit 1
fi

bash scripts/check-skills.sh >/dev/null

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

python3 - <<'PY' | while IFS=$'\t' read -r skill_name helper_file; do
import ast
from pathlib import Path


def has_helper_version(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "HELPER_VERSION":
                return True
    return False


for skill_dir in sorted(path for path in Path("skills").iterdir() if path.is_dir()):
    scripts_dir = skill_dir / "scripts"
    helper_files = []
    if scripts_dir.exists():
        helper_files = sorted(path for path in scripts_dir.glob("*.py") if has_helper_version(path))
    if len(helper_files) != 1:
        print(f"{skill_dir} 必须且只能有一个包含 HELPER_VERSION 的 helper 脚本", flush=True)
        raise SystemExit(1)
    print(f"{skill_dir.name}\t{helper_files[0]}")
PY
  version="$(HELPER_FILE="$helper_file" python3 - <<'PY'
import ast
import os
from pathlib import Path

tree = ast.parse(Path(os.environ["HELPER_FILE"]).read_text(encoding="utf-8"))
for node in ast.walk(tree):
    if not isinstance(node, ast.Assign):
        continue
    for target in node.targets:
        if isinstance(target, ast.Name) and target.id == "HELPER_VERSION" and isinstance(node.value, ast.Constant):
            print(str(node.value.value))
            raise SystemExit(0)
raise SystemExit("HELPER_VERSION not found")
PY
)"
  zip_path="$DIST_DIR/${skill_name}-${version}.zip"
  stage_dir="$(mktemp -d)"
  cleanup() {
    rm -rf "$stage_dir"
  }
  trap cleanup EXIT
  mkdir -p "$stage_dir/$skill_name"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a \
      --exclude '.DS_Store' \
      --exclude '__pycache__' \
      --exclude '*.pyc' \
      --exclude '*.pyo' \
      "skills/$skill_name/" "$stage_dir/$skill_name/"
  else
    cp -R "skills/$skill_name/." "$stage_dir/$skill_name/"
    find "$stage_dir/$skill_name" -name '.DS_Store' -delete
    find "$stage_dir/$skill_name" -name '__pycache__' -type d -prune -exec rm -rf {} +
    find "$stage_dir/$skill_name" \( -name '*.pyc' -o -name '*.pyo' \) -delete
  fi
  (
    cd "$stage_dir"
    zip -r "$zip_path" "$skill_name" \
      -x "*/__pycache__/*" \
      -x "*.pyc" \
      -x "*.pyo" \
      -x "*.DS_Store" >/dev/null
  )
  rm -rf "$stage_dir"
  trap - EXIT
  echo "已生成 Skill 安装包:"
  echo "$zip_path"
done

python3 - <<'PY'
import ast
from hashlib import sha256
import json
from pathlib import Path

dist_dir = Path("dist/skills")

def read_helper_version(helper_file: Path) -> str:
    tree = ast.parse(helper_file.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "HELPER_VERSION" and isinstance(node.value, ast.Constant):
                return str(node.value.value)
    return ""


expected = []
for skill_dir in sorted(path for path in Path("skills").iterdir() if path.is_dir()):
    scripts_dir = skill_dir / "scripts"
    helper_files = []
    if scripts_dir.exists():
        helper_files = sorted(
            path
            for path in scripts_dir.glob("*.py")
            if read_helper_version(path)
        )
    if len(helper_files) != 1:
        print(f"{skill_dir} 必须且只能有一个包含 HELPER_VERSION 的 helper 脚本")
        raise SystemExit(1)
    skill_id = skill_dir.name
    helper_file = helper_files[0]
    version = read_helper_version(helper_file)
    if not version:
        print(f"{helper_file} 缺少 HELPER_VERSION")
        raise SystemExit(1)
    expected.append((skill_id, version, dist_dir / f"{skill_id}-{version}.zip"))

if not expected:
    print("dist/skills 目录没有生成 ZIP 文件")
    raise SystemExit(1)
expected_names = {zip_file.name for _, _, zip_file in expected}
actual_names = {zip_file.name for zip_file in dist_dir.glob("*.zip")}
missing = sorted(expected_names - actual_names)
extra = sorted(actual_names - expected_names)
if missing or extra:
    if missing:
        print("dist/skills 缺少预期 ZIP:")
        print("\n".join(missing))
    if extra:
        print("dist/skills 包含未知 ZIP:")
        print("\n".join(extra))
    raise SystemExit(1)

lines = []
skills = []
for skill_id, version, zip_file in expected:
    digest = sha256(zip_file.read_bytes()).hexdigest()
    lines.append(f"{digest}  {zip_file.name}")
    skills.append(
        {
            "id": skill_id,
            "version": version,
            "zip": zip_file.name,
            "sha256": digest,
            "size": zip_file.stat().st_size,
        }
    )
(dist_dir / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
(dist_dir / "MANIFEST.json").write_text(
    json.dumps({"skills": skills}, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(f"skill_sha256_manifest_ok files={len(expected)}")
PY

bash scripts/verify-skill-dist.sh
