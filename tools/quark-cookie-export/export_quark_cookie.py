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
        description="Export Quark browser cookies and optionally write them back into MoviePilot plugin config."
    )
    parser.add_argument(
        "site",
        nargs="?",
        default="https://pan.quark.cn",
        help="Quark site URL. Default: https://pan.quark.cn",
    )
    parser.add_argument(
        "--browser",
        choices=["chrome", "edge", "brave", "chromium", "firefox", "opera", "vivaldi"],
        default="edge",
        help="Browser to read cookies from. Default: edge",
    )
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Do not copy the cookie header to clipboard.",
    )
    parser.add_argument(
        "--show-cookie",
        action="store_true",
        help="Print the raw cookie header to stdout. Disabled by default for safety.",
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
        help="MoviePilot sqlite config DB path.",
    )
    parser.add_argument(
        "--aro-plugin-key",
        default="plugin.AgentResourceOfficer",
        help="MoviePilot systemconfig key for AgentResourceOfficer. Default: plugin.AgentResourceOfficer",
    )
    parser.add_argument(
        "--qss-plugin-key",
        default="plugin.QuarkShareSaver",
        help="MoviePilot systemconfig key for QuarkShareSaver. Default: plugin.QuarkShareSaver",
    )
    parser.add_argument(
        "--restart-container",
        help="Optional Docker container name to restart after writing MoviePilot config.",
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
    except Exception as exc:
        raise RuntimeError(
            f"Failed to read cookies from {browser}. Make sure the browser is installed, "
            "you are logged in to Quark, and pan.quark.cn has been opened at least once."
        ) from exc


def domain_matches(cookie_domain: str, domain: str) -> bool:
    cookie_domain = cookie_domain.lstrip(".")
    return (
        cookie_domain == domain
        or domain.endswith(f".{cookie_domain}")
        or cookie_domain.endswith(f".{domain}")
    )


def build_cookie_list(cookiejar, domain: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for cookie in cookiejar:
        if not domain_matches(cookie.domain, domain):
            continue
        if cookie.name in seen:
            continue
        seen.add(cookie.name)
        items.append(
            {
                "domain": cookie.domain.lstrip("."),
                "name": cookie.name,
                "value": cookie.value,
            }
        )
    return items


def cookie_list_to_header(items: list[dict[str, str]]) -> str:
    return "; ".join(f"{item['name']}={item['value']}" for item in items if item.get("name"))


def copy_to_clipboard(text: str) -> None:
    subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)


def update_plugin_cookie(db_path: Path, plugin_key: str, field_name: str, cookie_header: str) -> tuple[dict, bool]:
    if not db_path.exists():
        raise RuntimeError(f"MoviePilot DB not found: {db_path}")
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        row = cur.execute("SELECT value FROM systemconfig WHERE key = ?", (plugin_key,)).fetchone()
        created = False
        if row and row[0]:
            try:
                config = json.loads(row[0])
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Existing config for {plugin_key} is not valid JSON") from exc
        else:
            config = {"enabled": True}
            created = True
        config[field_name] = cookie_header
        payload = json.dumps(config, ensure_ascii=False)
        if row:
            cur.execute("UPDATE systemconfig SET value = ? WHERE key = ?", (payload, plugin_key))
        else:
            cur.execute("INSERT INTO systemconfig(key, value) VALUES(?, ?)", (plugin_key, payload))
            created = True
        conn.commit()
        return config, created
    finally:
        conn.close()


def restart_container(container_name: str) -> None:
    subprocess.run(["docker", "restart", container_name], check=True)


def main() -> int:
    args = parse_args()
    try:
        domain = normalize_domain(args.site)
        cookiejar = load_cookiejar(args.browser, domain)
        items = build_cookie_list(cookiejar, domain)
        cookie_header = cookie_list_to_header(items)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not cookie_header:
        print(
            f"Error: no cookies found for {domain}. Open pan.quark.cn in {args.browser} and log in first.",
            file=sys.stderr,
        )
        return 1

    if not args.no_copy:
        try:
            copy_to_clipboard(cookie_header)
        except Exception as exc:
            print(f"Warning: failed to copy to clipboard: {exc}", file=sys.stderr)

    if args.show_cookie:
        print(cookie_header)

    print(f"Domain: {domain}", file=sys.stderr)
    print(f"Length: {len(cookie_header)}", file=sys.stderr)
    print("Found cookie names: " + ", ".join(item["name"] for item in items), file=sys.stderr)

    if args.write_mp:
        try:
            _, aro_created = update_plugin_cookie(args.mp_db, args.aro_plugin_key, "quark_cookie", cookie_header)
            print(
                f"AgentResourceOfficer Quark cookie updated: {args.aro_plugin_key} -> {args.mp_db}",
                file=sys.stderr,
            )
            if aro_created:
                print("AgentResourceOfficer config row did not exist and was created.", file=sys.stderr)

            _, qss_created = update_plugin_cookie(args.mp_db, args.qss_plugin_key, "cookie", cookie_header)
            print(
                f"QuarkShareSaver cookie updated: {args.qss_plugin_key} -> {args.mp_db}",
                file=sys.stderr,
            )
            if qss_created:
                print("QuarkShareSaver config row did not exist and was created.", file=sys.stderr)

            if args.restart_container:
                restart_container(args.restart_container)
                print(f"Docker container restarted: {args.restart_container}", file=sys.stderr)
        except Exception as exc:
            print(f"Error: failed to update MoviePilot config: {exc}", file=sys.stderr)
            return 3

    if args.write_mp:
        if args.no_copy:
            print("Quark cookie exported successfully and written back to MoviePilot.", file=sys.stderr)
        else:
            print(
                "Quark cookie exported successfully, copied to clipboard, and written back to MoviePilot.",
                file=sys.stderr,
            )
    else:
        if args.no_copy:
            print("Quark cookie exported successfully.", file=sys.stderr)
        else:
            print("Quark cookie exported successfully and copied to clipboard.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
