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


def message_text(result: dict) -> str:
    return str(result.get("message") or "")


def assert_route_action(name: str, result: dict, expected_action: str, *, require_success: bool = True) -> dict:
    result_data = data(result)
    condition = result_data.get("action") == expected_action
    if require_success:
        condition = condition and bool(result.get("success") and result_data.get("ok"))
    assert_ok(
        name,
        condition,
        json.dumps({
            "success": result.get("success"),
            "ok": result_data.get("ok"),
            "action": result_data.get("action"),
            "message": message_text(result)[:160],
        }, ensure_ascii=False),
    )
    return result_data


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
    parser.add_argument("--include-search", action="store_true", help="Also test MP native search, PanSou, and HDHive alias routes")
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
            f"smoke-aro-mp-readonly-{stamp}",
            f"smoke-aro-recommend-movie-{stamp}",
            f"smoke-aro-recommend-tv-{stamp}",
        ])

    try:
        selfcheck = request(base_url, api_key, "GET", "/api/v1/plugin/AgentResourceOfficer/assistant/selfcheck")
        selfcheck_data = data(selfcheck)
        assert_ok("selfcheck", bool(selfcheck.get("success") and selfcheck_data.get("ok")), str(selfcheck.get("message") or ""))
        print(f"plugin_version={selfcheck_data.get('version') or ''}")

        feishu = request(base_url, api_key, "GET", "/api/v1/plugin/AgentResourceOfficer/feishu/health")
        feishu_data = data(feishu)
        assert_ok("feishu_health", bool(feishu.get("success") and "sdk_available" in feishu_data), str(feishu.get("message") or ""))

        external_agent_templates = request_templates(base_url, api_key, "external_agent")
        external_agent_templates_data = data(external_agent_templates)
        selected_names = external_agent_templates_data.get("selected_names") or []
        assert_ok(
            "external_agent_request_templates",
            bool(
                external_agent_templates.get("success")
                and external_agent_templates_data.get("ok")
                and external_agent_templates_data.get("selected_recipe") == "external_agent_quickstart"
                and selected_names == ["startup_probe", "route_text", "pick_continue"]
            ),
            str(external_agent_templates.get("message") or ""),
        )

        mp_pt_templates = request_templates(base_url, api_key, "mp_pt")
        mp_pt_templates_data = data(mp_pt_templates)
        mp_pt_names = mp_pt_templates_data.get("selected_names") or []
        assert_ok(
            "mp_pt_request_templates",
            bool(
                mp_pt_templates.get("success")
                and mp_pt_templates_data.get("ok")
                and mp_pt_templates_data.get("selected_recipe") == "mp_pt_mainline"
                and "mp_search" in mp_pt_names
                and "mp_search_download_plan" in mp_pt_names
                and "saved_plan_execute" in mp_pt_names
            ),
            str(mp_pt_templates.get("message") or ""),
        )

        mp_recommend_templates = request_templates(base_url, api_key, "recommend")
        mp_recommend_templates_data = data(mp_recommend_templates)
        mp_recommend_names = mp_recommend_templates_data.get("selected_names") or []
        assert_ok(
            "mp_recommend_request_templates",
            bool(
                mp_recommend_templates.get("success")
                and mp_recommend_templates_data.get("ok")
                and mp_recommend_templates_data.get("selected_recipe") == "mp_recommendation"
                and "mp_recommend" in mp_recommend_names
                and "mp_recommend_search" in mp_recommend_names
                and "mp_search_download_plan" in mp_recommend_names
            ),
            str(mp_recommend_templates.get("message") or ""),
        )

        status = route(base_url, api_key, sessions[0], "115状态")
        assert_route_action("route_115_status", status, "p115_status")

        if args.include_search:
            mp_search = route(base_url, api_key, sessions[1], f"MP搜索 {args.keyword}")
            assert_route_action("route_mp_search", mp_search, "mp_media_search")
            mp_search_message = message_text(mp_search)
            assert_ok(
                "route_mp_search_plan_hint",
                "会先生成下载计划" in mp_search_message and "即可下载选中项" not in mp_search_message,
                mp_search_message[:240],
            )

            pansou = route(base_url, api_key, sessions[2], f"ps{args.pansou_keyword}")
            assert_route_action("route_pansou_alias", pansou, "pansou_search")

            hdhive = route(base_url, api_key, sessions[3], f"yc{args.keyword}")
            assert_route_action("route_hdhive_alias", hdhive, "hdhive_candidates")

            subscribe_list = route(base_url, api_key, sessions[4], f"订阅列表{args.keyword}")
            subscribe_data = assert_route_action("route_subscribe_list_compact", subscribe_list, "mp_subscribes")
            assert_ok("route_subscribe_list_no_plan", not subscribe_data.get("plan_id"), json.dumps(subscribe_data, ensure_ascii=False)[:240])

            download_history = route(base_url, api_key, sessions[4], f"下载历史{args.keyword}")
            assert_route_action("route_download_history_compact", download_history, "mp_download_history")

            lifecycle = route(base_url, api_key, sessions[4], f"追踪{args.keyword}")
            assert_route_action("route_lifecycle_compact", lifecycle, "mp_lifecycle_status")

            transfer_failed = route(base_url, api_key, sessions[4], f"入库失败{args.keyword}")
            assert_route_action("route_transfer_failed_compact", transfer_failed, "mp_transfer_history")

            movie_recommend = route(base_url, api_key, sessions[5], "热门电影")
            assert_route_action("route_recommend_movie", movie_recommend, "mp_recommendations")
            movie_message = message_text(movie_recommend)
            assert_ok("route_recommend_movie_type_filter", "| 电视剧 |" not in movie_message, movie_message[:240])

            tv_recommend = route(base_url, api_key, sessions[6], "热门电视剧")
            assert_route_action("route_recommend_tv", tv_recommend, "mp_recommendations")
            tv_message = message_text(tv_recommend)
            assert_ok("route_recommend_tv_type_filter", "| 电影 |" not in tv_message, tv_message[:240])
    finally:
        for session in sessions:
            clear_session(base_url, api_key, session)

    print("agent_resource_officer_smoke_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
