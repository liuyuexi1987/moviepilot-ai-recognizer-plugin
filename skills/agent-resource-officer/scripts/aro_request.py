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


def main():
    parser = argparse.ArgumentParser(description="AgentResourceOfficer request helper")
    parser.add_argument(
        "command",
        choices=[
            "auto",
            "doctor",
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
    args = parser.parse_args()

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
        if args.summary_only and not args.full:
            summary = {
                "startup_ok": bool((output.get("startup") or {}).get("success")),
                "recommended_recipe_request": (recommended or {}).get("recipe") or recipe,
                "recommended_recipe_reason": (recommended or {}).get("reason") or "",
                **request_templates_summary(templates),
            }
            print_json(summary)
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
            "recovery_can_resume": bool(((output.get("recover") or {}).get("recovery") or {}).get("can_resume")),
            "recommended_action": ((output.get("recover") or {}).get("recovery") or {}).get("recommended_action") or "",
            "recommended_tool": ((output.get("recover") or {}).get("recovery") or {}).get("recommended_tool") or "",
            **helper_commands,
        }
        output["summary"] = summary
        if args.summary_only and not args.full:
            print_json(summary)
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
    output = result if args.full else compact(result)
    print_json(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
