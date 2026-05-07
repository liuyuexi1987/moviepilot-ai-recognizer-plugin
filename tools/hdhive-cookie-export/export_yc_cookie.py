#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export browser cookies for a site into a single Cookie header string."
    )
    parser.add_argument(
        "site",
        help="Site domain or full URL, for example yc.example.com or https://yc.example.com",
    )
    parser.add_argument(
        "--browser",
        choices=["chrome", "edge", "brave", "chromium", "firefox", "opera", "vivaldi"],
        default="chrome",
        help="Browser to read cookies from. Default: chrome",
    )
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Print only and do not copy the result to clipboard.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Optional file path to write the cookie string to.",
    )
    parser.add_argument(
        "--write-mp",
        action="store_true",
        help="Write the exported cookie back into MoviePilot plugin config.",
    )
    parser.add_argument(
        "--mp-db",
        type=Path,
        default=Path("/Applications/Dockge/moviepilotv2/config/user.db"),
        help="MoviePilot sqlite config DB path. Default: /Applications/Dockge/moviepilotv2/config/user.db",
    )
    parser.add_argument(
        "--mp-plugin-key",
        default="plugin.HdhiveSign",
        help="MoviePilot systemconfig key for the HDHive plugin. Default: plugin.HdhiveSign",
    )
    parser.add_argument(
        "--aro-plugin-key",
        default="plugin.AgentResourceOfficer",
        help="MoviePilot systemconfig key for AgentResourceOfficer. Default: plugin.AgentResourceOfficer",
    )
    parser.add_argument(
        "--restart-container",
        help="Optional Docker container name to restart after writing MoviePilot config, for example moviepilot-v2",
    )
    parser.add_argument(
        "--hdhive-json",
        type=Path,
        default=Path("/Applications/Dockge/moviepilotv2/config/plugins/hdhivedailysign.json"),
        help="Optional HDHiveDailySign JSON config path to update alongside MoviePilot config.",
    )
    return parser.parse_args()


def normalize_domain(site: str) -> str:
    if "://" not in site:
        site = f"https://{site}"
    parsed = urlparse(site)
    domain = parsed.hostname
    if not domain:
        raise ValueError(f"Could not parse domain from input: {site}")
    return domain


def load_cookiejar(browser: str, domain: str):
    try:
        import browser_cookie3
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'browser_cookie3'. Install it with: pip3 install browser-cookie3"
        ) from exc

    loader = getattr(browser_cookie3, browser, None)
    if loader is None:
        raise RuntimeError(f"Browser '{browser}' is not supported by browser_cookie3")

    try:
        return loader(domain_name=domain)
    except Exception as exc:  # pragma: no cover - depends on local browser setup
        raise RuntimeError(
            f"Failed to read cookies from {browser}. Make sure the browser is installed, "
            "you are logged in to the site, and the site has been opened at least once."
        ) from exc


def build_cookie_header(cookiejar, domain: str) -> str:
    items: list[str] = []
    seen: set[str] = set()

    for cookie in cookiejar:
        cookie_domain = cookie.domain.lstrip(".")
        if not (cookie_domain == domain or domain.endswith(f".{cookie_domain}") or cookie_domain.endswith(f".{domain}")):
            continue
        if cookie.name in seen:
            continue
        seen.add(cookie.name)
        items.append(f"{cookie.name}={cookie.value}")

    return "; ".join(items)


def build_cookie_map(cookiejar, domain: str) -> dict[str, str]:
    items: dict[str, str] = {}
    for cookie in cookiejar:
        cookie_domain = cookie.domain.lstrip(".")
        if not (
            cookie_domain == domain
            or domain.endswith(f".{cookie_domain}")
            or cookie_domain.endswith(f".{domain}")
        ):
            continue
        items.setdefault(cookie.name, cookie.value)
    return items


def extract_cookie_names(cookiejar, domain: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    for cookie in cookiejar:
        cookie_domain = cookie.domain.lstrip(".")
        if not (
            cookie_domain == domain
            or domain.endswith(f".{cookie_domain}")
            or cookie_domain.endswith(f".{domain}")
        ):
            continue
        if cookie.name in seen:
            continue
        seen.add(cookie.name)
        names.append(cookie.name)

    return names


def copy_to_clipboard(text: str) -> None:
    subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)


def build_mp_cookie_header(cookie_map: dict[str, str]) -> str:
    names = ["token", "csrf_access_token", "refresh_token"]
    parts = [f"{name}={cookie_map[name]}" for name in names if cookie_map.get(name)]
    if parts:
        return "; ".join(parts)
    return "; ".join(f"{name}={value}" for name, value in cookie_map.items())


def update_moviepilot_config(db_path: Path, plugin_key: str, cookie_header: str) -> tuple[dict, bool]:
    if not db_path.exists():
        raise RuntimeError(f"MoviePilot DB not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT value FROM systemconfig WHERE key = ?",
            (plugin_key,),
        ).fetchone()

        created = False
        if row and row[0]:
            try:
                config = json.loads(row[0])
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Existing config for {plugin_key} is not valid JSON") from exc
        else:
            config = {"enabled": True}
            created = True

        config["cookie"] = cookie_header

        payload = json.dumps(config, ensure_ascii=False)
        if row:
            cur.execute(
                "UPDATE systemconfig SET value = ? WHERE key = ?",
                (payload, plugin_key),
            )
        else:
            cur.execute(
                "INSERT INTO systemconfig(key, value) VALUES(?, ?)",
                (plugin_key, payload),
            )
            created = True

        conn.commit()
        return config, created
    finally:
        conn.close()


