#!/usr/bin/env python3
"""Single-entry helper for stable, low-noise HDHive agent workflows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

import search_hdhive
import unlock_hdhive


def format_search_for_agent(payload: Dict[str, Any]) -> str:
    return search_hdhive.format_text(payload, compact=True)


def format_unlock_for_agent(payload: Dict[str, Any]) -> str:
    return unlock_hdhive.format_text(payload)


def emit(payload: Dict[str, Any], output: str, *, text: str) -> None:
    if output == "json":
        final_payload = dict(payload)
        final_payload["text"] = text
        print(json.dumps(final_payload, ensure_ascii=False, indent=2))
        return
    print(text)


def command_search(args: argparse.Namespace) -> int:
    try:
        payload = search_hdhive.execute_search(
            keyword=args.keyword,
            media_type=args.type,
            tmdb_id=args.tmdb_id,
            year=args.year,
            limit=args.limit,
            candidate_limit=args.candidate_limit,
            mp_base_url=args.mp_base_url,
            app_env=Path(args.app_env),
            cache_path=Path(args.cache_path),
            use_cache=not args.no_cache,
            tmdb_api_key=args.tmdb_api_key,
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2
    text = format_search_for_agent(payload)
    emit(payload, args.output, text=text)
    return 0 if payload.get("success") else 1


def command_show(args: argparse.Namespace) -> int:
    cache_path = Path(args.cache_path).expanduser()
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"读取缓存失败: {exc}", file=sys.stderr)
        return 2
    if not isinstance(payload, dict):
        print("缓存格式无效", file=sys.stderr)
        return 2
    text = format_search_for_agent(payload)
    emit(payload, args.output, text=text)
    return 0


def command_unlock(args: argparse.Namespace) -> int:
    try:
        payload = unlock_hdhive.execute_unlock(
            index=args.index,
            slug=args.slug,
            cache_path=Path(args.cache_path),
            allow_paid=args.allow_paid,
            transfer_115=not args.no_transfer_115,
            path=args.path,
            mp_base_url=args.mp_base_url,
            app_env=Path(args.app_env),
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    text = format_unlock_for_agent(payload)
    emit(payload, args.output, text=text)
    return 0 if payload.get("success") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Single-entry HDHive agent helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Search and cache HDHive results")
    search_parser.add_argument("keyword", help="Movie or TV keyword")
    search_parser.add_argument("--type", choices=["auto", "movie", "tv"], default="auto")
    search_parser.add_argument("--tmdb-id", default="")
    search_parser.add_argument("--year", default="")
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument("--candidate-limit", type=int, default=5)
    search_parser.add_argument("--cache-path", default=str(search_hdhive.DEFAULT_CACHE_PATH))
    search_parser.add_argument("--no-cache", action="store_true")
    search_parser.add_argument("--app-env", default=str(search_hdhive.DEFAULT_APP_ENV))
    search_parser.add_argument("--mp-base-url", default=search_hdhive.DEFAULT_MP_BASE_URL)
    search_parser.add_argument("--tmdb-api-key", default="", help="Optional TMDB API key override for actor enrichment")
    search_parser.add_argument("--output", choices=["text", "json"], default="text")
    search_parser.set_defaults(func=command_search)

    show_parser = subparsers.add_parser("show", help="Show cached search results")
    show_parser.add_argument("--cache-path", default=str(search_hdhive.DEFAULT_CACHE_PATH))
    show_parser.add_argument("--output", choices=["text", "json"], default="text")
    show_parser.set_defaults(func=command_show)

    unlock_parser = subparsers.add_parser("unlock", help="Unlock cached result by index or slug")
    unlock_parser.add_argument("--index", type=int, default=0)
    unlock_parser.add_argument("--slug", default="")
    unlock_parser.add_argument("--allow-paid", action="store_true")
    unlock_parser.add_argument("--no-transfer-115", action="store_true")
    unlock_parser.add_argument("--path", default="/待整理")
    unlock_parser.add_argument("--cache-path", default=str(search_hdhive.DEFAULT_CACHE_PATH))
    unlock_parser.add_argument("--app-env", default=str(search_hdhive.DEFAULT_APP_ENV))
    unlock_parser.add_argument("--mp-base-url", default=search_hdhive.DEFAULT_MP_BASE_URL)
    unlock_parser.add_argument("--output", choices=["text", "json"], default="text")
    unlock_parser.set_defaults(func=command_unlock)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
