#!/usr/bin/env python3
"""Search HDHive resources through the local MoviePilot plugin."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_MP_BASE_URL = os.environ.get("MP_BASE_URL", "http://127.0.0.1:3000").strip() or "http://127.0.0.1:3000"
DEFAULT_APP_ENV = Path(os.environ.get("MP_APP_ENV", "/config/app.env")).expanduser()
DEFAULT_CACHE_PATH = Path(
    os.environ.get("HDHIVE_SEARCH_CACHE", "~/.cache/hdhive-search-unlock-to-115/cache.json")
).expanduser()
TMDB_API_BASE = "https://api.themoviedb.org/3"
COMMON_APP_ENV_PATHS = [
    Path("/config/app.env"),
    Path("./config/app.env"),
    Path("./app.env"),
    Path("~/moviepilot/config/app.env").expanduser(),
]


def read_api_token(app_env_path: Path) -> str:
    candidates: List[Path] = []
    if str(app_env_path).strip() and str(app_env_path) != ".":
        candidates.append(app_env_path.expanduser())
    env_override = os.environ.get("MP_APP_ENV", "").strip()
    if env_override:
        candidates.append(Path(env_override).expanduser())
    candidates.extend(COMMON_APP_ENV_PATHS)

    checked: List[Path] = []
    for candidate in candidates:
        if candidate in checked:
            continue
        checked.append(candidate)
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("API_TOKEN="):
                return line.split("=", 1)[1].strip().strip("'\"")
        raise RuntimeError(f"API_TOKEN not found in app.env: {candidate}")
    raise FileNotFoundError("MoviePilot app.env not found. Set MP_APP_ENV or pass --app-env.")


def load_json(url: str) -> Dict[str, Any]:
    request = urllib.request.Request(url=url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {body[:300]}") from exc
    except Exception as exc:
        raise RuntimeError(f"request failed: {exc}") from exc
    try:
        return json.loads(raw)
    except Exception as exc:
        raise RuntimeError(f"invalid JSON response: {raw[:300]}") from exc


def fetch_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 60) -> Dict[str, Any]:
    request = urllib.request.Request(url=url, headers={"Accept": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {body[:300]}") from exc
    except Exception as exc:
        raise RuntimeError(f"request failed: {exc}") from exc
    try:
        data = json.loads(raw)
    except Exception as exc:
        raise RuntimeError(f"invalid JSON response: {raw[:300]}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("response must be a JSON object")
    return data


def read_tmdb_api_key(explicit_key: str = "") -> str:
    if explicit_key.strip():
        return explicit_key.strip()
    env_key = os.environ.get("TMDB_API_KEY", "").strip()
    if env_key:
        return env_key
    return ""


def build_search_url(
    *,
    mp_base_url: str,
    api_token: str,
    media_type: str,
    keyword: str,
    tmdb_id: str,
    year: str,
    candidate_limit: int,
    result_limit: int,
) -> str:
    params: Dict[str, Any] = {
        "type": media_type,
        "apikey": api_token,
        "candidate_limit": candidate_limit,
        "limit": result_limit,
    }
    if tmdb_id:
        params["tmdb_id"] = tmdb_id
    else:
        params["keyword"] = keyword
    if year:
        params["year"] = year
    query = urllib.parse.urlencode(params)
    return f"{mp_base_url.rstrip('/')}/api/v1/plugin/HdhiveOpenApi/resources/search?{query}"


def normalize_title(text: str) -> str:
    return re.sub(r"[\W_]+", "", (text or "").strip().lower())


def choose_best_result(keyword: str, results: List[Tuple[str, Dict[str, Any]]]) -> Tuple[str, Dict[str, Any]]:
    normalized_keyword = normalize_title(keyword)

    def score(item: Tuple[str, Dict[str, Any]]) -> Tuple[int, int, int, int, int]:
        _, payload = item
        data = payload.get("data") if isinstance(payload, dict) else {}
        items = data.get("data") if isinstance(data, dict) else []
        candidates = data.get("candidates") if isinstance(data, dict) else []
        candidate_titles = [
            normalize_title(str(entry.get("title") or ""))
            for entry in (candidates or [])
            if isinstance(entry, dict)
        ]
        matched_titles = [
            normalize_title(str(entry.get("matched_title") or entry.get("title") or ""))
            for entry in (items or [])[:5]
            if isinstance(entry, dict)
        ]
        exact_match = 1 if normalized_keyword and any(title == normalized_keyword for title in candidate_titles + matched_titles) else 0
        contains_match = 1 if normalized_keyword and any(normalized_keyword in title for title in candidate_titles + matched_titles if title) else 0
        return (
            exact_match,
            contains_match,
            len(items or []),
            len(candidates or []),
            1 if payload.get("success") else 0,
        )

    ranked = sorted(results, key=score, reverse=True)
    return ranked[0]


def normalize_items(items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for index, item in enumerate(items[:limit], start=1):
        normalized.append(
            {
                "index": index,
                "slug": item.get("slug", ""),
                "title": item.get("title", ""),
                "matched_title": item.get("matched_title", ""),
                "matched_year": item.get("matched_year", ""),
                "pan_type": item.get("pan_type", ""),
                "share_size": item.get("share_size", ""),
                "source": item.get("source") or [],
                "video_resolution": item.get("video_resolution") or [],
                "unlock_points": item.get("unlock_points"),
                "is_unlocked": bool(item.get("is_unlocked")),
                "is_official": bool(item.get("is_official")),
                "is_valid": item.get("is_valid"),
            }
        )
    return normalized


def normalize_candidates(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in items[:10]:
        normalized.append(
            {
                "tmdb_id": item.get("tmdb_id"),
                "title": item.get("title"),
                "year": item.get("year"),
                "media_type": item.get("media_type") or item.get("type"),
            }
        )
    return normalized


def fetch_candidate_actors(tmdb_id: Any, media_type: str, tmdb_api_key: str) -> List[str]:
    clean_tmdb_id = str(tmdb_id or "").strip()
    clean_media_type = str(media_type or "").strip().lower()
    if not clean_tmdb_id or clean_media_type not in {"movie", "tv"} or not tmdb_api_key:
        return []
    endpoint = "movie" if clean_media_type == "movie" else "tv"
    query = urllib.parse.urlencode(
        {
            "api_key": tmdb_api_key,
            "language": "zh-CN",
            "append_to_response": "credits",
        }
    )
    url = f"{TMDB_API_BASE}/{endpoint}/{clean_tmdb_id}?{query}"
    try:
        payload = fetch_json(url, timeout=20)
    except Exception:
        return []
    cast = ((payload.get("credits") or {}).get("cast") or []) if isinstance(payload, dict) else []
    actors: List[str] = []
    for member in cast[:10]:
        name = str((member or {}).get("name") or "").strip()
        department = str((member or {}).get("known_for_department") or "").strip()
        if not name:
            continue
        if department and department != "Acting":
            continue
        if name not in actors:
            actors.append(name)
        if len(actors) >= 2:
            break
    return actors


def enrich_candidates_with_actors(candidates: List[Dict[str, Any]], tmdb_api_key: str) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for item in candidates:
        candidate = dict(item)
        candidate["actors"] = fetch_candidate_actors(
            tmdb_id=candidate.get("tmdb_id"),
            media_type=str(candidate.get("media_type") or candidate.get("type") or "").lower(),
            tmdb_api_key=tmdb_api_key,
        )
        enriched.append(candidate)
    return enriched


def has_ambiguous_candidates(payload: Dict[str, Any]) -> bool:
    candidates = payload.get("candidates") or []
    if not isinstance(candidates, list):
        return False
    return len(candidates) > 1


def format_text(payload: Dict[str, Any], *, compact: bool = False) -> str:
    query = payload.get("query") or {}
    items = payload.get("results") or []
    candidates = payload.get("candidates") or []
    lines: List[str] = []
    if not compact:
        lines.append(
            f"影巢搜索: type={query.get('selected_type', query.get('type', '—'))} "
            f"keyword={query.get('keyword', '—')} year={query.get('year', '—')}"
        )
    if candidates and (not compact or has_ambiguous_candidates(payload)):
        lines.append("候选影片:")
        for item in candidates[:5]:
            actors = item.get("actors") or []
            actor_text = f" | 主演:{' / '.join(actors[:2])}" if actors else ""
            lines.append(
                f"- TMDB:{item.get('tmdb_id', '—')} | {item.get('title', '—')} ({item.get('year', '—')}) | {item.get('media_type', '—')}{actor_text}"
            )
    if not items:
        lines.append("没有找到影巢资源。")
        return "\n".join(lines)

    lines.append("前10条资源:")
    for item in items:
        matched = item.get("matched_title") or item.get("title") or "—"
        matched_year = item.get("matched_year")
        if matched_year:
            matched = f"{matched} ({matched_year})"
        resolution = "/".join(item.get("video_resolution") or []) or "—"
        source = "/".join(item.get("source") or []) or "—"
        points = item.get("unlock_points")
        point_text = "免费" if points in (None, "", 0, "0") else f"{points}分"
        lines.append(
            f"{item['index']}. {item.get('title', '—')} | 匹配:{matched} | "
            f"{item.get('pan_type', '—')} | {item.get('share_size', '—')} | "
            f"{resolution} | {source} | {point_text} | slug={item.get('slug', '')}"
        )
    if payload.get("cache_path") and not compact:
        lines.append(f"缓存: {payload['cache_path']}")
    return "\n".join(lines)


def write_cache(cache_path: Path, payload: Dict[str, Any]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def execute_search(
    *,
    keyword: str,
    media_type: str = "auto",
    tmdb_id: str = "",
    year: str = "",
    limit: int = 10,
    candidate_limit: int = 5,
    mp_base_url: str = DEFAULT_MP_BASE_URL,
    app_env: Path = DEFAULT_APP_ENV,
    cache_path: Path = DEFAULT_CACHE_PATH,
    use_cache: bool = True,
    tmdb_api_key: str = "",
) -> Dict[str, Any]:
    try:
        token = read_api_token(Path(app_env))
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc

    requested_type = media_type
    types = [requested_type] if requested_type != "auto" else ["movie", "tv"]
    attempts: List[Tuple[str, Dict[str, Any]]] = []
    for candidate_type in types:
        url = build_search_url(
            mp_base_url=mp_base_url,
            api_token=token,
            media_type=candidate_type,
            keyword=keyword.strip(),
            tmdb_id=tmdb_id.strip(),
            year=year.strip(),
            candidate_limit=max(1, min(10, candidate_limit)),
            result_limit=max(1, min(20, limit)),
        )
        try:
            payload = load_json(url)
        except Exception as exc:
            payload = {"success": False, "message": str(exc), "data": {}}
        attempts.append((candidate_type, payload))

    selected_type, selected_payload = choose_best_result(keyword.strip(), attempts)
    raw_data = selected_payload.get("data") if isinstance(selected_payload, dict) else {}
    raw_items = raw_data.get("data") if isinstance(raw_data, dict) else []
    raw_candidates = raw_data.get("candidates") if isinstance(raw_data, dict) else []

    normalized_candidates = normalize_candidates(raw_candidates or [])
    if len(normalized_candidates) > 1:
        normalized_candidates = enrich_candidates_with_actors(
            normalized_candidates,
            read_tmdb_api_key(tmdb_api_key),
        )

    result = {
        "success": bool(selected_payload.get("success")),
        "message": selected_payload.get("message", ""),
        "query": {
            "keyword": keyword.strip(),
            "tmdb_id": tmdb_id.strip(),
            "type": requested_type,
            "selected_type": selected_type,
            "year": year.strip(),
        },
        "summary": {
            "resource_count": len(raw_items or []),
            "candidate_count": len(normalized_candidates or []),
            "attempts": [
                {
                    "type": media_type,
                    "success": bool(payload.get("success")),
                    "message": payload.get("message", ""),
                    "resource_count": len(((payload.get("data") or {}).get("data") or []) if isinstance(payload.get("data"), dict) else []),
                    "candidate_count": len(((payload.get("data") or {}).get("candidates") or []) if isinstance(payload.get("data"), dict) else []),
                }
                for media_type, payload in attempts
            ],
        },
        "candidates": normalized_candidates,
        "results": normalize_items(raw_items or [], max(1, min(20, limit))),
        "cache_path": "",
    }

    if use_cache:
        cache_path = Path(os.path.expanduser(str(cache_path)))
        write_cache(cache_path, result)
        result["cache_path"] = str(cache_path)
        write_cache(cache_path, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search HDHive resources through local MoviePilot.")
    parser.add_argument("keyword", nargs="?", default="", help="Movie or TV title keyword")
    parser.add_argument("--type", choices=["auto", "movie", "tv"], default="auto", help="Search type")
    parser.add_argument("--tmdb-id", default="", help="Direct TMDB ID search")
    parser.add_argument("--year", default="", help="Optional year filter")
    parser.add_argument("--limit", type=int, default=10, help="Resource result limit")
    parser.add_argument("--candidate-limit", type=int, default=5, help="TMDB candidate limit")
    parser.add_argument("--format", choices=["json", "text"], default="json", help="Output format")
    parser.add_argument("--mp-base-url", default=DEFAULT_MP_BASE_URL, help="Local MoviePilot base URL")
    parser.add_argument("--app-env", default=str(DEFAULT_APP_ENV), help="Path to MoviePilot app.env")
    parser.add_argument("--cache-path", default=str(DEFAULT_CACHE_PATH), help="Where to save the normalized search cache")
    parser.add_argument("--no-cache", action="store_true", help="Do not write a search cache file")
    parser.add_argument("--compact", action="store_true", help="Print shorter text output")
    parser.add_argument("--tmdb-api-key", default="", help="Optional TMDB API key override for actor enrichment")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.tmdb_id and not args.keyword.strip():
        parser.error("keyword or --tmdb-id is required")

    try:
        result = execute_search(
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

    if args.format == "text":
        print(format_text(result, compact=args.compact))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