def update_agent_resource_officer_config(
    db_path: Path,
    plugin_key: str,
    cookie_header: str,
) -> tuple[dict, bool]:
    if not db_path.exists():
        raise RuntimeError(f"MoviePilot DB not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT value FROM systemconfig WHERE key = ?",
            (plugin_key,),
        ).fetchone()

        created = False
        if row and row[0]:
            try:
                config = json.loads(row[0])
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Existing config for {plugin_key} is not valid JSON") from exc
        else:
            config = {"enabled": True}
            created = True

        config["hdhive_checkin_cookie"] = cookie_header

        payload = json.dumps(config, ensure_ascii=False)
        if row:
            cur.execute(
                "UPDATE systemconfig SET value = ? WHERE key = ?",
                (payload, plugin_key),
            )
        else:
            cur.execute(
                "INSERT INTO systemconfig(key, value) VALUES(?, ?)",
                (plugin_key, payload),
            )
            created = True

        conn.commit()
        return config, created
    finally:
        conn.close()


def update_hdhive_daily_sign_json(file_path: Path, cookie_header: str) -> tuple[dict, bool]:
    created = False
    if file_path.exists():
        try:
            config = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Existing HDHiveDailySign config is not valid JSON: {file_path}"
            ) from exc
    else:
        config = {}
        created = True

    if not isinstance(config, dict):
        raise RuntimeError(f"HDHiveDailySign config is not an object: {file_path}")

    config["cookie"] = cookie_header
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return config, created


def restart_container(container_name: str) -> None:
    subprocess.run(["docker", "restart", container_name], check=True)


def main() -> int:
    args = parse_args()

    try:
        domain = normalize_domain(args.site)
        cookiejar = load_cookiejar(args.browser, domain)
        cookie_map = build_cookie_map(cookiejar, domain)
        cookie_names = extract_cookie_names(cookiejar, domain)
        cookie_header = build_cookie_header(cookiejar, domain)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not cookie_header:
        print(
            f"Error: no cookies found for {domain}. Open the site in {args.browser} and log in first.",
            file=sys.stderr,
        )
        return 1

    missing = [name for name in ("token", "csrf_access_token") if f"{name}=" not in cookie_header]

    mp_cookie_header = build_mp_cookie_header(cookie_map)

    if args.out:
        args.out.write_text(cookie_header, encoding="utf-8")

    if not args.no_copy:
        try:
            copy_to_clipboard(cookie_header)
        except Exception as exc:
            print(f"Warning: failed to copy to clipboard: {exc}", file=sys.stderr)

    print(cookie_header)
    print(file=sys.stderr)
    print(f"Domain: {domain}", file=sys.stderr)
    print(f"Length: {len(cookie_header)}", file=sys.stderr)
    print(
        "Found cookie names: " + (", ".join(cookie_names) if cookie_names else "(none)"),
        file=sys.stderr,
    )
    print(
        "MoviePilot cookie payload: " + (mp_cookie_header or "(empty)"),
        file=sys.stderr,
    )
    if missing:
        if "token" not in missing and "csrf_access_token" in missing:
            print(
                "Warning: browser contains token, but not csrf_access_token.",
                file=sys.stderr,
            )
            print(
                "This usually means the site did not issue a csrf cookie for the current login flow.",
                file=sys.stderr,
            )
            print(
                "For current HDHive + MoviePilot plugin, token-only mode is supported, so export/update can continue.",
                file=sys.stderr,
            )
        else:
            print(
                "Warning: missing required fields: "
                + ", ".join(missing)
                + ". You may need to re-login or confirm the correct site domain.",
                file=sys.stderr,
            )
            return 2

    if args.write_mp:
        try:
            _, created = update_moviepilot_config(args.mp_db, args.mp_plugin_key, mp_cookie_header)
            print(
                f"MoviePilot config updated: {args.mp_plugin_key} -> {args.mp_db}",
                file=sys.stderr,
            )
            if created:
                print("MoviePilot config row did not exist and was created.", file=sys.stderr)
            _, aro_created = update_agent_resource_officer_config(
                args.mp_db,
                args.aro_plugin_key,
                mp_cookie_header,
            )
            print(
                f"AgentResourceOfficer config updated: {args.aro_plugin_key} -> {args.mp_db}",
                file=sys.stderr,
            )
            if aro_created:
                print("AgentResourceOfficer config row did not exist and was created.", file=sys.stderr)
            if args.hdhive_json:
                _, json_created = update_hdhive_daily_sign_json(args.hdhive_json, mp_cookie_header)
                print(f"HDHiveDailySign cookie updated: {args.hdhive_json}", file=sys.stderr)
                if json_created:
                    print("HDHiveDailySign JSON did not exist and was created.", file=sys.stderr)
            if args.restart_container:
                restart_container(args.restart_container)
                print(f"Docker container restarted: {args.restart_container}", file=sys.stderr)
        except Exception as exc:
            print(f"Error: failed to update MoviePilot config: {exc}", file=sys.stderr)
            return 3

    if args.write_mp:
        if args.no_copy:
            print("Cookie exported successfully and written back to MoviePilot/HDHiveDailySign.", file=sys.stderr)
        else:
            print(
                "Cookie exported successfully, copied to clipboard, and written back to MoviePilot/HDHiveDailySign.",
                file=sys.stderr,
            )
    else:
        if args.no_copy:
            print("Cookie exported successfully.", file=sys.stderr)
        else:
            print("Cookie exported successfully and copied to clipboard.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
