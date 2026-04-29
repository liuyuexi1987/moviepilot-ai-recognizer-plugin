#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


CONFIG_PATH_DISPLAY = "~/.config/agent-resource-officer/config"
CONFIG_PATH = os.path.expanduser(CONFIG_PATH_DISPLAY)
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTERNAL_AGENT_GUIDE_PATH = os.path.join(SKILL_DIR, "EXTERNAL_AGENTS.md")
WORKBUDDY_GUIDE_PATH = EXTERNAL_AGENT_GUIDE_PATH
HELPER_VERSION = "0.1.18"
HELPER_COMMANDS = [
    "auto",
    "commands",
    "config-check",
    "decide",
    "doctor",
    "feishu-health",
    "readiness",
    "selftest",
    "startup",
    "selfcheck",
    "scoring-policy",
    "templates",
    "route",
    "pick",
    "preferences",
    "workflow",
    "plan-execute",
    "maintain",
    "recover",
    "session",
    "session-clear",
    "sessions",
    "sessions-clear",
    "history",
    "plans",
    "plans-clear",
    "raw",
    "version",
    "external-agent",
    "workbuddy",
]
WRITE_WORKFLOWS = {
    "pansou_transfer",
    "hdhive_unlock",
    "share_transfer",
    "mp_search_download",
    "mp_subscribe",
    "mp_subscribe_and_search",
}


def read_config():
    config = {}
    if not os.path.exists(CONFIG_PATH):
        return config
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as file_obj:
            for line in file_obj.read().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()
    except OSError:
        return {}
    return config


def config_value(config, *names):
    for name in names:
        value = os.environ.get(name) or config.get(name)
        if value:
            return value.strip()
    return ""


def config_source(config, *names):
    for name in names:
        if os.environ.get(name):
            return f"env:{name}"
        if config.get(name):
            return f"config:{name}"
    return ""


