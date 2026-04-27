#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


CONFIG_PATH = os.path.expanduser("~/.config/agent-resource-officer/config")


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


def load_json_arg(value):
    if not value:
        return {}
    if value.startswith("@"):
        with open(value[1:], "r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
            return data if isinstance(data, dict) else {}
    data = json.loads(value)
    return data if isinstance(data, dict) else {}


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
            "recommended_request_templates",
            "recommended_recipe_detail",
            "next_actions",
            "recovery",
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


def print_summary(summary, command_only=False, confirmed=False):
    if command_only:
        summary = summary or {}
        requires_confirmation = bool(summary.get("requires_confirmation"))
        command = str(summary.get("execute_helper_command") or "").strip()
        if requires_confirmation and not confirmed:
            command = str(summary.get("inspect_helper_command") or command).strip()
        if not command:
            command = str(summary.get("inspect_helper_command") or "").strip()
        print(command)
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
    target_path = str(body.get("path") or action_body.get("path") or "").strip()

    session_part = f" --session {shell_quote(session)}" if session else ""
    session_id_part = f" --session-id {shell_quote(session_id)}" if session_id else ""
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
            f"{session_part}{session_id_part}"
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


def run_selftest():
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

    bootstrap_commands = recipe_helper_commands({"first_template": "startup_probe"}, "bootstrap")
    check("bootstrap_execute_command", bootstrap_commands.get("execute_helper_command") == "python3 scripts/aro_request.py startup")
    check("bootstrap_inspect_command", bootstrap_commands.get("inspect_helper_command") == "python3 scripts/aro_request.py templates --recipe 'bootstrap' --policy-only")

    workflow_commands = recipe_helper_commands({"first_template": "workflow_dry_run"}, "plan")
    check("workflow_dry_run_command", workflow_commands.get("execute_helper_command") == "python3 scripts/aro_request.py workflow --workflow <workflow> --keyword <keyword>")

    quote_value = shell_quote("a'b")
    check("shell_quote_single_quote", quote_value == "'a'\"'\"'b'")

    passed = sum(1 for item in checks if item.get("ok"))
    failed = [item for item in checks if not item.get("ok")]
    result = {
        "success": not failed,
        "passed": passed,
        "failed": len(failed),
        "checks": checks,
    }
    print_json(result)
    return 0 if not failed else 1


def main():
    parser = argparse.ArgumentParser(description="AgentResourceOfficer request helper")
    parser.add_argument(
        "command",
        choices=[
            "auto",
            "decide",
            "doctor",
            "selftest",
            "startup",
            "selfcheck",
            "templates",
            "route",
            "pick",
            "workflow",
            "plan-execute",
            "maintain",
            "recover",
            "session",
            "sessions",
            "history",
            "plans",
            "raw",
        ],
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
    parser.add_argument("--kind")
    parser.add_argument("--has-pending-p115", action="store_true")
    parser.add_argument("--choice", type=int)
    parser.add_argument("--action")
    parser.add_argument("--path", dest="target_path")
    parser.add_argument("--workflow", default="hdhive_candidates")
    parser.add_argument("--keyword")
    parser.add_argument("--media-type", default="movie")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--executed", action="store_true")
    parser.add_argument("--include-actions", action="store_true")
    parser.add_argument("--prefer-unexecuted", action="store_true")
    parser.add_argument("--include-raw-results", action="store_true")
    parser.add_argument("--method", default="GET")
    parser.add_argument("--api-path")
    parser.add_argument("--json", dest="json_body")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--command-only", action="store_true")
    parser.add_argument("--confirmed", action="store_true")
    args = parser.parse_args()

    if args.command == "selftest":
        return run_selftest()

    config = read_config()
    base_url = args.base_url or config_value(config, "ARO_BASE_URL", "MP_BASE_URL", "MOVIEPILOT_URL")
    api_key = args.api_key or config_value(config, "ARO_API_KEY", "MP_API_TOKEN")
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
        if args.target_path:
            body["path"] = args.target_path
    elif args.command == "workflow":
        method = "POST"
        path = assistant_path("workflow")
        body = {
            "workflow": args.workflow,
            "name": args.workflow,
            "keyword": args.keyword or "",
            "media_type": args.media_type,
            "dry_run": True,
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
                "execute": "true",
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
        if args.session:
            query["session"] = args.session
        if args.session_id:
            query["session_id"] = args.session_id
        if args.executed:
            query["executed"] = "true"
        if args.include_actions:
            query["include_actions"] = "true"
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
