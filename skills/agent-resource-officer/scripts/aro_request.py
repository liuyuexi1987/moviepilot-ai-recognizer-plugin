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
HELPER_VERSION = "0.1.40"
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
    "followup",
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
    "mp_download_control",
    "mp_subscribe",
    "mp_subscribe_control",
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


def normalize_command_args(args):
    extra = list(getattr(args, "extra", []) or [])
    command = str(getattr(args, "command", "") or "").strip()

    if command == "route":
        if not getattr(args, "text", None) and extra:
            args.text = " ".join(extra).strip()
    elif command == "pick":
        if getattr(args, "choice", None) is None and extra:
            first = extra.pop(0)
            try:
                args.choice = int(str(first).strip())
            except (TypeError, ValueError):
                if not getattr(args, "action", None):
                    args.action = str(first).strip()
        if not getattr(args, "action", None) and extra:
            args.action = " ".join(str(item).strip() for item in extra if str(item).strip()).strip()
    elif command == "plan-execute":
        if not getattr(args, "plan_id", None) and extra:
            args.plan_id = str(extra[0]).strip()
    elif command == "followup":
        if not getattr(args, "plan_id", None) and extra:
            first = str(extra[0]).strip()
            if first.startswith("plan-"):
                args.plan_id = first
    elif command == "workflow":
        if getattr(args, "workflow", "hdhive_candidates") == "hdhive_candidates" and extra:
            args.workflow = str(extra.pop(0)).strip() or args.workflow
        if not getattr(args, "keyword", None) and extra:
            args.keyword = " ".join(str(item).strip() for item in extra if str(item).strip()).strip()
    elif command in {"session", "session-clear", "history"}:
        if not getattr(args, "session", None) and extra:
            args.session = str(extra[0]).strip()
    elif command in {"plans", "plans-clear"}:
        if not getattr(args, "plan_id", None) and extra:
            first = str(extra[0]).strip()
            if first.startswith("plan-"):
                args.plan_id = first

    return args


