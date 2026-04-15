#!/usr/bin/env python3
"""Unlock HDHive resources through the local MoviePilot plugin.

Supports selecting by cached search result index or direct slug. Defaults to a
safe mode that refuses paid unlocks unless explicitly allowed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

from search_hdhive import DEFAULT_APP_ENV, DEFAULT_CACHE_PATH, DEFAULT_MP_BASE_URL, read_api_token


def read_cache(cache_path: Path) -> Dict[str, Any]:
    if not cache_path.exists():
        raise FileNotFoundError(f"search cache not found: {cache_path}")
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"invalid search cache JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("search cache must be a JSON object")
    return payload


def select_item(cache_payload: Dict[str, Any], index: int) -> Dict[str, Any]:
    items = cache_payload.get("results") or []
    if not isinstance(items, list) or not items:
        raise RuntimeError("search cache has no results")
    for item in items:
        if int(item.get("index", 0)) == index:
            return item
    raise RuntimeError(f"result index {index} not found in cache")


def should_treat_as_paid(points: Any) -> bool:
    return points not in (None, "", 0, "0")


def build_unlock_request(
    *,
    mp_base_url: str,
    api_token: str,
    slug: str,
    transfer_115: bool,
    path: str,
) -> Tuple[str, bytes]:
    query = urllib.parse.urlencode({"apikey": api_token})
    url = f"{mp_base_url.rstrip('/')}/api/v1/plugin/HdhiveOpenApi/resources/unlock?{query}"
    body = {
        "slug": slug,
        "transfer_115": transfer_115,
    }
    if path:
        body["path"] = path
    return url, json.dumps(body).encode("utf-8")


def post_json(url: str, body: bytes) -> Dict[str, Any]:
    request = urllib.request.Request(
        url=url,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {body[:500]}") from exc
    except Exception as exc:
        raise RuntimeError(f"request failed: {exc}") from exc
    try:
        payload = json.loads(raw)
    except Exception as exc:
        raise RuntimeError(f"invalid JSON response: {raw[:300]}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("unlock response must be a JSON object")
    return payload


def normalize_output(
    *,
    selected_item: Dict[str, Any],
    response_payload: Dict[str, Any],
    transfer_115: bool,
    transfer_path: str,
    warning: str,
) -> Dict[str, Any]:
    data = response_payload.get("data") or {}
    unlock_data = data.get("data") if isinstance(data, dict) else {}
    transfer_data = data.get("transfer_115") if isinstance(data, dict) else {}
    return {
        "success": bool(response_payload.get("success")),
        "message": response_payload.get("message", ""),
        "selected": {
            "index": selected_item.get("index"),
            "slug": selected_item.get("slug"),
            "title": selected_item.get("title"),
            "pan_type": selected_item.get("pan_type"),
            "unlock_points": selected_item.get("unlock_points"),
        },
        "unlock": {
            "slug": data.get("slug") if isinstance(data, dict) else selected_item.get("slug"),
            "message": data.get("message", response_payload.get("message", "")) if isinstance(data, dict) else response_payload.get("message", ""),
            "url": unlock_data.get("url") if isinstance(unlock_data, dict) else "",
            "full_url": unlock_data.get("full_url") if isinstance(unlock_data, dict) else "",
            "access_code": unlock_data.get("access_code") if isinstance(unlock_data, dict) else "",
        },
        "transfer_115": {
            "requested": transfer_115,
            "path": transfer_path,
            "ok": bool((transfer_data or {}).get("ok")) if isinstance(transfer_data, dict) else False,
            "message": (transfer_data or {}).get("message", "") if isinstance(transfer_data, dict) else "",
            "save_parent": ((transfer_data or {}).get("data") or {}).get("save_parent", "") if isinstance(transfer_data, dict) else "",
        },
        "warning": warning,
    }


def format_text(payload: Dict[str, Any]) -> str:
    selected = payload.get("selected") or {}
    unlock = payload.get("unlock") or {}
    transfer = payload.get("transfer_115") or {}
    lines: List[str] = []
    lines.append(
        f"解锁结果: {selected.get('title', '—')} | slug={selected.get('slug', '—')} | {payload.get('message', '—')}"
    )
    if payload.get("warning"):
        lines.append(f"提示: {payload['warning']}")
    if unlock.get("full_url") or unlock.get("url"):
        lines.append(f"链接: {unlock.get('full_url') or unlock.get('url')}")
    if unlock.get("access_code"):
        lines.append(f"提取码: {unlock.get('access_code')}")
    if transfer.get("requested"):
        lines.append(
            f"115转存: {'成功' if transfer.get('ok') else '未完成'} | 目录={transfer.get('path', '—')} | {transfer.get('message', '')}"
        )
    return "\n".join(lines)


def execute_unlock(
    *,
    index: int = 0,
    slug: str = "",
    cache_path: Path = DEFAULT_CACHE_PATH,
    allow_paid: bool = False,
    transfer_115: bool = True,
    path: str = "/待整理",
    mp_base_url: str = DEFAULT_MP_BASE_URL,
    app_env: Path = DEFAULT_APP_ENV,
) -> Dict[str, Any]:
    selected_item: Dict[str, Any] = {}
    if index:
        cache_payload = read_cache(Path(os.path.expanduser(str(cache_path))))
        selected_item = select_item(cache_payload, index)
    else:
        selected_item = {
            "index": None,
            "slug": slug.strip(),
            "title": "",
            "pan_type": "",
            "unlock_points": None,
        }

    final_slug = str(selected_item.get("slug") or slug).strip()
    if not final_slug:
        raise RuntimeError("missing slug")

    if should_treat_as_paid(selected_item.get("unlock_points")) and not allow_paid:
        raise RuntimeError(
            f"refusing paid unlock without --allow-paid: "
            f"{selected_item.get('title', slug)} needs {selected_item.get('unlock_points')} points"
        )

    warning = ""
    pan_type = str(selected_item.get("pan_type") or "").strip().lower()
    if pan_type and pan_type != "115" and transfer_115:
        transfer_115 = False
        warning = f"selected resource pan_type={selected_item.get('pan_type')}，已自动关闭 115 转存"

    token = read_api_token(Path(app_env))

    url, body = build_unlock_request(
        mp_base_url=mp_base_url,
        api_token=token,
        slug=final_slug,
        transfer_115=transfer_115,
        path=path.strip(),
    )
    response_payload = post_json(url, body)

    output = normalize_output(
        selected_item=selected_item,
        response_payload=response_payload,
        transfer_115=transfer_115,
        transfer_path=path.strip(),
        warning=warning,
    )
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unlock HDHive resources through local MoviePilot.")
    parser.add_argument("--index", type=int, default=0, help="Select result by cached search index")
    parser.add_argument("--slug", default="", help="Direct HDHive resource slug")
    parser.add_argument("--cache-path", default=str(DEFAULT_CACHE_PATH), help="Search cache path")
    parser.add_argument("--allow-paid", action="store_true", help="Allow unlocks that cost points")
    parser.add_argument("--transfer-115", dest="transfer_115", action="store_true", help="Try 115 transfer after unlock")
    parser.add_argument("--no-transfer-115", dest="transfer_115", action="store_false", help="Disable 115 transfer")
    parser.set_defaults(transfer_115=True)
    parser.add_argument("--path", default="/待整理", help="115 transfer target path")
    parser.add_argument("--format", choices=["json", "text"], default="json", help="Output format")
    parser.add_argument("--mp-base-url", default=DEFAULT_MP_BASE_URL, help="Local MoviePilot base URL")
    parser.add_argument("--app-env", default=str(DEFAULT_APP_ENV), help="Path to MoviePilot app.env")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.index and not args.slug.strip():
        parser.error("--index or --slug is required")

    try:
        output = execute_unlock(
            index=args.index,
            slug=args.slug,
            cache_path=Path(args.cache_path),
            allow_paid=args.allow_paid,
            transfer_115=args.transfer_115,
            path=args.path,
            mp_base_url=args.mp_base_url,
            app_env=Path(args.app_env),
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "text":
        print(format_text(output))
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
