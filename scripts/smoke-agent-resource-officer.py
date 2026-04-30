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


def template_names(result_data: dict) -> list[str]:
    items = result_data.get("action_templates") or []
    return [str(item.get("name") or "").strip() for item in items if isinstance(item, dict) and str(item.get("name") or "").strip()]


def route(base_url: str, api_key: str, session: str, text: str) -> dict:
    return request(
        base_url,
        api_key,
        "POST",
        "/api/v1/plugin/AgentResourceOfficer/assistant/route",
        body={"session": session, "text": text, "compact": True},
    )


def workflow(base_url: str, api_key: str, session: str, workflow_name: str, **kwargs) -> dict:
    body = {"session": session, "workflow": workflow_name, "compact": True}
    body.update(kwargs)
    return request(
        base_url,
        api_key,
        "POST",
        "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
        body=body,
    )


def action(base_url: str, api_key: str, session: str, name: str, **kwargs) -> dict:
    body = {"session": session, "name": name, "compact": True}
    body.update(kwargs)
    return request(
        base_url,
        api_key,
        "POST",
        "/api/v1/plugin/AgentResourceOfficer/assistant/action",
        body=body,
    )


def recover(base_url: str, api_key: str, session: str) -> dict:
    return request(
        base_url,
        api_key,
        "POST",
        "/api/v1/plugin/AgentResourceOfficer/assistant/recover",
        body={"session": session, "compact": True},
    )


def plan_execute(base_url: str, api_key: str, session: str, plan_id: str) -> dict:
    return request(
        base_url,
        api_key,
        "POST",
        "/api/v1/plugin/AgentResourceOfficer/assistant/plan/execute",
        body={"session": session, "plan_id": plan_id, "compact": True},
    )