def external_agent_payload():
    prompt = (
        "你是外部智能体，通过 AgentResourceOfficer 控制 MoviePilot 资源工作流。"
        "不要直接调用影巢、115、夸克或盘搜原始 API。"
        "每个新会话先调用 startup 或 readiness；普通用户指令走 route；"
        "如果 preferences 未初始化，先询问并保存片源偏好；"
        "搜索某个具体片名时，优先用智能搜索统一决策，不要自己轮询盘搜、影巢和 MP/PT。"
        "如果需要一步得到更明确的下一步建议，优先用资源决策。"
        "云盘和 PT 使用不同评分规则：云盘看质量/完整度/字幕/影巢积分，PT 看做种/促销/质量/字幕。"
        "编号选择走 pick；写入动作遵守 dry_run、plan_id、execute 的确认流程。"
        "route/pick/workflow/plan-execute/followup 返回 compact JSON 时，优先读取顶层 command_source、preferred_command、fallback_command、compact_commands 作为下一步。"
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
        "preferences_recipe_command": "python3 scripts/aro_request.py templates --recipe preferences --compact",
        "smart_search_recipe_command": "python3 scripts/aro_request.py templates --recipe smart_search --compact",
        "smart_decision_route_command": "python3 scripts/aro_request.py route '资源决策 <片名>' --session 'agent:<会话ID>' --summary-only",
        "smart_decision_recipe_command": "python3 scripts/aro_request.py templates --recipe smart_decision --compact",
        "smart_search_plan_recipe_command": "python3 scripts/aro_request.py templates --recipe smart_search_plan --compact",
        "smart_search_execute_recipe_command": "python3 scripts/aro_request.py templates --recipe smart_search_execute --compact",
        "mp_pt_recipe_command": "python3 scripts/aro_request.py templates --recipe mp_pt --compact",
        "mp_recommend_recipe_command": "python3 scripts/aro_request.py templates --recipe recommend --compact",
        "post_execute_recipe_command": "python3 scripts/aro_request.py templates --recipe followup --compact",
        "local_ingest_recipe_command": "python3 scripts/aro_request.py templates --recipe local_ingest --compact",
        "startup_command": "python3 scripts/aro_request.py startup",
        "route_command": "python3 scripts/aro_request.py route '<用户原始指令>' --session 'agent:<会话ID>'",
        "pick_command": "python3 scripts/aro_request.py pick <编号> --session 'agent:<会话ID>'",
        "followup_command": "python3 scripts/aro_request.py followup --session 'agent:<会话ID>'",
        "next_command_rule": "优先读取 compact 主响应顶层的 preferred_command、fallback_command、compact_commands；只有这些字段为空时，再回退到 error_summary / followup_summary / score_summary.decision。",
        "auto_continue_rule": "如果 summary-only 输出里 recommended_agent_behavior=auto_continue 或 auto_continue_then_wait_confirmation，则可以直接执行 auto_run_command；如果是 wait_user_confirmation，则先向用户展示 confirm_command；如果是 stop，则不要继续自动执行。",
        "execution_policy_contract": {
            "auto_continue": "直接执行 auto_run_command。",
            "auto_continue_then_wait_confirmation": "先执行 auto_run_command，再停止并向用户展示 confirm_command。",
            "wait_user_confirmation": "不要自动执行；先向用户展示 confirm_command 或 display_command。",
            "show_only": "只展示 display_command，不要自动继续。",
            "stop": "当前没有适合自动继续的命令，不要继续执行。",
        },
        "execution_loop_contract": [
            {
                "step": "startup",
                "command": "python3 scripts/aro_request.py startup",
                "purpose": "检查插件状态并拿到推荐 recipe。",
            },
            {
                "step": "decide",
                "command": "python3 scripts/aro_request.py decide --summary-only",
                "purpose": "读取下一步 helper 决策摘要。",
            },
            {
                "step": "route",
                "command": "python3 scripts/aro_request.py route '<用户原始指令>' --session 'agent:<会话ID>' --summary-only",
                "purpose": "处理搜索、链接、状态查询等主入口。",
            },
            {
                "step": "policy",
                "command": "读取 recommended_agent_behavior / auto_run_command / confirm_command",
                "purpose": "按统一 5 类执行范式决定自动继续、确认或停止。",
            },
            {
                "step": "followup",
                "command": "python3 scripts/aro_request.py followup --session 'agent:<会话ID>' --summary-only",
                "purpose": "执行计划后继续追踪下载、入库或失败诊断。",
            },
        ],
        "entry_patterns": {
            "external_agent": {
                "label": "外部智能体",
                "start_with": "startup",
                "decide_with": "decide --summary-only",
                "route_with": "route --summary-only",
                "followup_with": "followup --summary-only",
                "notes": "WorkBuddy、Hermes、OpenClaw（小龙虾）优先使用这套 Skill/helper。",
            },
            "mp_builtin_agent": {
                "label": "MP 内置智能体",
                "start_with": "assistant/request_templates",
                "decide_with": "agent_resource_officer_request_templates",
                "route_with": "agent_resource_officer_smart_entry",
                "followup_with": "agent_resource_officer_execution_followup",
                "notes": "优先调用 Agent Tool / request_templates，不在模型侧直拼资源接口。",
            },
            "feishu_channel": {
                "label": "飞书入口",
                "start_with": "飞书消息进入内置 Channel",
                "decide_with": "插件内置命令解析",
                "route_with": "route / pick / followup",
                "followup_with": "followup --summary-only",
                "notes": "飞书是消息入口，不单独维护另一套状态机。",
            },
        },
        "entry_playbooks": {
            "external_agent": {
                "label": "外部智能体最小执行流",
                "steps": [
                    {
                        "step": "startup",
                        "helper_command": "python3 scripts/aro_request.py startup",
                        "purpose": "读取启动状态、恢复建议和推荐 recipe。",
                    },
                    {
                        "step": "decide",
                        "helper_command": "python3 scripts/aro_request.py decide --summary-only",
                        "purpose": "决定继续会话、初始化偏好还是直接进入 route。",
                    },
                    {
                        "step": "route",
                        "helper_command": "python3 scripts/aro_request.py route '<用户原始指令>' --session 'agent:<会话ID>' --summary-only",
                        "purpose": "执行自然语言主入口。",
                    },
                    {
                        "step": "followup",
                        "helper_command": "python3 scripts/aro_request.py followup --session 'agent:<会话ID>' --summary-only",
                        "purpose": "执行计划后继续追踪下载、入库或失败诊断。",
                    },
                ],
            },
            "mp_builtin_agent": {
                "label": "MP 内置智能体最小执行流",
                "steps": [
                    {
                        "step": "request_templates",
                        "tool": "agent_resource_officer_request_templates",
                        "purpose": "读取最小流程、确认策略和推荐入口。",
                    },
                    {
                        "step": "route",
                        "tool": "agent_resource_officer_smart_entry",
                        "purpose": "处理搜索、链接、登录状态等主入口。",
                    },
                    {
                        "step": "followup",
                        "tool": "agent_resource_officer_execution_followup",
                        "purpose": "执行计划后继续查看下载、入库和失败状态。",
                    },
                ],
            },
            "feishu_channel": {
                "label": "飞书入口最小执行流",
                "steps": [
                    {"step": "message_in", "purpose": "用户消息进入内置 Channel。"},
                    {"step": "route", "purpose": "复用同一套 assistant 协议，不维护单独状态机。"},
                    {"step": "reply", "purpose": "按确认策略回消息、展示编号或提示下一步。"},
                ],
            },
        },
        "orchestration_contract": {
            "service_role": "Agent影视助手 / AgentResourceOfficer 负责服务端能力执行。",
            "client_role": "外部智能体、MP 内置智能体、飞书入口负责客户端调度与展示。",
            "recommended_first_call": "startup",
            "recommended_decision_call": "decide --summary-only",
            "recommended_route_call": "route --summary-only",
            "recommended_followup_call": "followup --summary-only",
            "recommended_read_fields": [
                "recommended_agent_behavior",
                "auto_run_command",
                "confirm_command",
                "display_command",
                "preferred_command",
                "compact_commands",
            ],
            "confirmation_rule": "写入动作默认确认制；只有明确标记可自动继续的只读步骤才自动续跑。",
        },
        "compat_aliases": ["workbuddy"],
        "deprecated_aliases": ["workbuddy"],
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
                "command": "python3 scripts/aro_request.py route '<用户原始指令>' --session 'agent:<会话ID>'",
                "writes": "depends_on_route",
            },
            {
                "name": "pick_continue",
                "purpose": "继续编号选择、详情、审查、下一页等会话动作。",
                "command": "python3 scripts/aro_request.py pick <编号> --session 'agent:<会话ID>'",
                "writes": "depends_on_choice",
            },
            {
                "name": "execution_followup",
                "purpose": "在执行计划后自动追踪下载、订阅或入库状态。",
                "command": "python3 scripts/aro_request.py followup --session 'agent:<会话ID>'",
                "writes": False,
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
            "follow_up_hint",
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
            "decision_summary",
            "best_candidate",
            "sources_checked",
            "available_sources",
            "blocked_sources",
            "decision_mode",
            "decision_reason",
            "smart_plan_auto_selected",
            "smart_execute_auto_selected",
            "error_summary",
            "diagnosis_summary",
            "followup_summary",
            "preferences",
            "needs_onboarding",
            "initialized",
            "command_source",
            "command_policy",
            "preferred_requires_confirmation",
            "fallback_requires_confirmation",
            "can_auto_run_preferred",
            "preferred_command",
            "fallback_command",
            "compact_commands",
            "recommended_agent_behavior",
            "auto_run_command",
            "confirm_command",
            "display_command",
            "detail_short_command",
            "plan_short_command",
            "confirm_short_command",
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
    explicit_behavior = str(summary.get("recommended_agent_behavior") or "").strip()
    auto_run_command = str(summary.get("auto_run_command") or "").strip()
    confirm_command = str(summary.get("confirm_command") or "").strip()
    display_command = str(summary.get("display_command") or "").strip()
    auto_run_short_command = str(summary.get("auto_run_short_command") or "").strip()
    confirm_short_command = str(summary.get("confirm_short_command") or "").strip()
    display_short_command = str(summary.get("display_short_command") or "").strip()
    if explicit_behavior:
        if confirmed and confirm_command:
            return confirm_short_command or confirm_command
        if explicit_behavior in {"auto_continue", "auto_continue_then_wait_confirmation"} and auto_run_command:
            return auto_run_short_command or auto_run_command
        if explicit_behavior == "wait_user_confirmation":
            return confirm_short_command or confirm_command or display_short_command or display_command
        if explicit_behavior == "show_only":
            return display_short_command or display_command or auto_run_short_command or auto_run_command or confirm_short_command or confirm_command
        if explicit_behavior == "stop":
            return ""
        if auto_run_command or confirm_command or display_command:
            return auto_run_short_command or auto_run_command or confirm_short_command or confirm_command or display_short_command or display_command
    preferred_command = str(summary.get("preferred_command") or "").strip()
    fallback_command = str(summary.get("fallback_command") or "").strip()
    preferred_short_command = str(summary.get("preferred_short_command") or "").strip()
    fallback_short_command = str(summary.get("fallback_short_command") or "").strip()
    preferred_requires_confirmation = bool(summary.get("preferred_requires_confirmation"))
    fallback_requires_confirmation = bool(summary.get("fallback_requires_confirmation"))
    if preferred_command:
        if confirmed and fallback_command and fallback_requires_confirmation:
            return fallback_short_command or fallback_command
        if not confirmed and preferred_requires_confirmation:
            return preferred_short_command or preferred_command
        return preferred_short_command or preferred_command
    if "first_requires_confirmation" in summary:
        requires_confirmation = bool(summary.get("first_requires_confirmation"))
    else:
        requires_confirmation = bool(summary.get("requires_confirmation"))
    command = str(summary.get("execute_helper_command") or "").strip()
    if requires_confirmation and not confirmed:
        command = str(summary.get("inspect_helper_command") or command).strip()
    if not command:
        command = str(summary.get("inspect_helper_command") or "").strip()
    return command


def compact_command_summary(output):
    payload = output if isinstance(output, dict) else {}
    compact_commands = [
        str(item).strip()
        for item in (payload.get("compact_commands") or [])
        if str(item).strip()
    ]
    preferred_command = str(payload.get("preferred_command") or "").strip()
    fallback_command = str(payload.get("fallback_command") or "").strip()
    if preferred_command and not compact_commands:
        compact_commands = [preferred_command]
        if fallback_command:
            compact_commands.append(fallback_command)
    action = str(payload.get("action") or "").strip()
    write_effect = str(payload.get("write_effect") or "").strip()
    ok = bool(payload.get("ok")) if "ok" in payload else bool(payload.get("success"))
    session = str(payload.get("session") or "").strip()
    session_id = str(payload.get("session_id") or "").strip()
    detail_short_command = str(payload.get("detail_short_command") or "").strip()
    plan_short_command = str(payload.get("plan_short_command") or "").strip()
    confirm_short_command = str(payload.get("confirm_short_command") or "").strip()
    auto_run_command = str(payload.get("auto_run_command") or "").strip()
    confirm_command = str(payload.get("confirm_command") or "").strip()
    display_command = str(payload.get("display_command") or "").strip()
    auto_run_short_command = detail_short_command if detail_short_command and auto_run_command in {"先看详情", "详情"} else ""
    display_short_command = detail_short_command if detail_short_command and display_command in {"先看详情", "详情"} else ""
    confirm_command_map = {
        "执行最佳": confirm_short_command,
        "确认执行": confirm_short_command,
        "计划最佳": plan_short_command,
        "先计划": plan_short_command,
    }
    confirm_short_for_explicit = confirm_command_map.get(confirm_command, "")
    preferred_short_command = ""
    fallback_short_command = ""
    if preferred_command in {"先看详情", "详情"}:
        preferred_short_command = detail_short_command
    elif preferred_command in {"计划最佳", "先计划", "计划"}:
        preferred_short_command = plan_short_command
    elif preferred_command in {"执行最佳", "确认执行", "确认"}:
        preferred_short_command = confirm_short_command
    if fallback_command in {"先看详情", "详情"}:
        fallback_short_command = detail_short_command
    elif fallback_command in {"计划最佳", "先计划", "计划"}:
        fallback_short_command = plan_short_command
    elif fallback_command in {"执行最佳", "确认执行", "确认"}:
        fallback_short_command = confirm_short_command
    summary = {
        "success": bool(payload.get("success", ok)),
        "ok": ok,
        "action": action,
        "write_effect": write_effect,
        "command_source": str(payload.get("command_source") or "").strip(),
        "command_policy": str(payload.get("command_policy") or "").strip(),
        "preferred_requires_confirmation": bool(payload.get("preferred_requires_confirmation")),
        "fallback_requires_confirmation": bool(payload.get("fallback_requires_confirmation")),
        "can_auto_run_preferred": bool(payload.get("can_auto_run_preferred")) if "can_auto_run_preferred" in payload else write_effect != "write",
        "preferred_command": preferred_command or (compact_commands[0] if compact_commands else ""),
        "fallback_command": fallback_command or (compact_commands[1] if len(compact_commands) > 1 else ""),
        "preferred_short_command": preferred_short_command,
        "fallback_short_command": fallback_short_command,
        "compact_commands": compact_commands[:2],
        "preferred_helper_command": helper_route_command(preferred_command or (compact_commands[0] if compact_commands else ""), session=session, session_id=session_id),
        "fallback_helper_command": helper_route_command(fallback_command or (compact_commands[1] if len(compact_commands) > 1 else ""), session=session, session_id=session_id),
        "requires_confirmation": write_effect == "write",
        "message_head": str(payload.get("message") or payload.get("message_head") or "").strip(),
        "recommended_agent_behavior": str(payload.get("recommended_agent_behavior") or "").strip(),
        "auto_run_command": auto_run_command,
        "confirm_command": confirm_command,
        "display_command": display_command,
        "auto_run_short_command": auto_run_short_command,
        "display_short_command": display_short_command,
        "detail_short_command": detail_short_command,
        "plan_short_command": plan_short_command,
        "confirm_short_command": confirm_short_for_explicit or confirm_short_command,
    }
    summary.update(command_execution_policy(summary))
    return summary


def command_execution_policy(summary):
    summary = summary if isinstance(summary, dict) else {}
    explicit_behavior = str(summary.get("recommended_agent_behavior") or "").strip()
    explicit_auto = str(summary.get("auto_run_command") or "").strip()
    explicit_confirm = str(summary.get("confirm_command") or "").strip()
    explicit_display = str(summary.get("display_command") or "").strip()
    if explicit_behavior:
        return {
            "recommended_agent_behavior": explicit_behavior,
            "auto_run_command": explicit_auto,
            "confirm_command": explicit_confirm,
            "display_command": explicit_display or explicit_auto or explicit_confirm,
            "stop_after_auto": explicit_behavior == "auto_continue_then_wait_confirmation",
            "reason": "优先使用服务端返回的执行策略。",
            "execution_reason": "优先使用服务端返回的执行策略。",
        }
    preferred_command = str(summary.get("preferred_command") or "").strip()
    fallback_command = str(summary.get("fallback_command") or "").strip()
    preferred_requires_confirmation = bool(summary.get("preferred_requires_confirmation"))
    fallback_requires_confirmation = bool(summary.get("fallback_requires_confirmation"))
    can_auto_run_preferred = bool(summary.get("can_auto_run_preferred"))

    if preferred_command and can_auto_run_preferred and not preferred_requires_confirmation:
        if fallback_command and fallback_requires_confirmation:
            return {
                "recommended_agent_behavior": "auto_continue_then_wait_confirmation",
                "auto_run_command": preferred_command,
                "confirm_command": fallback_command,
                "display_command": preferred_command,
                "stop_after_auto": True,
                "reason": "首选命令是安全读步骤，可自动继续；后续备选命令涉及确认。",
                "execution_reason": "首选命令是安全读步骤，可自动继续；后续备选命令涉及确认。",
            }
        return {
            "recommended_agent_behavior": "auto_continue",
            "auto_run_command": preferred_command,
            "confirm_command": "",
            "display_command": preferred_command,
            "stop_after_auto": False,
            "reason": "首选命令是安全读步骤，可直接继续。",
            "execution_reason": "首选命令是安全读步骤，可直接继续。",
        }

    if preferred_command and preferred_requires_confirmation:
        return {
            "recommended_agent_behavior": "wait_user_confirmation",
            "auto_run_command": "",
            "confirm_command": preferred_command,
            "display_command": preferred_command,
            "stop_after_auto": False,
            "reason": "首选命令本身需要用户确认，不能自动执行。",
            "execution_reason": "首选命令本身需要用户确认，不能自动执行。",
        }

    if preferred_command:
        return {
            "recommended_agent_behavior": "show_only",
            "auto_run_command": "",
            "confirm_command": "",
            "display_command": preferred_command,
            "stop_after_auto": False,
            "reason": "已有首选命令，但当前不建议自动执行。",
            "execution_reason": "已有首选命令，但当前不建议自动执行。",
        }

    if fallback_command and fallback_requires_confirmation:
        return {
            "recommended_agent_behavior": "wait_user_confirmation",
            "auto_run_command": "",
            "confirm_command": fallback_command,
            "display_command": fallback_command,
            "stop_after_auto": False,
            "reason": "仅存在需要确认的备选命令。",
            "execution_reason": "仅存在需要确认的备选命令。",
        }

    if fallback_command:
        return {
            "recommended_agent_behavior": "show_only",
            "auto_run_command": "",
            "confirm_command": "",
            "display_command": fallback_command,
            "stop_after_auto": False,
            "reason": "仅存在备选命令，建议先展示。",
            "execution_reason": "仅存在备选命令，建议先展示。",
        }

    return {
        "recommended_agent_behavior": "stop",
        "auto_run_command": "",
        "confirm_command": "",
        "display_command": "",
        "stop_after_auto": False,
        "reason": "当前没有可继续执行的短命令。",
        "execution_reason": "当前没有可继续执行的短命令。",
    }


def helper_summary_execution_policy(summary):
    summary = summary if isinstance(summary, dict) else {}
    if summary.get("preferred_command") or summary.get("fallback_command"):
        return command_execution_policy(summary)

    inspect_command = str(summary.get("inspect_helper_command") or "").strip()
    execute_command = str(summary.get("execute_helper_command") or "").strip()
    if "first_requires_confirmation" in summary:
        first_requires_confirmation = bool(summary.get("first_requires_confirmation"))
    else:
        first_requires_confirmation = bool(summary.get("requires_confirmation"))
    requires_confirmation = bool(summary.get("requires_confirmation"))

    if execute_command and not first_requires_confirmation:
        if requires_confirmation and inspect_command:
            return {
                "recommended_agent_behavior": "auto_continue_then_wait_confirmation",
                "auto_run_command": execute_command,
                "confirm_command": inspect_command,
                "display_command": execute_command,
                "stop_after_auto": True,
                "reason": "当前步骤可直接执行，但后续链路存在确认动作。",
                "execution_reason": "当前步骤可直接执行，但后续链路存在确认动作。",
            }
        return {
            "recommended_agent_behavior": "auto_continue",
            "auto_run_command": execute_command,
            "confirm_command": "",
            "display_command": execute_command,
            "stop_after_auto": False,
            "reason": "当前步骤可直接执行。",
            "execution_reason": "当前步骤可直接执行。",
        }

    if inspect_command:
        return {
            "recommended_agent_behavior": "wait_user_confirmation" if requires_confirmation else "show_only",
            "auto_run_command": "",
            "confirm_command": inspect_command if requires_confirmation else "",
            "display_command": inspect_command,
            "stop_after_auto": False,
            "reason": "当前应先展示检查或确认命令。",
            "execution_reason": "当前应先展示检查或确认命令。",
        }

    return {
        "recommended_agent_behavior": "stop",
        "auto_run_command": "",
        "confirm_command": "",
        "display_command": "",
        "stop_after_auto": False,
        "reason": "当前没有可继续执行的 helper 命令。",
        "execution_reason": "当前没有可继续执行的 helper 命令。",
    }


def print_summary(summary, command_only=False, confirmed=False):
    if isinstance(summary, dict):
        policy = helper_summary_execution_policy(summary)
        if "reason" in summary and policy.get("reason"):
            policy = {
                **policy,
                "execution_reason": policy.get("execution_reason") or policy.get("reason") or "",
            }
            policy.pop("reason", None)
        summary = {**summary, **policy}
    if command_only:
        print(summary_command(summary, confirmed=confirmed))
        return
    print_json(summary)


def shell_quote(value):
    text = str(value or "")
    return "'" + text.replace("'", "'\"'\"'") + "'"


def helper_route_command(command, session="", session_id=""):
    command_text = str(command or "").strip()
    if not command_text:
        return ""
    session_part = f" --session {shell_quote(session)}" if str(session or "").strip() else ""
    session_id_part = f" --session-id {shell_quote(session_id)}" if str(session_id or "").strip() else ""
    return f"python3 scripts/aro_request.py route {shell_quote(command_text)}{session_part}{session_id_part}"


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
    detail = payload.get("recommended_recipe_detail") if isinstance(payload, dict) and isinstance(payload.get("recommended_recipe_detail"), dict) else {}
    first_call = detail.get("first_call") if isinstance(detail, dict) and isinstance(detail.get("first_call"), dict) else {}
    return {
        "selected_recipe": payload.get("selected_recipe") or payload.get("recommended_recipe") or "",
        "recommended_recipe": payload.get("recommended_recipe") or "",
        "first_template": detail.get("first_template") or "",
        "first_endpoint": first_call.get("endpoint") or "",
        "first_method": first_call.get("method") or "",
        "first_requires_confirmation": bool(first_call.get("requires_confirmation")),
        "requires_confirmation": bool(detail.get("confirmation_required_templates")),
        "confirmation_message": detail.get("confirmation_message") or "",
        "orchestration_contract": payload.get("orchestration_contract") or detail.get("orchestration_contract") or {},
        "entry_patterns": payload.get("entry_patterns") or detail.get("entry_patterns") or {},
        "entry_playbooks": payload.get("entry_playbooks") or detail.get("entry_playbooks") or {},
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
    elif first_template == "execution_followup":
        execute = "python3 scripts/aro_request.py followup"
    elif first_template == "pick_continue":
        execute = "python3 scripts/aro_request.py recover --execute"
    elif first_template == "preferences_get":
        execute = "python3 scripts/aro_request.py preferences"
    elif first_template == "scoring_policy":
        execute = "python3 scripts/aro_request.py scoring-policy"
    elif first_template == "workflow_dry_run":
        execute = "python3 scripts/aro_request.py workflow --workflow <workflow> --keyword <keyword>"
    elif first_template == "smart_search":
        execute = "python3 scripts/aro_request.py workflow --workflow smart_resource_search --keyword <keyword>"
    elif first_template == "smart_decision":
        execute = "python3 scripts/aro_request.py workflow --workflow smart_resource_decision --keyword <keyword>"
    elif first_template == "smart_search_plan":
        execute = "python3 scripts/aro_request.py workflow --workflow smart_resource_plan --keyword <keyword>"
    elif first_template == "smart_search_execute":
        execute = "python3 scripts/aro_request.py workflow --workflow smart_resource_execute --keyword <keyword>"
    elif first_template == "mp_media_detail":
        execute = "python3 scripts/aro_request.py workflow --workflow mp_media_detail --keyword <keyword>"
    elif first_template == "mp_search":
        execute = "python3 scripts/aro_request.py workflow --workflow mp_search --keyword <keyword>"
    elif first_template == "mp_search_detail":
        execute = "python3 scripts/aro_request.py workflow --workflow mp_search_detail --keyword <keyword> --choice <编号>"
    elif first_template == "mp_search_best":
        execute = "python3 scripts/aro_request.py workflow --workflow mp_search_best --keyword <keyword>"
    elif first_template == "mp_search_download_plan":
        execute = "python3 scripts/aro_request.py workflow --workflow mp_search_download --keyword <keyword> --choice <编号>"
    elif first_template == "mp_recommend":
        execute = "python3 scripts/aro_request.py workflow --workflow mp_recommend --source tmdb_trending --media-type all --limit 20"
    elif first_template == "mp_recommend_search":
        execute = "python3 scripts/aro_request.py workflow --workflow mp_recommend_search --source tmdb_trending --media-type all --choice <编号> --mode mp --limit 20"
    elif first_template == "mp_ingest_status":
        execute = "python3 scripts/aro_request.py workflow --workflow mp_ingest_status --keyword <keyword>"
    elif first_template == "mp_local_diagnose":
        execute = "python3 scripts/aro_request.py workflow --workflow mp_local_diagnose --keyword <keyword>"
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
    smart_search_commands = recipe_helper_commands({"first_template": "smart_search"}, "smart_search")
    check("smart_search_recipe_execute_command", smart_search_commands.get("execute_helper_command") == "python3 scripts/aro_request.py workflow --workflow smart_resource_search --keyword <keyword>")
    smart_decision_commands = recipe_helper_commands({"first_template": "smart_decision"}, "smart_decision")
    check("smart_decision_recipe_execute_command", smart_decision_commands.get("execute_helper_command") == "python3 scripts/aro_request.py workflow --workflow smart_resource_decision --keyword <keyword>")
    smart_search_plan_commands = recipe_helper_commands({"first_template": "smart_search_plan"}, "smart_search_plan")
    check("smart_search_plan_recipe_execute_command", smart_search_plan_commands.get("execute_helper_command") == "python3 scripts/aro_request.py workflow --workflow smart_resource_plan --keyword <keyword>")
    smart_search_execute_commands = recipe_helper_commands({"first_template": "smart_search_execute"}, "smart_search_execute")
    check("smart_search_execute_recipe_execute_command", smart_search_execute_commands.get("execute_helper_command") == "python3 scripts/aro_request.py workflow --workflow smart_resource_execute --keyword <keyword>")
    mp_pt_commands = recipe_helper_commands({"first_template": "mp_media_detail"}, "mp_pt")
    check("mp_pt_recipe_execute_command", mp_pt_commands.get("execute_helper_command") == "python3 scripts/aro_request.py workflow --workflow mp_media_detail --keyword <keyword>")
    mp_recommend_commands = recipe_helper_commands({"first_template": "mp_recommend"}, "recommend")
    check("mp_recommend_recipe_execute_command", mp_recommend_commands.get("execute_helper_command") == "python3 scripts/aro_request.py workflow --workflow mp_recommend --source tmdb_trending --media-type all --limit 20")
    preferences_commands = recipe_helper_commands({"first_template": "preferences_get"}, "preferences")
    check("preferences_recipe_execute_command", preferences_commands.get("execute_helper_command") == "python3 scripts/aro_request.py preferences")
    local_ingest_commands = recipe_helper_commands({"first_template": "mp_ingest_status"}, "local_ingest")
    check("local_ingest_recipe_execute_command", local_ingest_commands.get("execute_helper_command") == "python3 scripts/aro_request.py workflow --workflow mp_ingest_status --keyword <keyword>")
    maintain_commands = recipe_helper_commands({"first_template": "maintain_preview"}, "maintain")
    check("maintain_preview_command", maintain_commands.get("execute_helper_command") == "python3 scripts/aro_request.py maintain")
    maintain_execute_commands = recipe_helper_commands({"first_template": "maintain_execute"}, "maintain")
    check("maintain_execute_command", maintain_execute_commands.get("execute_helper_command") == "python3 scripts/aro_request.py maintain --execute")

    template_summary = request_templates_summary({
        "data": {
            "recommended_recipe": "bootstrap",
            "orchestration_contract": {
                "recommended_first_call": "startup",
                "recommended_route_call": "route --summary-only",
            },
            "entry_patterns": {
                "mp_builtin_agent": {"route_with": "agent_resource_officer_smart_entry"},
            },
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
    check("templates_summary_first_confirmation", template_summary.get("first_requires_confirmation") is False)
    check("templates_summary_orchestration_contract", (template_summary.get("orchestration_contract") or {}).get("recommended_first_call") == "startup")
    check("templates_summary_entry_patterns", bool(((template_summary.get("entry_patterns") or {}).get("mp_builtin_agent") or {}).get("route_with")))
    template_summary_with_playbooks = request_templates_summary({
        "data": {
            "recommended_recipe": "external_agent_quickstart",
            "entry_playbooks": {
                "external_agent": {
                    "steps": [{"step": "startup"}, {"step": "decide"}, {"step": "route"}, {"step": "followup"}],
                },
                "mp_builtin_agent": {
                    "steps": [{"step": "request_templates", "tool": "agent_resource_officer_request_templates"}],
                },
            },
        },
    })
    check("templates_summary_entry_playbooks", len(((template_summary_with_playbooks.get("entry_playbooks") or {}).get("external_agent") or {}).get("steps") or []) == 4)
    check("templates_summary_entry_playbooks_mp_tool", bool(((((template_summary_with_playbooks.get("entry_playbooks") or {}).get("mp_builtin_agent") or {}).get("steps") or [{}])[0]).get("tool")))

    confirm_summary = {
        "requires_confirmation": True,
        "inspect_helper_command": "inspect",
        "execute_helper_command": "execute",
    }
    check("command_only_requires_confirmation", summary_command(confirm_summary) == "inspect")
    later_confirm_summary = {
        "first_requires_confirmation": False,
        "requires_confirmation": True,
        "inspect_helper_command": "inspect",
        "execute_helper_command": "execute",
    }
    check("command_only_later_confirmation_executes_first_step", summary_command(later_confirm_summary) == "execute")
    check("command_only_confirmed_executes", summary_command(confirm_summary, confirmed=True) == "execute")
    no_confirm_summary = {
        "requires_confirmation": False,
        "inspect_helper_command": "inspect",
        "execute_helper_command": "execute",
    }
    check("command_only_without_confirmation_executes", summary_command(no_confirm_summary) == "execute")
    top_level_preferred_summary = {
        "requires_confirmation": False,
        "preferred_requires_confirmation": False,
        "fallback_requires_confirmation": True,
        "preferred_command": "选择 1",
        "fallback_command": "下载1",
    }
    check("command_only_prefers_top_level_command", summary_command(top_level_preferred_summary) == "选择 1")
    top_level_confirm_summary = {
        "requires_confirmation": True,
        "preferred_requires_confirmation": False,
        "fallback_requires_confirmation": True,
        "preferred_command": "选择 1",
        "fallback_command": "下载1",
    }
    check("command_only_confirmed_uses_top_level_fallback", summary_command(top_level_confirm_summary, confirmed=True) == "下载1")
    top_level_policy_summary = {
        "preferred_requires_confirmation": False,
        "fallback_requires_confirmation": True,
        "can_auto_run_preferred": True,
        "preferred_command": "选择 1",
        "fallback_command": "下载1",
    }
    top_level_policy = command_execution_policy(top_level_policy_summary)
    check("command_execution_policy_auto_continue_then_wait", top_level_policy.get("recommended_agent_behavior") == "auto_continue_then_wait_confirmation")
    explicit_summary_command = {
        "recommended_agent_behavior": "auto_continue_then_wait_confirmation",
        "auto_run_command": "先看详情",
        "confirm_command": "执行最佳",
        "display_command": "先看详情",
        "auto_run_short_command": "详情",
        "confirm_short_command": "确认",
        "display_short_command": "详情",
    }
    check("command_only_prefers_explicit_auto_run_command", summary_command(explicit_summary_command) == "详情")
    check("command_only_confirmed_prefers_explicit_confirm_command", summary_command(explicit_summary_command, confirmed=True) == "确认")
    explicit_top_level_policy = command_execution_policy({
        "recommended_agent_behavior": "auto_continue_then_wait_confirmation",
        "auto_run_command": "先看详情",
        "confirm_command": "执行最佳",
        "display_command": "先看详情",
    })
    check("command_execution_policy_prefers_explicit_server_policy", explicit_top_level_policy.get("auto_run_command") == "先看详情" and explicit_top_level_policy.get("confirm_command") == "执行最佳")
    confirm_only_policy = command_execution_policy({
        "preferred_requires_confirmation": True,
        "preferred_command": "下载1",
    })
    check("command_execution_policy_wait_confirmation", confirm_only_policy.get("recommended_agent_behavior") == "wait_user_confirmation" and confirm_only_policy.get("confirm_command") == "下载1")
    stop_policy = command_execution_policy({})
    check("command_execution_policy_stop_without_commands", stop_policy.get("recommended_agent_behavior") == "stop")
    helper_auto_policy = helper_summary_execution_policy({
        "first_requires_confirmation": False,
        "requires_confirmation": True,
        "inspect_helper_command": "inspect",
        "execute_helper_command": "execute",
    })
    check("helper_execution_policy_auto_then_confirm", helper_auto_policy.get("recommended_agent_behavior") == "auto_continue_then_wait_confirmation" and helper_auto_policy.get("auto_run_command") == "execute")
    helper_confirm_policy = helper_summary_execution_policy({
        "requires_confirmation": True,
        "inspect_helper_command": "inspect",
        "execute_helper_command": "",
    })
    check("helper_execution_policy_wait_confirmation", helper_confirm_policy.get("recommended_agent_behavior") == "wait_user_confirmation" and helper_confirm_policy.get("confirm_command") == "inspect")
    helper_stop_policy = helper_summary_execution_policy({})
    check("helper_execution_policy_stop_without_commands", helper_stop_policy.get("recommended_agent_behavior") == "stop")

    quote_value = shell_quote("a'b")
    check("shell_quote_single_quote", quote_value == "'a'\"'\"'b'")
    check("helper_route_command_with_session", helper_route_command("选择 1", session="agent:demo") == "python3 scripts/aro_request.py route '选择 1' --session 'agent:demo'")

    route_args = normalize_command_args(argparse.Namespace(command="route", extra=["盘搜搜索", "大君夫人"], text=None))
    check("normalize_route_positional_text", route_args.text == "盘搜搜索 大君夫人")

    pick_choice_args = normalize_command_args(
        argparse.Namespace(command="pick", extra=["11"], choice=None, action=None)
    )
    check("normalize_pick_positional_choice", pick_choice_args.choice == 11 and not pick_choice_args.action)

    pick_action_args = normalize_command_args(
        argparse.Namespace(command="pick", extra=["详情"], choice=None, action=None)
    )
    check("normalize_pick_positional_action", pick_action_args.action == "详情" and pick_action_args.choice is None)

    pick_choice_action_args = normalize_command_args(
        argparse.Namespace(command="pick", extra=["11", "详情"], choice=None, action=None)
    )
    check("normalize_pick_positional_choice_action", pick_choice_action_args.choice == 11 and pick_choice_action_args.action == "详情")

    plan_args = normalize_command_args(
        argparse.Namespace(command="plan-execute", extra=["plan-123"], plan_id=None)
    )
    check("normalize_plan_execute_positional_plan", plan_args.plan_id == "plan-123")
    followup_args = normalize_command_args(
        argparse.Namespace(command="followup", extra=["plan-123"], plan_id=None)
    )
    check("normalize_followup_positional_plan", followup_args.plan_id == "plan-123")

    workflow_args = normalize_command_args(
        argparse.Namespace(command="workflow", extra=["mp_media_detail", "蜘蛛侠"], workflow="hdhive_candidates", keyword=None)
    )
    check("normalize_workflow_positional_workflow", workflow_args.workflow == "mp_media_detail")
    check("normalize_workflow_positional_keyword", workflow_args.keyword == "蜘蛛侠")

    session_args = normalize_command_args(
        argparse.Namespace(command="session", extra=["agent:demo"], session=None)
    )
    check("normalize_session_positional_session", session_args.session == "agent:demo")

    history_args = normalize_command_args(
        argparse.Namespace(command="history", extra=["agent:demo"], session=None)
    )
    check("normalize_history_positional_session", history_args.session == "agent:demo")

    plans_args = normalize_command_args(
        argparse.Namespace(command="plans", extra=["plan-123"], plan_id=None)
    )
    check("normalize_plans_positional_plan", plans_args.plan_id == "plan-123")

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
    compact_execute = compact({
        "success": True,
        "data": {
            "action": "execute_plan",
            "recommended_action": "query_mp_download_history",
            "follow_up_hint": "先查下载历史。",
        },
    })
    check("compact_preserves_follow_up_hint", compact_execute.get("follow_up_hint") == "先查下载历史。")
    compact_top_level_commands = compact({
        "success": True,
        "data": {
            "action": "mp_media_search",
            "command_source": "score_summary",
            "command_policy": "read_then_confirm_write",
            "preferred_requires_confirmation": False,
            "fallback_requires_confirmation": True,
            "can_auto_run_preferred": True,
            "preferred_command": "选择 1",
            "fallback_command": "下载1",
            "compact_commands": ["选择 1", "下载1"],
        },
    })
    top_level_summary = compact_command_summary(compact_top_level_commands)
    check("compact_preserves_top_level_preferred_command", compact_top_level_commands.get("preferred_command") == "选择 1")
    check("compact_command_summary_prefers_top_level", top_level_summary.get("preferred_command") == "选择 1" and top_level_summary.get("command_source") == "score_summary")
    check("compact_command_summary_preserves_confirmation_flags", top_level_summary.get("fallback_requires_confirmation") is True and top_level_summary.get("can_auto_run_preferred") is True)
    check("compact_command_summary_builds_helper_command", top_level_summary.get("preferred_helper_command") == "python3 scripts/aro_request.py route '选择 1'")
    check("compact_command_summary_includes_execution_policy", top_level_summary.get("recommended_agent_behavior") == "auto_continue_then_wait_confirmation" and top_level_summary.get("auto_run_command") == "选择 1")
    compact_explicit_policy_commands = compact({
        "success": True,
        "data": {
            "action": "smart_resource_decision",
            "command_source": "decision_summary",
            "command_policy": "read_then_confirm_write",
            "preferred_requires_confirmation": True,
            "fallback_requires_confirmation": True,
            "can_auto_run_preferred": False,
            "preferred_command": "执行最佳",
            "fallback_command": "计划最佳",
            "compact_commands": ["执行最佳", "计划最佳"],
            "recommended_agent_behavior": "auto_continue_then_wait_confirmation",
            "auto_run_command": "先看详情",
            "confirm_command": "执行最佳",
            "display_command": "先看详情",
            "detail_short_command": "详情",
            "plan_short_command": "计划",
            "confirm_short_command": "确认",
        },
    })
    explicit_summary = compact_command_summary(compact_explicit_policy_commands)
    check("compact_command_summary_preserves_explicit_auto_run_command", explicit_summary.get("auto_run_command") == "先看详情" and explicit_summary.get("confirm_command") == "执行最佳")
    check("compact_command_summary_preserves_smart_short_commands", explicit_summary.get("detail_short_command") == "详情" and explicit_summary.get("plan_short_command") == "计划" and explicit_summary.get("confirm_short_command") == "确认")
    check("compact_command_summary_builds_preferred_short_commands", explicit_summary.get("auto_run_short_command") == "详情" and explicit_summary.get("display_short_command") == "详情")
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
    check("external_agent_payload_has_tools", len(external_agent.get("tools") or []) == 4)
    check("external_agent_payload_has_followup", bool(external_agent.get("followup_command")))
    check("external_agent_payload_has_preferences_recipe", bool(external_agent.get("preferences_recipe_command")))
    check("external_agent_payload_has_smart_search_recipe", bool(external_agent.get("smart_search_recipe_command")))
    check("external_agent_payload_has_smart_decision_route", bool(external_agent.get("smart_decision_route_command")))
    check("external_agent_payload_has_smart_decision_recipe", bool(external_agent.get("smart_decision_recipe_command")))
    check("external_agent_payload_has_smart_search_plan_recipe", bool(external_agent.get("smart_search_plan_recipe_command")))
    check("external_agent_payload_has_smart_search_execute_recipe", bool(external_agent.get("smart_search_execute_recipe_command")))
    check("external_agent_payload_has_mp_pt_recipe", bool(external_agent.get("mp_pt_recipe_command")))
    check("external_agent_payload_has_mp_recommend_recipe", bool(external_agent.get("mp_recommend_recipe_command")))
    check("external_agent_payload_has_post_execute_recipe", bool(external_agent.get("post_execute_recipe_command")))
    check("external_agent_payload_has_local_ingest_recipe", bool(external_agent.get("local_ingest_recipe_command")))
    check("external_agent_payload_has_next_command_rule", bool(external_agent.get("next_command_rule")))
    check("external_agent_payload_has_execution_policy_contract", bool((external_agent.get("execution_policy_contract") or {}).get("auto_continue")))
    check("external_agent_payload_has_execution_loop_contract", len(external_agent.get("execution_loop_contract") or []) >= 5)
    check("external_agent_payload_has_orchestration_contract_present", bool((external_agent.get("orchestration_contract") or {}).get("recommended_route_call")))
    check("external_agent_payload_has_feishu_entry_pattern", bool(((external_agent.get("entry_patterns") or {}).get("feishu_channel") or {}).get("route_with")))
    check("external_agent_payload_has_orchestration_contract_route", (external_agent.get("orchestration_contract") or {}).get("recommended_route_call") == "route --summary-only")
    check("external_agent_payload_has_entry_patterns", bool(((external_agent.get("entry_patterns") or {}).get("mp_builtin_agent") or {}).get("route_with")))
    check("external_agent_payload_has_entry_playbooks", len((((external_agent.get("entry_playbooks") or {}).get("external_agent") or {}).get("steps") or [])) >= 4)
    check("external_agent_payload_has_mp_playbook_tool", bool(((((external_agent.get("entry_playbooks") or {}).get("mp_builtin_agent") or {}).get("steps") or [{}])[0]).get("tool")))
    check("external_agent_payload_has_deprecated_aliases", "workbuddy" in (external_agent.get("deprecated_aliases") or []))

    catalog = commands_catalog()
    catalog_commands = catalog.get("commands") or []
    catalog_names = {item.get("name") for item in catalog_commands}
    check("helper_version_present", catalog.get("helper_version") == HELPER_VERSION)
    check("commands_schema_version", catalog.get("schema_version") == "commands.v1")
    check("commands_catalog_includes_version", "version" in catalog_names)
    check("commands_catalog_includes_external_agent", "external-agent" in catalog_names)
    check("commands_catalog_includes_workbuddy_alias", "workbuddy" in catalog_names)
    workbuddy_entry = next((item for item in catalog_commands if item.get("name") == "workbuddy"), {})
    check("commands_catalog_marks_workbuddy_deprecated", workbuddy_entry.get("deprecated") is True)
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
            {"name": "workbuddy", "network": False, "writes": False, "write_condition": "", "purpose": "compatibility alias for external-agent", "deprecated": True},
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
            {"name": "followup", "network": True, "writes": False, "write_condition": "", "purpose": "run the unified post-execution follow-up action for the latest executed or specified plan"},
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
    parser.add_argument("extra", nargs="*")
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
    parser.add_argument("--status", default="")
    parser.add_argument("--hash", dest="hash_value", default="")
    parser.add_argument("--target", default="")
    parser.add_argument("--control", default="")
    parser.add_argument("--downloader", default="")
    parser.add_argument("--delete-files", action="store_true")
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
    args = normalize_command_args(parser.parse_args())

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
        route_text = args.text or ""
        body = {
            "text": route_text,
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
            "status": args.status or "",
            "hash": args.hash_value or "",
            "target": args.target or "",
            "control": args.control or "",
            "downloader": args.downloader or "",
            "delete_files": bool(args.delete_files),
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
    elif args.command == "followup":
        method = "POST"
        path = assistant_path("action")
        body = {
            "name": "query_execution_followup",
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
    if args.command in {"route", "pick", "workflow", "plan-execute", "followup"} and (args.summary_only or args.command_only) and not args.full:
        output = compact(result)
        summary = compact_command_summary(output)
        print_summary(summary, command_only=args.command_only, confirmed=args.confirmed)
        return 0
    output = result if args.full else compact(result)
    print_json(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
