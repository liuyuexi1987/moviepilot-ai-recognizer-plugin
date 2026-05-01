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
import urllib.error
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
    last_error = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8")
            break
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {502, 503, 504} or attempt >= 5:
                raise
            time.sleep(2)
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt >= 5:
                raise
            time.sleep(2)
    else:
        raise last_error or RuntimeError("request failed without response")
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
            f"smoke-aro-smart-discovery-{stamp}",
            f"smoke-aro-smart-discovery-plan-{stamp}",
            f"smoke-aro-smart-discovery-execute-{stamp}",
        ])

    try:
        selfcheck = request(base_url, api_key, "GET", "/api/v1/plugin/AgentResourceOfficer/assistant/selfcheck")
        selfcheck_data = data(selfcheck)
        assert_ok("selfcheck", bool(selfcheck.get("success") and selfcheck_data.get("ok")), str(selfcheck.get("message") or ""))
        assert_ok(
            "selfcheck_executed_plan_recovery",
            bool(((selfcheck_data.get("checks") or {}).get("executed_plan_recovery"))),
            json.dumps((selfcheck_data.get("checks") or {}), ensure_ascii=False)[:240],
        )
        print(f"plugin_version={selfcheck_data.get('version') or ''}")
        execute_plan_followups = ((selfcheck_data.get("template_samples") or {}).get("execute_plan_followups") or {})
        assert_ok(
            "selfcheck_execute_plan_followups",
            (
                (execute_plan_followups.get("mp_best_download") or {}).get("template_names") == [
                    "query_execution_followup",
                    "query_mp_ingest_status",
                    "query_mp_download_history",
                    "query_mp_lifecycle_status",
                    "query_mp_local_diagnose",
                ]
                and (execute_plan_followups.get("mp_best_download") or {}).get("recommended_action") == "query_execution_followup"
                and bool((execute_plan_followups.get("mp_best_download") or {}).get("follow_up_hint"))
                and (execute_plan_followups.get("mp_subscribe") or {}).get("template_names") == [
                    "query_execution_followup",
                    "query_mp_subscribes",
                    "query_mp_ingest_status",
                    "start_mp_media_search",
                ]
                and (execute_plan_followups.get("mp_subscribe") or {}).get("recommended_action") == "query_execution_followup"
                and bool((execute_plan_followups.get("mp_subscribe") or {}).get("follow_up_hint"))
                and (execute_plan_followups.get("hdhive_unlock_selected") or {}).get("template_names") == [
                    "query_execution_followup",
                    "query_mp_transfer_history",
                    "query_mp_local_diagnose",
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
        preferences_templates = request_templates(base_url, api_key, "preferences")
        preferences_templates_data = data(preferences_templates)
        preferences_names = preferences_templates_data.get("selected_names") or []
        assert_ok(
            "preferences_request_templates",
            bool(
                preferences_templates.get("success")
                and preferences_templates_data.get("ok")
                and preferences_templates_data.get("selected_recipe") == "preferences_onboarding"
                and preferences_names == ["preferences_get", "scoring_policy", "preferences_save"]
            ),
            str(preferences_templates.get("message") or ""),
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
        local_ingest_templates = request_templates(base_url, api_key, "local_ingest")
        local_ingest_templates_data = data(local_ingest_templates)
        local_ingest_names = local_ingest_templates_data.get("selected_names") or []
        assert_ok(
            "local_ingest_request_templates",
            bool(
                local_ingest_templates.get("success")
                and local_ingest_templates_data.get("ok")
                and local_ingest_templates_data.get("selected_recipe") == "local_ingest"
                and "mp_ingest_status" in local_ingest_names
                and "mp_local_diagnose" in local_ingest_names
                and "mp_recent_activity" in local_ingest_names
            ),
            str(local_ingest_templates.get("message") or ""),
        )
        smart_search_templates = request_templates(base_url, api_key, "smart_search")
        smart_search_templates_data = data(smart_search_templates)
        smart_search_names = smart_search_templates_data.get("selected_names") or []
        assert_ok(
            "smart_search_request_templates",
            bool(
                smart_search_templates.get("success")
                and smart_search_templates_data.get("ok")
                and smart_search_templates_data.get("selected_recipe") == "smart_search"
                and smart_search_names == ["smart_search", "preferences_get", "scoring_policy"]
            ),
            str(smart_search_templates.get("message") or ""),
        )
        smart_decision_templates = request_templates(base_url, api_key, "smart_decision")
        smart_decision_templates_data = data(smart_decision_templates)
        smart_decision_names = smart_decision_templates_data.get("selected_names") or []
        assert_ok(
            "smart_decision_request_templates",
            bool(
                smart_decision_templates.get("success")
                and smart_decision_templates_data.get("ok")
                and smart_decision_templates_data.get("selected_recipe") == "smart_decision"
                and smart_decision_names == ["smart_decision", "preferences_get", "scoring_policy"]
            ),
            str(smart_decision_templates.get("message") or ""),
        )
        smart_search_plan_templates = request_templates(base_url, api_key, "smart_search_plan")
        smart_search_plan_templates_data = data(smart_search_plan_templates)
        smart_search_plan_names = smart_search_plan_templates_data.get("selected_names") or []
        assert_ok(
            "smart_search_plan_request_templates",
            bool(
                smart_search_plan_templates.get("success")
                and smart_search_plan_templates_data.get("ok")
                and smart_search_plan_templates_data.get("selected_recipe") == "smart_search_plan"
                and smart_search_plan_names == ["smart_search_plan", "preferences_get", "scoring_policy", "saved_plan_execute"]
            ),
            str(smart_search_plan_templates.get("message") or ""),
        )
        smart_search_execute_templates = request_templates(base_url, api_key, "smart_search_execute")
        smart_search_execute_templates_data = data(smart_search_execute_templates)
        smart_search_execute_names = smart_search_execute_templates_data.get("selected_names") or []
        assert_ok(
            "smart_search_execute_request_templates",
            bool(
                smart_search_execute_templates.get("success")
                and smart_search_execute_templates_data.get("ok")
                and smart_search_execute_templates_data.get("selected_recipe") == "smart_search_execute"
                and smart_search_execute_names == ["smart_search_execute", "preferences_get", "scoring_policy", "post_execute_followup"]
            ),
            str(smart_search_execute_templates.get("message") or ""),
        )
        preferences_view = route(base_url, api_key, sessions[0], "偏好")
        preferences_view_data = assert_route_action("route_preferences_get", preferences_view, "preferences")
        assert_ok(
            "route_preferences_get_payload",
            isinstance(preferences_view_data.get("preference_status"), dict)
            and "needs_onboarding" in (preferences_view_data.get("preference_status") or {}),
            json.dumps(preferences_view_data.get("preference_status") or {}, ensure_ascii=False)[:240],
        )

        scoring_policy = route(base_url, api_key, sessions[0], "评分策略")
        scoring_policy_data = assert_route_action("route_scoring_policy", scoring_policy, "scoring_policy")
        assert_ok(
            "route_scoring_policy_payload",
            isinstance(scoring_policy_data.get("scoring_policy"), dict)
            and (scoring_policy_data.get("scoring_policy") or {}).get("schema_version") == "scoring_policy.v1"
            and isinstance(((scoring_policy_data.get("scoring_policy") or {}).get("global_decision") or {}).get("default_confirm_score_threshold"), int)
            and isinstance(((scoring_policy_data.get("scoring_policy") or {}).get("global_decision") or {}).get("default_auto_ingest_score_threshold"), int),
            json.dumps(scoring_policy_data.get("scoring_policy") or {}, ensure_ascii=False)[:240],
        )

        preferences_save = route(
            base_url,
            api_key,
            sessions[0],
            "保存偏好 4K 杜比 HDR 中字 全集 做种>=5 影巢积分15 不自动入库",
        )
        preferences_save_data = assert_route_action("route_preferences_save", preferences_save, "preferences_save")
        saved_preferences = ((preferences_save_data.get("preference_status") or {}).get("summary") or {})
        assert_ok(
            "route_preferences_save_values",
            (
                saved_preferences.get("prefer_resolution") == "4K"
                and saved_preferences.get("pt_min_seeders") == 5
                and saved_preferences.get("hdhive_max_unlock_points") == 15
                and saved_preferences.get("auto_ingest_enabled") is False
            ),
            json.dumps(saved_preferences, ensure_ascii=False)[:240],
        )

        preferences_after_save = route(base_url, api_key, sessions[0], "偏好")
        preferences_after_save_data = assert_route_action("route_preferences_after_save", preferences_after_save, "preferences")
        assert_ok(
            "route_preferences_after_save_initialized",
            ((preferences_after_save_data.get("preference_status") or {}).get("initialized") is True),
            json.dumps(preferences_after_save_data.get("preference_status") or {}, ensure_ascii=False)[:240],
        )

        preferences_reset = route(base_url, api_key, sessions[0], "重置偏好")
        preferences_reset_data = assert_route_action("route_preferences_reset", preferences_reset, "preferences_reset")
        assert_ok(
            "route_preferences_reset_needs_onboarding",
            ((preferences_reset_data.get("preference_status") or {}).get("needs_onboarding") is True),
            json.dumps(preferences_reset_data.get("preference_status") or {}, ensure_ascii=False)[:240],
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
            execution_followup_error_summary = execution_followup_data.get("error_summary") or {}
            execution_followup_error_code = execution_followup_data.get("error_code")
            execution_followup_compact_commands = execution_followup_error_summary.get("compact_commands") or []
            assert_ok(
                "action_execution_followup_without_plan_error_summary",
                (
                    isinstance(execution_followup_error_summary, dict)
                    and bool(execution_followup_error_summary.get("decision_hint"))
                    and (
                        (
                            execution_followup_error_code == "latest_plan_not_executed"
                            and "执行计划" in execution_followup_compact_commands
                        ) or (
                            execution_followup_error_code == "executed_plan_not_found"
                            and "最近" in execution_followup_compact_commands
                        )
                    )
                ),
                json.dumps(execution_followup_error_summary, ensure_ascii=False)[:240],
            )
            assert_ok(
                "action_execution_followup_without_plan_preferred_command",
                (
                    execution_followup_data.get("command_source") == "error_summary"
                    and execution_followup_data.get("preferred_command") == execution_followup_error_summary.get("preferred_command")
                    and isinstance(execution_followup_data.get("compact_commands"), list)
                    and execution_followup_data.get("command_policy") == "safe_read_recovery"
                    and execution_followup_data.get("preferred_requires_confirmation") is False
                ),
                json.dumps(execution_followup_data, ensure_ascii=False)[:240],
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

            smart_search = route(base_url, api_key, sessions[1], f"智能搜索 {args.keyword}")
            smart_search_data = assert_route_action("route_smart_search", smart_search, "smart_resource_search")
            checked_sources = [
                str(item.get("source_type") or "").strip()
                for item in (smart_search_data.get("sources_checked") or [])
                if isinstance(item, dict)
            ]
            assert_ok(
                "route_smart_search_checked_sources",
                bool(checked_sources) and checked_sources[0] == "pansou",
                json.dumps(smart_search_data.get("sources_checked") or [], ensure_ascii=False)[:240],
            )
            assert_ok(
                "route_smart_search_best_candidate",
                isinstance(smart_search_data.get("best_candidate"), dict)
                and bool((smart_search_data.get("best_candidate") or {}).get("source_type"))
                and bool((smart_search_data.get("decision_summary") or {}).get("preferred_command")),
                json.dumps({
                    "best_candidate": smart_search_data.get("best_candidate"),
                    "decision_summary": smart_search_data.get("decision_summary"),
                }, ensure_ascii=False)[:240],
            )
            assert_ok(
                "route_smart_search_preference_status",
                (
                    isinstance((smart_search_data.get("preference_status") or {}).get("summary"), dict)
                    and "enable_pansou" in ((smart_search_data.get("preference_status") or {}).get("summary") or {})
                    and "has_quark" in ((smart_search_data.get("preference_status") or {}).get("summary") or {})
                ),
                json.dumps(smart_search_data.get("preference_status") or {}, ensure_ascii=False)[:240],
            )
            smart_decision = route(base_url, api_key, sessions[1], f"资源决策 {args.keyword}")
            smart_decision_data = assert_route_action("route_smart_decision", smart_decision, "smart_resource_decision")
            assert_ok(
                "route_smart_decision_payload",
                bool(smart_decision_data.get("decision_mode"))
                and isinstance(smart_decision_data.get("available_sources"), list)
                and isinstance(smart_decision_data.get("blocked_sources"), list)
                and bool((smart_decision_data.get("decision_summary") or {}).get("preferred_command")),
                json.dumps({
                    "decision_mode": smart_decision_data.get("decision_mode"),
                    "decision_summary": smart_decision_data.get("decision_summary"),
                    "available_sources": smart_decision_data.get("available_sources"),
                    "blocked_sources": smart_decision_data.get("blocked_sources"),
                }, ensure_ascii=False)[:320],
            )
            smart_decision_preferred = str((smart_decision_data.get("decision_summary") or {}).get("preferred_command") or "")
            assert_ok(
                "route_smart_decision_command_policy",
                (
                    smart_decision_data.get("command_policy") in {"wait_user_confirmation", "read_then_confirm_write"}
                    and smart_decision_data.get("preferred_requires_confirmation") is True
                    and smart_decision_data.get("can_auto_run_preferred") is False
                )
                if smart_decision_preferred in {"计划最佳", "执行最佳"}
                else (
                    smart_decision_data.get("command_policy") == "safe_read_only"
                    and smart_decision_data.get("preferred_requires_confirmation") is False
                ),
                json.dumps({
                    "preferred_command": smart_decision_preferred,
                    "command_policy": smart_decision_data.get("command_policy"),
                    "preferred_requires_confirmation": smart_decision_data.get("preferred_requires_confirmation"),
                    "can_auto_run_preferred": smart_decision_data.get("can_auto_run_preferred"),
                    "recommended_agent_behavior": smart_decision_data.get("recommended_agent_behavior"),
                    "auto_run_command": smart_decision_data.get("auto_run_command"),
                    "confirm_command": smart_decision_data.get("confirm_command"),
                }, ensure_ascii=False)[:240],
            )
            assert_ok(
                "route_smart_decision_explicit_execution_policy",
                (
                    smart_decision_data.get("recommended_agent_behavior") == "auto_continue_then_wait_confirmation"
                    and smart_decision_data.get("auto_run_command") == "先看详情"
                    and smart_decision_data.get("confirm_command") in {"计划最佳", "执行最佳"}
                )
                if smart_decision_preferred in {"计划最佳", "执行最佳"}
                else (
                    smart_decision_data.get("recommended_agent_behavior") in {"auto_continue", "show_only"}
                ),
                json.dumps({
                    "preferred_command": smart_decision_preferred,
                    "recommended_agent_behavior": smart_decision_data.get("recommended_agent_behavior"),
                    "auto_run_command": smart_decision_data.get("auto_run_command"),
                    "confirm_command": smart_decision_data.get("confirm_command"),
                }, ensure_ascii=False)[:240],
            )
            smart_decision_switch = route(base_url, api_key, sessions[1], "换影巢")
            smart_decision_switch_data = assert_route_action("route_smart_decision_switch_hdhive", smart_decision_switch, "smart_resource_decision")
            assert_ok(
                "route_smart_decision_switch_hdhive",
                isinstance(smart_decision_switch_data.get("sources_checked"), list)
                and bool(smart_decision_switch_data.get("decision_mode")),
                json.dumps({
                    "sources_checked": smart_decision_switch_data.get("sources_checked"),
                    "decision_mode": smart_decision_switch_data.get("decision_mode"),
                }, ensure_ascii=False)[:240],
            )
            smart_pref_session = f"{sessions[1]}-prefs"
            assert_route_action(
                "route_smart_decision_pref_session_start",
                route(base_url, api_key, smart_pref_session, f"资源决策 {args.keyword}"),
                "smart_resource_decision",
            )
            smart_decision_only_quark = route(base_url, api_key, smart_pref_session, "只用夸克")
            smart_decision_only_quark_data = assert_route_action("route_smart_decision_only_quark", smart_decision_only_quark, "smart_resource_decision")
            assert_ok(
                "route_smart_decision_only_quark_effective",
                (
                    isinstance(smart_decision_only_quark_data.get("session_preference_overrides"), dict)
                    and (smart_decision_only_quark_data.get("session_preference_overrides") or {}).get("has_quark") is True
                    and (smart_decision_only_quark_data.get("session_preference_overrides") or {}).get("has_115") is False
                    and any(
                        (item or {}).get("source_type") == "115"
                        for item in (smart_decision_only_quark_data.get("blocked_sources") or [])
                    )
                ),
                json.dumps(smart_decision_only_quark_data, ensure_ascii=False)[:320],
            )
            smart_decision_only_pt = route(base_url, api_key, smart_pref_session, "只走PT")
            smart_decision_only_pt_data = assert_route_action("route_smart_decision_only_pt", smart_decision_only_pt, "smart_resource_decision")
            assert_ok(
                "route_smart_decision_only_pt_effective",
                (
                    [(item or {}).get("source_type") for item in (smart_decision_only_pt_data.get("available_sources") or [])] == ["mp_pt"]
                    and any((item or {}).get("source_type") == "pansou" for item in (smart_decision_only_pt_data.get("blocked_sources") or []))
                    and any((item or {}).get("source_type") == "hdhive" for item in (smart_decision_only_pt_data.get("blocked_sources") or []))
                ),
                json.dumps({
                    "available_sources": smart_decision_only_pt_data.get("available_sources"),
                    "blocked_sources": smart_decision_only_pt_data.get("blocked_sources"),
                    "session_preference_overrides": smart_decision_only_pt_data.get("session_preference_overrides"),
                }, ensure_ascii=False)[:320],
            )
            smart_decision_reset = route(base_url, api_key, smart_pref_session, "按保存偏好")
            smart_decision_reset_data = assert_route_action("route_smart_decision_reset_preferences", smart_decision_reset, "smart_resource_decision")
            assert_ok(
                "route_smart_decision_reset_preferences_effective",
                isinstance(smart_decision_reset_data.get("session_preference_overrides"), dict)
                and not bool(smart_decision_reset_data.get("session_preference_overrides")),
                json.dumps(smart_decision_reset_data.get("session_preference_overrides") or {}, ensure_ascii=False)[:240],
            )
            smart_decision_plan = route(base_url, api_key, sessions[1], f"资源决策 {args.keyword} 计划")
            smart_decision_plan_data = assert_route_action("route_smart_decision_plan_intent", smart_decision_plan, "workflow_plan")
            assert_ok(
                "route_smart_decision_plan_intent",
                bool(smart_decision_plan_data.get("plan_id"))
                and smart_decision_plan_data.get("workflow") == "smart_resource_plan",
                json.dumps(smart_decision_plan_data, ensure_ascii=False)[:240],
            )
            smart_decision_confirm_plan = route(base_url, api_key, sessions[1], "先计划")
            smart_decision_confirm_plan_data = assert_route_action("route_smart_decision_confirm_plan", smart_decision_confirm_plan, "workflow_plan")
            assert_ok(
                "route_smart_decision_confirm_plan_has_plan",
                bool(smart_decision_confirm_plan_data.get("plan_id"))
                and smart_decision_confirm_plan_data.get("workflow") == "smart_resource_plan",
                json.dumps(smart_decision_confirm_plan_data, ensure_ascii=False)[:240],
            )
            smart_decision_best_detail = route(base_url, api_key, sessions[1], "先看详情")
            smart_decision_best_detail_data = assert_route_action("route_smart_decision_best_detail", smart_decision_best_detail, "pansou_best_detail")
            assert_ok(
                "route_smart_decision_best_detail_score_summary",
                isinstance(smart_decision_best_detail_data.get("score_summary"), dict),
                json.dumps(smart_decision_best_detail_data, ensure_ascii=False)[:240],
            )
            smart_decision_plan_after_detail = route(base_url, api_key, sessions[1], "计划")
            smart_decision_plan_after_detail_data = assert_route_action("route_smart_decision_plan_after_detail", smart_decision_plan_after_detail, "workflow_plan")
            assert_ok(
                "route_smart_decision_plan_after_detail_has_plan",
                bool(smart_decision_plan_after_detail_data.get("plan_id"))
                and smart_decision_plan_after_detail_data.get("workflow") == "smart_resource_plan",
                json.dumps(smart_decision_plan_after_detail_data, ensure_ascii=False)[:240],
            )
            smart_decision_detail_intent_session = f"{sessions[1]}-detail-intent"
            smart_decision_detail_intent = route(base_url, api_key, smart_decision_detail_intent_session, f"资源决策 {args.keyword} 详情")
            smart_decision_detail_intent_data = assert_route_action("route_smart_decision_detail_intent", smart_decision_detail_intent, "pansou_best_detail")
            assert_ok(
                "route_smart_decision_detail_intent_score_summary",
                isinstance(smart_decision_detail_intent_data.get("score_summary"), dict),
                json.dumps(smart_decision_detail_intent_data, ensure_ascii=False)[:240],
            )
            smart_search_detail_intent_session = f"{sessions[1]}-smart-detail-intent"
            smart_search_detail_intent = route(base_url, api_key, smart_search_detail_intent_session, f"智能搜索 {args.keyword} 详情")
            smart_search_detail_intent_data = assert_route_action("route_smart_search_detail_intent", smart_search_detail_intent, "pansou_best_detail")
            assert_ok(
                "route_smart_search_detail_intent_score_summary",
                isinstance(smart_search_detail_intent_data.get("score_summary"), dict),
                json.dumps(smart_search_detail_intent_data, ensure_ascii=False)[:240],
            )
            smart_decision_execute_intent_session = f"{sessions[1]}-execute-intent"
            smart_decision_execute_intent = route(base_url, api_key, smart_decision_execute_intent_session, f"资源决策 {args.keyword} 确认")
            smart_decision_execute_intent_data = assert_route_action("route_smart_decision_execute_intent", smart_decision_execute_intent, "execute_plan")
            assert_ok(
                "route_smart_decision_execute_intent_write_effect",
                smart_decision_execute_intent_data.get("write_effect") == "write"
                and bool(smart_decision_execute_intent_data.get("smart_execute_auto_selected")),
                json.dumps(smart_decision_execute_intent_data, ensure_ascii=False)[:240],
            )
            smart_shortcut_session = f"{sessions[1]}-shortcuts"
            assert_route_action(
                "route_smart_decision_shortcuts_start",
                route(base_url, api_key, smart_shortcut_session, f"资源决策 {args.keyword}"),
                "smart_resource_decision",
            )
            smart_decision_short_detail = route(base_url, api_key, smart_shortcut_session, "详情")
            smart_decision_short_detail_data = assert_route_action("route_smart_decision_short_detail", smart_decision_short_detail, "pansou_best_detail")
            assert_ok(
                "route_smart_decision_short_detail_score_summary",
                isinstance(smart_decision_short_detail_data.get("score_summary"), dict),
                json.dumps(smart_decision_short_detail_data, ensure_ascii=False)[:240],
            )
            assert_route_action(
                "route_smart_decision_short_plan_start",
                route(base_url, api_key, smart_shortcut_session, f"资源决策 {args.keyword}"),
                "smart_resource_decision",
            )
            smart_decision_short_plan = route(base_url, api_key, smart_shortcut_session, "计划")
            smart_decision_short_plan_data = assert_route_action("route_smart_decision_short_plan", smart_decision_short_plan, "workflow_plan")
            assert_ok(
                "route_smart_decision_short_plan_has_plan",
                bool(smart_decision_short_plan_data.get("plan_id"))
                and smart_decision_short_plan_data.get("workflow") == "smart_resource_plan",
                json.dumps(smart_decision_short_plan_data, ensure_ascii=False)[:240],
            )
            smart_search_best_plan = route(base_url, api_key, sessions[1], "计划最佳")
            smart_search_best_plan_data = assert_route_action("route_smart_search_best_plan", smart_search_best_plan, "workflow_plan")
            assert_ok(
                "route_smart_search_best_plan_has_plan",
                bool(smart_search_best_plan_data.get("plan_id"))
                and smart_search_best_plan_data.get("workflow") in {"smart_resource_plan", "pansou_best_plan", "hdhive_best_plan"},
                json.dumps(smart_search_best_plan_data, ensure_ascii=False)[:240],
            )
            smart_search_plan_recover = recover(base_url, api_key, sessions[1])
            smart_search_plan_recover_data = data(smart_search_plan_recover)
            assert_ok(
                "route_smart_search_plan_recover_priority",
                (smart_search_plan_recover_data.get("recovery") or {}).get("mode") == "resume_saved_plan"
                and (smart_search_plan_recover_data.get("recovery") or {}).get("recommended_action") == "execute_latest_plan",
                json.dumps(smart_search_plan_recover_data.get("recovery") or {}, ensure_ascii=False),
            )
            smart_plan = route(base_url, api_key, sessions[2], f"智能计划 {args.keyword}")
            smart_plan_data = assert_route_action("route_smart_plan", smart_plan, "workflow_plan")
            assert_ok(
                "route_smart_plan_has_plan",
                bool(smart_plan_data.get("plan_id")) and smart_plan_data.get("workflow") == "smart_resource_plan",
                json.dumps(smart_plan_data, ensure_ascii=False)[:240],
            )
            assert_ok(
                "route_smart_plan_best_candidate",
                isinstance(smart_plan_data.get("best_candidate"), dict)
                and bool((smart_plan_data.get("best_candidate") or {}).get("source_type"))
                and smart_plan_data.get("smart_plan_auto_selected") is True,
                json.dumps(smart_plan_data, ensure_ascii=False)[:240],
            )

            mp_search = route(base_url, api_key, sessions[1], f"MP搜索 {args.keyword}")
            mp_search_data = assert_route_action("route_mp_search", mp_search, "mp_media_search")
            mp_search_message = message_text(mp_search)
            mp_search_has_best = bool((mp_search_data.get("score_summary") or {}).get("best"))
            assert_ok(
                "route_mp_search_plan_hint",
                (
                    ("会先生成下载计划" in mp_search_message and "即可下载选中项" not in mp_search_message)
                    if mp_search_has_best
                    else ("暂未搜索到资源" in mp_search_message or "未搜索到资源" in mp_search_message)
                ),
                mp_search_message[:240],
            )
            assert_ok(
                "route_mp_search_score_summary",
                isinstance(((mp_search_data.get("score_summary") or {}).get("decision") or {}).get("recommended_commands"), list),
                json.dumps(mp_search_data.get("score_summary") or {}, ensure_ascii=False)[:240],
            )
            assert_ok(
                "route_mp_search_score_summary_compact_commands",
                bool((((mp_search_data.get("score_summary") or {}).get("decision") or {}).get("preferred_command")))
                and isinstance((((mp_search_data.get("score_summary") or {}).get("decision") or {}).get("compact_commands")), list),
                json.dumps((mp_search_data.get("score_summary") or {}).get("decision") or {}, ensure_ascii=False)[:240],
            )
            assert_ok(
                "route_mp_search_top_level_compact_commands",
                (
                    mp_search_data.get("command_source") == "score_summary"
                    and mp_search_data.get("preferred_command") == (((mp_search_data.get("score_summary") or {}).get("decision") or {}).get("preferred_command"))
                    and isinstance(mp_search_data.get("compact_commands"), list)
                    and mp_search_data.get("command_policy") == "read_then_confirm_write"
                    and mp_search_data.get("preferred_requires_confirmation") is False
                    and mp_search_data.get("fallback_requires_confirmation") is True
                ),
                json.dumps(mp_search_data, ensure_ascii=False)[:240],
            )

            mp_best = route(base_url, api_key, sessions[1], "最佳片源")
            mp_best_data = data(mp_best)
            if mp_search_has_best:
                mp_best_data = assert_route_action("route_mp_search_best", mp_best, "mp_search_best_detail")
                assert_ok(
                    "route_mp_search_best_score_summary",
                    bool((mp_best_data.get("score_summary") or {}).get("best"))
                    and bool(((mp_best_data.get("score_summary") or {}).get("decision") or {}).get("decision_hint")),
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
            else:
                assert_ok(
                    "route_mp_search_best_empty_ok",
                    mp_best.get("success") is False
                    and mp_best_data.get("action") == "mp_search_best_detail",
                    json.dumps(mp_best, ensure_ascii=False)[:240],
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

            download_history = route(base_url, api_key, sessions[4], f"记录{args.keyword}")
            download_history_data = assert_route_action("route_download_history_compact", download_history, "mp_download_history")
            download_history_recover = recover(base_url, api_key, sessions[4])
            download_history_recover_data = data(download_history_recover)
            assert_ok(
                "route_download_history_recover_priority",
                (download_history_recover_data.get("recovery") or {}).get("mode") == "continue_mp_download_history"
                and (download_history_recover_data.get("recovery") or {}).get("recommended_action") == "query_mp_lifecycle_status",
                json.dumps(download_history_recover_data.get("recovery") or {}, ensure_ascii=False),
            )

            lifecycle = route(base_url, api_key, sessions[4], f"状态{args.keyword}")
            lifecycle_data = assert_route_action("route_lifecycle_compact", lifecycle, "mp_lifecycle_status")
            lifecycle_recover = recover(base_url, api_key, sessions[4])
            lifecycle_recover_data = data(lifecycle_recover)
            assert_ok(
                "route_lifecycle_recover_priority",
                (lifecycle_recover_data.get("recovery") or {}).get("mode") == "continue_mp_lifecycle_status"
                and (lifecycle_recover_data.get("recovery") or {}).get("recommended_action") == "query_mp_download_history",
                json.dumps(lifecycle_recover_data.get("recovery") or {}, ensure_ascii=False),
            )

            smart_followup_keyword = route(base_url, api_key, sessions[4], f"跟进{args.keyword}")
            smart_followup_keyword_data = assert_route_action("route_smart_followup_keyword", smart_followup_keyword, "smart_followup")
            assert_ok(
                "route_smart_followup_keyword_resolved_lifecycle",
                smart_followup_keyword_data.get("resolved_followup_action") == "mp_lifecycle_status",
                json.dumps(smart_followup_keyword_data, ensure_ascii=False)[:240],
            )
            assert_ok(
                "route_smart_followup_keyword_compact_commands",
                bool(((smart_followup_keyword_data.get("followup_summary") or {}).get("preferred_command")))
                and isinstance(((smart_followup_keyword_data.get("followup_summary") or {}).get("compact_commands")), list),
                json.dumps(smart_followup_keyword_data.get("followup_summary") or {}, ensure_ascii=False)[:240],
            )

            ingest_status = route(base_url, api_key, sessions[4], f"入库{args.keyword}")
            ingest_status_data = assert_route_action("route_ingest_status_compact", ingest_status, "mp_ingest_status")
            assert_ok(
                "route_ingest_status_has_diagnosis",
                isinstance(ingest_status_data.get("diagnosis_summary"), dict)
                and bool((ingest_status_data.get("diagnosis_summary") or {}).get("stage"))
                and bool((((ingest_status_data.get("diagnosis_summary") or {}).get("followup_summary") or {}).get("label"))),
                json.dumps(ingest_status_data.get("diagnosis_summary") or {}, ensure_ascii=False)[:240],
            )

            transfer_failed = route(base_url, api_key, sessions[4], f"入库失败{args.keyword}")
            transfer_failed_data = assert_route_action("route_transfer_failed_compact", transfer_failed, "mp_ingest_failures")
            assert_ok(
                "route_transfer_failed_has_diagnosis",
                isinstance(transfer_failed_data.get("diagnosis_summary"), dict),
                json.dumps(transfer_failed_data.get("diagnosis_summary") or {}, ensure_ascii=False)[:240],
            )

            recent_ingest = route(base_url, api_key, sessions[4], "最近")
            recent_ingest_data = assert_route_action("route_recent_ingest_compact", recent_ingest, "mp_recent_activity")
            assert_ok(
                "route_recent_activity_has_transfer_history",
                isinstance((recent_ingest_data.get("transfer_history") or {}).get("items"), list),
                json.dumps(recent_ingest_data.get("transfer_history") or {}, ensure_ascii=False)[:240],
            )

            recent_download = route(base_url, api_key, sessions[4], "最近下载")
            recent_download_data = assert_route_action("route_recent_download_compact", recent_download, "mp_recent_activity")
            assert_ok(
                "route_recent_download_has_download_history",
                isinstance((recent_download_data.get("download_history") or {}).get("items"), list),
                json.dumps(recent_download_data.get("download_history") or {}, ensure_ascii=False)[:240],
            )

            local_diagnose = route(base_url, api_key, sessions[4], f"诊断{args.keyword}")
            local_diagnose_data = assert_route_action("route_local_diagnose_compact", local_diagnose, "mp_local_diagnose")
            assert_ok(
                "route_local_diagnose_has_diagnosis",
                isinstance(local_diagnose_data.get("diagnosis_summary"), dict),
                json.dumps(local_diagnose_data.get("diagnosis_summary") or {}, ensure_ascii=False)[:240],
            )
            assert_ok(
                "route_local_diagnose_ai_sample_worklist",
                isinstance((local_diagnose_data.get("ai_sample_worklist") or {}).get("items"), list),
                json.dumps(local_diagnose_data.get("ai_sample_worklist") or {}, ensure_ascii=False)[:240],
            )

            ai_failed_samples = route(base_url, api_key, sessions[4], f"失败样本 {args.keyword}")
            ai_failed_samples_data = assert_route_action("route_ai_failed_samples", ai_failed_samples, "ai_failed_samples", require_success=False)
            assert_ok(
                "route_ai_failed_samples_payload",
                isinstance(ai_failed_samples_data.get("items"), list),
                json.dumps(ai_failed_samples_data, ensure_ascii=False)[:240],
            )

            ai_worklist = route(base_url, api_key, sessions[4], f"工作清单 {args.keyword}")
            ai_worklist_data = assert_route_action("route_ai_sample_worklist", ai_worklist, "ai_sample_worklist", require_success=False)
            assert_ok(
                "route_ai_sample_worklist_payload",
                isinstance(ai_worklist_data.get("items"), list),
                json.dumps(ai_worklist_data, ensure_ascii=False)[:240],
            )
            ai_diagnose_short = route(base_url, api_key, sessions[4], "诊断")
            ai_diagnose_short_data = assert_route_action("route_ai_session_diagnose_short", ai_diagnose_short, "mp_local_diagnose", require_success=False)
            assert_ok(
                "route_ai_session_diagnose_short_ok",
                ai_diagnose_short_data.get("action") == "mp_local_diagnose",
                json.dumps(ai_diagnose_short_data, ensure_ascii=False)[:240],
            )
            ai_ingest_short = route(base_url, api_key, sessions[4], "入库状态")
            ai_ingest_short_data = assert_route_action("route_ai_session_ingest_short", ai_ingest_short, "mp_ingest_status", require_success=False)
            assert_ok(
                "route_ai_session_ingest_short_ok",
                ai_ingest_short_data.get("action") == "mp_ingest_status",
                json.dumps(ai_ingest_short_data, ensure_ascii=False)[:240],
            )

            ai_insights = route(base_url, api_key, sessions[4], f"样本洞察 {args.keyword}")
            ai_insights_data = assert_route_action("route_ai_sample_insights", ai_insights, "ai_sample_insights", require_success=False)
            assert_ok(
                "route_ai_sample_insights_payload",
                isinstance(ai_insights_data.get("insights"), dict),
                json.dumps(ai_insights_data, ensure_ascii=False)[:240],
            )

            ai_replay = route(base_url, api_key, sessions[4], "重放样本 1")
            ai_replay_data = assert_route_action("route_ai_replay_failed_sample", ai_replay, "ai_replay_failed_sample", require_success=False)
            if ai_replay.get("success"):
                assert_ok(
                    "route_ai_replay_failed_sample_plan",
                    bool(ai_replay_data.get("plan_id")) and ai_replay_data.get("workflow") == "ai_replay_failed_sample",
                    json.dumps(ai_replay_data, ensure_ascii=False)[:240],
                )
            else:
                assert_ok(
                    "route_ai_replay_failed_sample_empty_ok",
                    ai_replay_data.get("error_code") in {"sample_not_found", "missing_sample_index"},
                    json.dumps(ai_replay_data, ensure_ascii=False)[:240],
                )
            ai_replay_short = route(base_url, api_key, sessions[4], "重放 1")
            ai_replay_short_data = assert_route_action("route_ai_replay_short_command", ai_replay_short, "ai_replay_failed_sample", require_success=False)
            if ai_replay_short.get("success"):
                assert_ok(
                    "route_ai_replay_short_plan",
                    bool(ai_replay_short_data.get("plan_id")) and ai_replay_short_data.get("workflow") == "ai_replay_failed_sample",
                    json.dumps(ai_replay_short_data, ensure_ascii=False)[:240],
                )
                ai_replay_confirm = route(base_url, api_key, sessions[4], "确认")
                ai_replay_confirm_data = assert_route_action("route_ai_replay_confirm_short", ai_replay_confirm, "execute_plan", require_success=False)
                assert_ok(
                    "route_ai_replay_confirm_short_ok",
                    ai_replay_confirm_data.get("write_effect") == "write",
                    json.dumps(ai_replay_confirm_data, ensure_ascii=False)[:240],
                )
            else:
                assert_ok(
                    "route_ai_replay_short_empty_ok",
                    ai_replay_short_data.get("error_code") in {"sample_not_found", "missing_sample_index"},
                    json.dumps(ai_replay_short_data, ensure_ascii=False)[:240],
                )

            smart_followup_idle = route(base_url, api_key, sessions[4], "跟进")
            smart_followup_idle_data = assert_route_action("route_smart_followup_idle", smart_followup_idle, "smart_followup")
            assert_ok(
                "route_smart_followup_idle_recent_activity",
                smart_followup_idle_data.get("resolved_followup_action") == "mp_recent_activity",
                json.dumps(smart_followup_idle_data, ensure_ascii=False)[:240],
            )
            assert_ok(
                "route_smart_followup_idle_compact_commands",
                bool(((smart_followup_idle_data.get("followup_summary") or {}).get("preferred_command")))
                and isinstance(((smart_followup_idle_data.get("followup_summary") or {}).get("compact_commands")), list),
                json.dumps(smart_followup_idle_data.get("followup_summary") or {}, ensure_ascii=False)[:240],
            )
            assert_ok(
                "route_smart_followup_idle_top_level_compact_commands",
                (
                    smart_followup_idle_data.get("command_source") == "followup_summary"
                    and smart_followup_idle_data.get("preferred_command") == ((smart_followup_idle_data.get("followup_summary") or {}).get("preferred_command"))
                    and isinstance(smart_followup_idle_data.get("compact_commands"), list)
                    and smart_followup_idle_data.get("command_policy") == "safe_read_only"
                    and smart_followup_idle_data.get("preferred_requires_confirmation") is False
                ),
                json.dumps(smart_followup_idle_data, ensure_ascii=False)[:240],
            )

            movie_recommend = route(base_url, api_key, sessions[5], "热门电影")
            assert_route_action("route_recommend_movie", movie_recommend, "mp_recommendations")
            movie_message = message_text(movie_recommend)
            assert_ok("route_recommend_movie_type_filter", "| 电视剧 |" not in movie_message, movie_message[:240])
            movie_to_mp = route(base_url, api_key, sessions[5], "选择 1")
            movie_to_mp_data = data(movie_to_mp)
            if movie_to_mp.get("success"):
                movie_to_mp_data = assert_route_action("route_recommend_to_mp", movie_to_mp, "mp_media_search")
                assert_ok(
                    "route_recommend_to_mp_scored",
                    isinstance(((movie_to_mp_data.get("score_summary") or {}).get("decision") or {}).get("recommended_commands"), list),
                    json.dumps(movie_to_mp_data.get("score_summary") or {}, ensure_ascii=False)[:240],
                )
            else:
                assert_ok(
                    "route_recommend_to_mp_empty_ok",
                    movie_to_mp_data.get("action") == "mp_media_search"
                    and ("未识别到媒体信息" in message_text(movie_to_mp) or "搜索资源失败" in message_text(movie_to_mp)),
                    json.dumps(movie_to_mp, ensure_ascii=False)[:240],
                )
            movie_recommend_pansou = route(base_url, api_key, sessions[6], "热门电影")
            assert_route_action("route_recommend_movie_pansou_session", movie_recommend_pansou, "mp_recommendations")
            movie_to_pansou = route(base_url, api_key, sessions[6], "选择 1 盘搜")
            movie_to_pansou_data = assert_route_action("route_recommend_to_pansou", movie_to_pansou, "pansou_search")
            assert_ok(
                "route_recommend_to_pansou_scored",
                bool((movie_to_pansou_data.get("score_summary") or {}).get("best"))
                and isinstance(((movie_to_pansou_data.get("score_summary") or {}).get("decision") or {}).get("recommended_commands"), list),
                json.dumps(movie_to_pansou_data.get("score_summary") or {}, ensure_ascii=False)[:240],
            )
            smart_discovery = route(base_url, api_key, sessions[8], "智能发现 热门电影")
            assert_route_action("route_smart_discovery", smart_discovery, "mp_recommendations")
            recommend_to_decision = route(base_url, api_key, sessions[8], "选择 1 决策")
            recommend_to_decision_data = assert_route_action("route_recommend_to_decision", recommend_to_decision, "smart_resource_decision", require_success=False)
            assert_ok(
                "route_recommend_to_decision_payload",
                bool(recommend_to_decision_data.get("decision_mode"))
                and isinstance(recommend_to_decision_data.get("available_sources"), list)
                and isinstance(recommend_to_decision_data.get("blocked_sources"), list),
                json.dumps(recommend_to_decision_data, ensure_ascii=False)[:240],
            )
            smart_discovery_plan = route(base_url, api_key, sessions[9], "智能发现 热门电影")
            assert_route_action("route_smart_discovery_plan", smart_discovery_plan, "mp_recommendations")
            recommend_to_plan = route(base_url, api_key, sessions[9], "选择 1 计划")
            recommend_to_plan_data = data(recommend_to_plan)
            assert_ok(
                "route_recommend_to_plan",
                recommend_to_plan.get("success")
                and recommend_to_plan_data.get("action") in {"workflow_plan", "smart_resource_plan"},
                json.dumps(recommend_to_plan, ensure_ascii=False)[:240],
            )
            assert_ok(
                "route_recommend_to_plan_payload",
                bool(recommend_to_plan_data.get("plan_id")) and recommend_to_plan_data.get("workflow") == "smart_resource_plan",
                json.dumps(recommend_to_plan_data, ensure_ascii=False)[:240],
            )
            smart_discovery_execute = route(base_url, api_key, sessions[10], "智能发现 热门电影")
            assert_route_action("route_smart_discovery_execute", smart_discovery_execute, "mp_recommendations")
            recommend_to_execute = route(base_url, api_key, sessions[10], "选择 1 确认")
            recommend_to_execute_data = data(recommend_to_execute)
            assert_ok(
                "route_recommend_to_execute",
                recommend_to_execute_data.get("action") in {"smart_resource_execute", "execute_plan"}
                and recommend_to_execute_data.get("write_effect") == "write",
                json.dumps(recommend_to_execute, ensure_ascii=False)[:240],
            )
            assert_ok(
                "route_recommend_to_execute_payload",
                recommend_to_execute_data.get("write_effect") == "write",
                json.dumps(recommend_to_execute_data, ensure_ascii=False)[:240],
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