def session_state(base_url: str, api_key: str, session: str) -> dict:
    return request(
        base_url,
        api_key,
        "POST",
        "/api/v1/plugin/AgentResourceOfficer/assistant/session",
        body={"session": session, "compact": True},
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
    try:
        request(
            base_url,
            api_key,
            "POST",
            "/api/v1/plugin/AgentResourceOfficer/assistant/session/clear",
            body={"session": session, "compact": True},
        )
    except Exception:
        pass


def clear_plans(base_url: str, api_key: str, session: str) -> None:
    try:
        request(
            base_url,
            api_key,
            "POST",
            "/api/v1/plugin/AgentResourceOfficer/assistant/plans/clear",
            body={"session": session, "limit": 100},
        )
    except Exception:
        pass


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
            f"smoke-aro-recommend-pansou-{stamp}",
            f"smoke-aro-recommend-tv-{stamp}",
        ])

    try:
        selfcheck = request(base_url, api_key, "GET", "/api/v1/plugin/AgentResourceOfficer/assistant/selfcheck")
        selfcheck_data = data(selfcheck)
        assert_ok("selfcheck", bool(selfcheck.get("success") and selfcheck_data.get("ok")), str(selfcheck.get("message") or ""))
        print(f"plugin_version={selfcheck_data.get('version') or ''}")
        execute_plan_followups = ((selfcheck_data.get("template_samples") or {}).get("execute_plan_followups") or {})
        assert_ok(
            "selfcheck_execute_plan_followups",
            (
                (execute_plan_followups.get("mp_best_download") or {}).get("template_names") == [
                    "query_execution_followup",
                    "query_mp_download_history",
                    "query_mp_lifecycle_status",
                    "query_mp_download_tasks",
                ]
                and (execute_plan_followups.get("mp_best_download") or {}).get("recommended_action") == "query_execution_followup"
                and bool((execute_plan_followups.get("mp_best_download") or {}).get("follow_up_hint"))
                and (execute_plan_followups.get("mp_subscribe") or {}).get("template_names") == [
                    "query_execution_followup",
                    "query_mp_subscribes",
                    "query_mp_lifecycle_status",
                    "start_mp_media_search",
                ]
                and (execute_plan_followups.get("mp_subscribe") or {}).get("recommended_action") == "query_execution_followup"
                and bool((execute_plan_followups.get("mp_subscribe") or {}).get("follow_up_hint"))
                and (execute_plan_followups.get("hdhive_unlock_selected") or {}).get("template_names") == [
                    "query_execution_followup",
                    "query_mp_transfer_history",
                    "inspect_session_state",
                ]
                and (execute_plan_followups.get("hdhive_unlock_selected") or {}).get("recommended_action") == "query_execution_followup"
                and bool((execute_plan_followups.get("hdhive_unlock_selected") or {}).get("follow_up_hint"))
            ),
            json.dumps(execute_plan_followups, ensure_ascii=False),
        )

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
        followup_templates = request_templates(base_url, api_key, "followup")
        followup_templates_data = data(followup_templates)
        followup_names = followup_templates_data.get("selected_names") or []
        assert_ok(
            "followup_request_templates",
            bool(
                followup_templates.get("success")
                and followup_templates_data.get("ok")
                and followup_templates_data.get("selected_recipe") == "post_execute_followup"
                and "execution_followup" in followup_names
                and "mp_download_history" in followup_names
                and "mp_lifecycle_status" in followup_names
                and "mp_transfer_history" in followup_names
            ),
            str(followup_templates.get("message") or ""),
        )

        status = route(base_url, api_key, sessions[0], "115状态")
        assert_route_action("route_115_status", status, "p115_status")

        if args.include_search:
            download_tasks = route(base_url, api_key, sessions[0], "下载任务")
            download_tasks_data = assert_route_action("route_download_tasks", download_tasks, "mp_download_tasks")
            execution_followup = action(base_url, api_key, sessions[0], "query_execution_followup")
            execution_followup_data = data(execution_followup)
            assert_ok(
                "action_execution_followup_without_plan",
                (
                    execution_followup.get("success") is False
                    and execution_followup_data.get("action") == "execution_followup"
                    and execution_followup_data.get("error_code") in {"executed_plan_not_found", "latest_plan_not_executed"}
                ),
                json.dumps(execution_followup, ensure_ascii=False)[:240],
            )
            download_task_actions = list(download_tasks_data.get("next_actions") or [])
            assert_ok(
                "route_download_tasks_empty_next_actions",
                "mp_download_control.pause" not in download_task_actions
                and "mp_download_control.resume" not in download_task_actions
                and "mp_download_control.delete" not in download_task_actions,
                json.dumps(download_task_actions, ensure_ascii=False),
            )
            download_task_templates = template_names(download_tasks_data)
            assert_ok(
                "route_download_tasks_empty_templates",
                "pause_mp_download" not in download_task_templates
                and "resume_mp_download" not in download_task_templates
                and "delete_mp_download" not in download_task_templates
                and "query_mp_download_history" in download_task_templates,
                json.dumps(download_task_templates, ensure_ascii=False),
            )

            sites = route(base_url, api_key, sessions[0], "站点状态")
            sites_data = assert_route_action("route_sites", sites, "mp_sites")
            assert_ok(
                "route_sites_next_actions",
                "mp_downloaders" in list(sites_data.get("next_actions") or []),
                json.dumps(sites_data.get("next_actions") or [], ensure_ascii=False),
            )
            site_templates = template_names(sites_data)
            assert_ok(
                "route_sites_templates",
                "query_mp_downloaders" in site_templates and "start_mp_media_search" in site_templates,
                json.dumps(site_templates, ensure_ascii=False),
            )
            site_session = session_state(base_url, api_key, sessions[0])
            site_session_data = data(site_session)
            site_session_templates = template_names(site_session_data)
            assert_ok(
                "route_sites_session_templates",
                "query_mp_downloaders" in site_session_templates and "start_mp_media_search" in site_session_templates,
                json.dumps(site_session_templates, ensure_ascii=False),
            )
            site_recover = recover(base_url, api_key, sessions[0])
            site_recover_data = data(site_recover)
            site_recover_templates = template_names(site_recover_data)
            assert_ok(
                "route_sites_recover_templates",
                "preferences_save" in site_recover_templates and "query_mp_downloaders" in site_recover_templates,
                json.dumps(site_recover_templates, ensure_ascii=False),
            )
            assert_ok(
                "route_sites_recover_priority",
                (site_recover_data.get("recovery") or {}).get("recommended_action") == "query_mp_downloaders"
                and (site_recover_data.get("recovery") or {}).get("mode") == "continue_mp_sites",
                json.dumps(site_recover_data.get("recovery") or {}, ensure_ascii=False),
            )

            downloaders = route(base_url, api_key, sessions[0], "下载器状态")
            downloaders_data = assert_route_action("route_downloaders", downloaders, "mp_downloaders")
            assert_ok(
                "route_downloaders_next_actions",
                "mp_sites" in list(downloaders_data.get("next_actions") or []),
                json.dumps(downloaders_data.get("next_actions") or [], ensure_ascii=False),
            )
            downloader_templates = template_names(downloaders_data)
            assert_ok(
                "route_downloaders_templates",
                "query_mp_sites" in downloader_templates and "start_mp_media_search" in downloader_templates,
                json.dumps(downloader_templates, ensure_ascii=False),
            )

            mp_search = route(base_url, api_key, sessions[1], f"MP搜索 {args.keyword}")
            mp_search_data = assert_route_action("route_mp_search", mp_search, "mp_media_search")
            mp_search_message = message_text(mp_search)
            assert_ok(
                "route_mp_search_plan_hint",
                "会先生成下载计划" in mp_search_message and "即可下载选中项" not in mp_search_message,
                mp_search_message[:240],
            )
            assert_ok(
                "route_mp_search_score_summary",
                bool((mp_search_data.get("score_summary") or {}).get("best")),
                json.dumps(mp_search_data.get("score_summary") or {}, ensure_ascii=False)[:240],
            )

            mp_best = route(base_url, api_key, sessions[1], "最佳片源")
            mp_best_data = assert_route_action("route_mp_search_best", mp_best, "mp_search_best_detail")
            assert_ok(
                "route_mp_search_best_score_summary",
                bool((mp_best_data.get("score_summary") or {}).get("best")),
                json.dumps(mp_best_data.get("score_summary") or {}, ensure_ascii=False)[:240],
            )

            mp_best_download = route(base_url, api_key, sessions[1], "下载最佳")
            mp_best_download_data = assert_route_action("route_mp_download_best_plan", mp_best_download, "workflow_plan")
            assert_ok(
                "route_mp_download_best_has_plan",
                bool(mp_best_download_data.get("plan_id")) and mp_best_download_data.get("workflow") == "mp_best_download",
                json.dumps(mp_best_download_data, ensure_ascii=False)[:240],
            )
            mp_recover_after_plan = recover(base_url, api_key, sessions[1])
            mp_recover_after_plan_data = data(mp_recover_after_plan)
            assert_ok(
                "route_mp_download_recover_priority",
                (mp_recover_after_plan_data.get("recovery") or {}).get("mode") == "resume_saved_plan"
                and (mp_recover_after_plan_data.get("recovery") or {}).get("recommended_action") == "execute_latest_plan",
                json.dumps(mp_recover_after_plan_data.get("recovery") or {}, ensure_ascii=False),
            )
            missing_plan_execute = plan_execute(base_url, api_key, sessions[1], "plan-does-not-exist")
            missing_plan_execute_data = data(missing_plan_execute)
            assert_ok(
                "route_plan_execute_missing_compact",
                missing_plan_execute.get("success") is False
                and missing_plan_execute_data.get("action") == "execute_plan"
                and missing_plan_execute_data.get("write_effect") == "write"
                and missing_plan_execute_data.get("error_code") == "plan_not_found"
                and isinstance(missing_plan_execute_data.get("result_summary"), dict),
                json.dumps({
                    "success": missing_plan_execute.get("success"),
                    "action": missing_plan_execute_data.get("action"),
                    "write_effect": missing_plan_execute_data.get("write_effect"),
                    "error_code": missing_plan_execute_data.get("error_code"),
                    "result_summary": missing_plan_execute_data.get("result_summary"),
                }, ensure_ascii=False),
            )
            workflow_download_control_missing = workflow(
                base_url,
                api_key,
                sessions[1],
                "mp_download_control",
                control="pause",
                target="1",
            )
            workflow_download_control_missing_data = data(workflow_download_control_missing)
            assert_ok(
                "workflow_download_control_requires_task_item",
                workflow_download_control_missing.get("success") is False
                and workflow_download_control_missing_data.get("action") == "mp_download_control"
                and workflow_download_control_missing_data.get("error_code") == "download_target_not_found"
                and not workflow_download_control_missing_data.get("plan_id"),
                json.dumps({
                    "success": workflow_download_control_missing.get("success"),
                    "action": workflow_download_control_missing_data.get("action"),
                    "error_code": workflow_download_control_missing_data.get("error_code"),
                    "plan_id": workflow_download_control_missing_data.get("plan_id"),
                    "message": message_text(workflow_download_control_missing)[:160],
                }, ensure_ascii=False),
            )

            pansou = route(base_url, api_key, sessions[2], f"ps{args.pansou_keyword}")
            assert_route_action("route_pansou_alias", pansou, "pansou_search")

            hdhive = route(base_url, api_key, sessions[3], f"yc{args.keyword}")
            assert_route_action("route_hdhive_alias", hdhive, "hdhive_candidates")

            subscribe_list = route(base_url, api_key, sessions[4], f"订阅列表{args.keyword}")
            subscribe_data = assert_route_action("route_subscribe_list_compact", subscribe_list, "mp_subscribes")
            assert_ok("route_subscribe_list_no_plan", not subscribe_data.get("plan_id"), json.dumps(subscribe_data, ensure_ascii=False)[:240])
            subscribe_actions = list(subscribe_data.get("next_actions") or [])
            assert_ok(
                "route_subscribe_list_empty_next_actions",
                "mp_subscribe_control.search" not in subscribe_actions
                and "mp_subscribe_control.pause" not in subscribe_actions
                and "mp_subscribe_control.resume" not in subscribe_actions
                and "mp_subscribe_control.delete" not in subscribe_actions,
                json.dumps(subscribe_actions, ensure_ascii=False),
            )
            subscribe_templates = template_names(subscribe_data)
            assert_ok(
                "route_subscribe_list_empty_templates",
                "search_mp_subscribe" not in subscribe_templates
                and "pause_mp_subscribe" not in subscribe_templates
                and "resume_mp_subscribe" not in subscribe_templates
                and "delete_mp_subscribe" not in subscribe_templates
                and "start_mp_subscribe" in subscribe_templates,
                json.dumps(subscribe_templates, ensure_ascii=False),
            )
            subscribe_recover = recover(base_url, api_key, sessions[4])
            subscribe_recover_data = data(subscribe_recover)
            assert_ok(
                "route_subscribe_recover_priority",
                (subscribe_recover_data.get("recovery") or {}).get("mode") == "continue_mp_subscribes"
                and (subscribe_recover_data.get("recovery") or {}).get("recommended_action") == "start_mp_subscribe",
                json.dumps(subscribe_recover_data.get("recovery") or {}, ensure_ascii=False),
            )
            subscribe_control_missing = route(base_url, api_key, sessions[4], "搜索订阅 1")
            subscribe_control_missing_data = data(subscribe_control_missing)
            assert_ok(
                "route_subscribe_control_requires_list_item",
                subscribe_control_missing.get("success") is False
                and subscribe_control_missing_data.get("action") == "mp_subscribe_control"
                and subscribe_control_missing_data.get("error_code") == "subscribe_target_not_found"
                and not subscribe_control_missing_data.get("plan_id"),
                json.dumps({
                    "success": subscribe_control_missing.get("success"),
                    "action": subscribe_control_missing_data.get("action"),
                    "error_code": subscribe_control_missing_data.get("error_code"),
                    "plan_id": subscribe_control_missing_data.get("plan_id"),
                    "message": message_text(subscribe_control_missing)[:160],
                }, ensure_ascii=False),
            )
            workflow_subscribe_control_missing = workflow(
                base_url,
                api_key,
                sessions[4],
                "mp_subscribe_control",
                control="search",
                target="1",
            )
            workflow_subscribe_control_missing_data = data(workflow_subscribe_control_missing)
            assert_ok(
                "workflow_subscribe_control_requires_list_item",
                workflow_subscribe_control_missing.get("success") is False
                and workflow_subscribe_control_missing_data.get("action") == "mp_subscribe_control"
                and workflow_subscribe_control_missing_data.get("error_code") == "subscribe_target_not_found"
                and not workflow_subscribe_control_missing_data.get("plan_id"),
                json.dumps({
                    "success": workflow_subscribe_control_missing.get("success"),
                    "action": workflow_subscribe_control_missing_data.get("action"),
                    "error_code": workflow_subscribe_control_missing_data.get("error_code"),
                    "plan_id": workflow_subscribe_control_missing_data.get("plan_id"),
                    "message": message_text(workflow_subscribe_control_missing)[:160],
                }, ensure_ascii=False),
            )

            download_history = route(base_url, api_key, sessions[4], f"下载历史{args.keyword}")
            download_history_data = assert_route_action("route_download_history_compact", download_history, "mp_download_history")
            download_history_recover = recover(base_url, api_key, sessions[4])
            download_history_recover_data = data(download_history_recover)
            assert_ok(
                "route_download_history_recover_priority",
                (download_history_recover_data.get("recovery") or {}).get("mode") == "continue_mp_download_history"
                and (download_history_recover_data.get("recovery") or {}).get("recommended_action") == "query_mp_lifecycle_status",
                json.dumps(download_history_recover_data.get("recovery") or {}, ensure_ascii=False),
            )

            lifecycle = route(base_url, api_key, sessions[4], f"追踪{args.keyword}")
            lifecycle_data = assert_route_action("route_lifecycle_compact", lifecycle, "mp_lifecycle_status")
            lifecycle_recover = recover(base_url, api_key, sessions[4])
            lifecycle_recover_data = data(lifecycle_recover)
            assert_ok(
                "route_lifecycle_recover_priority",
                (lifecycle_recover_data.get("recovery") or {}).get("mode") == "continue_mp_lifecycle_status"
                and (lifecycle_recover_data.get("recovery") or {}).get("recommended_action") == "query_mp_download_history",
                json.dumps(lifecycle_recover_data.get("recovery") or {}, ensure_ascii=False),
            )

            transfer_failed = route(base_url, api_key, sessions[4], f"入库失败{args.keyword}")
            assert_route_action("route_transfer_failed_compact", transfer_failed, "mp_transfer_history")

            movie_recommend = route(base_url, api_key, sessions[5], "热门电影")
            assert_route_action("route_recommend_movie", movie_recommend, "mp_recommendations")
            movie_message = message_text(movie_recommend)
            assert_ok("route_recommend_movie_type_filter", "| 电视剧 |" not in movie_message, movie_message[:240])
            movie_to_mp = route(base_url, api_key, sessions[5], "选择 1")
            movie_to_mp_data = assert_route_action("route_recommend_to_mp", movie_to_mp, "mp_media_search")
            assert_ok(
                "route_recommend_to_mp_scored",
                bool((movie_to_mp_data.get("score_summary") or {}).get("best")),
                json.dumps(movie_to_mp_data.get("score_summary") or {}, ensure_ascii=False)[:240],
            )
            movie_recommend_pansou = route(base_url, api_key, sessions[6], "热门电影")
            assert_route_action("route_recommend_movie_pansou_session", movie_recommend_pansou, "mp_recommendations")
            movie_to_pansou = route(base_url, api_key, sessions[6], "选择 1 盘搜")
            movie_to_pansou_data = assert_route_action("route_recommend_to_pansou", movie_to_pansou, "pansou_search")
            assert_ok(
                "route_recommend_to_pansou_scored",
                bool((movie_to_pansou_data.get("score_summary") or {}).get("best")),
                json.dumps(movie_to_pansou_data.get("score_summary") or {}, ensure_ascii=False)[:240],
            )

            tv_recommend = route(base_url, api_key, sessions[7], "热门电视剧")
            assert_route_action("route_recommend_tv", tv_recommend, "mp_recommendations")
            tv_message = message_text(tv_recommend)
            assert_ok("route_recommend_tv_type_filter", "| 电影 |" not in tv_message, tv_message[:240])
    finally:
        for session in sessions:
            clear_plans(base_url, api_key, session)
            clear_session(base_url, api_key, session)

    print("agent_resource_officer_smoke_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
