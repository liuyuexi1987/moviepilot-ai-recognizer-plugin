#!/usr/bin/env bash
set -euo pipefail

container="${MP_CONTAINER:-moviepilot-v2}"
plugin_files=(
  "/app/app/plugins/p115strmhelper/__init__.py"
  "/config/plugins/p115strmhelper/__init__.py"
)
tmp_dir="$(mktemp -d)"

cleanup() {
  rm -rf "${tmp_dir}"
}
trap cleanup EXIT

echo "P115StrmHelper compatibility patch"
echo "container: ${container}"

patch_file() {
  local plugin_file="$1"
  local safe_name
  safe_name="$(echo "${plugin_file}" | tr '/:' '__')"
  local local_file="${tmp_dir}/${safe_name}"

  if ! docker exec "${container}" test -f "${plugin_file}"; then
    echo "skip missing: ${plugin_file}"
    return 0
  fi

  docker cp "${container}:${plugin_file}" "${local_file}"

  if grep -q "_optional_event_register(_TRANSFER_OVERWRITE_CHECK_EVENT)" "${local_file}"; then
    echo "already patched: ${plugin_file}"
  else
    python3 - "${local_file}" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

text = text.replace("    TransferOverwriteCheckEventData,\n", "")

markers = [
    "from app.schemas.types import ChainEventType\n",
    "from app.schemas.types import EventType, MessageChannel, ChainEventType, MediaType\n",
]
compat = '''from app.schemas.types import EventType, MessageChannel, ChainEventType, MediaType

_TRANSFER_OVERWRITE_CHECK_EVENT = getattr(ChainEventType, "TransferOverwriteCheck", None)
try:
    from app.schemas import TransferOverwriteCheckEventData
except Exception:
    class TransferOverwriteCheckEventData:
        pass


def _optional_event_register(event_type):
    if event_type is None:
        def decorator(func):
            return func
        return decorator
    return eventmanager.register(event_type)
'''

marker = next((item for item in markers if item in text), None)
if marker is None:
    raise SystemExit("cannot find ChainEventType import marker")
text = text.replace(marker, compat, 1)

old = "@eventmanager.register(ChainEventType.TransferOverwriteCheck)"
new = "@_optional_event_register(_TRANSFER_OVERWRITE_CHECK_EVENT)"
if old not in text:
    raise SystemExit("cannot find TransferOverwriteCheck decorator")
text = text.replace(old, new, 1)

path.write_text(text)
PY
  fi

  docker cp "${local_file}" "${container}:${plugin_file}"
  docker exec "${container}" /opt/venv/bin/python -m py_compile "${plugin_file}"
  echo "patched and syntax check passed: ${plugin_file}"
}

for plugin_file in "${plugin_files[@]}"; do
  patch_file "${plugin_file}"
done

echo "restart MoviePilot, then verify AgentResourceOfficer /p115/health"
