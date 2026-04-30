#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def extract_pattern(text: str, pattern: str, label: str) -> str:
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        raise SystemExit(f"missing_{label}")
    return match.group(1)


plugin_init = read_text("AgentResourceOfficer/__init__.py")
helper_script = read_text("skills/agent-resource-officer/scripts/aro_request.py")

plugin_version = extract_pattern(
    plugin_init,
    r'plugin_version\s*=\s*"([^"]+)"',
    "plugin_version",
)
helper_version = extract_pattern(
    helper_script,
    r'HELPER_VERSION\s*=\s*"([^"]+)"',
    "helper_version",
)
release_url = f"https://github.com/liuyuexi1987/MoviePilot-Plugins/releases/tag/v{plugin_version}"
plugin_zip = f"AgentResourceOfficer-{plugin_version}.zip"

checks = {
    "README.md": [
        f"当前发布版本：`{plugin_version}`",
        f"当前 Skill helper 版本：`{helper_version}`",
        release_url,
        f"当前版本：\n\n- `{plugin_version}`",
    ],
    "docs/PLUGIN_INSTALL.md": [
        f"资源主线：`Agent影视助手 / AgentResourceOfficer {plugin_version}`",
        f"当前 Skill helper：`agent-resource-officer {helper_version}`",
        release_url,
        plugin_zip,
    ],
    "docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md": [
        f"当前插件版本：`Agent影视助手 {plugin_version}`",
        f"当前 helper 版本：`agent-resource-officer {helper_version}`",
    ],
    "docs/AGENT_RESOURCE_OFFICER_REMOTE_DEPLOY.md": [
        f"当前插件版本：`Agent影视助手 {plugin_version}`",
        f"当前 helper 版本：`agent-resource-officer {helper_version}`",
    ],
    "skills/agent-resource-officer/README.md": [
        f"当前 helper 版本：`{helper_version}`",
        f"当前插件版本：`Agent影视助手 {plugin_version}`",
    ],
    "skills/agent-resource-officer/EXTERNAL_AGENTS.md": [
        f"当前插件版本：`Agent影视助手 {plugin_version}`",
        f"当前 helper 版本：`agent-resource-officer {helper_version}`",
    ],
}

failures: list[str] = []
for rel_path, required_fragments in checks.items():
    text = read_text(rel_path)
    for fragment in required_fragments:
        if fragment not in text:
            failures.append(f"{rel_path}: missing {fragment}")

if failures:
    print("doc_current_state_mismatch")
    for failure in failures:
        print(failure)
    raise SystemExit(1)

print(
    f"doc_current_state_ok plugin={plugin_version} helper={helper_version} release={release_url}"
)
