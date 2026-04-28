#!/usr/bin/env python3
"""Live smoke checks for AgentResourceOfficer.

This script intentionally does not print API keys or cookies. It reads the
same local config used by the public agent-resource-officer Skill:
~/.config/agent-resource-officer/config.
"""

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path


CONFIG_PATH = Path("~/.config/agent-resource-officer/config").expanduser()


def read_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    config = {}
    for line in CONFIG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        config[key.strip()] = value.strip()
    return config


def pick_config(config: dict, *names: str) -> str:
    for name in names:
        value = os.environ.get(name) or config.get(name)
        if value:
            return value.strip()
    return ""


def request(base_url: str, api_key: str, method: str, path: str, body: dict | None = None, query: dict | None = None) -> dict:
    query_items = list((query or {}).items())
    query_items.append(("apikey", api_key))
    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    url = url + "?" + urllib.parse.urlencode(query_items)
    payload = None
    headers = {}
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=payload, method=method.upper(), headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"success": False, "raw": raw}


def data(result: dict) -> dict:
    payload = result.get("data")
    return payload if isinstance(payload, dict) else result


def assert_ok(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(f"{name}_failed{suffix}")
    print(f"{name}_ok")


def route(base_url: str, api_key: str, session: str, text: str) -> dict:
    return request(
        base_url,
        api_key,
        "POST",
        "/api/v1/plugin/AgentResourceOfficer/assistant/route",
        body={"session": session, "text": text, "compact": True},
    )


def request_templates(base_url: str, api_key: str, recipe: str) -> dict:
    return request(
        base_url,
        api_key,
        "POST",
        "/api/v1/plugin/AgentResourceOfficer/assistant/request_templates",
        body={"recipe": recipe, "include_templates": False},
    )


def clear_session(base_url: str, api_key: str, session: str) -> None:
    request(
        base_url,
        api_key,
        "POST",
        "/api/v1/plugin/AgentResourceOfficer/assistant/session/clear",
        body={"session": session, "compact": True},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test AgentResourceOfficer live assistant endpoints")
    parser.add_argument("--base-url")
    parser.add_argument("--api-key")
    parser.add_argument("--include-search", action="store_true", help="Also test PanSou and HDHive alias searches")
    parser.add_argument("--keyword", default="蜘蛛侠")
    parser.add_argument("--pansou-keyword", default="大君夫人")
    args = parser.parse_args()

    config = read_config()
    base_url = args.base_url or pick_config(config, "ARO_BASE_URL", "MP_BASE_URL", "MOVIEPILOT_URL")
    api_key = args.api_key or pick_config(config, "ARO_API_KEY", "MP_API_TOKEN")
    if not base_url or not api_key:
        raise SystemExit("missing ARO_BASE_URL/ARO_API_KEY; configure ~/.config/agent-resource-officer/config or env")

    stamp = int(time.time())
    sessions = [
        f"smoke-aro-status-{stamp}",
    ]
    if args.include_search:
        sessions.extend([
            f"smoke-aro-mp-search-{stamp}",
            f"smoke-aro-pansou-{stamp}",
            f"smoke-aro-hdhive-{stamp}",
        ])

    try:
        selfcheck = request(base_url, api_key, "GET", "/api/v1/plugin/AgentResourceOfficer/assistant/selfcheck")
        selfcheck_data = data(selfcheck)
        assert_ok("selfcheck", bool(selfcheck.get("success") and selfcheck_data.get("ok")), str(selfcheck.get("message") or ""))
        print(f"plugin_version={selfcheck_data.get('version') or ''}")

        feishu = request(base_url, api_key, "GET", "/api/v1/plugin/AgentResourceOfficer/feishu/health")
        feishu_data = data(feishu)
        assert_ok("feishu_health", bool(feishu.get("success") and "sdk_available" in feishu_data), str(feishu.get("message") or ""))

        workbuddy_templates = request_templates(base_url, api_key, "workbuddy")
        workbuddy_templates_data = data(workbuddy_templates)
        selected_names = workbuddy_templates_data.get("selected_names") or []
        assert_ok(
            "workbuddy_request_templates",
            bool(
                workbuddy_templates.get("success")
                and workbuddy_templates_data.get("ok")
                and workbuddy_templates_data.get("selected_recipe") == "workbuddy_quickstart"
                and selected_names == ["startup_probe", "route_text", "pick_continue"]
            ),
            str(workbuddy_templates.get("message") or ""),
        )

        status = route(base_url, api_key, sessions[0], "115状态")
        status_data = data(status)
        assert_ok("route_115_status", bool(status.get("success") and status_data.get("ok")), str(status.get("message") or ""))

        if args.include_search:
            mp_search = route(base_url, api_key, sessions[1], f"MP搜索 {args.keyword}")
            mp_search_data = data(mp_search)
            assert_ok("route_mp_search", bool(mp_search.get("success") and mp_search_data.get("ok")), str(mp_search.get("message") or ""))

            pansou = route(base_url, api_key, sessions[2], f"ps{args.pansou_keyword}")
            pansou_data = data(pansou)
            assert_ok("route_pansou_alias", bool(pansou.get("success") and pansou_data.get("ok")), str(pansou.get("message") or ""))

            hdhive = route(base_url, api_key, sessions[3], f"yc{args.keyword}")
            hdhive_data = data(hdhive)
            assert_ok("route_hdhive_alias", bool(hdhive.get("success") and hdhive_data.get("ok")), str(hdhive.get("message") or ""))
    finally:
        for session in sessions:
            clear_session(base_url, api_key, session)

    print("agent_resource_officer_smoke_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