def load_json_arg(value):
    if not value:
        return {}
    if value.startswith("@"):
        with open(value[1:], "r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
            return data if isinstance(data, dict) else {}
    data = json.loads(value)
    return data if isinstance(data, dict) else {}


def external_agent_payload():
    prompt = (
        "你是外部智能体，通过 AgentResourceOfficer 控制 MoviePilot 资源工作流。"
        "不要直接调用影巢、115、夸克或盘搜原始 API。"
        "每个新会话先调用 startup 或 readiness；普通用户指令走 route；"
        "如果 preferences 未初始化，先询问并保存片源偏好；"
        "云盘和 PT 使用不同评分规则：云盘看质量/完整度/字幕/影巢积分，PT 看做种/促销/质量/字幕。"
        "编号选择走 pick；写入动作遵守 dry_run、plan_id、execute 的确认流程。"
        "输出时只展示用户需要选择或执行的信息，不回显 API Key、Cookie、Token。"
    )
    return {
        "success": True,
        "schema_version": "external_agent.v1",
        "helper_version": HELPER_VERSION,
        "guide_file": EXTERNAL_AGENT_GUIDE_PATH,
        "guide_file_exists": os.path.exists(EXTERNAL_AGENT_GUIDE_PATH),
        "recommended_recipe": "external_agent",
        "recipe_command": "python3 scripts/aro_request.py templates --recipe external_agent --compact",
        "startup_command": "python3 scripts/aro_request.py startup",
        "route_command": "python3 scripts/aro_request.py route --text '<用户原始指令>' --session 'agent:<会话ID>'",
        "pick_command": "python3 scripts/aro_request.py pick --choice <编号> --session 'agent:<会话ID>'",
        "compat_aliases": ["workbuddy"],
        "prompt": prompt,
        "tools": [
            {
                "name": "startup",
                "purpose": "检查插件状态、恢复建议和低 token recipe。",
                "command": "python3 scripts/aro_request.py startup",
                "writes": False,
            },
            {
                "name": "route_text",
                "purpose": "处理自然语言资源指令、链接转存、搜索和登录状态查询。",
                "command": "python3 scripts/aro_request.py route --text '<用户原始指令>' --session 'agent:<会话ID>'",
                "writes": "depends_on_route",
            },
            {
                "name": "pick_continue",
                "purpose": "继续编号选择、详情、审查、下一页等会话动作。",
                "command": "python3 scripts/aro_request.py pick --choice <编号> --session 'agent:<会话ID>'",
                "writes": "depends_on_choice",
            },
        ],
    }


def compact(data):
    if isinstance(data, dict):
        payload = data.get("data") if isinstance(data.get("data"), dict) else data
        keys = [
            "success",
            "message",
            "version",
            "ok",
            "action",
            "recommended_recipe",
            "selected_recipe",
            "requested_recipe",
            "invalid_recipe",
            "selected_names",
            "session",
            "session_id",
            "plan_id",
            "workflow",
            "plugin_version",
            "plugin_enabled",
            "services",
            "warnings",
            "defaults",
            "enabled",
            "running",
            "sdk_available",
            "app_id_configured",
            "app_secret_configured",
            "verification_token_configured",
            "allow_all",
            "reply_enabled",
            "allowed_chat_count",
            "allowed_user_count",
            "command_mode",
            "alias_count",
            "legacy_bridge_running",
            "conflict_warning",
            "ready_to_start",
            "safe_to_enable",
            "missing_requirements",
            "migration_hint",
            "recommended_action",
            "p115_ready",
            "p115_direct_ready",
            "hdhive_configured",
            "quark_configured",
            "quark_cookie_configured",
            "quark_cookie_valid",
            "default_target_path",
            "plan_auto_selected",
            "execute_plan_body",
            "executed",
            "removed",
            "removed_count",
            "cleared",
            "cleared_count",
            "cleared_session_ids",
            "matched",
            "remaining",
            "has_pending",
            "recommended_request_templates",
            "recommended_recipe_detail",
            "next_actions",
            "recovery",
            "scoring_policy",
            "preference_status",
            "score_summary",
            "preferences",
            "needs_onboarding",
            "initialized",
        ]
        out = {key: data.get(key) for key in ["success", "message"] if key in data}
        for key in keys:
            if key in payload:
                out[key] = payload.get(key)
        if out:
            return out
    return data


def data_payload(result):
    if isinstance(result, dict) and isinstance(result.get("data"), dict):
        return result.get("data")
    return result


def request(base_url, api_key, method, path, body=None, query=None):
    query_items = list((query or {}).items())
    query_items.append(("apikey", api_key))
    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    url = url + "?" + urllib.parse.urlencode(query_items)
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method.upper(), headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read()
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return {"raw": raw.decode("utf-8", errors="replace")}


def assistant_path(name):
    return f"/api/v1/plugin/AgentResourceOfficer/assistant/{name}"


def print_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def summary_command(summary, confirmed=False):
    summary = summary or {}
    requires_confirmation = bool(summary.get("requires_confirmation"))
    command = str(summary.get("execute_helper_command") or "").strip()
    if requires_confirmation and not confirmed:
        command = str(summary.get("inspect_helper_command") or command).strip()
    if not command:
        command = str(summary.get("inspect_helper_command") or "").strip()
    return command


def print_summary(summary, command_only=False, confirmed=False):
    if command_only:
        print(summary_command(summary, confirmed=confirmed))
        return
    print_json(summary)


def shell_quote(value):
    text = str(value or "")
    return "'" + text.replace("'", "'\"'\"'") + "'"


def recovery_helper_commands(recovery):
    recovery = recovery if isinstance(recovery, dict) else {}
    template = recovery.get("action_template") if isinstance(recovery.get("action_template"), dict) else {}
    body = template.get("body") if isinstance(template.get("body"), dict) else {}
    action_body = template.get("action_body") if isinstance(template.get("action_body"), dict) else {}
    name = str(template.get("name") or action_body.get("name") or "").strip()
    session = str(body.get("session") or action_body.get("session") or "").strip()
    session_id = str(body.get("session_id") or action_body.get("session_id") or "").strip()
    plan_id = str(body.get("plan_id") or action_body.get("plan_id") or "").strip()
    target_path = str(body.get("path") or action_body.get("path") or "").strip()

    session_part = f" --session {shell_quote(session)}" if session else ""
    session_id_part = f" --session-id {shell_quote(session_id)}" if session_id else ""
    plan_id_part = f" --plan-id {shell_quote(plan_id)}" if plan_id else ""
    path_part = f" --path {shell_quote(target_path)}" if target_path else ""

    inspect = None
    if session or session_id:
        inspect = (
            "python3 scripts/aro_request.py session"
            f"{session_part}{session_id_part}"
        )

    execute = None
    if name == "pick_hdhive_candidate":
        execute = (
            "python3 scripts/aro_request.py pick"
            f"{session_part}{session_id_part}{path_part} --choice <编号>"
        )
    elif name == "pick_hdhive_resource":
        execute = (
            "python3 scripts/aro_request.py pick"
            f"{session_part}{session_id_part}{path_part} --choice <资源编号>"
        )
    elif name == "pick_pansou_result":
        execute = (
            "python3 scripts/aro_request.py pick"
            f"{session_part}{session_id_part}{path_part} --choice <编号>"
        )
    elif name == "resume_pending_115":
        execute = (
            "python3 scripts/aro_request.py recover"
            f"{session_part}{session_id_part} --execute"
        )
    elif name in {"execute_plan", "execute_latest_plan", "execute_session_latest_plan"}:
        execute = (
            "python3 scripts/aro_request.py plan-execute"
            f"{session_part}{session_id_part}{plan_id_part}"
        )
    elif name == "inspect_session_state":
        execute = inspect

    return {
        "inspect_helper_command": inspect or "",
        "execute_helper_command": execute or "",
    }


def recovery_can_resume(recovery, helper_commands=None):
    recovery = recovery if isinstance(recovery, dict) else {}
    helper_commands = helper_commands if isinstance(helper_commands, dict) else recovery_helper_commands(recovery)
    mode = str(recovery.get("mode") or "").strip()
    if mode == "start_new":
        return False
    return bool(recovery.get("can_resume")) and bool(helper_commands.get("execute_helper_command"))


def request_templates_summary(data):
    payload = data_payload(data)
    detail = payload.get("recommended_recipe_detail") if isinstance(payload, dict) else {}
    first_call = detail.get("first_call") if isinstance(detail, dict) else {}
    return {
        "selected_recipe": payload.get("selected_recipe") or payload.get("recommended_recipe") or "",
        "recommended_recipe": payload.get("recommended_recipe") or "",
        "first_template": detail.get("first_template") or "",
        "first_endpoint": first_call.get("endpoint") or "",
        "first_method": first_call.get("method") or "",
        "requires_confirmation": bool(detail.get("confirmation_required_templates")),
        "confirmation_message": detail.get("confirmation_message") or "",
    }


def recipe_helper_commands(recipe_summary, recipe_request):
    recipe_summary = recipe_summary if isinstance(recipe_summary, dict) else {}
    recipe_request = str(recipe_request or "").strip()
    first_template = str(recipe_summary.get("first_template") or "").strip()
    first_method = str(recipe_summary.get("first_method") or "").strip().upper()
    first_endpoint = str(recipe_summary.get("first_endpoint") or "").strip()

    inspect = ""
    if recipe_request:
        inspect = (
            "python3 scripts/aro_request.py templates"
            f" --recipe {shell_quote(recipe_request)} --policy-only"
        )

    execute = ""
    if first_template == "startup_probe":
        execute = "python3 scripts/aro_request.py startup"
    elif first_template == "selfcheck_probe":
        execute = "python3 scripts/aro_request.py selfcheck"
    elif first_template == "maintain_preview":
        execute = "python3 scripts/aro_request.py maintain"
    elif first_template == "maintain_execute":
        execute = "python3 scripts/aro_request.py maintain --execute"
    elif first_template == "saved_plan_execute":
        execute = "python3 scripts/aro_request.py plan-execute"
    elif first_template == "pick_continue":
        execute = "python3 scripts/aro_request.py recover --execute"
    elif first_template == "workflow_dry_run":
        execute = "python3 scripts/aro_request.py workflow --workflow <workflow> --keyword <keyword>"
    elif first_endpoint:
        execute = f"# {first_method or 'CALL'} {first_endpoint}"

    return {
        "inspect_helper_command": inspect,
        "execute_helper_command": execute,
    }


def selftest_result():
    checks = []

    def check(name, condition):
        checks.append({"name": name, "ok": bool(condition)})

    start_new_recovery = {
        "mode": "start_new",
        "can_resume": True,
        "action_template": {
            "name": "start_pansou_search",
            "body": {"session": "empty", "session_id": "assistant::empty"},
        },
    }
    check("start_new_is_not_resumable", not recovery_can_resume(start_new_recovery))

    p115_recovery = {
        "mode": "resume_pending_115",
        "can_resume": True,
        "action_template": {
            "name": "resume_pending_115",
            "body": {"session": "s1", "session_id": "assistant::s1"},
        },
    }
    p115_commands = recovery_helper_commands(p115_recovery)
    check("resume_pending_115_is_resumable", recovery_can_resume(p115_recovery, p115_commands))
    check("resume_pending_115_execute_command", p115_commands.get("execute_helper_command") == "python3 scripts/aro_request.py recover --session 's1' --session-id 'assistant::s1' --execute")

    plan_recovery = {
        "mode": "execute_plan",
        "can_resume": True,
        "action_template": {
            "name": "execute_plan",
            "body": {"session": "s1", "plan_id": "plan-123"},
        },
    }
    plan_commands = recovery_helper_commands(plan_recovery)
    check("execute_plan_includes_plan_id", plan_commands.get("execute_helper_command") == "python3 scripts/aro_request.py plan-execute --session 's1' --plan-id 'plan-123'")

    bootstrap_commands = recipe_helper_commands({"first_template": "startup_probe"}, "bootstrap")
    check("bootstrap_execute_command", bootstrap_commands.get("execute_helper_command") == "python3 scripts/aro_request.py startup")
    check("bootstrap_inspect_command", bootstrap_commands.get("inspect_helper_command") == "python3 scripts/aro_request.py templates --recipe 'bootstrap' --policy-only")

    workflow_commands = recipe_helper_commands({"first_template": "workflow_dry_run"}, "plan")
    check("workflow_dry_run_command", workflow_commands.get("execute_helper_command") == "python3 scripts/aro_request.py workflow --workflow <workflow> --keyword <keyword>")
    maintain_commands = recipe_helper_commands({"first_template": "maintain_preview"}, "maintain")
    check("maintain_preview_command", maintain_commands.get("execute_helper_command") == "python3 scripts/aro_request.py maintain")
    maintain_execute_commands = recipe_helper_commands({"first_template": "maintain_execute"}, "maintain")
    check("maintain_execute_command", maintain_execute_commands.get("execute_helper_command") == "python3 scripts/aro_request.py maintain --execute")

    template_summary = request_templates_summary({
        "data": {
            "recommended_recipe": "bootstrap",
            "recommended_recipe_detail": {
                "first_template": "startup_probe",
                "first_call": {"endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/startup", "method": "GET"},
                "confirmation_required_templates": ["saved_plan_execute"],
                "confirmation_message": "需要确认",
            },
        },
    })
    check("templates_summary_recipe", template_summary.get("recommended_recipe") == "bootstrap")
    check("templates_summary_first_call", template_summary.get("first_template") == "startup_probe" and template_summary.get("first_method") == "GET")
    check("templates_summary_confirmation", template_summary.get("requires_confirmation") is True and template_summary.get("confirmation_message") == "需要确认")

    confirm_summary = {
        "requires_confirmation": True,
        "inspect_helper_command": "inspect",
        "execute_helper_command": "execute",
    }
    check("command_only_requires_confirmation", summary_command(confirm_summary) == "inspect")
    check("command_only_confirmed_executes", summary_command(confirm_summary, confirmed=True) == "execute")
    no_confirm_summary = {
        "requires_confirmation": False,
        "inspect_helper_command": "inspect",
        "execute_helper_command": "execute",
    }
    check("command_only_without_confirmation_executes", summary_command(no_confirm_summary) == "execute")

    quote_value = shell_quote("a'b")
    check("shell_quote_single_quote", quote_value == "'a'\"'\"'b'")

    compact_workflow = compact({
        "success": True,
        "data": {
            "action": "workflow_plan",
            "plan_id": "plan-123",
            "workflow": "hdhive_candidates",
            "execute_plan_body": {"plan_id": "plan-123"},
        },
    })
    check("compact_preserves_plan_id", compact_workflow.get("plan_id") == "plan-123")
    check("compact_preserves_execute_plan_body", (compact_workflow.get("execute_plan_body") or {}).get("plan_id") == "plan-123")
    compact_clear = compact({
        "success": True,
        "data": {
            "action": "plans_clear",
            "removed": 1,
            "remaining": 0,
        },
    })
    check("compact_preserves_plan_clear_counts", compact_clear.get("removed") == 1 and compact_clear.get("remaining") == 0)
    compact_feishu = compact({
        "success": True,
        "message": "feishu",
        "data": {
            "plugin_version": "0.1.110",
            "enabled": False,
            "running": False,
            "sdk_available": True,
            "legacy_bridge_running": True,
            "conflict_warning": False,
        },
    })
    check("compact_preserves_feishu_health", compact_feishu.get("plugin_version") == "0.1.110" and compact_feishu.get("legacy_bridge_running") is True)

    external_agent = external_agent_payload()
    check("external_agent_payload_has_prompt", bool(external_agent.get("prompt")))
    check("external_agent_payload_has_guide", external_agent.get("guide_file_exists") is True)
    check("external_agent_payload_has_tools", len(external_agent.get("tools") or []) == 3)

    catalog = commands_catalog()
    catalog_commands = catalog.get("commands") or []
    catalog_names = {item.get("name") for item in catalog_commands}
    check("helper_version_present", catalog.get("helper_version") == HELPER_VERSION)
    check("commands_schema_version", catalog.get("schema_version") == "commands.v1")
    check("commands_catalog_includes_version", "version" in catalog_names)
    check("commands_catalog_includes_external_agent", "external-agent" in catalog_names)
    check("commands_catalog_includes_workbuddy_alias", "workbuddy" in catalog_names)
    check("commands_catalog_complete", catalog_names == set(HELPER_COMMANDS))
    check("commands_writes_are_boolean", all(isinstance(item.get("writes"), bool) for item in catalog_commands))
    check("commands_have_write_condition", all("write_condition" in item for item in catalog_commands))
    workflow_entry = next((item for item in catalog_commands if item.get("name") == "workflow"), {})
    check("workflow_catalog_marks_plan_write", workflow_entry.get("writes") is True and "plan" in workflow_entry.get("write_condition", ""))
    check("commands_recommended_start", catalog.get("recommended_start") == "python3 scripts/aro_request.py decide --summary-only")

    passed = sum(1 for item in checks if item.get("ok"))
    failed = [item for item in checks if not item.get("ok")]
    result = {
        "success": not failed,
        "passed": passed,
        "failed": len(failed),
        "checks": checks,
    }
    return result


def run_selftest():
    result = selftest_result()
    print_json(result)
    return 0 if result.get("success") else 1


def commands_catalog():
    return {
        "success": True,
        "schema_version": "commands.v1",
        "helper_version": HELPER_VERSION,
        "recommended_start": "python3 scripts/aro_request.py decide --summary-only",
        "commands": [
            {"name": "version", "network": False, "writes": False, "write_condition": "", "purpose": "print local helper version"},
            {"name": "external-agent", "network": False, "writes": False, "write_condition": "", "purpose": "print external agent connection prompt and minimal tool contract"},
            {"name": "workbuddy", "network": False, "writes": False, "write_condition": "", "purpose": "compatibility alias for external-agent"},
            {"name": "commands", "network": False, "writes": False, "write_condition": "", "purpose": "print local helper command catalog"},
            {"name": "config-check", "network": False, "writes": False, "write_condition": "", "purpose": "check local connection settings without printing secrets"},
            {"name": "selftest", "network": False, "writes": False, "write_condition": "", "purpose": "test local helper decision and command generation logic"},
            {"name": "readiness", "network": True, "writes": False, "write_condition": "", "purpose": "run config-check, selftest, and live plugin selfcheck"},
            {"name": "startup", "network": True, "writes": False, "write_condition": "", "purpose": "inspect assistant startup state and recommended recipe"},
            {"name": "selfcheck", "network": True, "writes": False, "write_condition": "", "purpose": "run live AgentResourceOfficer protocol health check"},
            {"name": "scoring-policy", "network": True, "writes": False, "write_condition": "", "purpose": "read plugin-owned cloud/PT scoring rules and hard gates"},
            {"name": "templates", "network": True, "writes": False, "write_condition": "", "purpose": "fetch low-token assistant request templates by recipe or name"},
            {"name": "decide", "network": True, "writes": False, "write_condition": "", "purpose": "choose continue_session or start_recipe and return next helper command"},
            {"name": "doctor", "network": True, "writes": False, "write_condition": "", "purpose": "return startup, selfcheck, sessions, and recovery snapshot"},
            {"name": "feishu-health", "network": True, "writes": False, "write_condition": "", "purpose": "inspect AgentResourceOfficer built-in Feishu Channel status"},
            {"name": "auto", "network": True, "writes": False, "write_condition": "", "purpose": "follow startup recommended recipe and return request template summary"},
            {"name": "recover", "network": True, "writes": True, "write_condition": "only with --execute", "purpose": "inspect or execute the recommended recovery action"},
            {"name": "route", "network": True, "writes": True, "write_condition": "depends on text and routed action", "purpose": "route natural-language resource requests"},
            {"name": "pick", "network": True, "writes": True, "write_condition": "depends on current session and selected action", "purpose": "continue numbered choices or actions"},
            {"name": "preferences", "network": True, "writes": True, "write_condition": "only with --preferences-json or --reset", "purpose": "read/save/reset source preferences used by cloud and PT scoring"},
            {"name": "workflow", "network": True, "writes": True, "write_condition": "read workflows execute directly; write workflows save a dry-run plan by default", "purpose": "run or plan preset assistant workflows"},
            {"name": "plan-execute", "network": True, "writes": True, "write_condition": "always executes a saved plan; use --plan-id for exact execution", "purpose": "execute a saved plan by plan_id or latest unexecuted session plan"},
            {"name": "maintain", "network": True, "writes": True, "write_condition": "only with --execute", "purpose": "preview or execute low-risk maintenance"},
            {"name": "session", "network": True, "writes": False, "write_condition": "", "purpose": "inspect one assistant session"},
            {"name": "session-clear", "network": True, "writes": True, "write_condition": "clears exactly one assistant session by --session or --session-id", "purpose": "clear one assistant session, including abandoned pending 115 state"},
            {"name": "sessions", "network": True, "writes": False, "write_condition": "", "purpose": "list recent assistant sessions"},
            {"name": "sessions-clear", "network": True, "writes": True, "write_condition": "clears assistant sessions matching --session, --session-id, --kind, --has-pending-p115, --stale-only, or --all-sessions", "purpose": "bulk clear assistant sessions"},
            {"name": "history", "network": True, "writes": False, "write_condition": "", "purpose": "list recent assistant execution history"},
            {"name": "plans", "network": True, "writes": False, "write_condition": "", "purpose": "list saved workflow plans"},
            {"name": "plans-clear", "network": True, "writes": True, "write_condition": "clears saved plans matching --plan-id, session filters, --executed, or --all-plans", "purpose": "clear saved workflow plans"},
            {"name": "raw", "network": True, "writes": True, "write_condition": "depends on method, path, and JSON body", "purpose": "call a raw assistant endpoint for debugging"},
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="AgentResourceOfficer request helper")
    parser.add_argument(
        "command",
        choices=HELPER_COMMANDS,
    )
    parser.add_argument("--base-url")
    parser.add_argument("--api-key")
    parser.add_argument("--recipe")
    parser.add_argument("--names")
    parser.add_argument("--include-templates", action="store_true")
    parser.add_argument("--policy-only", action="store_true")
    parser.add_argument("--text")
    parser.add_argument("--session")
    parser.add_argument("--session-id")
    parser.add_argument("--plan-id")
    parser.add_argument("--kind")
    parser.add_argument("--has-pending-p115", action="store_true")
    parser.add_argument("--choice", type=int)
    parser.add_argument("--action")
    parser.add_argument("--path", dest="target_path")
    parser.add_argument("--workflow", default="hdhive_candidates")
    parser.add_argument("--keyword")
    parser.add_argument("--media-type", default="auto")
    parser.add_argument("--mode", default="")
    parser.add_argument("--source", default="")
    parser.add_argument("--preferences-json")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--executed", action="store_true")
    parser.add_argument("--unexecuted", action="store_true")
    parser.add_argument("--all-plans", action="store_true")
    parser.add_argument("--stale-only", action="store_true")
    parser.add_argument("--all-sessions", action="store_true")
    parser.add_argument("--include-actions", action="store_true")
    parser.add_argument("--prefer-unexecuted", action="store_true")
    parser.add_argument("--include-raw-results", action="store_true")
    parser.add_argument("--method", default="GET")
    parser.add_argument("--api-path")
    parser.add_argument("--json", dest="json_body")
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compatibility no-op; compact output is the default unless --full is used.",
    )
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--command-only", action="store_true")
    parser.add_argument("--confirmed", action="store_true")
    args = parser.parse_args()

    if args.executed and args.unexecuted:
        print("--executed and --unexecuted cannot be used together", file=sys.stderr)
        return 2

    if args.command == "commands":
        print_json(commands_catalog())
        return 0
    if args.command == "version":
        print_json({"success": True, "helper_version": HELPER_VERSION})
        return 0
    if args.command in {"external-agent", "workbuddy"}:
        if args.full and os.path.exists(EXTERNAL_AGENT_GUIDE_PATH):
            with open(EXTERNAL_AGENT_GUIDE_PATH, "r", encoding="utf-8") as file_obj:
                print(file_obj.read())
        else:
            print_json(external_agent_payload())
        return 0

    if args.command == "selftest":
        return run_selftest()

    config = read_config()
    base_url = args.base_url or config_value(config, "ARO_BASE_URL", "MP_BASE_URL", "MOVIEPILOT_URL")
    api_key = args.api_key or config_value(config, "ARO_API_KEY", "MP_API_TOKEN")
    if args.command == "config-check":
        result = {
            "success": bool(base_url and api_key),
            "config_path": CONFIG_PATH_DISPLAY,
            "config_file_exists": os.path.exists(CONFIG_PATH),
            "base_url_set": bool(base_url),
            "base_url_source": "arg:--base-url" if args.base_url else config_source(config, "ARO_BASE_URL", "MP_BASE_URL", "MOVIEPILOT_URL"),
            "api_key_set": bool(api_key),
            "api_key_source": "arg:--api-key" if args.api_key else config_source(config, "ARO_API_KEY", "MP_API_TOKEN"),
        }
        print_json(result)
        return 0 if result["success"] else 2
    if args.command == "readiness":
        config_result = {
            "success": bool(base_url and api_key),
            "config_path": CONFIG_PATH_DISPLAY,
            "config_file_exists": os.path.exists(CONFIG_PATH),
            "base_url_set": bool(base_url),
            "base_url_source": "arg:--base-url" if args.base_url else config_source(config, "ARO_BASE_URL", "MP_BASE_URL", "MOVIEPILOT_URL"),
            "api_key_set": bool(api_key),
            "api_key_source": "arg:--api-key" if args.api_key else config_source(config, "ARO_API_KEY", "MP_API_TOKEN"),
        }
        local_result = selftest_result()
        live_result = {"success": False, "skipped": True, "reason": "missing config"}
        if config_result["success"]:
            try:
                live_response = request(base_url, api_key, "GET", assistant_path("selfcheck"))
                live_compact = compact(live_response)
                live_result = {
                    "success": bool((live_compact or {}).get("ok") or (live_compact or {}).get("success")),
                    "skipped": False,
                    "version": (live_compact or {}).get("version") or "",
                    "message": (live_compact or {}).get("message") or "",
                }
            except Exception as exc:
                live_result = {"success": False, "skipped": False, "reason": str(exc)}
        result = {
            "success": bool(config_result["success"] and local_result["success"] and live_result["success"]),
            "helper_version": HELPER_VERSION,
            "config": config_result,
            "local_selftest": {
                "success": local_result["success"],
                "passed": local_result["passed"],
                "failed": local_result["failed"],
            },
            "live_selfcheck": live_result,
        }
        print_json(result)
        return 0 if result["success"] else 2
    if not base_url:
        print("ARO_BASE_URL / MP_BASE_URL / MOVIEPILOT_URL is not set", file=sys.stderr)
        return 2
    if not api_key:
        print("ARO_API_KEY / MP_API_TOKEN is not set", file=sys.stderr)
        return 2

    method = "GET"
    path = assistant_path("startup")
    body = None
    query = {}

    if args.command == "auto":
        startup = request(base_url, api_key, "GET", assistant_path("startup"))
        startup_data = data_payload(startup)
        recommended = startup_data.get("recommended_request_templates") if isinstance(startup_data, dict) else {}
        tool_args = recommended.get("tool_args") if isinstance(recommended, dict) else {}
        recipe = (tool_args or {}).get("recipe") or args.recipe or "bootstrap"
        templates = request(
            base_url,
            api_key,
            "POST",
            assistant_path("request_templates"),
            body={
                "recipe": recipe,
                "include_templates": bool(args.include_templates and not args.policy_only),
            },
        )
        output = {
            "startup": compact(startup),
            "request_templates": compact(templates),
        }
        if (args.summary_only or args.command_only) and not args.full:
            summary = {
                "startup_ok": bool((output.get("startup") or {}).get("success")),
                "recommended_recipe_request": (recommended or {}).get("recipe") or recipe,
                "recommended_recipe_reason": (recommended or {}).get("reason") or "",
                **request_templates_summary(templates),
                **recipe_helper_commands(request_templates_summary(templates), (recommended or {}).get("recipe") or recipe),
            }
            print_summary(summary, command_only=args.command_only, confirmed=args.confirmed)
            return 0
        print_json(output if not args.full else {"startup": startup, "request_templates": templates})
        return 0

    if args.command == "doctor":
        startup = request(base_url, api_key, "GET", assistant_path("startup"))
        selfcheck = request(base_url, api_key, "GET", assistant_path("selfcheck"))
        sessions = request(
            base_url,
            api_key,
            "GET",
            assistant_path("sessions"),
            query={
                "compact": "true",
                "limit": str(args.limit),
                **({"kind": args.kind} if args.kind else {}),
                **({"has_pending_p115": "true"} if args.has_pending_p115 else {}),
            },
        )
        recover_query = {
            "compact": "true",
            "limit": str(args.limit),
        }
        if args.session:
            recover_query["session"] = args.session
        if args.session_id:
            recover_query["session_id"] = args.session_id
        recover = request(
            base_url,
            api_key,
            "GET",
            assistant_path("recover"),
            query=recover_query,
        )
        output = {
            "startup": compact(startup),
            "selfcheck": compact(selfcheck),
            "sessions": compact(sessions),
            "recover": compact(recover),
        }
        helper_commands = recovery_helper_commands(((output.get("recover") or {}).get("recovery") or {}))
        output["helper_commands"] = helper_commands
        summary = {
            "startup_ok": bool((output.get("startup") or {}).get("success")),
            "selfcheck_ok": bool((output.get("selfcheck") or {}).get("ok")),
            "recovery_can_resume": recovery_can_resume(((output.get("recover") or {}).get("recovery") or {}), helper_commands),
            "requires_confirmation": recovery_can_resume(((output.get("recover") or {}).get("recovery") or {}), helper_commands),
            "recommended_action": ((output.get("recover") or {}).get("recovery") or {}).get("recommended_action") or "",
            "recommended_tool": ((output.get("recover") or {}).get("recovery") or {}).get("recommended_tool") or "",
            **helper_commands,
        }
        output["summary"] = summary
        if (args.summary_only or args.command_only) and not args.full:
            print_summary(summary, command_only=args.command_only, confirmed=args.confirmed)
            return 0
        if not args.full:
            output["summary"] = summary
        print_json(output if not args.full else {
            "startup": startup,
            "selfcheck": selfcheck,
            "sessions": sessions,
            "recover": recover,
        })
        return 0

    if args.command == "decide":
        startup = request(base_url, api_key, "GET", assistant_path("startup"))
        recover = request(
            base_url,
            api_key,
            "GET",
            assistant_path("recover"),
            query={
                "compact": "true",
                "limit": str(args.limit),
                **({"session": args.session} if args.session else {}),
                **({"session_id": args.session_id} if args.session_id else {}),
            },
        )
        startup_compact = compact(startup)
        recover_compact = compact(recover)
        recover_data = ((recover_compact or {}).get("recovery") or {}) if isinstance(recover_compact, dict) else {}
        helper_commands = recovery_helper_commands(recover_data)
        if recovery_can_resume(recover_data, helper_commands):
            summary = {
                "decision": "continue_session",
                "startup_ok": bool((startup_compact or {}).get("success")),
                "can_resume": True,
                "mode": recover_data.get("mode") or "",
                "reason": recover_data.get("reason") or "",
                "recommended_action": recover_data.get("recommended_action") or "",
                "recommended_tool": recover_data.get("recommended_tool") or "",
                "requires_confirmation": True,
                **helper_commands,
            }
            if (args.summary_only or args.command_only) and not args.full:
                print_summary(summary, command_only=args.command_only, confirmed=args.confirmed)
                return 0
            print_json({
                "summary": summary,
                "startup": startup_compact,
                "recover": recover_compact,
            } if not args.full else {
                "summary": summary,
                "startup": startup,
                "recover": recover,
            })
            return 0

        startup_data = data_payload(startup)
        recommended = startup_data.get("recommended_request_templates") if isinstance(startup_data, dict) else {}
        tool_args = recommended.get("tool_args") if isinstance(recommended, dict) else {}
        scoped_session = bool(args.session or args.session_id)
        recipe = args.recipe or ("bootstrap" if scoped_session else ((tool_args or {}).get("recipe") or "bootstrap"))
        templates = request(
            base_url,
            api_key,
            "POST",
            assistant_path("request_templates"),
            body={
                "recipe": recipe,
                "include_templates": bool(args.include_templates and not args.policy_only),
            },
        )
        template_summary = request_templates_summary(templates)
        helper_commands = recipe_helper_commands(template_summary, recipe)
        summary = {
            "decision": "start_recipe",
            "startup_ok": bool((startup_compact or {}).get("success")),
            "can_resume": False,
            "recommended_recipe_request": recipe,
            "recommended_recipe_reason": (
                f"使用指定 recipe：{args.recipe}。"
                if args.recipe
                else "指定会话没有可恢复状态，使用 bootstrap。"
                if scoped_session
                else ((recommended or {}).get("reason") or "")
            ),
            **template_summary,
            **helper_commands,
        }
        if (args.summary_only or args.command_only) and not args.full:
            print_summary(summary, command_only=args.command_only, confirmed=args.confirmed)
            return 0
        print_json({
            "summary": summary,
            "startup": startup_compact,
            "recover": recover_compact,
            "request_templates": compact(templates),
        } if not args.full else {
            "summary": summary,
            "startup": startup,
            "recover": recover,
            "request_templates": templates,
        })
        return 0

    if args.command == "startup":
        path = assistant_path("startup")
    elif args.command == "selfcheck":
        path = assistant_path("selfcheck")
    elif args.command == "scoring-policy":
        path = assistant_path("capabilities")
        query = {"compact": "true"}
    elif args.command == "feishu-health":
        path = "/api/v1/plugin/AgentResourceOfficer/feishu/health"
    elif args.command == "templates":
        method = "POST"
        path = assistant_path("request_templates")
        body = {
            "include_templates": bool(args.include_templates and not args.policy_only),
        }
        if args.recipe:
            body["recipe"] = args.recipe
        if args.names:
            body["names"] = args.names
    elif args.command == "route":
        method = "POST"
        path = assistant_path("route")
        body = {
            "text": args.text or "",
            "compact": True,
        }
        if args.session:
            body["session"] = args.session
        if args.session_id:
            body["session_id"] = args.session_id
        if args.target_path:
            body["path"] = args.target_path
    elif args.command == "pick":
        method = "POST"
        path = assistant_path("pick")
        body = {
            "compact": True,
        }
        if args.session:
            body["session"] = args.session
        if args.session_id:
            body["session_id"] = args.session_id
        if args.choice is not None:
            body["choice"] = args.choice
        if args.action:
            body["action"] = args.action
        if args.mode:
            body["mode"] = args.mode
        if args.target_path:
            body["path"] = args.target_path
    elif args.command == "preferences":
        method = "DELETE" if args.reset else "POST" if args.preferences_json else "GET"
        path = assistant_path("preferences")
        if method == "GET":
            query = {"compact": "true"}
            if args.session:
                query["session"] = args.session
            if args.session_id:
                query["session_id"] = args.session_id
        else:
            body = {"compact": True}
            if args.session:
                body["session"] = args.session
            if args.session_id:
                body["session_id"] = args.session_id
            if args.preferences_json:
                body["preferences"] = load_json_arg(args.preferences_json)
    elif args.command == "workflow":
        method = "POST"
        path = assistant_path("workflow")
        body = {
            "workflow": args.workflow,
            "name": args.workflow,
            "keyword": args.keyword or "",
            "media_type": args.media_type,
            "mode": args.mode or "",
            "choice": args.choice,
            "path": args.target_path or "",
            "source": args.source or "",
            "limit": args.limit,
            "dry_run": args.workflow in WRITE_WORKFLOWS,
            "compact": True,
        }
        if args.session:
            body["session"] = args.session
        if args.session_id:
            body["session_id"] = args.session_id
    elif args.command == "plan-execute":
        method = "POST"
        path = assistant_path("plan/execute")
        body = {
            "prefer_unexecuted": True,
            "compact": True,
        }
        if args.plan_id:
            body["plan_id"] = args.plan_id
        if args.session:
            body["session"] = args.session
        if args.session_id:
            body["session_id"] = args.session_id
    elif args.command == "maintain":
        method = "POST" if args.execute else "GET"
        path = assistant_path("maintain")
        if args.execute:
            body = {
                "execute": True,
                "limit": args.limit,
            }
        else:
            query = {
                "limit": str(args.limit),
            }
    elif args.command == "recover":
        method = "POST" if args.execute else "GET"
        path = assistant_path("recover")
        if args.execute:
            body = {
                "compact": True,
            }
            if args.session:
                body["session"] = args.session
            if args.session_id:
                body["session_id"] = args.session_id
            if args.prefer_unexecuted:
                body["prefer_unexecuted"] = True
            if args.include_raw_results:
                body["include_raw_results"] = True
        else:
            query = {
                "compact": "true",
            }
            if args.session:
                query["session"] = args.session
            if args.session_id:
                query["session_id"] = args.session_id
            if args.limit:
                query["limit"] = str(args.limit)
    elif args.command == "session":
        path = assistant_path("session")
        query = {
            "compact": "true",
        }
        if args.session:
            query["session"] = args.session
        if args.session_id:
            query["session_id"] = args.session_id
    elif args.command == "session-clear":
        method = "POST"
        path = assistant_path("session/clear")
        body = {
            "compact": True,
        }
        if args.session:
            body["session"] = args.session
        if args.session_id:
            body["session_id"] = args.session_id
    elif args.command == "sessions":
        path = assistant_path("sessions")
        query = {
            "compact": "true",
            "limit": str(args.limit),
        }
        if args.kind:
            query["kind"] = args.kind
        if args.has_pending_p115:
            query["has_pending_p115"] = "true"
    elif args.command == "sessions-clear":
        method = "POST"
        path = assistant_path("sessions/clear")
        body = {
            "limit": args.limit,
        }
        if args.session:
            body["session"] = args.session
        if args.session_id:
            body["session_id"] = args.session_id
        if args.kind:
            body["kind"] = args.kind
        if args.has_pending_p115:
            body["has_pending_p115"] = True
        if args.stale_only:
            body["stale_only"] = True
        if args.all_sessions:
            body["all_sessions"] = True
    elif args.command == "history":
        path = assistant_path("history")
        query = {
            "compact": "true",
            "limit": str(args.limit),
        }
        if args.session:
            query["session"] = args.session
        if args.session_id:
            query["session_id"] = args.session_id
    elif args.command == "plans":
        path = assistant_path("plans")
        query = {
            "compact": "true",
            "limit": str(args.limit),
        }
        if args.plan_id:
            query["plan_id"] = args.plan_id
        if args.session:
            query["session"] = args.session
        if args.session_id:
            query["session_id"] = args.session_id
        if args.executed:
            query["executed"] = "true"
        if args.unexecuted:
            query["executed"] = "false"
        if args.include_actions:
            query["include_actions"] = "true"
    elif args.command == "plans-clear":
        method = "POST"
        path = assistant_path("plans/clear")
        body = {
            "limit": args.limit,
        }
        if args.plan_id:
            body["plan_id"] = args.plan_id
        if args.session:
            body["session"] = args.session
        if args.session_id:
            body["session_id"] = args.session_id
        if args.executed:
            body["executed"] = True
        if args.unexecuted:
            body["executed"] = False
        if args.all_plans:
            body["all_plans"] = True
    elif args.command == "raw":
        method = args.method
        path = args.api_path or assistant_path("startup")
        body = load_json_arg(args.json_body) if args.json_body else None

    result = request(base_url, api_key, method, path, body=body, query=query)
    if args.command == "recover" and (args.summary_only or args.command_only) and not args.full:
        output = compact(result)
        recovery = ((output or {}).get("recovery") or {}) if isinstance(output, dict) else {}
        helper_commands = recovery_helper_commands(recovery)
        summary = {
            "success": bool((output or {}).get("success")),
            "can_resume": recovery_can_resume(recovery, helper_commands),
            "mode": recovery.get("mode") or "",
            "reason": recovery.get("reason") or "",
            "recommended_action": recovery.get("recommended_action") or "",
            "recommended_tool": recovery.get("recommended_tool") or "",
            "requires_confirmation": recovery_can_resume(recovery, helper_commands),
            **helper_commands,
        }
        print_summary(summary, command_only=args.command_only, confirmed=args.confirmed)
        return 0
    output = result if args.full else compact(result)
    print_json(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
