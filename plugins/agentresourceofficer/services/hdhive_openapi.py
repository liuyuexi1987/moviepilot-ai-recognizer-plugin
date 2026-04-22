from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests

try:
    from app.chain.media import MediaChain
except Exception:
    MediaChain = None

try:
    from app.core.config import settings
except Exception:
    settings = None


class HDHiveOpenApiService:
    """Reusable HDHive execution layer for Agent资源官."""

    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = "https://hdhive.com",
        timeout: int = 30,
    ) -> None:
        self.api_key = self.normalize_text(api_key)
        self.base_url = (self.normalize_text(base_url) or "https://hdhive.com").rstrip("/")
        self.timeout = self.safe_int(timeout, 30)

    @staticmethod
    def safe_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def normalize_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def normalize_slug(value: Any) -> str:
        return str(value or "").strip().replace("-", "")

    @staticmethod
    def normalize_pan_path(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if not text.startswith("/"):
            text = f"/{text}"
        return text.rstrip("/") or "/"

    @staticmethod
    def media_type_text(value: Any) -> str:
        if value is None:
            return ""
        raw = str(getattr(value, "value", value)).strip().lower()
        mapping = {
            "电影": "movie",
            "movie": "movie",
            "电视剧": "tv",
            "tv": "tv",
        }
        return mapping.get(raw, raw)

    def tz_now(self) -> datetime:
        if settings is not None:
            try:
                return datetime.now(ZoneInfo(getattr(settings, "TZ", "Asia/Shanghai")))
            except Exception:
                pass
        return datetime.now()

    def base_headers(self) -> Dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": getattr(settings, "USER_AGENT", "MoviePilot") if settings is not None else "MoviePilot",
        }

    def api_url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Tuple[bool, Dict[str, Any], str, int]:
        if not self.api_key:
            return False, {}, "未配置影巢 API Key", 400

        try:
            response = requests.request(
                method=method.upper(),
                url=self.api_url(path),
                headers=self.base_headers(),
                params=params,
                json=payload if payload is not None else None,
                timeout=timeout or self.timeout,
                proxies=getattr(settings, "PROXY", None) if settings is not None else None,
            )
        except Exception as exc:
            return False, {}, f"请求异常: {exc}", 0

        try:
            result = response.json()
        except Exception:
            result = {
                "success": False,
                "message": response.text[:300] if response.text else f"HTTP {response.status_code}",
                "description": "接口未返回有效 JSON",
            }

        if response.ok and isinstance(result, dict) and result.get("success", True):
            return True, result, "", response.status_code

        message = ""
        if isinstance(result, dict):
            message = (
                result.get("description")
                or result.get("message")
                or result.get("code")
                or f"HTTP {response.status_code}"
            )
        if not message:
            message = f"HTTP {response.status_code}"
        return False, result if isinstance(result, dict) else {}, message, response.status_code

    def resource_sort_key(self, item: Dict[str, Any]) -> Tuple[int, int, int, int, str]:
        pan = str(item.get("pan_type") or "").lower()
        points = item.get("unlock_points")
        try:
            points_value = int(points) if points is not None and str(points) != "" else 0
        except Exception:
            points_value = 9999
        validate = str(item.get("validate_status") or "").lower()
        resolutions = [str(v).upper() for v in (item.get("video_resolution") or [])]
        sources = [str(v) for v in (item.get("source") or [])]
        pan_rank = 0 if pan == "115" else 1 if pan == "quark" else 2
        points_rank = 0 if points_value <= 0 else 1
        validate_rank = 0 if validate in {"valid", ""} else 1
        resolution_rank = 0 if "4K" in resolutions else 1 if "1080P" in resolutions else 2
        source_rank = 0 if "蓝光原盘/REMUX" in sources else 1 if "WEB-DL/WEBRip" in sources else 2
        return (pan_rank, points_rank, validate_rank, resolution_rank + source_rank, str(item.get("title") or ""))

    async def resolve_candidates_by_keyword(
        self,
        keyword: str,
        media_type: str = "movie",
        year: str = "",
        candidate_limit: int = 10,
    ) -> Tuple[bool, Dict[str, Any], str]:
        keyword = self.normalize_text(keyword)
        media_type = self.normalize_text(media_type).lower() or "movie"
        year = self.normalize_text(year)
        candidate_limit = min(20, max(1, self.safe_int(candidate_limit, 10)))

        if not keyword:
            return False, {"message": "keyword 不能为空", "query": {"keyword": "", "media_type": media_type}}, "keyword 不能为空"
        if media_type not in {"movie", "tv"}:
            return False, {"message": "媒体类型必须是 movie 或 tv", "query": {"keyword": keyword, "media_type": media_type}}, "媒体类型必须是 movie 或 tv"
        if MediaChain is None:
            return False, {"message": "MoviePilot MediaChain 不可用", "query": {"keyword": keyword, "media_type": media_type}}, "MoviePilot MediaChain 不可用"

        try:
            _, medias = await MediaChain().async_search(title=keyword)
        except Exception as exc:
            return False, {"message": f"TMDB 解析失败: {exc}", "query": {"keyword": keyword, "media_type": media_type}}, f"TMDB 解析失败: {exc}"

        candidates: List[Dict[str, Any]] = []
        for media in medias or []:
            item_type = self.media_type_text(getattr(media, "type", ""))
            item_year = self.normalize_text(getattr(media, "year", ""))
            if media_type and item_type and item_type != media_type:
                continue
            if year and item_year and item_year != year:
                continue
            tmdb_id = getattr(media, "tmdb_id", None)
            if not tmdb_id:
                continue
            candidates.append(
                {
                    "title": getattr(media, "title", "") or getattr(media, "en_title", "") or "",
                    "year": item_year,
                    "media_type": item_type or media_type,
                    "tmdb_id": tmdb_id,
                    "poster_path": getattr(media, "poster_path", "") or "",
                }
            )
            if len(candidates) >= candidate_limit:
                break

        result = {
            "time": self.tz_now().strftime("%Y-%m-%d %H:%M:%S"),
            "ok": bool(candidates),
            "status_code": 200 if candidates else 404,
            "message": "success" if candidates else "未找到可用于影巢搜索的 TMDB 候选",
            "query": {"keyword": keyword, "media_type": media_type, "year": year},
            "candidates": candidates,
            "meta": {"total": len(candidates)},
        }
        return bool(candidates), result, result["message"]

    def search_resources(self, media_type: str, tmdb_id: str) -> Tuple[bool, Dict[str, Any], str]:
        media_type = (media_type or "").strip().lower()
        tmdb_id = self.normalize_text(tmdb_id)
        if media_type not in {"movie", "tv"}:
            return False, {"message": "媒体类型必须是 movie 或 tv", "query": {"media_type": media_type, "tmdb_id": tmdb_id}}, "媒体类型必须是 movie 或 tv"
        if not tmdb_id:
            return False, {"message": "TMDB ID 不能为空", "query": {"media_type": media_type, "tmdb_id": tmdb_id}}, "TMDB ID 不能为空"

        ok, payload, message, status_code = self.request("GET", f"/api/open/resources/{media_type}/{tmdb_id}")
        result = {
            "time": self.tz_now().strftime("%Y-%m-%d %H:%M:%S"),
            "ok": ok,
            "status_code": status_code,
            "message": payload.get("message") if ok else message,
            "query": {"media_type": media_type, "tmdb_id": tmdb_id},
            "data": payload.get("data") if isinstance(payload, dict) else [],
            "meta": payload.get("meta") if isinstance(payload, dict) else {},
        }
        return ok, result, message

    async def search_resources_by_keyword(
        self,
        keyword: str,
        media_type: str = "movie",
        year: str = "",
        candidate_limit: int = 10,
        result_limit: int = 12,
    ) -> Tuple[bool, Dict[str, Any], str]:
        result_limit = min(50, max(1, self.safe_int(result_limit, 12)))
        ok, candidate_result, candidate_message = await self.resolve_candidates_by_keyword(
            keyword=keyword,
            media_type=media_type,
            year=year,
            candidate_limit=candidate_limit,
        )
        if not ok:
            result = dict(candidate_result)
            result["data"] = []
            return False, result, candidate_message
        candidates = candidate_result.get("candidates") or []

        merged_items: List[Dict[str, Any]] = []
        seen_slugs: set[str] = set()
        last_status = 200

        for candidate in candidates:
            ok, payload, message = self.search_resources(
                media_type=candidate["media_type"] or media_type,
                tmdb_id=str(candidate["tmdb_id"]),
            )
            last_status = payload.get("status_code", last_status) if isinstance(payload, dict) else last_status
            if not ok:
                continue
            for resource in payload.get("data") or []:
                slug = self.normalize_slug(resource.get("slug"))
                if not slug or slug in seen_slugs:
                    continue
                seen_slugs.add(slug)
                annotated = dict(resource)
                annotated["matched_tmdb_id"] = candidate["tmdb_id"]
                annotated["matched_title"] = candidate["title"]
                annotated["matched_year"] = candidate["year"]
                merged_items.append(annotated)

        merged_items.sort(key=self.resource_sort_key)
        merged_items = merged_items[:result_limit]

        result = {
            "time": self.tz_now().strftime("%Y-%m-%d %H:%M:%S"),
            "ok": bool(merged_items),
            "status_code": last_status,
            "message": "success" if merged_items else "已解析 TMDB，但影巢暂无匹配资源",
            "query": {"keyword": keyword, "media_type": media_type, "year": year},
            "candidates": candidates,
            "data": merged_items,
            "meta": {"total": len(merged_items), "candidate_count": len(candidates)},
        }
        return bool(merged_items), result, result["message"]

    def unlock_resource(self, slug: str) -> Tuple[bool, Dict[str, Any], str]:
        slug = self.normalize_slug(slug)
        if not slug:
            return False, {"message": "slug 不能为空", "slug": ""}, "slug 不能为空"
        ok, payload, message, status_code = self.request("POST", f"/api/open/resource/{slug}/unlock")
        result = {
            "time": self.tz_now().strftime("%Y-%m-%d %H:%M:%S"),
            "ok": ok,
            "status_code": status_code,
            "message": payload.get("message") if ok else message,
            "slug": slug,
            "data": payload.get("data") if isinstance(payload, dict) else {},
        }
        return ok, result, message
