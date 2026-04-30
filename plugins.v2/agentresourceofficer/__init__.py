import concurrent.futures
import asyncio
import os
import threading
import time
import uuid
import json
import re
from hashlib import md5
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlencode
from urllib.request import Request as UrlRequest, urlopen

from fastapi import Request
try:
    from apscheduler.triggers.cron import CronTrigger
except Exception:
    CronTrigger = None
try:
    from app.core.config import settings
except Exception:
    settings = None
try:
    from app.log import logger
except Exception:
    class _FallbackLogger:
        @staticmethod
        def info(message: str) -> None:
            print(message)

        @staticmethod
        def warning(message: str) -> None:
            print(message)

        @staticmethod
        def error(message: str) -> None:
            print(message)

    logger = _FallbackLogger()
try:
    from app.utils.crypto import CryptoJsUtils
except Exception:
    CryptoJsUtils = None
try:
    from app.agent.tools.manager import moviepilot_tool_manager
except Exception:
    moviepilot_tool_manager = None
from app.plugins import _PluginBase

from .services.hdhive_openapi import HDHiveOpenApiService
from .services.p115_transfer import P115TransferService
from .services.quark_transfer import QuarkTransferService
from .feishu_channel import FeishuChannel
from .agenttool import (
    AssistantCapabilitiesTool,
    AssistantExecuteActionTool,
    AssistantExecuteActionsTool,
    AssistantExecutePlanTool,
    AssistantHistoryTool,
    AssistantHelpTool,
    AssistantMaintainTool,
    AssistantPickTool,
    AssistantPlansClearTool,
    AssistantPlansTool,
    AssistantPulseTool,
    AssistantReadinessTool,
    AssistantRecoverTool,
    AssistantRequestTemplatesTool,
    AssistantRouteTool,
    AssistantSessionClearTool,
    AssistantSessionsClearTool,
    AssistantSessionsTool,
    AssistantSessionStateTool,
    AssistantSelfcheckTool,
    AssistantStartupTool,
    AssistantToolboxTool,
    AssistantWorkflowTool,
    FeishuChannelHealthTool,
    HDHiveSearchSessionTool,
    HDHiveSessionPickTool,
    P115CancelPendingTool,
    P115PendingTool,
    P115QRCodeCheckTool,
    P115QRCodeStartTool,
    P115ResumePendingTool,
    P115StatusTool,
    ShareRouteTool,
)


class _JsonRequestShim:
    def __init__(self, request: Request, body: Dict[str, Any], method: str = "POST") -> None:
        self.method = str(method or "POST").upper()
        self.headers = request.headers
        self.query_params = request.query_params
        self._body = body

    async def json(self) -> Dict[str, Any]:
        return self._body


class _RequestContextShim:
    def __init__(self, headers: Optional[Dict[str, Any]] = None, query_params: Optional[Dict[str, Any]] = None) -> None:
        default_headers = dict(headers or {})
        if settings is not None and not default_headers.get("Authorization"):
            token = str(getattr(settings, "API_TOKEN", "") or "").strip()
            if token:
                default_headers["Authorization"] = f"Bearer {token}"
        self.headers = default_headers
        self.query_params = query_params or {}


class AgentResourceOfficer(_PluginBase):
    plugin_name = "Agent影视助手"
    plugin_desc = "统一承接影巢、115、夸克、飞书与智能体入口的资源工作流主插件。"
    plugin_icon = "https://raw.githubusercontent.com/liuyuexi1987/MoviePilot-Plugins/main/icons/agentresourceofficer.png"
    plugin_version = "0.2.44"
    request_templates_schema_version = "request_templates.v1"
    plugin_author = "liuyuexi1987"
    author_url = "https://github.com/liuyuexi1987"
    plugin_config_prefix = "agentresourceofficer_"
    plugin_order = 40
    auth_level = 1

    _enabled = False
    _notify = True
    _debug = False
    _quark_cookie = ""
    _quark_default_path = "/飞书"
    _quark_timeout = 30
    _quark_auto_import_cookiecloud = True
    _pansou_base_url = "http://127.0.0.1:805"
    _pansou_timeout = 20
    _hdhive_api_key = ""
    _hdhive_base_url = "https://hdhive.com"
    _hdhive_timeout = 30
    _hdhive_default_path = "/待整理"
    _hdhive_candidate_page_size = 10
    _hdhive_resource_enabled = True
    _hdhive_max_unlock_points = 20
    _hdhive_checkin_enabled = False
    _hdhive_checkin_gambler_mode = False
    _hdhive_checkin_cron = "0 8 * * *"
    _hdhive_checkin_cookie = ""
    _hdhive_checkin_auto_login = True
    _hdhive_checkin_username = ""
    _hdhive_checkin_password = ""
    _p115_default_path = "/待整理"
    _p115_client_type = "alipaymini"
    _p115_cookie = ""
    _p115_prefer_direct = True
    _feishu_enabled = False
    _feishu_allow_all = False
    _feishu_reply_enabled = True
    _feishu_reply_receive_id_type = "chat_id"
    _feishu_app_id = ""
    _feishu_app_secret = ""
    _feishu_verification_token = ""
    _feishu_allowed_chat_ids: List[str] = []
    _feishu_allowed_user_ids: List[str] = []
    _feishu_command_whitelist: List[str] = []
    _feishu_command_aliases = ""
    _feishu_command_mode = "resource_officer"

    _quark_service: Optional[QuarkTransferService] = None
    _hdhive_service: Optional[HDHiveOpenApiService] = None
    _p115_service: Optional[P115TransferService] = None
    _feishu_channel: Optional[FeishuChannel] = None
    _session_cache: Dict[str, Dict[str, Any]] = {}
    _agent_tools_reloaded = False
    _candidate_actor_cache: Dict[str, List[str]] = {}
    _candidate_actor_cache_lock = threading.Lock()
    _session_store_key = "assistant_session_cache"
    _session_retention_seconds = 7 * 24 * 60 * 60
    _execution_history_store_key = "assistant_execution_history"
    _execution_history_limit = 100
    _execution_history: List[Dict[str, Any]] = []
    _workflow_plan_store_key = "assistant_workflow_plans"
    _workflow_plan_limit = 50
    _workflow_plans: Dict[str, Dict[str, Any]] = {}
    _assistant_preferences_store_key = "assistant_preferences"
    _assistant_preferences_limit = 100
    _assistant_preferences: Dict[str, Dict[str, Any]] = {}
    _hdhive_checkin_history_store_key = "hdhive_checkin_history"
    _hdhive_checkin_history_limit = 60
    _hdhive_checkin_history: List[Dict[str, Any]] = []
    _agent_tools_reload_lock = threading.Lock()
    _agent_tools_reload_version = ""
    _agent_tools_reload_at = 0.0

    @staticmethod
    def _extract_first_url(text: str) -> str:
        match = re.search(r"https?://[^\s<>\"']+", str(text or ""))
        return match.group(0).rstrip(".,);]") if match else ""

    @staticmethod
    def _format_pansou_datetime(value: Any) -> str:
        text = str(value or "").strip()
        if not text or text.startswith("0001-01-01"):
            return ""
        text = text.replace("T", " ").replace("Z", "")
        if len(text) >= 10:
            text = text[:10].replace("-", "/")
        return text.strip()

    @staticmethod
    def _normalize_search_prefix(text: str) -> Tuple[str, str]:
        raw = str(text or "").strip()
        mappings = [
            ("MP搜索", "mp"),
            ("原生搜索", "mp"),
            ("搜索资源", "mp"),
            ("搜索", "mp"),
            ("1搜索", "pansou"),
            ("2搜索", "hdhive"),
            ("影巢搜索", "hdhive"),
            ("yc", "hdhive"),
            ("2", "hdhive"),
            ("盘搜搜索", "pansou"),
            ("盘搜", "pansou"),
            ("ps", "pansou"),
            ("1", "pansou"),
        ]
        for prefix, mode in mappings:
            if raw == prefix:
                return mode, ""
            if raw.startswith(prefix + " "):
                return mode, raw[len(prefix):].strip()
            if raw.startswith(prefix):
                remain = raw[len(prefix):].strip()
                if remain:
                    return mode, remain
        return "", raw

    @staticmethod
    def _match_command_prefix(raw: str, prefixes: List[str]) -> Optional[Tuple[str, str]]:
        text = str(raw or "").strip()
        for prefix in prefixes:
            if not text.startswith(prefix):
                continue
            remain = text[len(prefix):]
            if not remain:
                return prefix, ""
            return prefix, remain.lstrip(" ：:").strip()
        return None

    @staticmethod
    def _normalize_mp_recommend_request(value: Any, default_source: str = "tmdb_trending") -> Tuple[str, str]:
        raw = str(value or "").strip()
        compact = re.sub(r"[\s，。？！!?,、:：]+", "", raw).lower()
        allowed_sources = {
            "tmdb_trending",
            "tmdb_movies",
            "tmdb_tvs",
            "douban_hot",
            "douban_movie_hot",
            "douban_tv_hot",
            "douban_showing",
            "douban_movie_showing",
            "douban_movie_top250",
            "douban_tv_animation",
            "bangumi_calendar",
        }
        if compact in allowed_sources:
            if compact == "douban_showing":
                return "douban_movie_showing", "movie"
            return compact, "all"
        source_aliases = {
            "trending": ("tmdb_trending", "all"),
            "tmdb": ("tmdb_trending", "all"),
            "tmdb热门": ("tmdb_trending", "all"),
            "tmdb电影": ("tmdb_movies", "movie"),
            "tmdb剧集": ("tmdb_tvs", "tv"),
            "tmdb电视剧": ("tmdb_tvs", "tv"),
            "豆瓣": ("douban_hot", "all"),
            "豆瓣热门": ("douban_hot", "all"),
            "豆瓣电影": ("douban_movie_hot", "movie"),
            "豆瓣热门电影": ("douban_movie_hot", "movie"),
            "豆瓣热映": ("douban_movie_showing", "movie"),
            "豆瓣电视剧": ("douban_tv_hot", "tv"),
            "豆瓣剧集": ("douban_tv_hot", "tv"),
            "豆瓣top250": ("douban_movie_top250", "movie"),
            "top250": ("douban_movie_top250", "movie"),
            "douban_showing": ("douban_movie_showing", "movie"),
            "正在热映": ("douban_movie_showing", "movie"),
            "热映": ("douban_movie_showing", "movie"),
            "院线": ("douban_movie_showing", "movie"),
            "bangumi": ("bangumi_calendar", "tv"),
            "番剧": ("bangumi_calendar", "tv"),
            "今日番剧": ("bangumi_calendar", "tv"),
            "每日放送": ("bangumi_calendar", "tv"),
            "动画番剧": ("bangumi_calendar", "tv"),
        }
        if compact in source_aliases:
            return source_aliases[compact]
        if "top250" in compact:
            return "douban_movie_top250", "movie"
        if any(token in compact for token in ["bangumi", "番剧", "每日放送", "今日放送", "今日动画"]):
            return "bangumi_calendar", "tv"
        if any(token in compact for token in ["正在热映", "热映", "院线"]):
            return "douban_movie_showing", "movie"
        if "豆瓣" in compact:
            if "动画" in compact:
                return "douban_tv_animation", "tv"
            if any(token in compact for token in ["电视剧", "剧集", "剧", "tv"]):
                return "douban_tv_hot", "tv"
            if any(token in compact for token in ["电影", "movie"]):
                return "douban_movie_hot", "movie"
            return "douban_hot", "all"
        if "tmdb" in compact:
            if any(token in compact for token in ["电视剧", "剧集", "剧", "tv"]):
                return "tmdb_tvs", "tv"
            if any(token in compact for token in ["电影", "movie"]):
                return "tmdb_movies", "movie"
            return "tmdb_trending", "all"
        if any(token in compact for token in ["电视剧", "剧集", "剧集推荐", "热门剧", "热门电视剧"]):
            return "tmdb_tvs", "tv"
        if any(token in compact for token in ["电影", "影视电影", "热门电影"]):
            return "tmdb_movies", "movie"
        return default_source or "tmdb_trending", "all"

    @classmethod
    def _resolve_pan_path_value(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        alias_map = {
            "分享": "/飞书",
            "飞书": "/飞书",
            "待整理": "/待整理",
            "最新动画": "/最新动画",
        }
        mapped = alias_map.get(text, text)
        return cls._normalize_path(mapped)

    @staticmethod
    def _normalize_pick_action(value: Any) -> str:
        text = str(value or "").strip().lower()
        if text in {"detail", "details", "review", "详情", "审查"}:
            return "detail"
        if text in {"best", "best_result", "recommend_best", "最佳", "最佳片源", "推荐片源", "推荐下载", "最优"}:
            return "best"
        if text in {"plan", "dry_run", "make_plan", "计划", "生成计划", "计划选择", "计划处理", "转存计划", "解锁计划"}:
            return "plan"
        if text in {"n", "next", "next_page", "下一页", "下页"} or text.startswith("n "):
            return "next_page"
        return ""

    @staticmethod
    def _normalize_pick_mode(value: Any) -> str:
        text = str(value or "").strip().lower()
        compact = re.sub(r"\s+", "", text)
        if not compact:
            return ""
        if any(token in compact for token in ["hdhive", "影巢", "影潮", "走影巢", "用影巢"]):
            return "hdhive"
        if re.search(r"(^|[^a-z])yc($|[^a-z])", text):
            return "hdhive"
        if any(token in compact for token in ["pansou", "盘搜", "走盘搜", "用盘搜"]):
            return "pansou"
        if re.search(r"(^|[^a-z])ps($|[^a-z])", text):
            return "pansou"
        if any(token in compact for token in ["mp", "原生", "moviepilot", "站点", "pt"]):
            return "mp"
        return ""

    @classmethod
    def _parse_pick_text(cls, value: Any) -> Tuple[int, str, str, str]:
        raw = cls._clean_text(value)
        action = cls._normalize_pick_action(raw)
        if action:
            return 0, "", action, ""
        alias_pattern = r"^(?:/smart_pick|smart_pick|计划选择|计划处理|生成计划|转存计划|解锁计划|计划(?=\s*\d)|选择|选|继续|pick|plan|dry_run|make_plan)\s*"
        alias_match = re.match(alias_pattern, raw, flags=re.IGNORECASE)
        digit_match = re.match(r"^(\d+)(.*)$", raw)
        if not alias_match and not digit_match:
            return 0, "", "", ""
        if digit_match and not alias_match:
            suffix = cls._clean_text(digit_match.group(2))
            if suffix and not (
                suffix.startswith("/")
                or "=" in suffix
                or cls._normalize_pick_mode(suffix)
                or cls._normalize_pick_action(suffix)
                or suffix.lower() in {"n", "next"}
            ):
                return 0, "", "", ""
        text = re.sub(alias_pattern, "", raw, flags=re.IGNORECASE).strip()
        if alias_match and cls._normalize_pick_action(alias_match.group(0).strip()) == "plan":
            action = "plan"
        index = 0
        path = ""
        mode = ""
        pick_action = action or ""
        match = re.search(r"\d+", text)
        if match:
            index = cls._safe_int(match.group(0), 0)
        for token in text.split():
            if "=" not in token:
                if not pick_action:
                    pick_action = cls._normalize_pick_action(token)
                continue
            key, token_value = token.split("=", 1)
            key = key.strip().lower()
            token_value = token_value.strip()
            if key in {"path", "dir", "目录", "位置"} and token_value:
                path = cls._resolve_pan_path_value(token_value)
            elif key in {"mode", "search_mode", "target", "方式", "来源", "渠道"} and token_value:
                mode = cls._normalize_pick_mode(token_value)
        if not mode:
            mode = cls._normalize_pick_mode(text)
        if not pick_action:
            suffix = re.sub(r"\d+", " ", text, count=1).strip()
            pick_action = cls._normalize_pick_action(suffix)
        return index, path, pick_action, mode

    def init_plugin(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._notify = bool(config.get("notify", True))
        self._debug = bool(config.get("debug", False))
        self._quark_cookie = self._clean_text(config.get("quark_cookie"))
        self._quark_default_path = self._normalize_path(config.get("quark_default_path") or "/飞书")
        self._quark_timeout = self._safe_int(config.get("quark_timeout"), 30)
        self._quark_auto_import_cookiecloud = bool(config.get("quark_auto_import_cookiecloud", True))
        self._pansou_base_url = self._clean_text(config.get("pansou_base_url") or "http://127.0.0.1:805").rstrip("/")
        self._pansou_timeout = max(3, min(120, self._safe_int(config.get("pansou_timeout"), 20)))
        self._hdhive_api_key = self._clean_text(config.get("hdhive_api_key"))
        self._hdhive_base_url = self._clean_text(config.get("hdhive_base_url") or "https://hdhive.com").rstrip("/")
        self._hdhive_timeout = self._safe_int(config.get("hdhive_timeout"), 30)
        self._hdhive_default_path = self._normalize_path(config.get("hdhive_default_path") or "/待整理")
        self._hdhive_candidate_page_size = max(5, min(20, self._safe_int(config.get("hdhive_candidate_page_size"), 10)))
        self._hdhive_resource_enabled = bool(config.get("hdhive_resource_enabled", True))
        self._hdhive_max_unlock_points = max(0, self._safe_int(config.get("hdhive_max_unlock_points"), 20))
        self._hdhive_checkin_enabled = bool(config.get("hdhive_checkin_enabled", False))
        self._hdhive_checkin_gambler_mode = bool(config.get("hdhive_checkin_gambler_mode", False))
        self._hdhive_checkin_cron = self._clean_text(config.get("hdhive_checkin_cron") or "0 8 * * *")
        self._hdhive_checkin_cookie = self._clean_text(config.get("hdhive_checkin_cookie"))
        self._hdhive_checkin_auto_login = bool(config.get("hdhive_checkin_auto_login", True))
        self._hdhive_checkin_username = self._clean_text(config.get("hdhive_checkin_username"))
        self._hdhive_checkin_password = self._clean_text(config.get("hdhive_checkin_password"))
        self._p115_default_path = self._normalize_path(config.get("p115_default_path") or "/待整理")
        self._p115_client_type = P115TransferService.normalize_qrcode_client_type(config.get("p115_client_type"))
        self._p115_cookie = self._clean_text(config.get("p115_cookie"))
        self._p115_prefer_direct = bool(config.get("p115_prefer_direct", True))
        self._feishu_enabled = bool(config.get("feishu_enabled", False))
        self._feishu_allow_all = bool(config.get("feishu_allow_all", False))
        self._feishu_reply_enabled = bool(config.get("feishu_reply_enabled", True))
        self._feishu_reply_receive_id_type = self._clean_text(config.get("feishu_reply_receive_id_type") or "chat_id")
        self._feishu_app_id = self._clean_text(config.get("feishu_app_id"))
        self._feishu_app_secret = self._clean_text(config.get("feishu_app_secret"))
        self._feishu_verification_token = self._clean_text(config.get("feishu_verification_token"))
        self._feishu_allowed_chat_ids = FeishuChannel.split_lines(config.get("feishu_allowed_chat_ids"))
        self._feishu_allowed_user_ids = FeishuChannel.split_lines(config.get("feishu_allowed_user_ids"))
        self._feishu_command_whitelist = FeishuChannel.merge_command_whitelist(
            FeishuChannel.split_commands(config.get("feishu_command_whitelist"))
        )
        self._feishu_command_aliases = FeishuChannel.merge_command_aliases(
            self._clean_text(config.get("feishu_command_aliases"))
        )
        self._feishu_command_mode = self._clean_text(config.get("feishu_command_mode") or "resource_officer")
        self._quark_service = QuarkTransferService(
            cookie=self._quark_cookie,
            timeout=self._quark_timeout,
            default_target_path=self._quark_default_path,
            auto_import_cookiecloud=self._quark_auto_import_cookiecloud,
            cookie_refresh_callback=self._refresh_quark_cookie_from_cookiecloud,
        )
        self._hdhive_service = HDHiveOpenApiService(
            api_key=self._hdhive_api_key,
            base_url=self._hdhive_base_url,
            timeout=self._hdhive_timeout,
        )
        self._p115_service = P115TransferService(
            default_target_path=self._p115_default_path,
            cookie=self._p115_cookie,
            prefer_direct=self._p115_prefer_direct,
        )
        self._restore_persisted_sessions()
        self._restore_execution_history()
        self._restore_hdhive_checkin_history()
        self._restore_workflow_plans()
        self._restore_assistant_preferences()
        self._agent_tools_reloaded = False
        self._ensure_feishu_channel().configure(self._build_config())
        if self._enabled and self._feishu_enabled:
            self._feishu_channel.start()
        elif self._feishu_channel is not None:
            self._feishu_channel.stop()

    def get_state(self) -> bool:
        if self._enabled:
            self._maybe_reload_agent_tools_once()
        return self._enabled

    def get_agent_tools(self) -> List[type]:
        return [
            AssistantCapabilitiesTool,
            AssistantExecuteActionTool,
            AssistantExecuteActionsTool,
            AssistantExecutePlanTool,
            AssistantPlansTool,
            AssistantPlansClearTool,
            AssistantRecoverTool,
            AssistantPulseTool,
            AssistantStartupTool,
            AssistantMaintainTool,
            AssistantToolboxTool,
            AssistantRequestTemplatesTool,
            AssistantSelfcheckTool,
            AssistantReadinessTool,
            FeishuChannelHealthTool,
            AssistantHistoryTool,
            AssistantHelpTool,
            AssistantRouteTool,
            AssistantPickTool,
            AssistantWorkflowTool,
            AssistantSessionsTool,
            AssistantSessionStateTool,
            AssistantSessionClearTool,
            AssistantSessionsClearTool,
            HDHiveSearchSessionTool,
            HDHiveSessionPickTool,
            ShareRouteTool,
            P115QRCodeStartTool,
            P115QRCodeCheckTool,
            P115StatusTool,
            P115PendingTool,
            P115ResumePendingTool,
            P115CancelPendingTool,
        ]

    @staticmethod
    def _reload_agent_tools() -> None:
        if moviepilot_tool_manager is None:
            return
        try:
            moviepilot_tool_manager._load_tools()
        except Exception:
            return

    def _maybe_reload_agent_tools_once(self) -> None:
        if moviepilot_tool_manager is None:
            return
        now = time.time()
        with self.__class__._agent_tools_reload_lock:
            if (
                self.__class__._agent_tools_reload_version == self.plugin_version
                and now - self.__class__._agent_tools_reload_at < 600
            ):
                return
            # Mark before reloading, because tool loading can query plugin states recursively.
            self.__class__._agent_tools_reload_version = self.plugin_version
            self.__class__._agent_tools_reload_at = now
        self._reload_agent_tools()

    @staticmethod
    def _clean_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _parse_optional_bool(value: Any) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
        return None

    @classmethod
    def _parse_bool_value(cls, value: Any, default: bool = False) -> bool:
        parsed = cls._parse_optional_bool(value)
        return bool(default) if parsed is None else bool(parsed)

    @staticmethod
    def _normalize_path(value: Any) -> str:
        return QuarkTransferService.normalize_path(value)

    @staticmethod
    def _friendly_hdhive_error(message: str, capability: str) -> str:
        text = str(message or "").strip()
        lowered = text.lower()
        if "premium" in lowered or "仅对 premium 用户开放" in text:
            if capability == "checkin":
                return "影巢 OpenAPI 签到当前需要 Premium 用户；普通用户可配置网页 Cookie 或账号密码启用网页签到兜底。"
            return f"影巢 OpenAPI 的{capability}接口当前需要 Premium 用户。"
        return text or f"影巢 {capability} 接口调用失败"

    @staticmethod
    def _is_hdhive_premium_limited(message: str) -> bool:
        text = str(message or "").strip()
        lowered = text.lower()
        return "premium" in lowered or "仅对 premium 用户开放" in text

    @staticmethod
    def _read_json_file(path: Path) -> Optional[Dict[str, Any]]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    @classmethod
    def _hdhive_daily_sign_config_paths(cls) -> List[Path]:
        return [
            Path("/config/plugins/hdhivedailysign.json"),
            Path("/Applications/Dockge/moviepilotv2/config/plugins/hdhivedailysign.json"),
        ]

    @classmethod
    def _hdhive_daily_sign_user_info_paths(cls) -> List[Path]:
        return [
            Path("/config/logs/plugins/hdhivedailysign_user_info.json"),
            Path("/Applications/Dockge/moviepilotv2/config/logs/plugins/hdhivedailysign_user_info.json"),
        ]

    @classmethod
    def _load_hdhive_daily_sign_config(cls) -> Dict[str, Any]:
        for path in cls._hdhive_daily_sign_config_paths():
            if not path.exists():
                continue
            data = cls._read_json_file(path)
            if data:
                return data
        return {}

    @classmethod
    def _load_hdhive_daily_sign_user_info(cls) -> Dict[str, Any]:
        for path in cls._hdhive_daily_sign_user_info_paths():
            if not path.exists():
                continue
            data = cls._read_json_file(path)
            if data:
                return data
        return {}

    @classmethod
    def _build_hdhive_account_snapshot(cls, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(snapshot, dict) or not snapshot:
            return {}
        return {
            "id": snapshot.get("id"),
            "nickname": snapshot.get("nickname"),
            "username": snapshot.get("nickname"),
            "avatar_url": snapshot.get("avatar_url"),
            "created_at": snapshot.get("created_at"),
            "is_vip": False,
            "source": "hdhivedailysign_snapshot",
            "user_meta": {
                "points": snapshot.get("points"),
                "signin_days_total": snapshot.get("signin_days_total"),
            },
            "warnings_nums": snapshot.get("warnings_nums"),
        }

    @classmethod
    def _extract_hdhive_account_fields(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}
        meta = data.get("user_meta") if isinstance(data.get("user_meta"), dict) else {}
        return {
            "nickname": data.get("nickname") or data.get("username") or "—",
            "points": meta.get("points", data.get("points", "—")),
            "signin_days_total": meta.get("signin_days_total", data.get("signin_days_total", "—")),
            "is_vip": bool(data.get("is_vip")),
        }

    def _get_hdhive_fallback_cookie(self) -> str:
        own_cookie = self._clean_text(self._hdhive_checkin_cookie)
        if own_cookie:
            return own_cookie
        config = self._load_hdhive_daily_sign_config()
        return self._clean_text(config.get("cookie"))

    def _refresh_hdhive_checkin_cookie(self) -> Tuple[bool, str, str]:
        if not self._hdhive_checkin_auto_login:
            return False, "", "未启用影巢自动登录刷新 Cookie"
        service = self._ensure_hdhive_service()
        # Playwright sync API cannot run inside MoviePilot's asyncio loop; keep login isolated.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                service.login_for_cookie,
                username=self._hdhive_checkin_username,
                password=self._hdhive_checkin_password,
            )
            try:
                login_ok, cookie_string, login_message = future.result(timeout=max(60, self._hdhive_timeout * 4))
            except Exception as exc:
                return False, "", f"影巢自动登录超时或异常: {exc}"
        if not login_ok or not cookie_string:
            return False, "", login_message or "影巢自动登录失败"
        self._hdhive_checkin_cookie = cookie_string
        try:
            self.update_config(self._build_config())
        except Exception as exc:
            logger.warning(f"[Agent影视助手] 影巢自动登录已获取 Cookie，但保存配置失败：{exc}")
        return True, cookie_string, login_message or "影巢自动登录成功"

    def _run_hdhive_checkin(self, *, is_gambler: Optional[bool] = None, trigger: str = "Agent影视助手") -> Dict[str, Any]:
        if not self._hdhive_checkin_enabled:
            return self._hdhive_checkin_disabled_response()
        service = self._ensure_hdhive_service()
        final_gambler_mode = self._hdhive_checkin_gambler_mode if is_gambler is None else bool(is_gambler)
        checkin_ok, result, checkin_message = service.perform_checkin(
            is_gambler=final_gambler_mode,
            trigger=trigger,
        )
        if checkin_ok:
            final_result = {"success": True, "message": result.get("message") or "success", "data": result}
            self._record_hdhive_checkin_history(trigger=trigger, is_gambler=final_gambler_mode, result=final_result)
            return final_result

        raw_message = result.get("message") or checkin_message
        checkin_status_code = self._safe_int(result.get("status_code"), 0) if isinstance(result, dict) else 0
        should_try_web_fallback = (
            self._is_hdhive_premium_limited(raw_message)
            or checkin_status_code in (404, 405)
            or "405 not allowed" in self._clean_text(raw_message).lower()
            or "<html" in self._clean_text(raw_message).lower()
        )
        if should_try_web_fallback:
            fallback_cookie = self._get_hdhive_fallback_cookie()
            if fallback_cookie:
                fallback_ok, fallback_result, fallback_message = service.perform_web_checkin_with_fallback(
                    cookie_string=fallback_cookie,
                    is_gambler=final_gambler_mode,
                    trigger=f"{trigger} 网页兜底",
                )
                if fallback_ok:
                    final_result = {
                        "success": True,
                        "message": fallback_result.get("message") or fallback_message or "签到成功",
                        "data": fallback_result,
                    }
                    self._record_hdhive_checkin_history(trigger=trigger, is_gambler=final_gambler_mode, result=final_result)
                    return final_result
                if self._hdhive_checkin_auto_login and self._hdhive_checkin_username and self._hdhive_checkin_password:
                    login_ok, new_cookie, login_message = self._refresh_hdhive_checkin_cookie()
                    if login_ok and new_cookie:
                        retry_ok, retry_result, retry_message = service.perform_web_checkin_with_fallback(
                            cookie_string=new_cookie,
                            is_gambler=final_gambler_mode,
                            trigger=f"{trigger} 自动刷新 Cookie 后重试",
                        )
                        if retry_ok:
                            final_result = {
                                "success": True,
                                "message": retry_result.get("message") or retry_message or "签到成功",
                                "data": retry_result,
                            }
                            self._record_hdhive_checkin_history(trigger=trigger, is_gambler=final_gambler_mode, result=final_result)
                            return final_result
                        final_result = {
                            "success": False,
                            "message": f"影巢自动登录刷新 Cookie 成功，但签到重试失败：{retry_result.get('message') or retry_message}",
                            "data": {
                                "openapi": result,
                                "web_fallback": fallback_result,
                                "login": {"ok": True, "message": login_message},
                                "retry": retry_result,
                            },
                        }
                        self._record_hdhive_checkin_history(trigger=trigger, is_gambler=final_gambler_mode, result=final_result)
                        return final_result
                    final_result = {
                        "success": False,
                        "message": f"影巢网页兜底签到失败，自动登录刷新 Cookie 也失败：{login_message}",
                        "data": {
                            "openapi": result,
                            "web_fallback": fallback_result,
                            "login": {"ok": False, "message": login_message},
                        },
                    }
                    self._record_hdhive_checkin_history(trigger=trigger, is_gambler=final_gambler_mode, result=final_result)
                    return final_result
                final_result = {
                    "success": False,
                    "message": f"影巢 OpenAPI 签到受 Premium 限制，且网页兜底签到失败：{fallback_result.get('message') or fallback_message}",
                    "data": {
                        "openapi": result,
                        "web_fallback": fallback_result,
                    },
                }
                self._record_hdhive_checkin_history(trigger=trigger, is_gambler=final_gambler_mode, result=final_result)
                return final_result
            if self._hdhive_checkin_auto_login and self._hdhive_checkin_username and self._hdhive_checkin_password:
                login_ok, new_cookie, login_message = self._refresh_hdhive_checkin_cookie()
                if login_ok and new_cookie:
                    retry_ok, retry_result, retry_message = service.perform_web_checkin_with_fallback(
                        cookie_string=new_cookie,
                        is_gambler=final_gambler_mode,
                        trigger=f"{trigger} 自动刷新 Cookie",
                    )
                    if retry_ok:
                        final_result = {
                            "success": True,
                            "message": retry_result.get("message") or retry_message or "签到成功",
                            "data": retry_result,
                        }
                        self._record_hdhive_checkin_history(trigger=trigger, is_gambler=final_gambler_mode, result=final_result)
                        return final_result
                    final_result = {
                        "success": False,
                        "message": f"影巢自动登录刷新 Cookie 成功，但签到失败：{retry_result.get('message') or retry_message}",
                        "data": {
                            "openapi": result,
                            "login": {"ok": True, "message": login_message},
                            "retry": retry_result,
                        },
                    }
                    self._record_hdhive_checkin_history(trigger=trigger, is_gambler=final_gambler_mode, result=final_result)
                    return final_result
                final_result = {
                    "success": False,
                    "message": f"影巢 OpenAPI 签到受 Premium 限制，且自动登录刷新 Cookie 失败：{login_message}",
                    "data": {
                        "openapi": result,
                        "login": {"ok": False, "message": login_message},
                    },
                }
                self._record_hdhive_checkin_history(trigger=trigger, is_gambler=final_gambler_mode, result=final_result)
                return final_result
            final_result = {
                "success": False,
                "message": "影巢 OpenAPI 签到受 Premium 限制，且本插件没有配置网页 Cookie 兜底或自动登录账号密码",
                "data": result,
            }
            self._record_hdhive_checkin_history(trigger=trigger, is_gambler=final_gambler_mode, result=final_result)
            return final_result

        final_result = {
            "success": False,
            "message": self._friendly_hdhive_error(raw_message, "checkin"),
            "data": result,
        }
        self._record_hdhive_checkin_history(trigger=trigger, is_gambler=final_gambler_mode, result=final_result)
        return final_result

    def _scheduled_hdhive_checkin(self):
        if not self._enabled or not self._hdhive_checkin_enabled:
            return
        result = self._run_hdhive_checkin(trigger="Agent影视助手 定时签到")
        status = "成功" if result.get("success") else "失败"
        logger.info(f"[Agent影视助手] 影巢定时签到{status}: {result.get('message')}")

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled or not self._hdhive_checkin_enabled or not self._hdhive_checkin_cron:
            return []
        if CronTrigger is None:
            logger.warning("[Agent影视助手] apscheduler 不可用，无法注册影巢定时签到")
            return []
        try:
            trigger = CronTrigger.from_crontab(self._hdhive_checkin_cron)
        except Exception as exc:
            logger.warning(f"[Agent影视助手] 影巢签到 Cron 配置无效：{self._hdhive_checkin_cron} {exc}")
            return []
        return [{
            "id": "agentresourceofficer_hdhive_checkin",
            "name": "Agent影视助手影巢签到",
            "trigger": trigger,
            "func": self._scheduled_hdhive_checkin,
            "kwargs": {},
        }]

    def _build_config(self, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        config = {
            "enabled": self._enabled,
            "notify": self._notify,
            "debug": self._debug,
            "quark_cookie": self._quark_cookie,
            "quark_default_path": self._quark_default_path,
            "quark_timeout": self._quark_timeout,
            "quark_auto_import_cookiecloud": self._quark_auto_import_cookiecloud,
            "pansou_base_url": self._pansou_base_url,
            "pansou_timeout": self._pansou_timeout,
            "hdhive_api_key": self._hdhive_api_key,
            "hdhive_base_url": self._hdhive_base_url,
            "hdhive_timeout": self._hdhive_timeout,
            "hdhive_default_path": self._hdhive_default_path,
            "hdhive_candidate_page_size": self._hdhive_candidate_page_size,
            "hdhive_resource_enabled": self._hdhive_resource_enabled,
            "hdhive_max_unlock_points": self._hdhive_max_unlock_points,
            "hdhive_checkin_enabled": self._hdhive_checkin_enabled,
            "hdhive_checkin_gambler_mode": self._hdhive_checkin_gambler_mode,
            "hdhive_checkin_cron": self._hdhive_checkin_cron,
            "hdhive_checkin_cookie": self._hdhive_checkin_cookie,
            "hdhive_checkin_auto_login": self._hdhive_checkin_auto_login,
            "hdhive_checkin_username": self._hdhive_checkin_username,
            "hdhive_checkin_password": self._hdhive_checkin_password,
            "p115_default_path": self._p115_default_path,
            "p115_client_type": self._p115_client_type,
            "p115_cookie": self._p115_cookie,
            "p115_prefer_direct": self._p115_prefer_direct,
            "feishu_enabled": self._feishu_enabled,
            "feishu_allow_all": self._feishu_allow_all,
            "feishu_reply_enabled": self._feishu_reply_enabled,
            "feishu_reply_receive_id_type": self._feishu_reply_receive_id_type,
            "feishu_app_id": self._feishu_app_id,
            "feishu_app_secret": self._feishu_app_secret,
            "feishu_verification_token": self._feishu_verification_token,
            "feishu_allowed_chat_ids": "\n".join(self._feishu_allowed_chat_ids),
            "feishu_allowed_user_ids": "\n".join(self._feishu_allowed_user_ids),
            "feishu_command_whitelist": ",".join(self._feishu_command_whitelist),
            "feishu_command_aliases": self._feishu_command_aliases,
            "feishu_command_mode": self._feishu_command_mode,
        }
        if overrides:
            config.update(overrides)
        return config

    @staticmethod
    def _extract_apikey(request: Request, body: Optional[Dict[str, Any]] = None) -> str:
        header = str(request.headers.get("Authorization") or "").strip()
        if header.lower().startswith("bearer "):
            return header.split(" ", 1)[1].strip()
        if body:
            token = str(body.get("apikey") or body.get("api_key") or "").strip()
            if token:
                return token
        return str(request.query_params.get("apikey") or "").strip()

    def _check_api_access(self, request: Request, body: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        expected = self._clean_text(getattr(settings, "API_TOKEN", "") if settings is not None else "")
        if not expected:
            return False, "服务端未配置 API Token"
        actual = self._extract_apikey(request, body)
        if actual != expected:
            return False, "API Token 无效"
        return True, ""

    async def _request_payload(self, request: Request) -> Dict[str, Any]:
        if str(getattr(request, "method", "") or "").upper() == "GET":
            return {}
        try:
            data = await request.json()
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _ensure_quark_service(self) -> QuarkTransferService:
        if self._quark_service is None:
            self._quark_service = QuarkTransferService(
                cookie=self._quark_cookie,
                timeout=self._quark_timeout,
                default_target_path=self._quark_default_path,
                auto_import_cookiecloud=self._quark_auto_import_cookiecloud,
                cookie_refresh_callback=self._refresh_quark_cookie_from_cookiecloud,
            )
        else:
            self._quark_service.set_cookie(self._quark_cookie)
            self._quark_service.timeout = max(10, self._safe_int(self._quark_timeout, 30))
            self._quark_service.default_target_path = self._quark_default_path
            self._quark_service.auto_import_cookiecloud = self._quark_auto_import_cookiecloud
            self._quark_service.cookie_refresh_callback = self._refresh_quark_cookie_from_cookiecloud
        return self._quark_service

    def _load_cookiecloud_quark_cookie(self) -> Tuple[str, str]:
        if settings is None:
            return "", "未获取到系统设置"
        if CryptoJsUtils is None:
            return "", "运行环境缺少 CookieCloud 解密依赖"

        key = self._clean_text(getattr(settings, "COOKIECLOUD_KEY", ""))
        password = self._clean_text(getattr(settings, "COOKIECLOUD_PASSWORD", ""))
        cookie_path = getattr(settings, "COOKIE_PATH", None)
        if not bool(getattr(settings, "COOKIECLOUD_ENABLE_LOCAL", False)):
            return "", "未启用本地 CookieCloud"
        if not key or not password or not cookie_path:
            return "", "CookieCloud 参数不完整"

        file_path = Path(cookie_path) / f"{key}.json"
        if not file_path.exists():
            return "", f"未找到 CookieCloud 文件: {file_path.name}"

        try:
            encrypted_data = json.loads(file_path.read_text(encoding="utf-8"))
            encrypted = encrypted_data.get("encrypted")
            if not encrypted:
                return "", "CookieCloud 文件缺少 encrypted 字段"
            crypt_key = md5(f"{key}-{password}".encode("utf-8")).hexdigest()[:16].encode("utf-8")
            decrypted = CryptoJsUtils.decrypt(encrypted, crypt_key).decode("utf-8")
            payload = json.loads(decrypted)
        except Exception as exc:
            return "", f"CookieCloud 解密失败: {exc}"

        contents = payload.get("cookie_data") if isinstance(payload, dict) else None
        if not isinstance(contents, dict):
            contents = payload if isinstance(payload, dict) else {}

        merged: Dict[str, str] = {}
        for cookie_items in contents.values():
            if not isinstance(cookie_items, list):
                continue
            for item in cookie_items:
                if not isinstance(item, dict):
                    continue
                domain = self._clean_text(item.get("domain")).lower()
                name = self._clean_text(item.get("name"))
                value = self._clean_text(item.get("value"))
                if "quark.cn" not in domain or not name:
                    continue
                merged[name] = value

        if not merged:
            return "", "CookieCloud 中没有 quark.cn 的 Cookie"
        return "; ".join(f"{name}={value}" for name, value in merged.items() if value), ""

    def _refresh_quark_cookie_from_cookiecloud(self) -> str:
        cookie, _message = self._load_cookiecloud_quark_cookie()
        if cookie:
            self._quark_cookie = cookie
        return cookie

    def _ensure_hdhive_service(self) -> HDHiveOpenApiService:
        if self._hdhive_service is None:
            self._hdhive_service = HDHiveOpenApiService(
                api_key=self._hdhive_api_key,
                base_url=self._hdhive_base_url,
                timeout=self._hdhive_timeout,
            )
        else:
            self._hdhive_service.api_key = self._hdhive_api_key
            self._hdhive_service.base_url = self._hdhive_base_url
            self._hdhive_service.timeout = self._hdhive_timeout
        return self._hdhive_service

    def _ensure_p115_service(self) -> P115TransferService:
        if self._p115_service is None:
            self._p115_service = P115TransferService(
                default_target_path=self._p115_default_path,
                cookie=self._p115_cookie,
                prefer_direct=self._p115_prefer_direct,
            )
        else:
            self._p115_service.default_target_path = self._p115_default_path
            self._p115_service.set_cookie(self._p115_cookie)
            self._p115_service.prefer_direct = self._p115_prefer_direct
        return self._p115_service

    def _apply_runtime_config(self, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        config = self._build_config(overrides)
        self.update_config(config)
        self.init_plugin(config)
        return config

    @staticmethod
    def _p115_client_type_items() -> List[Dict[str, str]]:
        return [
            {"title": "支付宝小程序（推荐）", "value": "alipaymini"},
            {"title": "115 Android", "value": "115android"},
            {"title": "115 iOS", "value": "115ios"},
            {"title": "115 iPad", "value": "115ipad"},
            {"title": "115 TV", "value": "tv"},
            {"title": "微信小程序", "value": "wechatmini"},
            {"title": "Web", "value": "web"},
        ]

    @classmethod
    def _p115_client_type_title(cls, value: str) -> str:
        final_value = P115TransferService.normalize_qrcode_client_type(value)
        for item in cls._p115_client_type_items():
            if item.get("value") == final_value:
                return str(item.get("title") or final_value)
        return final_value

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def stop_service(self):
        if self._feishu_channel is not None:
            self._feishu_channel.stop()
        return

    def _ensure_feishu_channel(self) -> FeishuChannel:
        if self._feishu_channel is None:
            self._feishu_channel = FeishuChannel(self)
        return self._feishu_channel

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/quark/health",
                "endpoint": self.api_quark_health,
                "methods": ["GET"],
                "summary": "检查 Agent影视助手 的夸克配置",
            },
            {
                "path": "/quark/transfer",
                "endpoint": self.api_quark_transfer,
                "methods": ["POST"],
                "summary": "通过 Agent影视助手 执行夸克分享转存",
            },
            {
                "path": "/hdhive/health",
                "endpoint": self.api_hdhive_health,
                "methods": ["GET"],
                "summary": "检查 Agent影视助手 的影巢配置",
            },
            {
                "path": "/hdhive/account",
                "endpoint": self.api_hdhive_account,
                "methods": ["GET"],
                "summary": "获取影巢当前账号信息",
            },
            {
                "path": "/hdhive/checkin",
                "endpoint": self.api_hdhive_checkin,
                "methods": ["POST"],
                "summary": "执行影巢普通签到或赌狗签到",
            },
            {
                "path": "/hdhive/checkin/history",
                "endpoint": self.api_hdhive_checkin_history,
                "methods": ["GET"],
                "summary": "查看插件保存的影巢签到日志",
            },
            {
                "path": "/hdhive/quota",
                "endpoint": self.api_hdhive_quota,
                "methods": ["GET"],
                "summary": "获取影巢当前配额信息",
            },
            {
                "path": "/hdhive/usage_today",
                "endpoint": self.api_hdhive_usage_today,
                "methods": ["GET"],
                "summary": "获取影巢今日用量统计",
            },
            {
                "path": "/hdhive/weekly_free_quota",
                "endpoint": self.api_hdhive_weekly_free_quota,
                "methods": ["GET"],
                "summary": "获取影巢每周免费解锁额度",
            },
            {
                "path": "/hdhive/search",
                "endpoint": self.api_hdhive_search,
                "methods": ["POST"],
                "summary": "通过 Agent影视助手 执行影巢资源搜索",
            },
            {
                "path": "/hdhive/search_by_keyword",
                "endpoint": self.api_hdhive_search_by_keyword,
                "methods": ["POST"],
                "summary": "通过 Agent影视助手 执行影巢关键词候选搜索",
            },
            {
                "path": "/hdhive/unlock",
                "endpoint": self.api_hdhive_unlock,
                "methods": ["POST"],
                "summary": "通过 Agent影视助手 执行影巢资源解锁",
            },
            {
                "path": "/hdhive/unlock_and_route",
                "endpoint": self.api_hdhive_unlock_and_route,
                "methods": ["POST"],
                "summary": "通过 Agent影视助手 解锁影巢资源并尝试自动路由到对应网盘执行层",
            },
            {
                "path": "/p115/health",
                "endpoint": self.api_p115_health,
                "methods": ["GET"],
                "summary": "检查 Agent影视助手 的 115 转存依赖状态",
            },
            {
                "path": "/p115/qrcode",
                "endpoint": self.api_p115_qrcode,
                "methods": ["GET"],
                "summary": "获取 Agent影视助手 的 115 扫码登录二维码",
            },
            {
                "path": "/p115/qrcode/check",
                "endpoint": self.api_p115_qrcode_check,
                "methods": ["GET"],
                "summary": "检查 Agent影视助手 的 115 扫码登录状态",
            },
            {
                "path": "/p115/transfer",
                "endpoint": self.api_p115_transfer,
                "methods": ["POST"],
                "summary": "通过 Agent影视助手 执行 115 分享转存",
            },
            {
                "path": "/p115/pending",
                "endpoint": self.api_p115_pending,
                "methods": ["GET", "POST"],
                "summary": "查看指定会话中待继续的 115 任务",
            },
            {
                "path": "/p115/pending/resume",
                "endpoint": self.api_p115_pending_resume,
                "methods": ["POST"],
                "summary": "继续执行指定会话中待处理的 115 任务",
            },
            {
                "path": "/p115/pending/cancel",
                "endpoint": self.api_p115_pending_cancel,
                "methods": ["POST"],
                "summary": "取消指定会话中待处理的 115 任务",
            },
            {
                "path": "/share/route",
                "endpoint": self.api_share_route,
                "methods": ["POST"],
                "summary": "通过 Agent影视助手 自动识别 115 / 夸克分享链接并执行对应转存",
            },
            {
                "path": "/feishu/health",
                "endpoint": self.api_feishu_health,
                "methods": ["GET"],
                "summary": "检查 Agent影视助手 内置飞书入口状态",
            },
            {
                "path": "/assistant/route",
                "endpoint": self.api_assistant_route,
                "methods": ["POST"],
                "summary": "统一智能入口：盘搜 / 影巢 / 直链分享",
            },
            {
                "path": "/assistant/pick",
                "endpoint": self.api_assistant_pick,
                "methods": ["POST"],
                "summary": "统一智能入口的按编号继续执行",
            },
            {
                "path": "/assistant/capabilities",
                "endpoint": self.api_assistant_capabilities,
                "methods": ["GET"],
                "summary": "查看统一智能入口支持的结构化参数、默认值与推荐调用方式",
            },
            {
                "path": "/assistant/readiness",
                "endpoint": self.api_assistant_readiness,
                "methods": ["GET"],
                "summary": "检查 Agent影视助手 是否已准备好给外部智能体调用",
            },
            {
                "path": "/assistant/pulse",
                "endpoint": self.api_assistant_pulse,
                "methods": ["GET"],
                "summary": "轻量启动探针：返回版本、关键服务状态、警告和最佳恢复建议",
            },
            {
                "path": "/assistant/startup",
                "endpoint": self.api_assistant_startup,
                "methods": ["GET"],
                "summary": "启动聚合包：一次返回 pulse、自检、核心工具、端点、默认目录和恢复建议",
            },
            {
                "path": "/assistant/maintain",
                "endpoint": self.api_assistant_maintain,
                "methods": ["GET", "POST"],
                "summary": "低风险维护：查看或执行过期会话、已执行计划清理",
            },
            {
                "path": "/assistant/toolbox",
                "endpoint": self.api_assistant_toolbox,
                "methods": ["GET"],
                "summary": "轻量工具清单：返回推荐工具、端点、工作流、动作名、默认目录和命令示例",
            },
            {
                "path": "/assistant/request_templates",
                "endpoint": self.api_assistant_request_templates,
                "methods": ["GET", "POST"],
                "summary": "轻量请求模板：返回外部智能体常用 assistant 请求模板",
            },
            {
                "path": "/assistant/selfcheck",
                "endpoint": self.api_assistant_selfcheck,
                "methods": ["GET"],
                "summary": "轻量自检：确认 compact 协议、模板默认 compact 和布尔字符串解析是否正常",
            },
            {
                "path": "/assistant/history",
                "endpoint": self.api_assistant_history,
                "methods": ["GET"],
                "summary": "查看最近执行历史，便于外部智能体判断上一步是否完成",
            },
            {
                "path": "/assistant/action",
                "endpoint": self.api_assistant_action,
                "methods": ["POST"],
                "summary": "直接执行统一智能入口返回的动作模板名，适合外部智能体无映射继续执行",
            },
            {
                "path": "/assistant/actions",
                "endpoint": self.api_assistant_actions,
                "methods": ["POST"],
                "summary": "批量执行多个动作模板，适合外部智能体一次请求串起多步工作流，减少往返",
            },
            {
                "path": "/assistant/workflow",
                "endpoint": self.api_assistant_workflow,
                "methods": ["GET", "POST"],
                "summary": "运行预设工作流，适合外部智能体用更短参数完成常见资源任务",
            },
            {
                "path": "/assistant/preferences",
                "endpoint": self.api_assistant_preferences,
                "methods": ["GET", "POST", "DELETE"],
                "summary": "读取、保存或重置智能体片源偏好画像，用于云盘和 PT 分源评分",
            },
            {
                "path": "/assistant/plan/execute",
                "endpoint": self.api_assistant_plan_execute,
                "methods": ["POST"],
                "summary": "执行 dry_run 保存的工作流计划，避免外部智能体重复携带大 JSON",
            },
            {
                "path": "/assistant/plans",
                "endpoint": self.api_assistant_plans,
                "methods": ["GET"],
                "summary": "查看 dry_run 保存的工作流计划，便于断线恢复和选择 plan_id",
            },
            {
                "path": "/assistant/plans/clear",
                "endpoint": self.api_assistant_plans_clear,
                "methods": ["POST"],
                "summary": "清理 dry_run 保存的工作流计划",
            },
            {
                "path": "/assistant/recover",
                "endpoint": self.api_assistant_recover,
                "methods": ["GET", "POST"],
                "summary": "查看或直接执行当前最推荐的恢复动作，给外部智能体提供单入口续跑能力",
            },
            {
                "path": "/assistant/session",
                "endpoint": self.api_assistant_session_state,
                "methods": ["GET", "POST"],
                "summary": "查看统一智能入口当前会话状态与建议动作",
            },
            {
                "path": "/assistant/session/clear",
                "endpoint": self.api_assistant_session_clear,
                "methods": ["POST"],
                "summary": "清理统一智能入口当前会话缓存",
            },
            {
                "path": "/assistant/sessions",
                "endpoint": self.api_assistant_sessions,
                "methods": ["GET"],
                "summary": "列出当前活跃的统一智能入口会话，便于外部智能体恢复和接续",
            },
            {
                "path": "/assistant/sessions/clear",
                "endpoint": self.api_assistant_sessions_clear,
                "methods": ["POST"],
                "summary": "按 session_id、类型或过滤条件批量清理统一智能入口会话",
            },
            {
                "path": "/session/hdhive/search",
                "endpoint": self.api_session_hdhive_search,
                "methods": ["POST"],
                "summary": "创建影巢搜索会话并返回候选影片列表",
            },
            {
                "path": "/session/hdhive/pick",
                "endpoint": self.api_session_hdhive_pick,
                "methods": ["POST"],
                "summary": "按编号继续影巢会话：候选选片或资源解锁落盘",
            },
        ]

    def _build_hdhive_page_summary(self) -> str:
        if not self._enabled:
            return "插件未启用"
        if not self._hdhive_api_key:
            return "影巢 API Key 未配置"
        service = self._ensure_hdhive_service()
        account_ok, account_result, account_message = service.fetch_me()
        quota_ok, quota_result, _quota_message = service.fetch_quota()
        usage_ok, usage_result, _usage_message = service.fetch_usage_today()

        account = account_result.get("data") or {}
        account_source = "hdhive_openapi"
        if not account_ok and self._is_hdhive_premium_limited(account_message):
            fallback_account = self._build_hdhive_account_snapshot(self._load_hdhive_daily_sign_user_info())
            if fallback_account:
                account = fallback_account
                account_ok = True
                account_source = "hdhivedailysign_snapshot"
        account_fields = self._extract_hdhive_account_fields(account)
        quota = quota_result.get("data") or {}
        usage = usage_result.get("data") or {}

        return (
            f"影巢账号：{'可用' if account_ok else '异常'}"
            f"\n资源入口：{'开启' if self._hdhive_resource_enabled else '关闭'}"
            f"\n单资源积分上限：{self._hdhive_max_unlock_points if self._hdhive_max_unlock_points > 0 else '不限制'}"
            f"\n签到入口：{'开启' if self._hdhive_checkin_enabled else '关闭'}"
            f"\n昵称：{account_fields.get('nickname', '—')}"
            f"\n积分：{account_fields.get('points', '—')}"
            f"\nVIP：{'是' if account_fields.get('is_vip') else '否'}"
            f"\n累计签到：{account_fields.get('signin_days_total', '—')}"
            f"\n今日剩余配额：{quota.get('endpoint_remaining', '—')}"
            f"\n今日总调用：{usage.get('total_calls', '—')}"
            f"\n账号来源：{'网页快照' if account_source == 'hdhivedailysign_snapshot' else 'OpenAPI'}"
        )

    def get_page(self) -> List[dict]:
        quark_ready = "已配置" if self._quark_cookie else "未配置"
        hdhive_ready = "已配置" if self._hdhive_api_key else "未配置"
        p115_health_ok, p115_health, _p115_health_message = self._ensure_p115_service().health()
        cookie_state = p115_health.get("cookie_state") or {}
        if cookie_state.get("valid"):
            p115_ready = "已配置扫码会话"
        elif cookie_state.get("configured"):
            p115_ready = "已配置但不是扫码会话"
        else:
            p115_ready = "复用 115 助手客户端"
        hdhive_summary = self._build_hdhive_page_summary()
        feishu_health = self._ensure_feishu_channel().health()
        feishu_state = "已启用" if feishu_health.get("enabled") else "未启用"
        feishu_running = "运行中" if feishu_health.get("running") else "未运行"
        hdhive_lines = [line.strip() for line in str(hdhive_summary or "").splitlines() if line.strip()]

        def text_line(text: str, css_class: str = "text-body-2 py-1") -> Dict[str, Any]:
            return {
                "component": "div",
                "props": {"class": css_class},
                "text": text,
            }

        def status_card(title: str, subtitle: str, lines: List[str], color: str = "primary") -> Dict[str, Any]:
            return {
                "component": "VCard",
                "props": {"variant": "tonal", "color": color, "class": "h-100"},
                "content": [
                    {
                        "component": "VCardTitle",
                        "props": {"class": "text-subtitle-1 font-weight-bold pb-1"},
                        "text": title,
                    },
                    {
                        "component": "VCardSubtitle",
                        "props": {"class": "text-body-2"},
                        "text": subtitle,
                    },
                    {
                        "component": "VCardText",
                        "content": [text_line(line) for line in lines],
                    },
                ],
            }

        def section_card(title: str, lines: List[str]) -> Dict[str, Any]:
            return {
                "component": "VCard",
                "props": {"flat": True, "border": True, "class": "h-100"},
                "content": [
                    {
                        "component": "VCardTitle",
                        "props": {"class": "text-subtitle-1 font-weight-bold"},
                        "text": title,
                    },
                    {
                        "component": "VCardText",
                        "content": [text_line(line) for line in lines],
                    },
                ],
            }

        return [
            {
                "component": "VContainer",
                "props": {"fluid": True, "class": "pa-0"},
                "content": [
                    {
                        "component": "VAlert",
                        "props": {
                            "type": "info",
                            "variant": "tonal",
                            "class": "mb-4",
                            "title": "统一资源入口",
                        },
                        "content": [
                            text_line(
                                "Agent影视助手支持三种接入模式：外部智能体调用 Skill/API、MP 内置智能体调用 Agent Tool、飞书 Channel 直接收命令。",
                                "text-body-2 mb-3",
                            ),
                            text_line(
                                "与智能体搭配",
                                "text-subtitle-2 font-weight-bold mb-2",
                            ),
                            {
                                "component": "div",
                                "props": {
                                    "class": "pa-3 rounded text-body-2",
                                    "style": "white-space: pre-line; line-height: 1.75; background: rgba(255,255,255,.55);",
                                },
                                "text": (
                                    "把下面这段话直接发给 WorkBuddy、Hermes、OpenClaw（小龙虾）或其他外部智能体：\n"
                                    "请阅读 https://github.com/liuyuexi1987/MoviePilot-Plugins ，并按 Agent影视助手文档接入我的 MoviePilot。"
                                    "重点看 docs/AGENT_RESOURCE_OFFICER_EXTERNAL_AGENTS.md、skills/agent-resource-officer/SKILL.md、skills/agent-resource-officer/EXTERNAL_AGENTS.md。"
                                    "读完后请在你的环境里创建或安装一个 agent-resource-officer Skill，把这些规则固化下来，不要只依赖普通聊天记忆。"
                                    "你的职责是理解我的需求、展示候选结果、让我选择编号；资源搜索、影巢解锁、115/夸克转存、115 登录状态都调用 Agent影视助手。"
                                    "不要自己拼影巢、盘搜、115 或夸克底层接口，也不要在 Skill 或聊天里写入 API Key、Cookie、Token。"
                                ),
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "props": {"dense": True},
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    status_card(
                                        "影巢",
                                        hdhive_ready,
                                        [
                                            f"默认目录：{self._hdhive_default_path}",
                                            "能力：搜索 / 解锁 / 签到",
                                            "API：/hdhive/account /checkin /quota",
                                        ],
                                        "success" if self._hdhive_api_key else "warning",
                                    )
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    status_card(
                                        "115",
                                        "可用" if p115_health_ok else "待修复",
                                        [
                                            f"默认目录：{self._p115_default_path}",
                                            f"登录方式：{p115_ready}",
                                            f"扫码客户端：{self._p115_client_type_title(self._p115_client_type)}",
                                        ],
                                        "success" if p115_health_ok else "error",
                                    )
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    status_card(
                                        "夸克",
                                        quark_ready,
                                        [
                                            f"默认目录：{self._quark_default_path}",
                                            "能力：分享链接转存",
                                            "入口：通用分享路由",
                                        ],
                                        "success" if self._quark_cookie else "warning",
                                    )
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    status_card(
                                        "飞书",
                                        f"{feishu_state}，长连接：{feishu_running}",
                                        [
                                            "模式：内置 Channel",
                                            "健康检查：/feishu/health",
                                            "建议：只保留一个飞书入口监听",
                                        ],
                                        "success" if feishu_health.get("running") else "secondary",
                                    )
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "props": {"dense": True, "class": "mt-1"},
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 4},
                                "content": [
                                    section_card(
                                        "智能体入口",
                                        [
                                            "统一路由：/assistant/route",
                                            "继续选择：/assistant/pick",
                                            "工作流：/assistant/workflow",
                                            "计划执行：/assistant/plan/execute",
                                            "Agent Tool：搜索/选择、115 扫码、待任务查看/继续/取消、通用分享路由",
                                        ],
                                    )
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 4},
                                "content": [
                                    section_card(
                                        "账号与签到",
                                        hdhive_lines
                                        + [
                                            f"115 Cookie：{cookie_state.get('message') or '当前会话可直接用于 115 直转'}",
                                        ],
                                    )
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 4},
                                "content": [
                                    section_card(
                                        "盘搜服务",
                                        [
                                            f"API 地址：{self._pansou_base_url}",
                                            f"请求超时：{self._pansou_timeout} 秒",
                                            "用法：发送“盘搜搜索 片名”“ps片名”或“1片名”。",
                                            "说明：插件只负责调用 PanSou API，本机需要先运行 PanSou 服务。",
                                        ],
                                    )
                                ],
                            }
                        ],
                    },
                ],
            }
        ]

    @staticmethod
    def get_render_mode() -> Tuple[str, Optional[str]]:
        return "vuetify", None

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        form = [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": "插件把资源搜索、链接转存、扫码登录、飞书消息和智能体调用集中到一个入口。首次使用先配置默认目录、影巢 OpenAPI、夸克会话，以及需要的飞书机器人信息。调试模式仅排查问题时打开。",
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "notify",
                                            "label": "发送通知",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "debug",
                                            "label": "调试模式",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": "影巢用于资源搜索、解锁、配额查询和签到。资源入口关闭后，智能体和飞书都不会执行影巢搜索、解锁或转存；单资源积分上限默认 20 分，超过就拦截提醒，填 0 表示不限制。",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "hdhive_api_key",
                                            "label": "影巢 API Key",
                                            "rows": 2,
                                            "placeholder": "填写影巢 OpenAPI 的 API Key",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "hdhive_resource_enabled",
                                            "label": "启用影巢资源搜索/解锁",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "hdhive_max_unlock_points",
                                            "label": "单资源积分上限",
                                            "type": "number",
                                            "placeholder": "20；填 0 不限制",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "warning",
                                            "variant": "tonal",
                                            "text": "建议保留积分上限，避免智能体一步到位时误选高积分资源。",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "hdhive_base_url",
                                            "label": "影巢 Base URL",
                                            "placeholder": "https://hdhive.com",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 2},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "hdhive_timeout",
                                            "label": "影巢超时(秒)",
                                            "type": "number",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "hdhive_default_path",
                                            "label": "影巢默认目录",
                                            "placeholder": "/待整理",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "hdhive_candidate_page_size",
                                            "label": "候选页大小",
                                            "type": "number",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": "影巢签到支持 OpenAPI 与网页兜底两种方式。OpenAPI 签到需要 Premium；普通用户可填写网页 Cookie，或填写账号密码让插件在 Cookie 失效时自动刷新。",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "hdhive_checkin_enabled",
                                            "label": "启用影巢签到",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "hdhive_checkin_gambler_mode",
                                            "label": "默认赌狗签到",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "hdhive_checkin_cron",
                                            "label": "影巢签到 Cron",
                                            "placeholder": "0 8 * * *",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "hdhive_checkin_cookie",
                                            "label": "影巢网页 Cookie（非 Premium 兜底）",
                                            "rows": 3,
                                            "placeholder": "浏览器登录 hdhive.com 后复制 Cookie；OpenAPI 签到失败时自动兜底",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "hdhive_checkin_auto_login",
                                            "label": "自动刷新 Cookie",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "hdhive_checkin_username",
                                            "label": "影巢用户名/邮箱",
                                            "placeholder": "用于 Cookie 失效时自动登录",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 5},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "hdhive_checkin_password",
                                            "label": "影巢密码",
                                            "type": "password",
                                            "placeholder": "仅保存在 MoviePilot 本机配置中",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": "盘搜用于聚合公开网盘分享结果。请先运行 PanSou 服务，再填写 MoviePilot 容器可以访问的 API 地址；留空默认使用 http://127.0.0.1:805，请求失败时会继续尝试 http://host.docker.internal:805 和 http://127.0.0.1:805。",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 8},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "pansou_base_url",
                                            "label": "盘搜 API 地址",
                                            "placeholder": "http://host.docker.internal:805",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "pansou_timeout",
                                            "label": "盘搜超时(秒)",
                                            "type": "number",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": "夸克用于转存 pan.quark.cn 分享链接。Cookie 可手动填写，也可以开启自动刷新：转存遇到 401 登录失效时，插件会尝试从 MoviePilot 本地 CookieCloud 导入 quark.cn Cookie，并自动重试一次。",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "quark_cookie",
                                            "label": "夸克 Cookie",
                                            "rows": 4,
                                            "placeholder": "浏览器登录 pan.quark.cn 后复制完整 Cookie",
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "quark_default_path",
                                            "label": "夸克默认目录",
                                            "placeholder": "/飞书",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "quark_timeout",
                                            "label": "夸克超时(秒)",
                                            "type": "number",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "quark_auto_import_cookiecloud",
                                            "label": "允许自动刷新 Cookie",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": "115 建议走扫码会话，不建议填网页版 Cookie。插件支持 /p115/qrcode 和 /p115/qrcode/check 两步扫码登录；手填 Cookie 仅作为高级兜底。",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "p115_default_path",
                                            "label": "115 默认目录",
                                            "placeholder": "/待整理",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 5},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "p115_client_type",
                                            "label": "115 扫码客户端类型",
                                            "items": self._p115_client_type_items(),
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "p115_prefer_direct",
                                            "label": "115 优先直转",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "p115_cookie",
                                            "label": "115 扫码会话 Cookie（高级，可选）",
                                            "rows": 3,
                                            "placeholder": "仅支持 UID/CID/SEID/KID 这类扫码客户端 Cookie；普通网页版 Cookie 不建议粘贴到这里",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": "飞书入口默认关闭。开启后可以在飞书里发送搜索、选择、链接转存、115 登录和 STRM 调度命令；同一个飞书机器人建议只配置一个接收入口。",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "feishu_enabled",
                                            "label": "启用内置飞书入口",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "feishu_allow_all",
                                            "label": "允许所有飞书会话",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "feishu_reply_enabled",
                                            "label": "发送飞书回复",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "feishu_app_id",
                                            "label": "飞书 App ID",
                                            "placeholder": "cli_xxxxxxxxx",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "feishu_app_secret",
                                            "label": "飞书 App Secret",
                                            "type": "password",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "feishu_verification_token",
                                            "label": "Verification Token",
                                            "type": "password",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "feishu_reply_receive_id_type",
                                            "label": "回复 ID 类型",
                                            "items": [
                                                {"title": "群聊 chat_id", "value": "chat_id"},
                                                {"title": "用户 open_id", "value": "open_id"},
                                                {"title": "用户 union_id", "value": "union_id"},
                                                {"title": "用户 user_id", "value": "user_id"},
                                            ],
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "feishu_allowed_chat_ids",
                                            "label": "允许的群聊 Chat ID",
                                            "rows": 3,
                                            "placeholder": "一个一行；allow_all 关闭时生效",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 5},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "feishu_allowed_user_ids",
                                            "label": "允许的用户 Open ID",
                                            "rows": 3,
                                            "placeholder": "一个一行",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "feishu_command_whitelist",
                                            "label": "飞书命令白名单",
                                            "rows": 3,
                                            "placeholder": "逗号或换行分隔；留空时会自动合并默认命令",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "feishu_command_aliases",
                                            "label": "飞书命令别名",
                                            "rows": 5,
                                            "placeholder": FeishuChannel.default_command_aliases(),
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                ],
            }
        ]
        return form, self._build_config()

    async def api_feishu_health(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        channel = self._ensure_feishu_channel()
        return {
            "success": True,
            "message": "Agent影视助手 内置飞书入口状态",
            "data": {
                "plugin_version": self.plugin_version,
                "plugin_enabled": self._enabled,
                **channel.health(),
            },
        }

    async def api_quark_health(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}

        service = self._ensure_quark_service()
        cookie_ok, cookie_message = service.check_cookie()
        return {
            "success": True,
            "data": {
                "plugin_version": self.plugin_version,
                "enabled": self._enabled,
                "quark_cookie_configured": bool(self._quark_cookie),
                "quark_cookie_valid": cookie_ok,
                "default_target_path": self._quark_default_path,
                "message": "" if cookie_ok else cookie_message,
            },
        }

    async def api_quark_transfer(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}

        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        share_text = self._clean_text(body.get("url") or body.get("share_url") or body.get("share_text"))
        access_code = self._clean_text(body.get("access_code") or body.get("pwd") or body.get("code"))
        target_path = self._clean_text(body.get("path") or body.get("target_path"))
        trigger = self._clean_text(body.get("trigger") or "Agent影视助手 API")

        service = self._ensure_quark_service()
        transfer_ok, result, transfer_message = service.transfer_share(
            share_text,
            access_code=access_code,
            target_path=target_path,
            trigger=trigger,
        )
        if not transfer_ok:
            return {"success": False, "message": transfer_message, "data": result}
        return {"success": True, "message": transfer_message, "data": result}

    async def api_hdhive_health(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}

        service = self._ensure_hdhive_service()
        ping_ok, result, ping_message, _status_code = service.request("GET", "/api/open/ping")
        return {
            "success": True,
            "data": {
                "plugin_version": self.plugin_version,
                "enabled": self._enabled,
                "hdhive_api_key_configured": bool(self._hdhive_api_key),
                "hdhive_ping_ok": ping_ok,
                "base_url": self._hdhive_base_url,
                "default_target_path": self._hdhive_default_path,
                "resource_enabled": self._hdhive_resource_enabled,
                "max_unlock_points": self._hdhive_max_unlock_points,
                "checkin_enabled": self._hdhive_checkin_enabled,
                "checkin_gambler_mode": self._hdhive_checkin_gambler_mode,
                "checkin_cron": self._hdhive_checkin_cron,
                "checkin_web_cookie_configured": bool(self._hdhive_checkin_cookie),
                "checkin_auto_login_enabled": self._hdhive_checkin_auto_login,
                "checkin_username_configured": bool(self._hdhive_checkin_username),
                "message": "" if ping_ok else ping_message,
                "raw": result,
            },
        }

    async def api_hdhive_account(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        service = self._ensure_hdhive_service()
        account_ok, result, account_message = service.fetch_me()
        if not account_ok:
            if self._is_hdhive_premium_limited(account_message):
                fallback_account = self._build_hdhive_account_snapshot(self._load_hdhive_daily_sign_user_info())
                if fallback_account:
                    return {
                        "success": True,
                        "message": "当前返回的是网页用户快照",
                        "data": fallback_account,
                    }
            return {"success": False, "message": self._friendly_hdhive_error(account_message, "账号"), "data": result}
        return {"success": True, "message": result.get("message") or "success", "data": result.get("data") or {}}

    async def api_hdhive_checkin(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        is_gambler = self._parse_bool_value(body.get("is_gambler"), self._hdhive_checkin_gambler_mode)
        return self._run_hdhive_checkin(is_gambler=is_gambler, trigger="Agent影视助手 API")

    async def api_hdhive_checkin_history(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        limit = self._safe_int(request.query_params.get("limit"), 20)
        data = self._hdhive_checkin_history_public_data(limit=limit)
        return {
            "success": True,
            "message": self._format_hdhive_checkin_history_text(limit=limit),
            "data": data,
        }

    async def api_hdhive_quota(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        service = self._ensure_hdhive_service()
        quota_ok, result, quota_message = service.fetch_quota()
        if not quota_ok:
            return {"success": False, "message": self._friendly_hdhive_error(quota_message, "配额"), "data": result}
        return {"success": True, "message": result.get("message") or "success", "data": result.get("data") or {}}

    async def api_hdhive_usage_today(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        service = self._ensure_hdhive_service()
        usage_ok, result, usage_message = service.fetch_usage_today()
        if not usage_ok:
            return {"success": False, "message": self._friendly_hdhive_error(usage_message, "今日用量"), "data": result}
        return {"success": True, "message": result.get("message") or "success", "data": result.get("data") or {}}

    async def api_hdhive_weekly_free_quota(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        service = self._ensure_hdhive_service()
        weekly_ok, result, weekly_message = service.fetch_weekly_free_quota()
        if not weekly_ok:
            return {"success": False, "message": self._friendly_hdhive_error(weekly_message, "每周免费额度"), "data": result}
        return {"success": True, "message": result.get("message") or "success", "data": result.get("data") or {}}

    async def api_hdhive_search(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        allowed, disabled = self._ensure_hdhive_resource_enabled()
        if not allowed:
            return disabled

        media_type = self._clean_text(body.get("media_type") or body.get("type") or "movie").lower()
        tmdb_id = self._clean_text(body.get("tmdb_id"))
        service = self._ensure_hdhive_service()
        search_ok, result, search_message = service.search_resources(media_type=media_type, tmdb_id=tmdb_id)
        if not search_ok:
            return {"success": False, "message": search_message, "data": result}
        return {"success": True, "message": "success", "data": result}

    async def api_hdhive_search_by_keyword(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        allowed, disabled = self._ensure_hdhive_resource_enabled()
        if not allowed:
            return disabled

        keyword = self._clean_text(body.get("keyword") or body.get("title"))
        media_type = self._clean_text(body.get("media_type") or body.get("type") or "auto").lower()
        year = self._clean_text(body.get("year"))
        candidate_limit = self._safe_int(body.get("candidate_limit"), self._hdhive_candidate_page_size)
        result_limit = self._safe_int(body.get("limit"), 12)

        service = self._ensure_hdhive_service()
        search_ok, result, search_message = await service.search_resources_by_keyword(
            keyword=keyword,
            media_type=media_type,
            year=year,
            candidate_limit=candidate_limit,
            result_limit=result_limit,
        )
        if not search_ok:
            return {"success": False, "message": search_message, "data": result}
        return {"success": True, "message": "success", "data": result}

    async def api_hdhive_unlock(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        allowed, disabled = self._ensure_hdhive_resource_enabled()
        if not allowed:
            return disabled

        slug = self._clean_text(body.get("slug"))
        points_ok, points_message, points_data = self._check_hdhive_unlock_points_limit(body)
        if not points_ok:
            return {"success": False, "message": points_message, "data": {"resource_guard": points_data}}
        service = self._ensure_hdhive_service()
        unlock_ok, result, unlock_message = service.unlock_resource(slug)
        if not unlock_ok:
            return {"success": False, "message": unlock_message, "data": result}
        return {"success": True, "message": "success", "data": result}

    @staticmethod
    def _new_session_id(prefix: str = "aro") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    def _save_session(self, session_id: str, payload: Dict[str, Any]) -> None:
        payload = dict(payload)
        payload["updated_at"] = int(time.time())
        self._session_cache[session_id] = payload
        self._persist_relevant_sessions()

    def _load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self._session_cache.get(session_id)
        if not session:
            return None
        return dict(session)

    def _persist_relevant_sessions(self) -> None:
        try:
            data: Dict[str, Dict[str, Any]] = {}
            for session_id, payload in (self._session_cache or {}).items():
                session = dict(payload or {})
                if self._is_session_expired(session):
                    continue
                if str(session_id).startswith("assistant::") or session.get("pending_p115") or str(session.get("kind") or "").strip() == "assistant_p115_login":
                    data[session_id] = session
            self.save_data(key=self._session_store_key, value=data)
        except Exception:
            pass

    def _restore_persisted_sessions(self) -> None:
        try:
            restored = self.get_data(self._session_store_key) or {}
            if isinstance(restored, dict):
                for session_id, payload in restored.items():
                    if isinstance(payload, dict) and not self._is_session_expired(payload):
                        self._session_cache[str(session_id)] = dict(payload)
        except Exception:
            pass

    def _persist_execution_history(self) -> None:
        try:
            history = list(self._execution_history or [])[-self._execution_history_limit:]
            self._execution_history = history
            self.save_data(key=self._execution_history_store_key, value=history)
        except Exception:
            pass

    def _restore_execution_history(self) -> None:
        try:
            restored = self.get_data(self._execution_history_store_key) or []
            if isinstance(restored, list):
                self._execution_history = [
                    dict(item)
                    for item in restored[-self._execution_history_limit:]
                    if isinstance(item, dict)
                ]
        except Exception:
            self._execution_history = []

    def _persist_hdhive_checkin_history(self) -> None:
        try:
            history = list(self._hdhive_checkin_history or [])[-self._hdhive_checkin_history_limit:]
            self._hdhive_checkin_history = history
            self.save_data(key=self._hdhive_checkin_history_store_key, value=history)
        except Exception:
            pass

    def _restore_hdhive_checkin_history(self) -> None:
        try:
            restored = self.get_data(self._hdhive_checkin_history_store_key) or []
            if isinstance(restored, list):
                self._hdhive_checkin_history = [
                    dict(item)
                    for item in restored[-self._hdhive_checkin_history_limit:]
                    if isinstance(item, dict)
                ]
        except Exception:
            self._hdhive_checkin_history = []

    def _record_hdhive_checkin_history(
        self,
        *,
        trigger: str,
        is_gambler: bool,
        result: Dict[str, Any],
    ) -> None:
        timestamp = int(time.time())
        payload = dict(result or {})
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        entry = {
            "id": self._new_session_id("hdhive-sign"),
            "time": timestamp,
            "time_text": self._format_unix_time(timestamp),
            "trigger": self._clean_text(trigger),
            "mode": "赌狗签到" if is_gambler else "普通签到",
            "is_gambler": bool(is_gambler),
            "success": bool(payload.get("success")),
            "message_head": self._assistant_result_message_head(payload.get("message")),
            "status": self._clean_text(data.get("status")) or ("成功" if payload.get("success") else "失败"),
            "source": self._clean_text(data.get("source")),
            "status_code": data.get("status_code"),
            "login_retry": bool(((data.get("login") or {}) if isinstance(data.get("login"), dict) else {}).get("ok")),
            "web_fallback": bool(data.get("web_fallback")) if isinstance(data, dict) else False,
        }
        self._hdhive_checkin_history.append(entry)
        self._hdhive_checkin_history = self._hdhive_checkin_history[-self._hdhive_checkin_history_limit:]
        self._persist_hdhive_checkin_history()

    def _hdhive_checkin_history_public_data(self, *, limit: int = 20) -> Dict[str, Any]:
        max_limit = min(max(1, self._safe_int(limit, 20)), self._hdhive_checkin_history_limit)
        items = list(reversed(self._hdhive_checkin_history or []))[:max_limit]
        return {
            "total": len(self._hdhive_checkin_history or []),
            "limit": max_limit,
            "items": items,
        }

    def _format_hdhive_checkin_history_text(self, *, limit: int = 10) -> str:
        data = self._hdhive_checkin_history_public_data(limit=limit)
        items = data.get("items") or []
        if not items:
            return "暂无影巢签到日志。"
        lines = [f"影巢签到日志：最近 {len(items)} 条"]
        for idx, item in enumerate(items, start=1):
            ok_text = "成功" if item.get("success") else "失败"
            parts = [
                f"{idx}. {item.get('time_text') or ''}",
                f"{item.get('mode') or ''}",
                ok_text,
            ]
            if item.get("trigger"):
                parts.append(f"来源:{item.get('trigger')}")
            if item.get("login_retry"):
                parts.append("已自动刷新Cookie")
            message = self._clean_text(item.get("message_head"))
            if message:
                parts.append(message)
            lines.append(" | ".join(part for part in parts if part))
        return "\n".join(lines)

    def _hdhive_resource_disabled_response(self) -> Dict[str, Any]:
        return {
            "success": False,
            "message": "影巢资源入口已关闭：当前不会执行影巢搜索、解锁或转存。可在插件设置中开启“影巢资源搜索/解锁”。",
            "data": {
                "provider": "hdhive",
                "resource_enabled": False,
                "error_code": "hdhive_resource_disabled",
            },
        }

    def _ensure_hdhive_resource_enabled(self) -> Tuple[bool, Dict[str, Any]]:
        if self._hdhive_resource_enabled:
            return True, {}
        return False, self._hdhive_resource_disabled_response()

    def _hdhive_checkin_disabled_response(self) -> Dict[str, Any]:
        return {
            "success": False,
            "message": "影巢签到入口已关闭：如需执行签到，请先在插件设置中开启“影巢签到”。",
            "data": {
                "provider": "hdhive",
                "checkin_enabled": False,
                "error_code": "hdhive_checkin_disabled",
            },
        }

    @staticmethod
    def _resource_points_value(item: Optional[Dict[str, Any]]) -> Optional[int]:
        if not item:
            return None
        raw = item.get("unlock_points")
        if raw is None:
            raw = item.get("cost")
        if raw is None:
            raw = item.get("points")
        text = str(raw or "").strip()
        if not text:
            return None
        if text.lower() == "free" or text == "免费":
            return 0
        match = re.search(r"-?\d+", text)
        if not match:
            return None
        try:
            return int(match.group(0))
        except Exception:
            return None

    def _check_hdhive_unlock_points_limit(self, resource: Optional[Dict[str, Any]]) -> Tuple[bool, str, Dict[str, Any]]:
        limit = max(0, self._safe_int(self._hdhive_max_unlock_points, 20))
        if limit <= 0:
            return True, "", {"limit": limit, "points": None, "limited": False}
        points = self._resource_points_value(resource)
        title = self._clean_text((resource or {}).get("title") or (resource or {}).get("matched_title") or "该资源")
        if points is None:
            return False, (
                f"已阻止影巢解锁：{title} 的积分消耗未知，当前单资源积分上限为 {limit} 分。"
                "如确认要解锁，请把上限临时设为 0。"
            ), {"limit": limit, "points": None, "limited": True, "reason": "unknown_points"}
        if points > limit:
            return False, (
                f"已阻止影巢解锁：{title} 需要 {points} 分，超过当前单资源积分上限 {limit} 分。"
                "如确认要解锁，请提高上限或临时设为 0。"
            ), {"limit": limit, "points": points, "limited": True, "reason": "points_over_limit"}
        return True, "", {"limit": limit, "points": points, "limited": False}

    def _default_assistant_preferences(self) -> Dict[str, Any]:
        return {
            "schema_version": "preferences.v1",
            "initialized": False,
            "prefer_resolution": "4K",
            "prefer_dolby_vision": True,
            "prefer_hdr": True,
            "prefer_chinese_subtitle": True,
            "prefer_complete_series": True,
            "prefer_cloud_provider": "",
            "cloud_default_path": self._hdhive_default_path,
            "quark_default_path": self._quark_default_path,
            "p115_default_path": self._p115_default_path,
            "pt_require_free": False,
            "pt_min_seeders": 3,
            "pt_prefer_free": True,
            "hdhive_max_unlock_points": self._hdhive_max_unlock_points,
            "auto_ingest_enabled": False,
            "auto_ingest_score_threshold": 90,
            "confirm_score_threshold": 70,
            "updated_at": 0,
        }

    def _normalize_preference_key(self, session: Any = None, user_key: Any = None) -> str:
        key = self._clean_text(user_key)
        if key:
            return key
        session_name = self._clean_text(session) or "default"
        return f"session:{session_name}"

    def _normalize_assistant_preferences(self, value: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        defaults = self._default_assistant_preferences()
        payload = dict(value or {})
        if "resolution_priority" in payload and "prefer_resolution" not in payload:
            choices = payload.get("resolution_priority")
            if isinstance(choices, (list, tuple)) and choices:
                payload["prefer_resolution"] = choices[0]
            else:
                payload["prefer_resolution"] = choices
        if "subtitle_priority" in payload and "prefer_chinese_subtitle" not in payload:
            subtitle_text = " ".join(str(item) for item in payload.get("subtitle_priority") or []) if isinstance(payload.get("subtitle_priority"), (list, tuple)) else str(payload.get("subtitle_priority") or "")
            payload["prefer_chinese_subtitle"] = bool(re.search(r"中文|中字|简中|繁中|双语|chinese", subtitle_text, flags=re.IGNORECASE))
        if "pt_free_only" in payload and "pt_require_free" not in payload:
            payload["pt_require_free"] = payload.get("pt_free_only")
        if "preferred_cloud_drive" in payload and "prefer_cloud_provider" not in payload:
            providers = payload.get("preferred_cloud_drive")
            payload["prefer_cloud_provider"] = providers[0] if isinstance(providers, (list, tuple)) and providers else providers
        if "auto_ingest" in payload and "auto_ingest_enabled" not in payload:
            payload["auto_ingest_enabled"] = payload.get("auto_ingest")
        if "auto_execute_score_threshold" in payload and "auto_ingest_score_threshold" not in payload:
            payload["auto_ingest_score_threshold"] = payload.get("auto_execute_score_threshold")
        normalized = {**defaults, **payload}
        normalized["schema_version"] = "preferences.v1"
        normalized["initialized"] = bool(normalized.get("initialized"))
        normalized["prefer_resolution"] = self._clean_text(normalized.get("prefer_resolution") or defaults["prefer_resolution"]).upper()
        normalized["prefer_dolby_vision"] = self._parse_bool_value(normalized.get("prefer_dolby_vision"), True)
        normalized["prefer_hdr"] = self._parse_bool_value(normalized.get("prefer_hdr"), True)
        normalized["prefer_chinese_subtitle"] = self._parse_bool_value(normalized.get("prefer_chinese_subtitle"), True)
        normalized["prefer_complete_series"] = self._parse_bool_value(normalized.get("prefer_complete_series"), True)
        normalized["prefer_cloud_provider"] = self._clean_text(normalized.get("prefer_cloud_provider")).lower()
        normalized["cloud_default_path"] = self._normalize_path(normalized.get("cloud_default_path") or self._hdhive_default_path)
        normalized["quark_default_path"] = self._normalize_path(normalized.get("quark_default_path") or self._quark_default_path)
        normalized["p115_default_path"] = self._normalize_path(normalized.get("p115_default_path") or self._p115_default_path)
        normalized["pt_require_free"] = self._parse_bool_value(normalized.get("pt_require_free"), False)
        normalized["pt_min_seeders"] = max(0, self._safe_int(normalized.get("pt_min_seeders"), 3))
        normalized["pt_prefer_free"] = self._parse_bool_value(normalized.get("pt_prefer_free"), True)
        normalized["hdhive_max_unlock_points"] = max(0, self._safe_int(normalized.get("hdhive_max_unlock_points"), self._hdhive_max_unlock_points))
        normalized["auto_ingest_enabled"] = self._parse_bool_value(normalized.get("auto_ingest_enabled"), False)
        normalized["auto_ingest_score_threshold"] = max(1, min(100, self._safe_int(normalized.get("auto_ingest_score_threshold"), 90)))
        normalized["confirm_score_threshold"] = max(1, min(100, self._safe_int(normalized.get("confirm_score_threshold"), 70)))
        normalized["updated_at"] = self._safe_int(normalized.get("updated_at"), 0)
        return normalized

    def _restore_assistant_preferences(self) -> None:
        try:
            restored = self.get_data(self._assistant_preferences_store_key) or {}
            if isinstance(restored, dict):
                self._assistant_preferences = {
                    self._clean_text(key): self._normalize_assistant_preferences(value)
                    for key, value in restored.items()
                    if self._clean_text(key) and isinstance(value, dict)
                }
        except Exception:
            self._assistant_preferences = {}

    def _persist_assistant_preferences(self) -> None:
        try:
            items = list((self._assistant_preferences or {}).items())[-self._assistant_preferences_limit:]
            self._assistant_preferences = {key: value for key, value in items if key}
            self.save_data(key=self._assistant_preferences_store_key, value=self._assistant_preferences)
        except Exception:
            pass

    def _assistant_preferences_public_data(self, *, session: str = "", user_key: str = "") -> Dict[str, Any]:
        key = self._normalize_preference_key(session=session, user_key=user_key)
        preferences = self._normalize_assistant_preferences((self._assistant_preferences or {}).get(key))
        questions = [
            "你更偏好 4K 还是 1080P？",
            "是否优先杜比视界 / HDR？",
            "是否必须中文字幕？",
            "电视剧是否优先全集或完整季？",
            "PT 资源最低做种数是多少？默认 3。",
            "影巢单资源最多愿意消耗多少积分？默认 20。",
            "是否允许 90 分以上资源自动入库？默认关闭。",
        ]
        return {
            "schema_version": "preferences.v1",
            "key": key,
            "initialized": bool(preferences.get("initialized")),
            "preferences": preferences,
            "needs_onboarding": not bool(preferences.get("initialized")),
            "onboarding_questions": questions if not bool(preferences.get("initialized")) else [],
            "defaults": self._default_assistant_preferences(),
        }

    def _save_assistant_preferences(
        self,
        *,
        session: str = "",
        user_key: str = "",
        preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        key = self._normalize_preference_key(session=session, user_key=user_key)
        current = self._normalize_assistant_preferences((self._assistant_preferences or {}).get(key))
        incoming = dict(preferences or {})
        merged = {**current, **incoming}
        merged["initialized"] = self._parse_bool_value(incoming.get("initialized"), True) if "initialized" in incoming else True
        merged["updated_at"] = int(time.time())
        normalized = self._normalize_assistant_preferences(merged)
        self._assistant_preferences[key] = normalized
        self._persist_assistant_preferences()
        return self._assistant_preferences_public_data(session=session, user_key=key)

    def _reset_assistant_preferences(self, *, session: str = "", user_key: str = "") -> Dict[str, Any]:
        key = self._normalize_preference_key(session=session, user_key=user_key)
        self._assistant_preferences.pop(key, None)
        self._persist_assistant_preferences()
        return self._assistant_preferences_public_data(session=session, user_key=key)

    def _assistant_preferences_status_brief(self, *, session: str = "", user_key: str = "") -> Dict[str, Any]:
        data = self._assistant_preferences_public_data(session=session, user_key=user_key)
        prefs = dict(data.get("preferences") or {})
        brief = {
            "key": data.get("key"),
            "initialized": bool(data.get("initialized")),
            "needs_onboarding": bool(data.get("needs_onboarding")),
            "summary": {
                "prefer_resolution": self._clean_text(prefs.get("prefer_resolution")),
                "prefer_dolby_vision": bool(prefs.get("prefer_dolby_vision")),
                "prefer_hdr": bool(prefs.get("prefer_hdr")),
                "prefer_chinese_subtitle": bool(prefs.get("prefer_chinese_subtitle")),
                "prefer_complete_series": bool(prefs.get("prefer_complete_series")),
                "prefer_cloud_provider": self._clean_text(prefs.get("prefer_cloud_provider")),
                "pt_min_seeders": self._safe_int(prefs.get("pt_min_seeders"), 3),
                "pt_require_free": bool(prefs.get("pt_require_free")),
                "hdhive_max_unlock_points": self._safe_int(prefs.get("hdhive_max_unlock_points"), self._hdhive_max_unlock_points),
                "auto_ingest_enabled": bool(prefs.get("auto_ingest_enabled")),
                "auto_ingest_score_threshold": self._safe_int(prefs.get("auto_ingest_score_threshold"), 90),
            },
        }
        if brief["needs_onboarding"]:
            brief["onboarding_questions"] = data.get("onboarding_questions") or []
            brief["recommended_action"] = "ask_user_preferences_then_save"
        return brief

    def _assistant_default_preferences_template(self) -> Dict[str, Any]:
        prefs = self._default_assistant_preferences()
        return {
            "prefer_resolution": prefs.get("prefer_resolution"),
            "prefer_dolby_vision": prefs.get("prefer_dolby_vision"),
            "prefer_hdr": prefs.get("prefer_hdr"),
            "prefer_chinese_subtitle": prefs.get("prefer_chinese_subtitle"),
            "prefer_complete_series": prefs.get("prefer_complete_series"),
            "prefer_cloud_provider": prefs.get("prefer_cloud_provider"),
            "pt_require_free": prefs.get("pt_require_free"),
            "pt_min_seeders": prefs.get("pt_min_seeders"),
            "hdhive_max_unlock_points": prefs.get("hdhive_max_unlock_points"),
            "p115_default_path": prefs.get("p115_default_path"),
            "quark_default_path": prefs.get("quark_default_path"),
            "auto_ingest_enabled": prefs.get("auto_ingest_enabled"),
            "auto_ingest_score_threshold": prefs.get("auto_ingest_score_threshold"),
        }

    def _parse_assistant_preferences_text(self, text: str) -> Dict[str, Any]:
        raw = self._clean_text(text)
        compact = re.sub(r"\s+", "", raw).lower()
        payload: Dict[str, Any] = {}
        if re.search(r"1080|fhd", raw, flags=re.IGNORECASE):
            payload["prefer_resolution"] = "1080P"
        elif re.search(r"4k|2160|uhd", raw, flags=re.IGNORECASE):
            payload["prefer_resolution"] = "4K"

        if re.search(r"(不要|不需要|关闭|禁用).{0,4}(杜比|dv)", raw, flags=re.IGNORECASE):
            payload["prefer_dolby_vision"] = False
        elif re.search(r"杜比|dv|dolby", raw, flags=re.IGNORECASE):
            payload["prefer_dolby_vision"] = True

        if re.search(r"(不要|不需要|关闭|禁用).{0,4}hdr", raw, flags=re.IGNORECASE):
            payload["prefer_hdr"] = False
        elif re.search(r"hdr", raw, flags=re.IGNORECASE):
            payload["prefer_hdr"] = True

        if re.search(r"(不要|不需要|关闭|禁用).{0,6}(中字|中文|字幕)", raw, flags=re.IGNORECASE) or re.search(r"无字幕也可|字幕无所谓", raw):
            payload["prefer_chinese_subtitle"] = False
        elif re.search(r"中字|中文|简中|繁中|双语字幕|字幕", raw, flags=re.IGNORECASE):
            payload["prefer_chinese_subtitle"] = True

        if re.search(r"不强求全集|不要全集|单集也可|更新也可", raw):
            payload["prefer_complete_series"] = False
        elif re.search(r"全集|完整季|整季|完结", raw):
            payload["prefer_complete_series"] = True

        if re.search(r"夸克优先|优先夸克|quark", raw, flags=re.IGNORECASE):
            payload["prefer_cloud_provider"] = "quark"
        elif re.search(r"115优先|优先115", raw):
            payload["prefer_cloud_provider"] = "115"

        if re.search(r"pt.{0,4}(只要|必须).{0,4}免费|只下免费|只要免费", raw, flags=re.IGNORECASE):
            payload["pt_require_free"] = True
        elif re.search(r"pt.{0,4}(不限|不强求).{0,4}免费|不只要免费|免费不强求", raw, flags=re.IGNORECASE):
            payload["pt_require_free"] = False

        seed_match = re.search(r"(?:做种|种子|seeders?|seeder)[^\d]{0,8}(\d+)", raw, flags=re.IGNORECASE)
        if seed_match:
            payload["pt_min_seeders"] = self._safe_int(seed_match.group(1), 3)

        points_match = re.search(r"(?:影巢|积分|解锁)[^\d]{0,10}(\d+)", raw)
        if points_match:
            payload["hdhive_max_unlock_points"] = self._safe_int(points_match.group(1), self._hdhive_max_unlock_points)

        if re.search(r"(不|不要|关闭|禁用).{0,4}自动入库", raw):
            payload["auto_ingest_enabled"] = False
        elif re.search(r"自动入库|自动下载|自动转存", raw):
            payload["auto_ingest_enabled"] = True

        threshold_match = re.search(r"(?:自动入库(?:评分|分数|阈值)|评分阈值|分数阈值|阈值)[^\d]{0,10}(\d{2,3})", raw)
        if threshold_match:
            payload["auto_ingest_score_threshold"] = self._safe_int(threshold_match.group(1), 90)

        for key, target in [
            ("115目录", "p115_default_path"),
            ("p115目录", "p115_default_path"),
            ("夸克目录", "quark_default_path"),
            ("quark目录", "quark_default_path"),
            ("云盘目录", "cloud_default_path"),
        ]:
            match = re.search(rf"{re.escape(key)}\s*=\s*([^\s，,]+)", raw, flags=re.IGNORECASE)
            if match:
                payload[target] = self._normalize_path(match.group(1))

        if "initialized" not in payload and payload:
            payload["initialized"] = True
        if "auto_ingest_score_threshold" in payload:
            payload["auto_ingest_score_threshold"] = max(1, min(100, self._safe_int(payload["auto_ingest_score_threshold"], 90)))
        if "pt_min_seeders" in payload:
            payload["pt_min_seeders"] = max(0, self._safe_int(payload["pt_min_seeders"], 3))
        if "hdhive_max_unlock_points" in payload:
            payload["hdhive_max_unlock_points"] = max(0, self._safe_int(payload["hdhive_max_unlock_points"], self._hdhive_max_unlock_points))
        return payload

    @staticmethod
    def _score_text_blob(item: Any) -> str:
        if isinstance(item, dict):
            parts: List[str] = []
            for value in item.values():
                if isinstance(value, (dict, list, tuple)):
                    parts.append(AgentResourceOfficer._score_text_blob(value))
                elif value is not None:
                    parts.append(str(value))
            return " ".join(parts).lower()
        if isinstance(item, (list, tuple)):
            return " ".join(AgentResourceOfficer._score_text_blob(value) for value in item).lower()
        return str(item or "").lower()

    @staticmethod
    def _score_has_any(text: str, keywords: List[str]) -> bool:
        return any(keyword.lower() in text for keyword in keywords)

    @staticmethod
    def _score_level(score: int) -> str:
        if score >= 90:
            return "excellent"
        if score >= 70:
            return "confirm"
        return "low"

    def _score_decision(
        self,
        *,
        score: int,
        risk_reasons: List[str],
        hard_risk_reasons: Optional[List[str]] = None,
        preferences: Dict[str, Any],
        default_action: str,
    ) -> Dict[str, Any]:
        threshold = max(1, min(100, self._safe_int(preferences.get("auto_ingest_score_threshold"), 90)))
        confirm_threshold = max(1, min(100, self._safe_int(preferences.get("confirm_score_threshold"), 70)))
        auto_enabled = self._parse_bool_value(preferences.get("auto_ingest_enabled"), False)
        hard_risks = [self._clean_text(item) for item in (hard_risk_reasons or []) if self._clean_text(item)]
        hard_risk = bool(hard_risks)
        can_auto = bool(auto_enabled and not hard_risk and score >= threshold)
        if can_auto:
            recommended = default_action
        elif score >= confirm_threshold and not hard_risk:
            recommended = "ask_confirm"
        else:
            recommended = "do_not_auto"
        return {
            "score": score,
            "score_level": self._score_level(score),
            "risk_reasons": risk_reasons,
            "hard_risk_reasons": hard_risks,
            "can_auto_execute": can_auto,
            "recommended_action": recommended,
            "auto_ingest_enabled": auto_enabled,
            "auto_ingest_score_threshold": threshold,
            "confirm_score_threshold": confirm_threshold,
        }

    def _score_cloud_resource(
        self,
        item: Dict[str, Any],
        *,
        preferences: Optional[Dict[str, Any]] = None,
        source_type: str = "cloud",
        target_path: str = "",
    ) -> Dict[str, Any]:
        prefs = self._normalize_assistant_preferences(preferences)
        text = self._score_text_blob(item)
        score = 20
        reasons: List[str] = []
        risks: List[str] = []
        hard_risks: List[str] = []
        resolution_pref = self._clean_text(prefs.get("prefer_resolution")).lower()
        provider = self._clean_text(item.get("pan_type") or item.get("channel")).lower()
        media_type = self._clean_text(item.get("media_type") or item.get("type")).lower()
        series_like = (
            media_type in {"tv", "series", "电视剧", "剧集", "番剧"}
            or bool(re.search(r"\bs\d{1,2}\b|\be\d{1,3}\b|season|第\s*\d+\s*集|[全整]季|全集|完结|更至|更新至|短剧|剧集", text, flags=re.IGNORECASE))
        )

        if "2160" in text or "4k" in text or "uhd" in text:
            score += 25
            reasons.append("4K/UHD +25")
        elif "1080" in text:
            score += 16
            reasons.append("1080P +16")
        elif "720" in text:
            score += 6
            reasons.append("720P +6")
        if resolution_pref and resolution_pref in text:
            score += 5
            reasons.append(f"匹配偏好分辨率 {resolution_pref.upper()} +5")

        if self._score_has_any(text, ["dolby vision", "dovi", "dv", "杜比视界"]):
            score += 18
            reasons.append("杜比视界 +18")
        elif self._score_has_any(text, ["hdr10", "hdr", "hlg", "杜比"]):
            score += 12
            reasons.append("HDR +12")

        if self._score_has_any(text, ["中字", "中文字幕", "简中", "繁中", "内封简繁", "双语", "官中"]):
            score += 14
            reasons.append("中文字幕 +14")
        elif self._parse_bool_value(prefs.get("prefer_chinese_subtitle"), True):
            score -= 5
            risks.append("未识别到中文字幕")

        if self._score_has_any(text, ["全集", "全季", "完结", "complete", "全 ", "更至", "更0", "更新至"]):
            score += 12
            reasons.append("完整度信息 +12")
        elif series_like and self._parse_bool_value(prefs.get("prefer_complete_series"), True):
            score -= 6
            risks.append("未识别到全集/更新完整度")

        if self._score_has_any(text, ["remux", "原盘", "blu-ray", "bluray", "web-dl", "高码率"]):
            score += 8
            reasons.append("片源质量标识 +8")

        prefer_provider = self._clean_text(prefs.get("prefer_cloud_provider")).lower()
        if prefer_provider and provider and prefer_provider == provider:
            score += 5
            reasons.append(f"匹配网盘偏好 {provider} +5")
        if target_path and target_path in {
            self._clean_text(prefs.get("cloud_default_path")),
            self._clean_text(prefs.get("p115_default_path")),
            self._clean_text(prefs.get("quark_default_path")),
        }:
            score += 3
            reasons.append("匹配默认目录 +3")

        if source_type == "hdhive":
            limit = max(0, self._safe_int(prefs.get("hdhive_max_unlock_points"), self._hdhive_max_unlock_points))
            points = self._resource_points_value(item)
            if points == 0:
                score += 10
                reasons.append("影巢免费 +10")
            elif points is None and limit > 0:
                score -= 20
                message = "影巢积分未知，禁止自动解锁"
                risks.append(message)
                hard_risks.append(message)
            elif limit > 0 and points is not None and points > limit:
                score -= 30
                message = f"影巢积分 {points} 超过上限 {limit}，禁止自动解锁"
                risks.append(message)
                hard_risks.append(message)
            elif points is not None:
                score += max(0, 10 - points)
                reasons.append(f"影巢积分 {points}")

        final_score = max(0, min(100, score))
        decision = self._score_decision(
            score=final_score,
            risk_reasons=risks,
            hard_risk_reasons=hard_risks,
            preferences=prefs,
            default_action="auto_ingest_cloud",
        )
        return {
            **decision,
            "source_type": source_type,
            "score_reasons": reasons,
        }

    def _score_pt_resource(
        self,
        item: Dict[str, Any],
        *,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        prefs = self._normalize_assistant_preferences(preferences)
        text = self._score_text_blob(item)
        torrent = item.get("torrent_info") if isinstance(item.get("torrent_info"), dict) else item
        meta = item.get("meta_info") if isinstance(item.get("meta_info"), dict) else {}
        media = item.get("media_info") if isinstance(item.get("media_info"), dict) else {}
        score = 20
        reasons: List[str] = []
        risks: List[str] = []
        hard_risks: List[str] = []
        min_seeders = max(0, self._safe_int(prefs.get("pt_min_seeders"), 3))
        seeders = self._safe_int(torrent.get("seeders"), 0)
        peers = self._safe_int(torrent.get("peers"), 0)
        volume = self._clean_text(torrent.get("volume_factor") or item.get("volume_factor")).lower()
        title = self._clean_text(torrent.get("title"))
        site_name = self._clean_text(torrent.get("site_name"))
        group_name = self._clean_text(meta.get("resource_team"))
        media_title = self._clean_text(media.get("title")).lower()
        media_year = self._clean_text(media.get("year"))
        resolution_pref = self._clean_text(prefs.get("prefer_resolution")).lower()
        prefer_dovi = self._parse_bool_value(prefs.get("prefer_dolby_vision"), True)
        prefer_hdr = self._parse_bool_value(prefs.get("prefer_hdr"), True)
        prefer_subtitle = self._parse_bool_value(prefs.get("prefer_chinese_subtitle"), True)
        prefer_complete = self._parse_bool_value(prefs.get("prefer_complete_series"), True)

        if seeders <= 0:
            message = "做种数 0，禁止自动下载"
            risks.append(message)
            hard_risks.append(message)
            score -= 35
        elif seeders < min_seeders:
            message = f"做种数 {seeders}，低于阈值 {min_seeders}，禁止自动下载"
            risks.append(message)
            hard_risks.append(message)
            score -= 25
        elif seeders >= 20:
            score += 22
            reasons.append(f"做种数 {seeders} +22")
        elif seeders >= 10:
            score += 16
            reasons.append(f"做种数 {seeders} +16")
        else:
            score += 10
            reasons.append(f"做种数 {seeders} +10")

        if peers >= seeders * 5 and seeders < 5:
            score -= 8
            risks.append("下载需求高但做种偏低")
        elif peers >= max(8, seeders):
            score += 6
            reasons.append(f"下载热度 {peers} +6")
        elif peers >= 3:
            score += 3
            reasons.append(f"下载热度 {peers} +3")

        if self._score_has_any(volume, ["free", "免费", "2xfree", "2x free", "freeleech"]):
            score += 18
            reasons.append("免费/促销 +18")
        elif self._parse_bool_value(prefs.get("pt_require_free"), False):
            score -= 20
            message = "用户要求 PT 免费资源"
            risks.append(message)
            hard_risks.append(message)
        elif self._parse_bool_value(prefs.get("pt_prefer_free"), True):
            reasons.append("普通 PT 资源，未额外扣分")

        if "2160" in text or "4k" in text or "uhd" in text:
            score += 20
            reasons.append("4K/UHD +20")
        elif "1080" in text:
            score += 12
            reasons.append("1080P +12")
        elif "720" in text:
            score += 4
            reasons.append("720P +4")
        if resolution_pref and resolution_pref in text:
            score += 6
            reasons.append(f"匹配偏好分辨率 {resolution_pref.upper()} +6")
        has_dovi = self._score_has_any(text, ["dolby vision", "dovi", "dv", "杜比视界"])
        has_hdr = self._score_has_any(text, ["hdr10", "hdr", "hlg"])
        if has_dovi:
            score += 14
            reasons.append("杜比视界 +14")
        elif prefer_dovi:
            score -= 4
            risks.append("未识别到杜比视界")
        if has_hdr:
            score += 9
            reasons.append("HDR +9")
        elif prefer_hdr:
            score -= 2
            risks.append("未识别到 HDR")
        if self._score_has_any(text, ["中字", "简中", "繁中", "双语", "内封", "字幕"]):
            score += 10
            reasons.append("字幕信息 +10")
        elif prefer_subtitle:
            score -= 5
            risks.append("未识别到中文字幕")
        if self._score_has_any(text, ["remux", "原盘", "blu-ray", "bluray", "web-dl", "高码率"]):
            score += 8
            reasons.append("片源质量标识 +8")
        if self._score_has_any(text, ["s01", "season", "全集", "全季", "complete", "完结", "更新至", "更至"]):
            score += 6
            reasons.append("季/全集标识 +6")
        elif prefer_complete and self._score_has_any(text, ["s01", "s02", "e01", "第1集", "season"]):
            score -= 4
            risks.append("未识别到全集/完整季")

        if media_title:
            if media_title in title.lower():
                score += 8
                reasons.append("标题匹配媒体名 +8")
            else:
                score -= 4
                risks.append("标题与识别媒体名匹配一般")
        if media_year and media_year in title:
            score += 4
            reasons.append(f"年份匹配 {media_year} +4")
        if site_name:
            score += 2
            reasons.append(f"站点标识 {site_name} +2")
        if group_name:
            score += 2
            reasons.append(f"发布组 {group_name} +2")

        size_text = self._clean_text(torrent.get("size") or item.get("size"))
        size_value = 0.0
        size_match = re.search(r"(\d+(?:\.\d+)?)\s*(tb|gb|mb)", size_text, flags=re.IGNORECASE)
        if size_match:
            size_value = float(size_match.group(1))
            unit = size_match.group(2).lower()
            if unit == "tb":
                size_value *= 1024
            elif unit == "mb":
                size_value /= 1024
        if size_value > 0:
            if self._score_has_any(text, ["2160", "4k", "uhd", "remux", "原盘"]) and size_value < 8:
                score -= 6
                risks.append(f"体积 {size_text} 偏小，需留意是否压制过度")
            elif self._score_has_any(text, ["1080", "web-dl", "bluray"]) and size_value >= 4:
                score += 3
                reasons.append(f"体积 {size_text} 较充足 +3")
        if peers >= 30 and seeders >= min_seeders:
            score += 4
            reasons.append("热度稳定 +4")

        final_score = max(0, min(100, score))
        decision = self._score_decision(
            score=final_score,
            risk_reasons=risks,
            hard_risk_reasons=hard_risks,
            preferences=prefs,
            default_action="auto_download_pt",
        )
        return {
            **decision,
            "source_type": "pt",
            "score_reasons": reasons,
            "seeders": seeders,
            "peers": peers,
            "min_seeders": min_seeders,
            "volume_factor": volume,
            "site_name": site_name,
            "resource_team": group_name,
        }

    def _attach_cloud_scores(
        self,
        items: List[Dict[str, Any]],
        *,
        preferences: Optional[Dict[str, Any]] = None,
        source_type: str = "cloud",
        target_path: str = "",
    ) -> List[Dict[str, Any]]:
        return [
            {
                **dict(item or {}),
                "score": self._score_cloud_resource(
                    dict(item or {}),
                    preferences=preferences,
                    source_type=source_type,
                    target_path=target_path,
                ),
            }
            for item in items
            if isinstance(item, dict)
        ]

    @staticmethod
    def _format_score_label(item: Dict[str, Any]) -> str:
        score = item.get("score") if isinstance(item.get("score"), dict) else {}
        if not score:
            return ""
        try:
            value = int(float(score.get("score") or 0))
        except Exception:
            value = 0
        action = AgentResourceOfficer._clean_text(score.get("recommended_action"))
        if score.get("can_auto_execute"):
            suffix = "可自动入库"
        elif action == "ask_confirm":
            suffix = "建议确认"
        else:
            suffix = "不建议自动"
        return f"{value}分 {suffix}"

    def _score_brief_item(self, item: Dict[str, Any], fallback_index: int = 0) -> Dict[str, Any]:
        current = dict(item or {})
        score = current.get("score") if isinstance(current.get("score"), dict) else {}
        if not score:
            return {}
        torrent = current.get("torrent_info") if isinstance(current.get("torrent_info"), dict) else {}
        index = self._safe_int(
            current.get("pick_index") or current.get("index") or fallback_index,
            fallback_index,
        )
        title = (
            self._clean_text(torrent.get("title"))
            or self._clean_text(current.get("note"))
            or self._clean_text(current.get("title") or current.get("matched_title"))
            or "未命名资源"
        )
        provider = (
            self._clean_text(current.get("pan_type") or current.get("channel"))
            or self._clean_text(torrent.get("site_name"))
            or self._clean_text(current.get("site"))
        )
        reasons = [self._clean_text(value) for value in (score.get("score_reasons") or []) if self._clean_text(value)]
        risks = [self._clean_text(value) for value in (score.get("risk_reasons") or []) if self._clean_text(value)]
        hard_risks = [self._clean_text(value) for value in (score.get("hard_risk_reasons") or []) if self._clean_text(value)]
        brief = {
            "index": index,
            "title": title[:160],
            "provider": provider,
            "source_type": self._clean_text(score.get("source_type")),
            "score": self._safe_int(score.get("score"), 0),
            "score_level": self._clean_text(score.get("score_level")),
            "recommended_action": self._clean_text(score.get("recommended_action")),
            "can_auto_execute": bool(score.get("can_auto_execute")),
            "score_reasons": reasons[:3],
            "risk_reasons": risks[:2],
            "hard_risk_reasons": hard_risks[:2],
        }
        points_text = self._resource_points_text(current) if current and brief.get("source_type") != "pt" else ""
        if points_text and points_text != "积分未知":
            brief["points_text"] = points_text
        seeders = torrent.get("seeders") if torrent else score.get("seeders")
        if seeders is not None:
            brief["seeders"] = seeders
        volume = self._clean_text(torrent.get("volume_factor") if torrent else score.get("volume_factor"))
        if volume:
            brief["volume_factor"] = volume
        size = self._clean_text(current.get("share_size") or current.get("size") or torrent.get("size"))
        if size:
            brief["size"] = size
        return brief

    def _score_summary(self, items: List[Dict[str, Any]], *, limit: int = 5) -> Dict[str, Any]:
        scored: List[Dict[str, Any]] = []
        for index, item in enumerate(items or [], 1):
            if not isinstance(item, dict):
                continue
            brief = self._score_brief_item(item, fallback_index=index)
            if brief:
                scored.append(brief)
        scored.sort(key=lambda value: (
            1 if value.get("can_auto_execute") else 0,
            self._safe_int(value.get("score"), 0),
        ), reverse=True)
        auto_count = len([item for item in scored if item.get("can_auto_execute")])
        confirm_count = len([item for item in scored if item.get("recommended_action") == "ask_confirm"])
        blocked_count = len([item for item in scored if item.get("hard_risk_reasons")])
        warning_count = len([item for item in scored if item.get("risk_reasons")])
        return {
            "total_scored": len(scored),
            "auto_count": auto_count,
            "confirm_count": confirm_count,
            "blocked_count": blocked_count,
            "warning_count": warning_count,
            "best": scored[0] if scored else None,
            "top_recommendations": scored[:max(1, min(10, self._safe_int(limit, 5)))],
        }

    def _best_scored_source_item(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        candidates = [
            dict(item or {})
            for item in (items or [])
            if isinstance(item, dict) and isinstance(item.get("score"), dict)
        ]
        if not candidates:
            return {}
        return max(
            candidates,
            key=lambda item: (
                1 if (item.get("score") or {}).get("can_auto_execute") else 0,
                self._safe_int((item.get("score") or {}).get("score"), 0),
                self._safe_int(item.get("index") or item.get("pick_index"), 0),
            ),
        )

    def _format_cloud_item_detail_text(self, item: Dict[str, Any], *, title: str = "云盘资源详情") -> str:
        current = dict(item or {})
        score = current.get("score") if isinstance(current.get("score"), dict) else {}
        index = self._safe_int(current.get("index") or current.get("pick_index"), 0)
        name = (
            self._clean_text(current.get("note"))
            or self._clean_text(current.get("title"))
            or self._clean_text(current.get("matched_title"))
            or "未命名资源"
        )
        provider = self._clean_text(current.get("channel") or current.get("pan_type") or current.get("provider"))
        size = self._clean_text(current.get("share_size") or current.get("size"))
        resolution = self._clean_text(current.get("resolution"))
        source = self._clean_text(current.get("source") or current.get("source_name"))
        points = self._resource_points_text(current)
        lines = [title]
        if index:
            lines.append(f"编号：{index}")
        lines.append(f"资源：{name}")
        if provider:
            lines.append(f"网盘：{provider}")
        if points:
            lines.append(f"积分：{points}")
        if resolution:
            lines.append(f"分辨率：{resolution}")
        if size:
            lines.append(f"大小：{size}")
        if source:
            lines.append(f"来源：{source}")
        if score:
            lines.append(f"评分：{self._safe_int(score.get('score'), 0)} / {self._clean_text(score.get('score_level')) or '-'}")
            reasons = [self._clean_text(value) for value in (score.get("score_reasons") or []) if self._clean_text(value)]
            hard_risks = [self._clean_text(value) for value in (score.get("hard_risk_reasons") or []) if self._clean_text(value)]
            risks = [self._clean_text(value) for value in (score.get("risk_reasons") or []) if self._clean_text(value)]
            risks = [risk for risk in risks if risk not in hard_risks]
            if reasons:
                lines.append("加分理由：" + "；".join(reasons[:6]))
            if hard_risks:
                lines.append("硬风险：" + "；".join(hard_risks[:6]))
            if risks:
                lines.append("提醒：" + "；".join(risks[:6]))
        if index:
            lines.append(f"下一步：确认处理请回复“选择 {index}”。")
        return "\n".join(lines)

    def _assistant_scoring_policy_public_data(self) -> Dict[str, Any]:
        prefs = self._default_assistant_preferences()
        return {
            "schema_version": "scoring_policy.v1",
            "owner": "plugin_rules",
            "agent_role": "explain_and_confirm_only",
            "summary": "评分由插件内置规则执行；外部智能体只读取 score_summary、解释原因、请求确认，不能绕过硬风险。",
            "global_decision": {
                "auto_execute_requires": [
                    "auto_ingest_enabled=true",
                    "score >= auto_ingest_score_threshold",
                    "hard_risk_reasons 为空",
                ],
                "confirm_range": "confirm_score_threshold <= score < auto_ingest_score_threshold 且无硬风险",
                "default_confirm_score_threshold": prefs.get("confirm_score_threshold"),
                "default_auto_ingest_score_threshold": prefs.get("auto_ingest_score_threshold"),
                "auto_ingest_default": prefs.get("auto_ingest_enabled"),
            },
            "cloud": {
                "source_types": ["hdhive", "pansou", "115", "quark"],
                "positive_signals": [
                    "4K/UHD",
                    "杜比视界/HDR",
                    "中文字幕",
                    "全集/完整季/更新完整度",
                    "REMUX/原盘/Web-DL/高码率",
                    "匹配网盘偏好",
                    "匹配默认目录",
                ],
                "hard_gates": [
                    "影巢积分超过 hdhive_max_unlock_points 时禁止自动解锁",
                    "影巢积分未知时禁止自动解锁",
                ],
                "default_hdhive_max_unlock_points": prefs.get("hdhive_max_unlock_points"),
                "pansou_cost": "无积分成本，主要按质量、完整度、字幕和网盘类型评分",
            },
            "pt": {
                "source_types": ["moviepilot_native_search", "torrent_search", "subscribe_search"],
                "positive_signals": [
                    "做种数高",
                    "免费/促销/FreeLeech",
                    "4K/UHD",
                    "杜比视界/HDR",
                    "字幕信息",
                    "REMUX/原盘/Web-DL/高码率",
                    "季/全集标识",
                ],
                "hard_gates": [
                    "做种数 0 禁止自动下载",
                    "做种数低于 pt_min_seeders 禁止自动下载",
                    "用户要求免费时，非免费资源禁止自动下载",
                ],
                "default_pt_min_seeders": prefs.get("pt_min_seeders"),
                "volume_factor_note": "免费/促销明显加分；普通资源默认中性，不强行判废",
            },
            "score_summary_contract": {
                "read_fields": [
                    "best",
                    "top_recommendations",
                    "score",
                    "score_level",
                    "recommended_action",
                    "can_auto_execute",
                    "score_reasons",
                    "risk_reasons",
                    "hard_risk_reasons",
                ],
                "blocked_count": "只统计 hard_risk_reasons，不统计缺字幕等软提醒",
                "warning_count": "统计 risk_reasons，用于解释需要用户确认的原因",
                "do_not_parse": "不要解析自然语言 message 来判断自动化，优先读取 score_summary",
            },
        }

    @staticmethod
    def _format_bytes_size(value: Any) -> str:
        try:
            size = float(value or 0)
        except Exception:
            return ""
        if size <= 0:
            return ""
        units = ["B", "KB", "MB", "GB", "TB"]
        index = 0
        while size >= 1024 and index < len(units) - 1:
            size /= 1024
            index += 1
        return f"{size:.2f}{units[index]}" if index else f"{int(size)}B"

    def _mp_context_preview_item(self, context: Any, index: int, preferences: Dict[str, Any]) -> Dict[str, Any]:
        torrent = getattr(context, "torrent_info", None)
        meta = getattr(context, "meta_info", None)
        media = getattr(context, "media_info", None)
        item = {
            "index": index,
            "torrent_info": {
                "title": self._clean_text(getattr(torrent, "title", "")),
                "size": self._format_bytes_size(getattr(torrent, "size", None)),
                "seeders": getattr(torrent, "seeders", None),
                "peers": getattr(torrent, "peers", None),
                "site_name": self._clean_text(getattr(torrent, "site_name", "")),
                "volume_factor": self._clean_text(getattr(torrent, "volume_factor", "")),
                "page_url": self._clean_text(getattr(torrent, "page_url", "")),
            },
            "meta_info": {
                "season_episode": self._clean_text(getattr(meta, "season_episode", "")),
                "resource_team": self._clean_text(getattr(meta, "resource_team", "")),
                "video_encode": self._clean_text(getattr(meta, "video_encode", "")),
                "edition": self._clean_text(getattr(meta, "edition", "")),
                "resource_pix": self._clean_text(getattr(meta, "resource_pix", "")),
            },
            "media_info": {
                "title": self._clean_text(getattr(media, "title", "")),
                "year": self._clean_text(getattr(media, "year", "")),
                "tmdb_id": getattr(media, "tmdb_id", None),
                "douban_id": getattr(media, "douban_id", None),
            },
        }
        item["score"] = self._score_pt_resource(item, preferences=preferences)
        return item

    def _mp_search_cache_preview(self, cache_key: str, preferences: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
        try:
            cache = self._ensure_feishu_channel()._get_search_cache(cache_key)
        except Exception:
            cache = None
        results = (cache or {}).get("results") or []
        preview: List[Dict[str, Any]] = []
        for index, context in enumerate(results[:max(1, limit)], 1):
            preview.append(self._mp_context_preview_item(context, index, preferences))
        return preview

    def _format_mp_search_text(self, keyword: str, message_text: str, preview: List[Dict[str, Any]]) -> str:
        lines = [message_text.strip()] if message_text else [f"MP 原生搜索：{keyword}"]
        if preview:
            lines.append("")
            lines.append("PT 评分摘要：")
            for item in preview[:10]:
                torrent = item.get("torrent_info") or {}
                score = item.get("score") or {}
                title = torrent.get("title") or "未命名资源"
                lines.append(f"{item.get('index')}. {self._format_score_label(item)} | [{torrent.get('site_name') or '未知站点'}] {title}")
                details = [
                    f"做种：{torrent.get('seeders') if torrent.get('seeders') is not None else '?'}",
                    f"促销：{torrent.get('volume_factor') or '普通'}",
                    f"大小：{torrent.get('size') or '未知'}",
                ]
                hard_risks = score.get("hard_risk_reasons") or []
                risks = score.get("risk_reasons") or []
                risks = [risk for risk in risks if risk not in hard_risks]
                if hard_risks:
                    details.append("硬风险：" + "；".join(str(item) for item in hard_risks[:2]))
                elif risks:
                    details.append("提醒：" + "；".join(str(item) for item in risks[:2]))
                lines.append("   " + " | ".join(details))
            lines.append("下载/订阅属于写入动作，默认请先用 dry_run 生成 plan_id，再确认执行。")
        return "\n".join(line for line in lines if line)

    async def _assistant_mp_media_detail(
        self,
        *,
        keyword: str,
        session: str,
        cache_key: str,
        media_type: str = "",
        year: str = "",
    ) -> Dict[str, Any]:
        result = self._ensure_feishu_channel()._query_media_detail(
            keyword=keyword,
            media_type=media_type,
            year=year,
        )
        item = result.get("item") if isinstance(result.get("item"), dict) else {}
        self._save_session(cache_key, {
            "kind": "assistant_mp_media_detail",
            "stage": "media_detail",
            "keyword": keyword,
            "items": [item] if item else [],
            "target_path": "",
        })
        return {
            "success": bool(result.get("success")),
            "message": self._clean_text(result.get("message")) or "媒体识别完成",
            "data": self._assistant_response_data(session=session, data={
                "action": "mp_media_detail",
                "ok": bool(result.get("success")),
                "keyword": keyword,
                "media_type": media_type,
                "year": year,
                "item": item,
            }),
        }

    async def _assistant_mp_media_search(
        self,
        *,
        keyword: str,
        session: str,
        cache_key: str,
        preferences: Dict[str, Any],
    ) -> Dict[str, Any]:
        message_text = self._ensure_feishu_channel()._execute_media_search(keyword, cache_key)
        failed_prefixes = ("MP 原生搜索失败", "未识别到媒体信息", "搜索资源失败")
        route_ok = not any(message_text.startswith(prefix) for prefix in failed_prefixes)
        preview = self._mp_search_cache_preview(cache_key, preferences=preferences, limit=10)
        self._save_session(cache_key, {
            "kind": "assistant_mp",
            "stage": "search_result",
            "keyword": keyword,
            "items": preview,
            "target_path": "",
        })
        return {
            "success": route_ok,
            "message": self._format_mp_search_text(keyword, message_text, preview),
            "data": self._assistant_response_data(session=session, data={
                "action": "mp_media_search",
                "ok": route_ok,
                "keyword": keyword,
                "source_type": "pt",
                "items": preview,
                "score_summary": self._score_summary(preview, limit=5),
                "preferences": preferences,
            }),
        }

    async def _assistant_mp_result_detail(
        self,
        *,
        choice: int,
        session: str,
        cache_key: str,
        preferences: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            cache = self._ensure_feishu_channel()._get_search_cache(cache_key)
        except Exception:
            cache = None
        results = (cache or {}).get("results") or []
        if choice <= 0 or choice > len(results):
            return {
                "success": False,
                "message": f"序号超出范围，请输入 1 到 {len(results)} 之间的数字。" if results else "没有可继续的 MP 搜索结果，请先发送“MP搜索 片名”。",
                "data": self._assistant_response_data(session=session, data={
                    "action": "mp_search_result_detail",
                    "ok": False,
                    "error_code": "mp_result_not_found",
                }),
            }
        item = self._mp_context_preview_item(results[choice - 1], choice, preferences=preferences)
        torrent = item.get("torrent_info") or {}
        meta = item.get("meta_info") or {}
        media = item.get("media_info") or {}
        score = item.get("score") or {}
        lines = [
            f"MP 搜索结果详情 #{choice}",
            f"标题：{torrent.get('title') or '未命名资源'}",
            f"站点：{torrent.get('site_name') or '未知站点'}",
            f"大小：{torrent.get('size') or '未知'}",
            f"做种：{torrent.get('seeders') if torrent.get('seeders') is not None else '?'} | 下载：{torrent.get('peers') if torrent.get('peers') is not None else '?'} | 促销：{torrent.get('volume_factor') or '普通'}",
        ]
        media_text = " / ".join(str(part) for part in [
            media.get("title"),
            media.get("year"),
            f"TMDB:{media.get('tmdb_id')}" if media.get("tmdb_id") else "",
            f"豆瓣:{media.get('douban_id')}" if media.get("douban_id") else "",
        ] if part)
        if media_text:
            lines.append(f"媒体：{media_text}")
        meta_text = " / ".join(str(part) for part in [
            meta.get("season_episode"),
            meta.get("resource_pix"),
            meta.get("video_encode"),
            meta.get("edition"),
            meta.get("resource_team"),
        ] if part)
        if meta_text:
            lines.append(f"识别标签：{meta_text}")
        score_label = self._format_score_label(item)
        if score_label:
            lines.append(f"评分：{score_label}")
        reasons = [str(value) for value in (score.get("score_reasons") or []) if value]
        hard_risks = [str(value) for value in (score.get("hard_risk_reasons") or []) if value]
        risks = [str(value) for value in (score.get("risk_reasons") or []) if value]
        risks = [risk for risk in risks if risk not in hard_risks]
        if reasons:
            lines.append("加分理由：" + "；".join(reasons[:6]))
        if hard_risks:
            lines.append("硬风险：" + "；".join(hard_risks[:6]))
        if risks:
            lines.append("提醒：" + "；".join(risks[:6]))
        if torrent.get("page_url"):
            lines.append(f"详情页：{torrent.get('page_url')}")
        lines.append(f"下一步：确认下载请发“下载{choice}”，会先生成 plan_id，不会静默下载。")
        self._save_session(cache_key, {
            "kind": "assistant_mp",
            "stage": "search_result",
            "keyword": (cache or {}).get("keyword") or "",
            "items": self._mp_search_cache_preview(cache_key, preferences=preferences, limit=10),
            "selected_index": choice,
            "target_path": "",
        })
        return {
            "success": True,
            "message": "\n".join(lines),
            "data": self._assistant_response_data(session=session, data={
                "action": "mp_search_result_detail",
                "ok": True,
                "choice": choice,
                "item": item,
                "score_summary": self._score_summary([item], limit=1),
            }),
        }

    async def _assistant_mp_best_result_detail(
        self,
        *,
        session: str,
        cache_key: str,
        preferences: Dict[str, Any],
    ) -> Dict[str, Any]:
        preview = self._mp_search_cache_preview(cache_key, preferences=preferences, limit=10)
        scored = [
            item for item in preview
            if isinstance(item, dict) and isinstance(item.get("score"), dict)
        ]
        if not scored:
            return {
                "success": False,
                "message": "没有可评分的 MP 搜索结果，请先发送“MP搜索 片名”。",
                "data": self._assistant_response_data(session=session, data={
                    "action": "mp_search_best_detail",
                    "ok": False,
                    "error_code": "mp_best_result_not_found",
                }),
            }
        best = max(
            scored,
            key=lambda item: (
                self._safe_int((item.get("score") or {}).get("score"), 0),
                self._safe_int(((item.get("torrent_info") or {}).get("seeders")), 0),
            ),
        )
        choice = self._safe_int(best.get("index"), 0)
        result = await self._assistant_mp_result_detail(
            choice=choice,
            session=session,
            cache_key=cache_key,
            preferences=preferences,
        )
        if result.get("success"):
            result["message"] = f"当前评分最高的 PT 候选是 #{choice}\n{result.get('message') or ''}".strip()
            data = dict(result.get("data") or {})
            data["action"] = "mp_search_best_detail"
            data["best_choice"] = choice
            result["data"] = data
        return result

    async def _assistant_mp_best_download_plan(
        self,
        *,
        session: str,
        cache_key: str,
        preferences: Dict[str, Any],
    ) -> Dict[str, Any]:
        preview = self._mp_search_cache_preview(cache_key, preferences=preferences, limit=10)
        scored = [
            item for item in preview
            if isinstance(item, dict) and isinstance(item.get("score"), dict)
        ]
        if not scored:
            return {
                "success": False,
                "message": "没有可评分的 MP 搜索结果，请先发送“MP搜索 片名”。",
                "data": self._assistant_response_data(session=session, data={
                    "action": "mp_best_download_plan",
                    "ok": False,
                    "error_code": "mp_best_result_not_found",
                }),
            }
        best = max(
            scored,
            key=lambda item: (
                self._safe_int((item.get("score") or {}).get("score"), 0),
                self._safe_int(((item.get("torrent_info") or {}).get("seeders")), 0),
            ),
        )
        choice = self._safe_int(best.get("index"), 0)
        result = self._assistant_mp_download_plan_response(
            choice=choice,
            session=session,
            cache_key=cache_key,
            preferences=preferences,
            workflow="mp_best_download",
            message="最佳片源下载计划已生成",
        )
        if result.get("success"):
            result["message"] = "\n".join(line for line in [
                f"已选择当前评分最高的 PT 候选：#{choice}",
                result.get("message") or "",
            ] if line)
            data = dict(result.get("data") or {})
            data["choice"] = choice
            data["item"] = best
            result["data"] = data
        return result

    @staticmethod
    def _assistant_score_warning_text(score: Dict[str, Any], *, limit: int = 3) -> str:
        risks = [str(value) for value in (score.get("risk_reasons") or []) if value]
        if not risks:
            return ""
        return "风险提示：" + "；".join(risks[:max(1, limit)])

    def _assistant_mp_download_plan_response(
        self,
        *,
        choice: int,
        session: str,
        cache_key: str,
        preferences: Dict[str, Any],
        workflow: str = "mp_download",
        message: str = "PT 下载计划已生成",
    ) -> Dict[str, Any]:
        preview = self._mp_search_cache_preview(cache_key, preferences=preferences, limit=10)
        selected = next((item for item in preview if self._safe_int(item.get("index"), 0) == choice), {})
        if not selected:
            return {
                "success": False,
                "message": "没有可继续的 MP 搜索结果，请先发送“MP搜索 片名”后再选择编号。",
                "data": self._assistant_response_data(session=session, data={
                    "action": "mp_download",
                    "ok": False,
                    "error_code": "mp_result_not_found",
                    "choice": choice,
                }),
            }
        result = self._save_assistant_pick_plan_response(
            workflow=workflow,
            session=session,
            session_id=cache_key,
            actions=[{
                "name": "pick_mp_download",
                "session": session,
                "session_id": cache_key,
                "choice": choice,
            }],
            execute_body={
                "workflow": workflow,
                "session": session,
                "session_id": cache_key,
                "choice": choice,
                "dry_run": False,
            },
            message=message,
            score_items=[selected],
            extra_data={
                "choice": choice,
                "selected": selected,
            },
        )
        score = selected.get("score") if isinstance(selected.get("score"), dict) else {}
        warning = self._assistant_score_warning_text(score)
        if warning:
            result["message"] = f"{result.get('message')}\n{warning}"
        return result

    def _assistant_mp_subscribe_plan_response(
        self,
        *,
        keyword: str,
        session: str,
        cache_key: str,
        immediate_search: bool = False,
    ) -> Dict[str, Any]:
        keyword = self._clean_text(keyword)
        if not keyword:
            return {
                "success": False,
                "message": "订阅失败：缺少片名或关键词",
                "data": self._assistant_response_data(session=session, data={
                    "action": "mp_subscribe_search" if immediate_search else "mp_subscribe",
                    "ok": False,
                    "error_code": "missing_keyword",
                }),
            }
        action_name = "start_mp_subscribe_search" if immediate_search else "start_mp_subscribe"
        workflow = "mp_subscribe_and_search" if immediate_search else "mp_subscribe"
        label = "订阅并搜索计划已生成" if immediate_search else "订阅计划已生成"
        return self._save_assistant_pick_plan_response(
            workflow=workflow,
            session=session,
            session_id=cache_key,
            actions=[{
                "name": action_name,
                "session": session,
                "session_id": cache_key,
                "keyword": keyword,
            }],
            execute_body={
                "workflow": workflow,
                "session": session,
                "session_id": cache_key,
                "keyword": keyword,
                "dry_run": False,
            },
            message=label,
            extra_data={
                "keyword": keyword,
                "immediate_search": bool(immediate_search),
            },
        )

    def _assistant_mp_download_control_plan_response(
        self,
        *,
        control: str,
        target: str,
        session: str,
        cache_key: str,
        downloader: str = "",
        delete_files: bool = False,
    ) -> Dict[str, Any]:
        control = self._clean_text(control)
        target = self._clean_text(target)
        if not control or not target:
            return {
                "success": False,
                "message": "下载任务操作缺少 control 或 target。",
                "data": self._assistant_response_data(session=session, data={
                    "action": "mp_download_control",
                    "ok": False,
                    "error_code": "invalid_download_control_args",
                }),
            }
        if not self._resolve_mp_download_task_target(target=target, cache_key=cache_key):
            return {
                "success": False,
                "message": "未找到可操作的下载任务。请先发送“下载任务”获取列表，再按编号操作；也可以直接传 40 位任务 hash。",
                "data": self._assistant_response_data(session=session, data={
                    "action": "mp_download_control",
                    "ok": False,
                    "error_code": "download_target_not_found",
                    "target": target,
                }),
            }
        downloader = self._clean_text(downloader)
        return self._save_assistant_pick_plan_response(
            workflow="mp_download_control",
            session=session,
            session_id=cache_key,
            actions=[{
                "name": "mp_download_control",
                "session": session,
                "session_id": cache_key,
                "control": control,
                "target": target,
                "downloader": downloader,
                "delete_files": delete_files,
            }],
            execute_body={
                "workflow": "mp_download_control",
                "session": session,
                "session_id": cache_key,
                "control": control,
                "target": target,
                "downloader": downloader,
                "delete_files": delete_files,
                "dry_run": False,
            },
            message="下载任务操作计划已生成",
            extra_data={
                "control": control,
                "target": target,
            },
        )

    def _assistant_mp_subscribe_control_plan_response(
        self,
        *,
        control: str,
        target: str,
        session: str,
        cache_key: str,
        allow_raw_id: bool = False,
    ) -> Dict[str, Any]:
        control = self._clean_text(control)
        target = self._clean_text(target)
        if not control or not target:
            return {
                "success": False,
                "message": "订阅操作缺少 control 或 target。",
                "data": self._assistant_response_data(session=session, data={
                    "action": "mp_subscribe_control",
                    "ok": False,
                    "error_code": "invalid_subscribe_control_args",
                }),
            }
        if not self._resolve_mp_subscribe_target(target=target, cache_key=cache_key, allow_raw_id=allow_raw_id):
            return {
                "success": False,
                "message": "未找到可操作的订阅。请先发送“订阅列表”获取列表，再按编号操作；也可以直接传订阅 ID。",
                "data": self._assistant_response_data(session=session, data={
                    "action": "mp_subscribe_control",
                    "ok": False,
                    "error_code": "subscribe_target_not_found",
                    "target": target,
                }),
            }
        return self._save_assistant_pick_plan_response(
            workflow="mp_subscribe_control",
            session=session,
            session_id=cache_key,
            actions=[{
                "name": "mp_subscribe_control",
                "session": session,
                "session_id": cache_key,
                "control": control,
                "target": target,
            }],
            execute_body={
                "workflow": "mp_subscribe_control",
                "session": session,
                "session_id": cache_key,
                "control": control,
                "target": target,
                "dry_run": False,
            },
            message="订阅操作计划已生成",
            extra_data={
                "control": control,
                "target": target,
            },
        )

    async def _assistant_mp_download(self, *, choice: int, session: str, cache_key: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
        preview = self._mp_search_cache_preview(cache_key, preferences=preferences, limit=10)
        selected = next((item for item in preview if self._safe_int(item.get("index"), 0) == choice), {})
        score = selected.get("score") if isinstance(selected.get("score"), dict) else {}
        message_text = self._ensure_feishu_channel()._execute_media_download(choice, cache_key)
        ok = not message_text.startswith("下载资源失败") and not message_text.startswith("没有可用")
        warning = self._assistant_score_warning_text(score)
        if warning:
            message_text = f"{warning}\n{message_text}".strip()
        return {
            "success": ok,
            "message": message_text,
            "data": self._assistant_response_data(session=session, data={
                "action": "mp_download",
                "ok": ok,
                "choice": choice,
                "selected": selected,
                "score": score,
                "write_effect": "write",
            }),
        }

    async def _assistant_mp_subscribe(
        self,
        *,
        keyword: str,
        session: str,
        immediate_search: bool = False,
    ) -> Dict[str, Any]:
        keyword = self._clean_text(keyword)
        if not keyword:
            return {
                "success": False,
                "message": "订阅失败：缺少片名或关键词",
                "data": self._assistant_response_data(session=session, data={
                    "action": "mp_subscribe_search" if immediate_search else "mp_subscribe",
                    "ok": False,
                    "error_code": "missing_keyword",
                }),
            }
        message_text = self._ensure_feishu_channel()._execute_media_subscribe(keyword, immediate_search)
        ok = not message_text.startswith("订阅失败")
        return {
            "success": ok,
            "message": message_text,
            "data": self._assistant_response_data(session=session, data={
                "action": "mp_subscribe_search" if immediate_search else "mp_subscribe",
                "ok": ok,
                "keyword": keyword,
                "immediate_search": bool(immediate_search),
                "write_effect": "write",
            }),
        }

    def _resolve_mp_download_task_target(self, *, target: str, cache_key: str) -> Dict[str, Any]:
        target_text = self._clean_text(target)
        state = self._load_session(cache_key) or {}
        items = state.get("items") if isinstance(state.get("items"), list) else []
        index = self._safe_int(target_text, 0)
        if index > 0:
            for item in items:
                if self._safe_int(item.get("index"), 0) == index:
                    return dict(item)
        hash_match = re.search(r"\b[0-9a-fA-F]{40}\b", target_text)
        if hash_match:
            task_hash = hash_match.group(0)
            return {"hash": task_hash, "hash_short": task_hash[:8]}
        short_hash_match = re.search(r"\b[0-9a-fA-F]{6,12}\b", target_text)
        if short_hash_match:
            short_hash = short_hash_match.group(0).lower()
            for item in items:
                task_hash = self._clean_text(item.get("hash")).lower()
                if task_hash.startswith(short_hash):
                    return dict(item)
        return {}

    async def _assistant_mp_download_tasks(
        self,
        *,
        session: str,
        cache_key: str,
        status: str = "downloading",
        title: str = "",
        hash_value: str = "",
        downloader: str = "",
        limit: int = 10,
    ) -> Dict[str, Any]:
        result = self._ensure_feishu_channel()._query_download_tasks(
            downloader=downloader,
            status=status or "downloading",
            title=title,
            hash_value=hash_value,
            limit=max(1, min(30, self._safe_int(limit, 10))),
        )
        items = result.get("items") if isinstance(result.get("items"), list) else []
        self._save_session(cache_key, {
            "kind": "assistant_mp_download_tasks",
            "stage": "download_tasks",
            "keyword": title or hash_value or status or "downloading",
            "items": items,
            "target_path": "",
        })
        return {
            "success": bool(result.get("success")),
            "message": self._clean_text(result.get("message")) or "下载任务查询完成",
            "data": self._assistant_response_data(session=session, data={
                "action": "mp_download_tasks",
                "ok": bool(result.get("success")),
                "status": result.get("status") or status,
                "items": items,
                "total": result.get("total", len(items)),
            }),
        }

    async def _assistant_mp_download_control(
        self,
        *,
        session: str,
        cache_key: str,
        control: str,
        target: str,
        downloader: str = "",
        delete_files: bool = False,
    ) -> Dict[str, Any]:
        selected = self._resolve_mp_download_task_target(target=target, cache_key=cache_key)
        task_hash = self._clean_text(selected.get("hash"))
        if not task_hash:
            return {
                "success": False,
                "message": "操作下载任务失败：请先发送“下载任务”获取列表，再按编号操作，例如“暂停下载 1”。",
                "data": self._assistant_response_data(session=session, data={
                    "action": "mp_download_control",
                    "ok": False,
                    "error_code": "missing_download_task_hash",
                    "target": target,
                }),
            }
        result = self._ensure_feishu_channel()._control_download_task(
            action=control,
            hash_value=task_hash,
            downloader=downloader or self._clean_text(selected.get("downloader")),
            delete_files=delete_files,
        )
        return {
            "success": bool(result.get("success")),
            "message": self._clean_text(result.get("message")) or "下载任务操作完成",
            "data": self._assistant_response_data(session=session, data={
                "action": "mp_download_control",
                "ok": bool(result.get("success")),
                "control": control,
                "target": target,
                "selected": selected,
                "result": result,
                "write_effect": "write",
            }),
        }

    async def _assistant_mp_download_history(
        self,
        *,
        session: str,
        cache_key: str,
        title: str = "",
        hash_value: str = "",
        limit: int = 10,
        page: int = 1,
    ) -> Dict[str, Any]:
        result = self._ensure_feishu_channel()._query_download_history(
            title=title,
            hash_value=hash_value,
            limit=max(1, min(50, self._safe_int(limit, 10))),
            page=max(1, self._safe_int(page, 1)),
        )
        items = result.get("items") if isinstance(result.get("items"), list) else []
        self._save_session(cache_key, {
            "kind": "assistant_mp_download_history",
            "stage": "download_history",
            "keyword": title or hash_value or "all",
            "items": items,
            "target_path": "",
        })
        return {
            "success": bool(result.get("success")),
            "message": self._clean_text(result.get("message")) or "下载历史查询完成",
            "data": self._assistant_response_data(session=session, data={
                "action": "mp_download_history",
                "ok": bool(result.get("success")),
                "source_type": "moviepilot_download_history",
                "title": title,
                "hash": hash_value,
                "items": items,
                "total": self._safe_int(result.get("total"), len(items)),
                "page": self._safe_int(result.get("page"), page),
                "limit": self._safe_int(result.get("limit"), limit),
            }),
        }

    async def _assistant_mp_downloaders(self, *, session: str, cache_key: str) -> Dict[str, Any]:
        result = self._ensure_feishu_channel()._query_downloaders()
        items = result.get("items") if isinstance(result.get("items"), list) else []
        self._save_session(cache_key, {
            "kind": "assistant_mp_downloaders",
            "stage": "downloaders",
            "keyword": "downloaders",
            "items": items,
            "enabled_count": self._safe_int(result.get("enabled_count"), 0),
            "target_path": "",
        })
        return {
            "success": bool(result.get("success")),
            "message": self._clean_text(result.get("message")) or "下载器查询完成",
            "data": self._assistant_response_data(session=session, data={
                "action": "mp_downloaders",
                "ok": bool(result.get("success")),
                "items": items,
                "enabled_count": self._safe_int(result.get("enabled_count"), 0),
            }),
        }

    async def _assistant_mp_sites(
        self,
        *,
        session: str,
        cache_key: str,
        status: str = "active",
        name: str = "",
        limit: int = 30,
    ) -> Dict[str, Any]:
        result = self._ensure_feishu_channel()._query_sites(
            status=status or "active",
            name=name,
            limit=max(1, min(100, self._safe_int(limit, 30))),
        )
        items = result.get("items") if isinstance(result.get("items"), list) else []
        self._save_session(cache_key, {
            "kind": "assistant_mp_sites",
            "stage": "sites",
            "keyword": name or status or "active",
            "items": items,
            "status": result.get("status") or status,
            "target_path": "",
        })
        return {
            "success": bool(result.get("success")),
            "message": self._clean_text(result.get("message")) or "站点查询完成",
            "data": self._assistant_response_data(session=session, data={
                "action": "mp_sites",
                "ok": bool(result.get("success")),
                "status": result.get("status") or status,
                "items": items,
                "total": self._safe_int(result.get("total"), 0),
            }),
        }

    def _resolve_mp_subscribe_target(self, *, target: str, cache_key: str, allow_raw_id: bool = False) -> Dict[str, Any]:
        target_text = self._clean_text(target)
        state = self._load_session(cache_key) or {}
        items = state.get("items") if isinstance(state.get("items"), list) else []
        index = self._safe_int(target_text, 0)
        if index > 0:
            for item in items:
                if self._safe_int(item.get("index"), 0) == index or self._safe_int(item.get("id"), 0) == index:
                    return dict(item)
            if allow_raw_id:
                return {"id": index}
        return {}

    async def _assistant_mp_subscribes(
        self,
        *,
        session: str,
        cache_key: str,
        status: str = "all",
        media_type: str = "all",
        name: str = "",
        limit: int = 20,
    ) -> Dict[str, Any]:
        result = self._ensure_feishu_channel()._query_subscribes(
            status=status or "all",
            media_type=media_type or "all",
            name=name,
            limit=max(1, min(100, self._safe_int(limit, 20))),
        )
        items = result.get("items") if isinstance(result.get("items"), list) else []
        self._save_session(cache_key, {
            "kind": "assistant_mp_subscribes",
            "stage": "subscribe_list",
            "keyword": name or status or "all",
            "items": items,
            "target_path": "",
        })
        return {
            "success": bool(result.get("success")),
            "message": self._clean_text(result.get("message")) or "订阅查询完成",
            "data": self._assistant_response_data(session=session, data={
                "action": "mp_subscribes",
                "ok": bool(result.get("success")),
                "status": result.get("status") or status,
                "items": items,
                "total": self._safe_int(result.get("total"), len(items)),
            }),
        }

    async def _assistant_mp_subscribe_control(
        self,
        *,
        session: str,
        cache_key: str,
        control: str,
        target: str,
        allow_raw_id: bool = False,
    ) -> Dict[str, Any]:
        selected = self._resolve_mp_subscribe_target(target=target, cache_key=cache_key, allow_raw_id=allow_raw_id)
        subscribe_id = self._safe_int(selected.get("id") or target, 0)
        if subscribe_id <= 0:
            return {
                "success": False,
                "message": "操作订阅失败：请先发送“订阅列表”获取列表，再按编号操作，例如“搜索订阅 1”。",
                "data": self._assistant_response_data(session=session, data={
                    "action": "mp_subscribe_control",
                    "ok": False,
                    "error_code": "missing_subscribe_id",
                    "target": target,
                }),
            }
        result = self._ensure_feishu_channel()._control_subscribe(action=control, subscribe_id=subscribe_id)
        return {
            "success": bool(result.get("success")),
            "message": self._clean_text(result.get("message")) or "订阅操作完成",
            "data": self._assistant_response_data(session=session, data={
                "action": "mp_subscribe_control",
                "ok": bool(result.get("success")),
                "control": control,
                "target": target,
                "selected": selected,
                "result": result,
                "write_effect": "write",
            }),
        }

    async def _assistant_mp_transfer_history(
        self,
        *,
        session: str,
        cache_key: str,
        title: str = "",
        status: str = "all",
        limit: int = 10,
        page: int = 1,
    ) -> Dict[str, Any]:
        result = self._ensure_feishu_channel()._query_transfer_history(
            title=title,
            status=status or "all",
            limit=max(1, min(50, self._safe_int(limit, 10))),
            page=max(1, self._safe_int(page, 1)),
        )
        items = result.get("items") if isinstance(result.get("items"), list) else []
        self._save_session(cache_key, {
            "kind": "assistant_mp_transfer_history",
            "stage": "transfer_history",
            "keyword": title or status or "all",
            "items": items,
            "target_path": "",
        })
        return {
            "success": bool(result.get("success")),
            "message": self._clean_text(result.get("message")) or "整理历史查询完成",
            "data": self._assistant_response_data(session=session, data={
                "action": "mp_transfer_history",
                "ok": bool(result.get("success")),
                "source_type": "moviepilot_transfer_history",
                "status": result.get("status") or status,
                "title": title,
                "items": items,
                "total": self._safe_int(result.get("total"), len(items)),
                "page": self._safe_int(result.get("page"), page),
                "limit": self._safe_int(result.get("limit"), limit),
            }),
        }

    async def _assistant_mp_lifecycle_status(
        self,
        *,
        session: str,
        cache_key: str,
        title: str = "",
        hash_value: str = "",
        limit: int = 5,
    ) -> Dict[str, Any]:
        safe_limit = max(1, min(10, self._safe_int(limit, 5)))
        channel = self._ensure_feishu_channel()
        task_result = channel._query_download_tasks(
            status="all",
            title=title,
            hash_value=hash_value,
            limit=safe_limit,
        )
        download_result = channel._query_download_history(
            title=title,
            hash_value=hash_value,
            limit=safe_limit,
        )
        transfer_result = channel._query_transfer_history(
            title=title,
            status="all",
            limit=safe_limit,
        )
        task_items = task_result.get("items") if isinstance(task_result.get("items"), list) else []
        download_items = download_result.get("items") if isinstance(download_result.get("items"), list) else []
        transfer_items = transfer_result.get("items") if isinstance(transfer_result.get("items"), list) else []
        keyword = title or hash_value or "全部"
        lines = [f"MP 生命周期追踪：{keyword}"]
        lines.append(f"活动下载任务：{len(task_items)} 条；下载历史：{download_result.get('total', len(download_items))} 条；整理历史：{transfer_result.get('total', len(transfer_items))} 条")
        if task_items:
            lines.append("下载任务：")
            for item in task_items[:safe_limit]:
                lines.append(f"{item.get('index')}. {item.get('title')} | {item.get('progress') or '-'} | {item.get('state') or '-'} | Hash:{item.get('hash_short') or '-'}")
        if download_items:
            lines.append("下载历史：")
            for item in download_items[:safe_limit]:
                lines.append(f"{item.get('index')}. {item.get('title')} ({item.get('year') or '-'}) | {item.get('date') or '-'} | {item.get('transfer_status_text') or '-'} | Hash:{item.get('download_hash_short') or '-'}")
        if transfer_items:
            lines.append("整理/入库历史：")
            for item in transfer_items[:safe_limit]:
                lines.append(f"{item.get('index')}. {item.get('title')} ({item.get('year') or '-'}) | {item.get('status_text') or '-'} | {item.get('date') or '-'}")
        if not task_items and not download_items and not transfer_items:
            lines.append("未找到相关任务、下载历史或整理历史。")
        lines.append("说明：这是只读聚合查询，用于判断资源处于搜索后、下载中、已下载还是已落库阶段。")
        self._save_session(cache_key, {
            "kind": "assistant_mp_lifecycle_status",
            "stage": "lifecycle_status",
            "keyword": keyword,
            "items": {
                "download_tasks": task_items,
                "download_history": download_items,
                "transfer_history": transfer_items,
            },
            "target_path": "",
        })
        ok = bool(task_result.get("success")) and bool(download_result.get("success")) and bool(transfer_result.get("success"))
        return {
            "success": ok,
            "message": "\n".join(lines),
            "data": self._assistant_response_data(session=session, data={
                "action": "mp_lifecycle_status",
                "ok": ok,
                "source_type": "moviepilot_lifecycle_status",
                "title": title,
                "hash": hash_value,
                "download_tasks": {
                    "ok": bool(task_result.get("success")),
                    "total": self._safe_int(task_result.get("total"), len(task_items)),
                    "items": task_items,
                },
                "download_history": {
                    "ok": bool(download_result.get("success")),
                    "total": self._safe_int(download_result.get("total"), len(download_items)),
                    "items": download_items,
                },
                "transfer_history": {
                    "ok": bool(transfer_result.get("success")),
                    "total": self._safe_int(transfer_result.get("total"), len(transfer_items)),
                    "items": transfer_items,
                },
            }),
        }

    async def _assistant_mp_recommendations(
        self,
        *,
        source: str = "tmdb_trending",
        media_type: str = "all",
        limit: int = 20,
        session: str = "default",
        cache_key: str = "",
    ) -> Dict[str, Any]:
        try:
            from app.chain.recommend import RecommendChain
            from app.schemas.types import MediaType, media_type_to_agent
        except Exception as exc:
            return {
                "success": False,
                "message": f"MP 推荐失败：当前环境缺少推荐依赖 {exc}",
                "data": self._assistant_response_data(session=session, data={"action": "mp_recommendations", "ok": False}),
            }
        max_limit = max(1, min(50, self._safe_int(limit, 20)))
        source_name = self._clean_text(source) or "tmdb_trending"
        media_type_name = self._clean_text(media_type) or "all"
        chain = RecommendChain()
        try:
            def collect_items(raw_results: List[Dict[str, Any]], media_type_filter: str = "") -> List[Dict[str, Any]]:
                current_media_type = media_type_filter or media_type_name
                collected = []
                for raw_item in (raw_results or [])[:max_limit]:
                    if not isinstance(raw_item, dict):
                        continue
                    item_type = raw_item.get("type")
                    if current_media_type != "all":
                        enum_type = MediaType.from_agent(current_media_type)
                        agent_type = media_type_to_agent(item_type)
                        expected_types = {current_media_type}
                        if current_media_type == "movie":
                            expected_types.add("电影")
                        elif current_media_type == "tv":
                            expected_types.update({"电视剧", "剧集"})
                        if enum_type and item_type != enum_type and agent_type not in expected_types:
                            continue
                    collected.append({
                        "index": len(collected) + 1,
                        "title": raw_item.get("title"),
                        "year": raw_item.get("year"),
                        "type": media_type_to_agent(item_type),
                        "tmdb_id": raw_item.get("tmdb_id"),
                        "douban_id": raw_item.get("douban_id"),
                        "vote_average": raw_item.get("vote_average"),
                        "poster_path": raw_item.get("poster_path"),
                        "detail_link": raw_item.get("detail_link"),
                    })
                return collected

            results: List[Dict[str, Any]] = []
            if source_name == "tmdb_trending":
                results = await chain.async_tmdb_trending(page=1)
            elif source_name == "tmdb_movies":
                results = await chain.async_tmdb_movies(page=1)
            elif source_name == "tmdb_tvs":
                results = await chain.async_tmdb_tvs(page=1)
            elif source_name in {"douban_hot", "douban_movie_hot"}:
                results = await chain.async_douban_movie_hot(page=1, count=max_limit)
                if source_name == "douban_hot" and media_type_name in {"all", "tv"}:
                    results.extend(await chain.async_douban_tv_hot(page=1, count=max_limit))
            elif source_name == "douban_tv_hot":
                results = await chain.async_douban_tv_hot(page=1, count=max_limit)
            elif source_name == "douban_movie_showing":
                results = await chain.async_douban_movie_showing(page=1, count=max_limit)
            elif source_name == "douban_movie_top250":
                results = await chain.async_douban_movie_top250(page=1, count=max_limit)
            elif source_name == "douban_tv_animation":
                results = await chain.async_douban_tv_animation(page=1, count=max_limit)
            elif source_name == "bangumi_calendar":
                results = await chain.async_bangumi_calendar(page=1, count=max_limit)
            else:
                return {
                    "success": False,
                    "message": f"不支持的推荐来源：{source_name}",
                    "data": self._assistant_response_data(session=session, data={"action": "mp_recommendations", "ok": False}),
                }
            items = collect_items(results)
            fallback_source = ""
            if not items and source_name != "tmdb_trending":
                fallback_source = "tmdb_trending"
                fallback_media_type = media_type_name if media_type_name in {"movie", "tv"} else "all"
                items = collect_items(await chain.async_tmdb_trending(page=1), fallback_media_type)
            display_source = fallback_source or source_name
            lines = [f"MP 热门推荐：{display_source}，共 {len(items)} 条"]
            if fallback_source:
                lines.append(f"注：{source_name} 当前暂无结果，已自动回退 {fallback_source}。")
            for item in items[:10]:
                lines.append(f"{item.get('index')}. {item.get('title') or '-'} ({item.get('year') or '-'}) | {item.get('type') or '-'} | 评分 {item.get('vote_average') or '-'}")
            lines.append("下一步：回复“选择 1”进入 MP 原生搜索。")
            lines.append("如果想转去别的源，也可以回复“选择 1 影巢”或“选择 1 盘搜”。")
            if cache_key:
                self._save_session(cache_key, {
                    "kind": "assistant_mp_recommend",
                    "stage": "result",
                    "source": fallback_source or source_name,
                    "requested_source": source_name,
                    "media_type": media_type_name,
                    "keyword": "",
                    "items": items,
                    "target_path": "",
                })
            return {
                "success": True,
                "message": "\n".join(lines),
                "data": self._assistant_response_data(session=session, data={
                    "action": "mp_recommendations",
                    "ok": True,
                    "source_type": "moviepilot_recommendation",
                    "source": fallback_source or source_name,
                    "requested_source": source_name,
                    "fallback_source": fallback_source,
                    "media_type": media_type_name,
                    "items": items,
                }),
            }
        except Exception as exc:
            logger.error(f"MP 推荐失败：{source_name} {exc}", exc_info=True)
            return {
                "success": False,
                "message": f"MP 推荐失败：{exc}",
                "data": self._assistant_response_data(session=session, data={"action": "mp_recommendations", "ok": False}),
            }

    def _persist_workflow_plans(self) -> None:
        try:
            items = sorted(
                (dict(item) for item in (self._workflow_plans or {}).values() if isinstance(item, dict)),
                key=lambda item: self._safe_int(item.get("created_at"), 0),
                reverse=True,
            )[:self._workflow_plan_limit]
            self._workflow_plans = {
                self._clean_text(item.get("plan_id")): item
                for item in items
                if self._clean_text(item.get("plan_id"))
            }
            self.save_data(key=self._workflow_plan_store_key, value=self._workflow_plans)
        except Exception:
            pass

    def _restore_workflow_plans(self) -> None:
        try:
            restored = self.get_data(self._workflow_plan_store_key) or {}
            if isinstance(restored, dict):
                self._workflow_plans = {
                    self._clean_text(plan_id): dict(payload)
                    for plan_id, payload in restored.items()
                    if self._clean_text(plan_id) and isinstance(payload, dict)
                }
        except Exception:
            self._workflow_plans = {}

    def _save_workflow_plan(
        self,
        *,
        workflow: str,
        session: str,
        session_id: str = "",
        actions: List[Dict[str, Any]],
        execute_body: Dict[str, Any],
    ) -> Dict[str, Any]:
        plan_id = self._new_session_id("plan")
        created_at = int(time.time())
        session_name, normalized_session_id = self._normalize_assistant_session_ref(
            session=session,
            session_id=session_id,
        )
        plan = {
            "plan_id": plan_id,
            "workflow": self._clean_text(workflow),
            "session": session_name,
            "session_id": normalized_session_id,
            "actions": [dict(item or {}) for item in (actions or [])],
            "execute_body": dict(execute_body or {}),
            "created_at": created_at,
            "created_at_text": self._format_unix_time(created_at),
            "executed_at": 0,
            "executed_at_text": "",
            "executed": False,
        }
        self._workflow_plans[plan_id] = plan
        self._persist_workflow_plans()
        return dict(plan)

    def _save_assistant_pick_plan_response(
        self,
        *,
        workflow: str,
        session: str,
        session_id: str,
        actions: List[Dict[str, Any]],
        execute_body: Dict[str, Any],
        message: str,
        score_items: Optional[List[Dict[str, Any]]] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        plan = self._save_workflow_plan(
            workflow=workflow,
            session=session,
            session_id=session_id,
            actions=actions,
            execute_body=execute_body,
        )
        plan_id = self._clean_text(plan.get("plan_id"))
        template = self._assistant_action_template(
            name="execute_plan",
            description="执行刚生成的计划",
            endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/plan/execute",
            tool="agent_resource_officer_execute_plan",
            body={
                "plan_id": plan_id,
                "session": session,
                "session_id": session_id,
                "prefer_unexecuted": True,
            },
        )
        data = {
            "action": "workflow_plan",
            "ok": True,
            "plan_id": plan_id,
            "workflow": workflow,
            "dry_run": True,
            "workflow_actions": [dict(item or {}) for item in actions],
            "estimated_steps": len(actions),
            "ready_to_execute": True,
            "execute_plan_endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/plan/execute",
            "execute_plan_body": {"plan_id": plan_id},
            "plan_created_at": plan.get("created_at"),
            "plan_created_at_text": plan.get("created_at_text"),
            "next_actions": ["execute_plan"],
            "action_templates": [template],
            "write_effect": "state",
        }
        if score_items:
            data["score_summary"] = self._score_summary(score_items, limit=1)
        if extra_data:
            data.update(extra_data)
        return {
            "success": True,
            "message": f"{message}：{plan_id}\n未实际执行。回复“执行计划 {plan_id}”后才会写入。",
            "data": self._assistant_response_data(session=session, data=data),
        }

    def _load_workflow_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        plan = (self._workflow_plans or {}).get(self._clean_text(plan_id))
        return dict(plan) if isinstance(plan, dict) else None

    def _find_workflow_plan(
        self,
        *,
        plan_id: str = "",
        session: str = "",
        session_id: str = "",
        executed: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        clean_plan_id = self._clean_text(plan_id)
        if clean_plan_id:
            return self._load_workflow_plan(clean_plan_id)
        session_filter = ""
        session_id_filter = ""
        if self._clean_text(session) or self._clean_text(session_id):
            session_filter, session_id_filter = self._normalize_assistant_session_ref(
                session=session,
                session_id=session_id,
            )
        if not session_id_filter:
            return None
        plans = sorted(
            (dict(item) for item in (self._workflow_plans or {}).values() if isinstance(item, dict)),
            key=lambda item: self._safe_int(item.get("created_at"), 0),
            reverse=True,
        )
        for plan in plans:
            if self._clean_text(plan.get("session_id")) != session_id_filter:
                continue
            if executed is not None and bool(plan.get("executed")) != bool(executed):
                continue
            return dict(plan)
        return None

    def _workflow_plan_public_item(self, plan: Dict[str, Any], *, include_actions: bool = False) -> Dict[str, Any]:
        current = dict(plan or {})
        actions = current.get("actions") or []
        item = {
            "plan_id": self._clean_text(current.get("plan_id")),
            "workflow": self._clean_text(current.get("workflow")),
            "session": self._clean_text(current.get("session")),
            "session_id": self._clean_text(current.get("session_id")),
            "created_at": self._safe_int(current.get("created_at"), 0),
            "created_at_text": self._clean_text(current.get("created_at_text")),
            "executed": bool(current.get("executed")),
            "executed_at": self._safe_int(current.get("executed_at"), 0),
            "executed_at_text": self._clean_text(current.get("executed_at_text")),
            "last_success": current.get("last_success"),
            "last_message": self._clean_text(current.get("last_message")),
            "action_count": len(actions) if isinstance(actions, list) else 0,
        }
        if include_actions:
            item["actions"] = [dict(action or {}) for action in actions] if isinstance(actions, list) else []
            item["execute_body"] = dict(current.get("execute_body") or {})
        return item

    def _session_workflow_plan_public_data(self, *, session: str = "", session_id: str = "") -> Dict[str, Any]:
        pending = self._find_workflow_plan(session=session, session_id=session_id, executed=False)
        latest = pending or self._find_workflow_plan(session=session, session_id=session_id, executed=None)
        if not latest:
            return {
                "has_plan": False,
                "has_pending": False,
                "latest": None,
            }
        return {
            "has_plan": True,
            "has_pending": bool(pending),
            "latest": self._workflow_plan_public_item(latest, include_actions=False),
        }

    def _assistant_plans_public_data(
        self,
        *,
        session: str = "",
        session_id: str = "",
        executed: Optional[bool] = None,
        include_actions: bool = False,
        limit: int = 20,
    ) -> Dict[str, Any]:
        max_limit = min(max(1, self._safe_int(limit, 20)), 100)
        session_filter = ""
        session_id_filter = ""
        if self._clean_text(session) or self._clean_text(session_id):
            session_filter, session_id_filter = self._normalize_assistant_session_ref(
                session=session,
                session_id=session_id,
            )
        plans = sorted(
            (dict(item) for item in (self._workflow_plans or {}).values() if isinstance(item, dict)),
            key=lambda item: self._safe_int(item.get("created_at"), 0),
            reverse=True,
        )
        items: List[Dict[str, Any]] = []
        matching_total = 0
        for plan in plans:
            if session_id_filter and self._clean_text(plan.get("session_id")) != session_id_filter:
                continue
            if executed is not None and bool(plan.get("executed")) != bool(executed):
                continue
            matching_total += 1
            if len(items) < max_limit:
                items.append(self._workflow_plan_public_item(plan, include_actions=include_actions))
        return {
            "total": matching_total,
            "total_matching": matching_total,
            "total_all": len(self._workflow_plans or {}),
            "limit": max_limit,
            "session": session_filter,
            "session_id": session_id_filter,
            "executed": executed,
            "include_actions": bool(include_actions),
            "items": items,
        }

    def _format_assistant_plans_text(
        self,
        *,
        session: str = "",
        session_id: str = "",
        executed: Optional[bool] = None,
        include_actions: bool = False,
        limit: int = 20,
    ) -> str:
        data = self._assistant_plans_public_data(
            session=session,
            session_id=session_id,
            executed=executed,
            include_actions=include_actions,
            limit=limit,
        )
        items = data.get("items") or []
        if not items:
            return "当前没有 Agent影视助手 保存计划。"
        lines = [f"已保存计划：{len(items)} 条"]
        for index, item in enumerate(items, 1):
            status = "已执行" if item.get("executed") else "待执行"
            line = (
                f"{index}. {item.get('plan_id') or '-'} | {status} | "
                f"{item.get('workflow') or '-'} | {item.get('session') or '-'} | "
                f"{item.get('action_count') or 0}步 | {item.get('created_at_text') or '-'}"
            )
            if item.get("last_message"):
                line = f"{line} | {item.get('last_message')}"
            lines.append(line)
        lines.append("下一步：可用 agent_resource_officer_execute_plan 执行 plan_id，或用 agent_resource_officer_plans_clear 清理。")
        return "\n".join(lines)

    def _clear_workflow_plans(
        self,
        *,
        plan_id: str = "",
        session: str = "",
        session_id: str = "",
        executed: Optional[bool] = None,
        all_plans: bool = False,
        limit: int = 100,
    ) -> Dict[str, Any]:
        clean_plan_id = self._clean_text(plan_id)
        max_limit = min(max(1, self._safe_int(limit, 100)), 500)
        session_filter = ""
        session_id_filter = ""
        if self._clean_text(session) or self._clean_text(session_id):
            session_filter, session_id_filter = self._normalize_assistant_session_ref(
                session=session,
                session_id=session_id,
            )
        if not any([clean_plan_id, session_id_filter, executed is not None, all_plans]):
            return {
                "ok": False,
                "message": "请指定 plan_id、session/session_id、executed 过滤条件，或显式 all_plans=true",
                "removed": 0,
                "removed_ids": [],
            }
        removed_ids: List[str] = []
        for current_id, plan in list((self._workflow_plans or {}).items()):
            if len(removed_ids) >= max_limit:
                break
            current = dict(plan or {})
            if clean_plan_id and self._clean_text(current_id) != clean_plan_id:
                continue
            if session_id_filter and self._clean_text(current.get("session_id")) != session_id_filter:
                continue
            if executed is not None and bool(current.get("executed")) != bool(executed):
                continue
            removed_ids.append(self._clean_text(current_id))
        for current_id in removed_ids:
            self._workflow_plans.pop(current_id, None)
        if removed_ids:
            self._persist_workflow_plans()
        return {
            "ok": True,
            "message": f"已清理 {len(removed_ids)} 条计划",
            "removed": len(removed_ids),
            "removed_ids": removed_ids,
            "session": session_filter,
            "session_id": session_id_filter,
            "executed": executed,
            "all_plans": bool(all_plans),
        }

    def _record_assistant_execution(
        self,
        *,
        action: str,
        session: str = "default",
        session_id: str = "",
        success: bool = False,
        message: str = "",
        summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        session_name, normalized_session_id = self._normalize_assistant_session_ref(
            session=session,
            session_id=session_id,
        )
        entry = {
            "id": self._new_session_id("exec"),
            "time": int(time.time()),
            "time_text": self._format_unix_time(int(time.time())),
            "action": self._clean_text(action),
            "session": session_name,
            "session_id": normalized_session_id,
            "success": bool(success),
            "message_head": self._assistant_result_message_head(message),
            "summary": dict(summary or {}),
        }
        self._execution_history.append(entry)
        self._execution_history = self._execution_history[-self._execution_history_limit:]
        self._persist_execution_history()

    def _assistant_history_public_data(
        self,
        *,
        session: str = "",
        session_id: str = "",
        limit: int = 20,
    ) -> Dict[str, Any]:
        max_limit = min(max(1, self._safe_int(limit, 20)), 100)
        session_filter = ""
        session_id_filter = ""
        if self._clean_text(session) or self._clean_text(session_id):
            session_filter, session_id_filter = self._normalize_assistant_session_ref(
                session=session,
                session_id=session_id,
            )
        items: List[Dict[str, Any]] = []
        for entry in reversed(self._execution_history or []):
            current = dict(entry or {})
            if session_id_filter and self._clean_text(current.get("session_id")) != session_id_filter:
                continue
            items.append(current)
            if len(items) >= max_limit:
                break
        return {
            "total": len(self._execution_history or []),
            "limit": max_limit,
            "session": session_filter,
            "session_id": session_id_filter,
            "items": items,
        }

    def _format_assistant_history_text(
        self,
        *,
        session: str = "",
        session_id: str = "",
        limit: int = 20,
    ) -> str:
        data = self._assistant_history_public_data(session=session, session_id=session_id, limit=limit)
        items = data.get("items") or []
        if not items:
            return "当前没有 Agent影视助手 执行历史。"
        lines = [f"最近执行历史：{len(items)} 条"]
        for index, item in enumerate(items, 1):
            status = "成功" if item.get("success") else "失败"
            line = f"{index}. {item.get('time_text') or '-'} | {status} | {item.get('action') or '-'} | {item.get('session') or '-'}"
            if item.get("message_head"):
                line = f"{line} | {item.get('message_head')}"
            lines.append(line)
        return "\n".join(lines)

    def _is_session_expired(self, payload: Optional[Dict[str, Any]]) -> bool:
        session = dict(payload or {})
        updated_at = self._safe_int(session.get("updated_at"), 0)
        if updated_at <= 0:
            return False
        return (int(time.time()) - updated_at) > self._session_retention_seconds

    @staticmethod
    def _format_unix_time(value: Any) -> str:
        try:
            timestamp = int(value)
        except Exception:
            return ""
        if timestamp <= 0:
            return ""
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
        except Exception:
            return ""

    @staticmethod
    def _group_resource_preview(items: List[Dict[str, Any]], per_group: int = 6) -> List[Dict[str, Any]]:
        groups: Dict[str, List[Dict[str, Any]]] = {"115": [], "quark": [], "other": []}
        for item in items:
            pan = str(item.get("pan_type") or "").lower()
            if pan == "115":
                key = "115"
            elif pan == "quark":
                key = "quark"
            else:
                key = "other"
            if len(groups[key]) < per_group:
                groups[key].append(item)
        ordered = groups["115"] + groups["quark"]
        if not ordered:
            ordered = groups["other"]
        preview: List[Dict[str, Any]] = []
        for index, item in enumerate(ordered, 1):
            row = dict(item)
            row["pick_index"] = index
            preview.append(row)
        return preview

    def _assistant_session_id(self, session: str) -> str:
        session = self._clean_text(session) or "default"
        return f"assistant::{session}"

    def _assistant_session_name_from_id(self, session_id: str) -> str:
        clean_session_id = self._clean_text(session_id)
        if clean_session_id.startswith("assistant::"):
            return clean_session_id.split("assistant::", 1)[1] or "default"
        return clean_session_id or "default"

    def _normalize_assistant_session_ref(
        self,
        *,
        session: Any = None,
        session_id: Any = None,
        fallback: str = "default",
    ) -> Tuple[str, str]:
        clean_session_id = self._clean_text(session_id)
        if clean_session_id:
            session_name = self._assistant_session_name_from_id(clean_session_id)
            return session_name, self._assistant_session_id(session_name)
        session_name = self._clean_text(session) or fallback
        return session_name, self._assistant_session_id(session_name)

    def _p115_status_snapshot(self) -> Dict[str, Any]:
        health_ok, result, health_message = self._ensure_p115_service().health()
        return {
            "ready": health_ok,
            "message": health_message or result.get("message") or "",
            "direct_source": self._clean_text(result.get("direct_source")),
            "helper_ready": bool(result.get("helper_ready")),
            "client_type": self._p115_client_type,
            "default_target_path": self._p115_default_path,
            "cookie_mode": self._clean_text((result.get("cookie_state") or {}).get("mode")),
        }

    def _format_p115_next_actions(self, status: Optional[Dict[str, Any]] = None) -> str:
        current = dict(status or self._p115_status_snapshot())
        final_path = current.get("default_target_path") or self._p115_default_path
        if current.get("ready"):
            lines = [
                "下一步建议：",
                f"1. 直接发：链接 https://115cdn.com/s/xxxx path={final_path}",
                "2. 也可以直接贴 115 链接，不写前缀也能识别",
                "3. 搜资源可发：影巢搜索 片名",
                "4. 外部搜资源可发：盘搜搜索 片名",
                "5. 想复查登录状态可发：115状态",
            ]
        else:
            lines = [
                "下一步建议：",
                "1. 回复：115登录",
                "2. 扫码确认后回复：检查115登录",
                "3. 登录完成后可回复：115状态",
                f"4. 然后可直接发 115 链接转存到 {final_path}",
                "5. 也可以继续发：影巢搜索 片名",
            ]
        return "\n".join(lines)

    def _format_p115_transfer_failure(
        self,
        *,
        detail: str = "",
        target_path: str = "",
        title: str = "115 转存失败",
    ) -> str:
        status = self._p115_status_snapshot()
        final_path = target_path or status.get("default_target_path") or self._p115_default_path
        clean_detail = self._clean_text(detail)
        status_message = self._clean_text(status.get("message"))
        lines = [title]
        if clean_detail:
            lines.append(f"原因：{clean_detail}")
        if final_path:
            lines.append(f"目标目录：{final_path}")
        lines.append(f"当前状态：{'可用' if status.get('ready') else '待登录/待修复'}")
        if status_message and status_message.lower() not in {"success", "ok"} and status_message != clean_detail:
            lines.append(f"状态详情：{status_message}")
        if status.get("ready"):
            lines.append("建议：先回复 115状态 检查当前会话；如果还是失败，再回复 115登录 重新扫码。")
        else:
            lines.append("建议：先回复 115登录，扫码成功后再重试当前操作。")
        return "\n".join(lines)

    @staticmethod
    def _format_p115_resume_hint(title: str = "") -> str:
        clean_title = str(title or "").strip()
        prefix = f"已记住这次 115 任务（{clean_title}）。" if clean_title else "已记住这次 115 任务。"
        return f"{prefix}\n登录成功后回复：检查115登录，我会自动继续处理。"

    def _save_pending_p115_share(
        self,
        session_id: str,
        *,
        share_url: str,
        access_code: str = "",
        target_path: str = "",
        source: str = "",
        title: str = "",
        last_error: str = "",
    ) -> None:
        clean_url = self._clean_text(share_url)
        if not clean_url:
            return
        state = self._load_session(session_id) or {}
        previous = dict(state.get("pending_p115") or {})
        now = int(time.time())
        state["pending_p115"] = {
            "kind": "share_route",
            "share_url": clean_url,
            "access_code": self._clean_text(access_code),
            "target_path": target_path or self._p115_default_path,
            "source": self._clean_text(source),
            "title": self._clean_text(title),
            "created_at": self._safe_int(previous.get("created_at"), now) or now,
            "last_attempt_at": now,
            "retry_count": max(0, self._safe_int(previous.get("retry_count"), 0)),
            "last_error": self._clean_text(last_error) or self._clean_text(previous.get("last_error")),
        }
        if not state.get("kind"):
            state["kind"] = "assistant_p115_pending"
            state["stage"] = "pending_login"
        self._save_session(session_id, state)

    def _clear_pending_p115_share(self, session_id: str) -> None:
        state = self._load_session(session_id)
        if not state or "pending_p115" not in state:
            return
        state.pop("pending_p115", None)
        self._save_session(session_id, state)

    def _pending_p115_summary(self, state: Optional[Dict[str, Any]]) -> str:
        pending = dict((state or {}).get("pending_p115") or {})
        share_url = self._clean_text(pending.get("share_url"))
        if not share_url:
            return ""
        title = self._clean_text(pending.get("title")) or "未命名任务"
        target_path = self._clean_text(pending.get("target_path")) or self._p115_default_path
        source = self._clean_text(pending.get("source")) or "unknown"
        created_at = self._format_unix_time(pending.get("created_at"))
        last_attempt_at = self._format_unix_time(pending.get("last_attempt_at"))
        retry_count = max(0, self._safe_int(pending.get("retry_count"), 0))
        last_error = self._clean_text(pending.get("last_error"))
        lines = [
            "待继续的 115 任务：",
            f"资源：{title}",
            f"目录：{target_path}",
            f"来源：{source}",
        ]
        if created_at:
            lines.append(f"首次记录：{created_at}")
        if last_attempt_at:
            lines.append(f"最近尝试：{last_attempt_at}")
        if retry_count:
            lines.append(f"重试次数：{retry_count}")
        if last_error:
            lines.append(f"最近错误：{last_error}")
        lines.append("可用命令：继续115任务 / 取消115任务")
        return "\n".join(lines)

    def _pending_p115_public_data(self, state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        pending = dict((state or {}).get("pending_p115") or {})
        if not self._clean_text(pending.get("share_url")):
            return {"has_pending": False}
        return {
            "has_pending": True,
            "title": self._clean_text(pending.get("title")) or "未命名任务",
            "target_path": self._clean_text(pending.get("target_path")) or self._p115_default_path,
            "source": self._clean_text(pending.get("source")) or "unknown",
            "created_at": self._safe_int(pending.get("created_at"), 0),
            "created_at_text": self._format_unix_time(pending.get("created_at")),
            "last_attempt_at": self._safe_int(pending.get("last_attempt_at"), 0),
            "last_attempt_at_text": self._format_unix_time(pending.get("last_attempt_at")),
            "retry_count": max(0, self._safe_int(pending.get("retry_count"), 0)),
            "last_error": self._clean_text(pending.get("last_error")),
        }

    @staticmethod
    def _assistant_find_action_template(
        templates: Optional[List[Dict[str, Any]]],
        names: List[str],
    ) -> Optional[Dict[str, Any]]:
        rows = [dict(item or {}) for item in (templates or []) if isinstance(item, dict)]
        for current_name in names:
            for item in rows:
                if str(item.get("name") or "").strip() == current_name:
                    return item
        return None

    def _assistant_recovery_public_data(
        self,
        *,
        session_state: Optional[Dict[str, Any]] = None,
        action_templates: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        state = dict(session_state or {})
        templates = [dict(item or {}) for item in (action_templates or state.get("action_templates") or []) if isinstance(item, dict)]
        saved_plan = dict(state.get("saved_plan") or {})
        pending_p115 = dict(state.get("pending_p115") or {})
        has_session = bool(state.get("has_session"))
        kind = self._clean_text(state.get("kind"))
        stage = self._clean_text(state.get("stage"))
        mode = ""
        reason = ""
        template: Optional[Dict[str, Any]] = None

        if saved_plan.get("has_pending"):
            mode = "resume_saved_plan"
            reason = "当前会话存在待执行计划"
            template = self._assistant_find_action_template(templates, [
                "execute_latest_plan",
                "execute_plan",
                "execute_session_latest_plan",
            ])
        elif pending_p115.get("has_pending"):
            mode = "resume_pending_115"
            reason = "当前会话存在待继续的 115 任务"
            template = self._assistant_find_action_template(templates, [
                "resume_pending_115",
                "check_115_login",
            ])
        elif has_session and kind == "assistant_pansou":
            mode = "continue_pansou"
            reason = "当前会话停留在盘搜结果列表"
            template = self._assistant_find_action_template(templates, ["pick_pansou_result"])
        elif has_session and kind == "assistant_mp":
            mode = "continue_mp_search"
            reason = "当前会话停留在 MP 原生搜索结果列表"
            template = self._assistant_find_action_template(templates, [
                "query_mp_best_result_detail",
                "query_mp_search_result_detail",
                "pick_mp_download",
            ])
        elif has_session and kind == "assistant_mp_recommend":
            mode = "continue_mp_recommend"
            reason = "当前会话停留在 MP 热门推荐列表"
            template = self._assistant_find_action_template(templates, ["pick_recommend_mp_search"])
        elif has_session and kind == "assistant_mp_download_tasks":
            mode = "continue_mp_download_tasks"
            reason = "当前会话停留在 MP 下载任务列表"
            template = self._assistant_find_action_template(templates, [
                "query_mp_download_history",
                "pause_mp_download",
                "resume_mp_download",
                "delete_mp_download",
            ])
        elif has_session and kind == "assistant_mp_download_history":
            mode = "continue_mp_download_history"
            reason = "当前会话停留在 MP 下载历史"
            template = self._assistant_find_action_template(templates, [
                "query_mp_lifecycle_status",
                "start_mp_media_search",
            ])
        elif has_session and kind == "assistant_mp_downloaders":
            mode = "continue_mp_downloaders"
            reason = "当前会话停留在 MP 下载器状态"
            template = self._assistant_find_action_template(templates, [
                "query_mp_sites",
                "start_mp_media_search",
            ])
        elif has_session and kind == "assistant_mp_sites":
            mode = "continue_mp_sites"
            reason = "当前会话停留在 MP 站点状态"
            template = self._assistant_find_action_template(templates, [
                "query_mp_downloaders",
                "start_mp_media_search",
            ])
        elif has_session and kind == "assistant_mp_subscribes":
            mode = "continue_mp_subscribes"
            reason = "当前会话停留在 MP 订阅列表"
            template = self._assistant_find_action_template(templates, [
                "start_mp_subscribe",
                "search_mp_subscribe",
                "start_mp_media_search",
            ])
        elif has_session and kind == "assistant_mp_lifecycle_status":
            mode = "continue_mp_lifecycle_status"
            reason = "当前会话停留在 MP 生命周期追踪"
            template = self._assistant_find_action_template(templates, [
                "query_mp_download_history",
                "start_mp_media_search",
            ])
        elif has_session and kind == "assistant_hdhive" and stage == "candidate":
            mode = "continue_hdhive_candidate"
            reason = "当前会话停留在影巢候选列表"
            template = self._assistant_find_action_template(templates, ["pick_hdhive_candidate"])
        elif has_session and kind == "assistant_hdhive" and stage == "resource":
            mode = "continue_hdhive_resource"
            reason = "当前会话停留在影巢资源列表"
            template = self._assistant_find_action_template(templates, ["pick_hdhive_resource"])
        elif has_session and kind == "assistant_p115_login":
            mode = "continue_115_login"
            reason = "当前会话停留在 115 登录检查阶段"
            template = self._assistant_find_action_template(templates, ["check_115_login", "show_115_status"])
        elif self._assistant_find_action_template(templates, ["preferences_save"]):
            mode = "onboard_preferences"
            reason = "智能体片源偏好未初始化，建议先询问并保存用户偏好"
            template = self._assistant_find_action_template(templates, ["preferences_save"])
        else:
            mode = "start_new"
            reason = "当前没有待恢复的执行状态，可直接开始新任务"
            template = self._assistant_find_action_template(templates, [
                "start_pansou_search",
                "start_hdhive_search",
                "start_115_login",
            ])

        can_resume = mode != "start_new" and bool(template)
        return {
            "mode": mode,
            "reason": reason,
            "can_resume": can_resume,
            "recommended_action": self._clean_text((template or {}).get("name")),
            "recommended_tool": self._clean_text((template or {}).get("tool")),
            "action_template": template or None,
            "alternatives": [
                self._clean_text(item.get("name"))
                for item in templates[:6]
                if self._clean_text(item.get("name"))
            ],
        }

    def _assistant_session_public_data(self, session: str = "default") -> Dict[str, Any]:
        session_name = self._clean_text(session) or "default"
        session_id = self._assistant_session_id(session_name)
        saved_plan = self._session_workflow_plan_public_data(session=session_name, session_id=session_id)
        state = self._load_session(session_id) or {}
        if not state:
            payload = {
                "has_session": False,
                "session": session_name,
                "session_id": session_id,
                "saved_plan": saved_plan,
                "suggested_actions": ["execute_plan.session", "smart_entry"] if saved_plan.get("has_pending") else ["smart_entry"],
            }
            payload["action_templates"] = self._assistant_action_templates(payload)
            payload["recovery"] = self._assistant_recovery_public_data(session_state=payload)
            return payload

        kind = self._clean_text(state.get("kind"))
        stage = self._clean_text(state.get("stage"))
        target_path = self._clean_text(state.get("target_path"))
        payload: Dict[str, Any] = {
            "has_session": True,
            "session": session_name,
            "session_id": session_id,
            "kind": kind,
            "stage": stage,
            "updated_at": self._safe_int(state.get("updated_at"), 0),
            "updated_at_text": self._format_unix_time(state.get("updated_at")),
            "target_path": target_path,
            "keyword": self._clean_text(state.get("keyword")),
            "media_type": self._clean_text(state.get("media_type")),
            "year": self._clean_text(state.get("year")),
            "pending_p115": self._pending_p115_public_data(state),
            "saved_plan": saved_plan,
            "suggested_actions": [],
        }

        if kind == "assistant_pansou":
            items = state.get("items") or []
            payload.update({
                "result_count": len(items),
                "items_preview": [
                    {
                        "index": self._safe_int(item.get("index"), idx + 1),
                        "channel": self._clean_text(item.get("channel")),
                        "title": self._clean_text(item.get("note")),
                        "source": self._clean_text(item.get("source")),
                    }
                    for idx, item in enumerate(items[:6])
                    if isinstance(item, dict)
                ],
                "score_summary": self._score_summary(items, limit=5),
                "suggested_actions": ["smart_pick.choice", "session_clear"],
            })
        elif kind == "assistant_mp":
            items = state.get("items") or []
            payload.update({
                "result_count": len(items),
                "items_preview": [
                    {
                        "index": self._safe_int(item.get("index"), idx + 1),
                        "title": self._clean_text(((item.get("torrent_info") or {}).get("title")) or item.get("title")),
                        "site": self._clean_text((item.get("torrent_info") or {}).get("site_name")),
                        "seeders": (item.get("torrent_info") or {}).get("seeders"),
                        "volume_factor": self._clean_text((item.get("torrent_info") or {}).get("volume_factor")),
                        "score": (item.get("score") or {}).get("score") if isinstance(item.get("score"), dict) else None,
                        "score_level": (item.get("score") or {}).get("score_level") if isinstance(item.get("score"), dict) else "",
                        "recommended_action": (item.get("score") or {}).get("recommended_action") if isinstance(item.get("score"), dict) else "",
                        "risk_reasons": (item.get("score") or {}).get("risk_reasons", [])[:2] if isinstance(item.get("score"), dict) else [],
                    }
                    for idx, item in enumerate(items[:8])
                    if isinstance(item, dict)
                ],
                "score_summary": self._score_summary(items, limit=5),
                "suggested_actions": ["mp_download.choice", "mp_subscribe.keyword", "session_clear"],
            })
        elif kind == "assistant_mp_download_tasks":
            items = state.get("items") or []
            payload.update({
                "result_count": len(items),
                "items_preview": [
                    {
                        "index": self._safe_int(item.get("index"), idx + 1),
                        "title": self._clean_text(item.get("title")),
                        "hash_short": self._clean_text(item.get("hash_short")),
                        "downloader": self._clean_text(item.get("downloader")),
                        "progress": self._clean_text(item.get("progress")),
                        "state": self._clean_text(item.get("state")),
                    }
                    for idx, item in enumerate(items[:8])
                    if isinstance(item, dict)
                ],
                "suggested_actions": (
                    ["mp_download_control.pause", "mp_download_control.resume", "mp_download_control.delete", "session_clear"]
                    if items else
                    ["mp_media_search", "mp_download_history", "session_clear"]
                ),
            })
        elif kind == "assistant_mp_download_history":
            items = state.get("items") or []
            payload.update({
                "result_count": len(items),
                "items_preview": [
                    {
                        "index": self._safe_int(item.get("index"), idx + 1),
                        "title": self._clean_text(item.get("title")),
                        "year": self._clean_text(item.get("year")),
                        "date": self._clean_text(item.get("date")),
                        "transfer_status_text": self._clean_text(item.get("transfer_status_text")),
                        "download_hash_short": self._clean_text(item.get("download_hash_short")),
                    }
                    for idx, item in enumerate(items[:8])
                    if isinstance(item, dict)
                ],
                "suggested_actions": ["mp_lifecycle_status", "mp_media_search", "session_clear"],
            })
        elif kind == "assistant_mp_downloaders":
            items = state.get("items") or []
            payload.update({
                "enabled_count": self._safe_int(state.get("enabled_count"), 0),
                "result_count": len(items),
                "items_preview": [
                    {
                        "name": self._clean_text(item.get("name")),
                        "type": self._clean_text(item.get("type")),
                        "enabled": bool(item.get("enabled")),
                        "default": bool(item.get("default")),
                    }
                    for item in items[:8]
                    if isinstance(item, dict)
                ],
                "suggested_actions": ["mp_sites", "mp_media_search", "session_clear"],
            })
        elif kind == "assistant_mp_sites":
            items = state.get("items") or []
            payload.update({
                "status": self._clean_text(state.get("status")),
                "result_count": len(items),
                "items_preview": [
                    {
                        "index": self._safe_int(item.get("index"), idx + 1),
                        "name": self._clean_text(item.get("name")),
                        "domain": self._clean_text(item.get("domain")),
                        "enabled": bool(item.get("enabled")),
                        "has_cookie": bool(item.get("has_cookie")),
                        "priority": item.get("priority"),
                    }
                    for idx, item in enumerate(items[:8])
                    if isinstance(item, dict)
                ],
                "suggested_actions": ["mp_downloaders", "mp_media_search", "session_clear"],
            })
        elif kind == "assistant_mp_subscribes":
            items = state.get("items") or []
            payload.update({
                "result_count": len(items),
                "items_preview": [
                    {
                        "index": self._safe_int(item.get("index"), idx + 1),
                        "id": self._safe_int(item.get("id"), 0),
                        "title": self._clean_text(item.get("name")),
                        "year": self._clean_text(item.get("year")),
                        "state": self._clean_text(item.get("state")),
                        "lack_episode": item.get("lack_episode"),
                    }
                    for idx, item in enumerate(items[:8])
                    if isinstance(item, dict)
                ],
                "suggested_actions": (
                    ["mp_subscribe_control.search", "mp_subscribe_control.pause", "mp_subscribe_control.resume", "mp_subscribe_control.delete", "session_clear"]
                    if items else
                    ["mp_subscribe.keyword", "mp_media_search", "session_clear"]
                ),
            })
        elif kind == "assistant_mp_lifecycle_status":
            result_groups = state.get("items") if isinstance(state.get("items"), dict) else {}
            task_items = result_groups.get("download_tasks") if isinstance(result_groups.get("download_tasks"), list) else []
            download_items = result_groups.get("download_history") if isinstance(result_groups.get("download_history"), list) else []
            transfer_items = result_groups.get("transfer_history") if isinstance(result_groups.get("transfer_history"), list) else []
            payload.update({
                "download_task_count": len(task_items),
                "download_history_count": len(download_items),
                "transfer_history_count": len(transfer_items),
                "items_preview": [
                    {
                        "kind": "download_task",
                        "title": self._clean_text(item.get("title")),
                        "progress": self._clean_text(item.get("progress")),
                        "state": self._clean_text(item.get("state")),
                    }
                    for item in task_items[:3]
                    if isinstance(item, dict)
                ] + [
                    {
                        "kind": "download_history",
                        "title": self._clean_text(item.get("title")),
                        "date": self._clean_text(item.get("date")),
                        "transfer_status_text": self._clean_text(item.get("transfer_status_text")),
                    }
                    for item in download_items[:3]
                    if isinstance(item, dict)
                ] + [
                    {
                        "kind": "transfer_history",
                        "title": self._clean_text(item.get("title")),
                        "date": self._clean_text(item.get("date")),
                        "status_text": self._clean_text(item.get("status_text")),
                    }
                    for item in transfer_items[:3]
                    if isinstance(item, dict)
                ],
                "suggested_actions": ["mp_media_search", "mp_download_history", "session_clear"],
            })
        elif kind == "assistant_mp_recommend":
            items = state.get("items") or []
            payload.update({
                "source": self._clean_text(state.get("source")),
                "result_count": len(items),
                "items_preview": [
                    {
                        "index": self._safe_int(item.get("index"), idx + 1),
                        "title": self._clean_text(item.get("title")),
                        "year": self._clean_text(item.get("year")),
                        "type": self._clean_text(item.get("type")),
                        "tmdb_id": self._clean_text(item.get("tmdb_id")),
                        "douban_id": self._clean_text(item.get("douban_id")),
                        "vote_average": item.get("vote_average"),
                    }
                    for idx, item in enumerate(items[:10])
                    if isinstance(item, dict)
                ],
                "suggested_actions": [
                    "smart_pick.choice",
                    "smart_pick.choice mode=hdhive",
                    "smart_pick.choice mode=pansou",
                    "session_clear",
                ],
            })
        elif kind == "assistant_hdhive":
            if stage == "candidate":
                candidates = state.get("candidates") or []
                current_page = max(1, self._safe_int(state.get("page"), 1))
                page_size = max(1, self._safe_int(state.get("page_size"), self._hdhive_candidate_page_size))
                total_pages = max(1, (len(candidates) + page_size - 1) // page_size) if candidates else 1
                start = (current_page - 1) * page_size
                end = start + page_size
                payload.update({
                    "page": current_page,
                    "page_size": page_size,
                    "total_candidates": len(candidates),
                    "total_pages": total_pages,
                    "candidates_preview": [
                        {
                            "index": start + idx + 1,
                            "tmdb_id": self._clean_text(item.get("tmdb_id")),
                            "title": self._clean_text(item.get("title")),
                            "year": self._clean_text(item.get("year")),
                            "media_type": self._clean_text(item.get("media_type")),
                            "actors": item.get("actors") or [],
                        }
                        for idx, item in enumerate(candidates[start:end])
                        if isinstance(item, dict)
                    ],
                    "suggested_actions": ["smart_pick.choice", "smart_pick.action=详情", "smart_pick.action=下一页", "session_clear"],
                })
            elif stage == "resource":
                resources = state.get("resources") or []
                selected_candidate = dict(state.get("selected_candidate") or {})
                payload.update({
                    "selected_candidate": {
                        "tmdb_id": self._clean_text(selected_candidate.get("tmdb_id")),
                        "title": self._clean_text(selected_candidate.get("title")),
                        "year": self._clean_text(selected_candidate.get("year")),
                        "media_type": self._clean_text(selected_candidate.get("media_type")),
                        "actors": selected_candidate.get("actors") or [],
                    },
                    "total_resources": len(resources),
                    "resource_count_115": len([x for x in resources if str((x or {}).get("pan_type") or "").lower() == "115"]),
                    "resource_count_quark": len([x for x in resources if str((x or {}).get("pan_type") or "").lower() == "quark"]),
                    "resources_preview": [
                        {
                            "index": self._safe_int(item.get("pick_index"), idx + 1),
                            "provider": self._clean_text(item.get("pan_type")),
                            "title": self._clean_text(item.get("title") or item.get("matched_title")),
                            "points": item.get("unlock_points"),
                            "points_text": self._resource_points_text(item),
                            "quality": self._clean_text(self._list_text(item.get("video_resolution")) or item.get("quality")),
                            "source": self._clean_text(self._list_text(item.get("source"))),
                            "size": self._clean_text(item.get("share_size") or item.get("size")),
                            "episodes": self._resource_episode_text(item),
                            "subtitle": self._resource_subtitle_text(item),
                            "remark": self._resource_remark_text(item),
                            "score": (item.get("score") or {}).get("score") if isinstance(item.get("score"), dict) else None,
                            "score_level": (item.get("score") or {}).get("score_level") if isinstance(item.get("score"), dict) else "",
                            "recommended_action": (item.get("score") or {}).get("recommended_action") if isinstance(item.get("score"), dict) else "",
                            "risk_reasons": (item.get("score") or {}).get("risk_reasons", [])[:2] if isinstance(item.get("score"), dict) else [],
                        }
                        for idx, item in enumerate(resources[:8])
                        if isinstance(item, dict)
                    ],
                    "score_summary": self._score_summary(resources, limit=5),
                    "suggested_actions": ["smart_pick.choice", "session_clear"],
                })
        elif kind == "assistant_p115_login":
            payload.update({
                "client_type": self._clean_text(state.get("client_type")) or self._p115_client_type,
                "has_qrcode_session": bool(self._clean_text(state.get("uid")) and self._clean_text(state.get("time")) and self._clean_text(state.get("sign"))),
                "suggested_actions": ["smart_entry.text=检查115登录", "p115_status", "session_clear"],
            })
        else:
            payload["suggested_actions"] = ["smart_entry", "session_clear"]
        if saved_plan.get("has_pending"):
            payload["suggested_actions"] = ["execute_plan.session", *list(payload.get("suggested_actions") or [])]
        payload["action_templates"] = self._assistant_action_templates(payload)
        payload["recovery"] = self._assistant_recovery_public_data(session_state=payload)
        return payload

    def _assistant_session_brief_public_data(self, session_id: str, state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        payload = dict(state or {})
        name = str(session_id or "")
        session_name = name.split("assistant::", 1)[1] if name.startswith("assistant::") else name or "default"
        saved_plan = self._session_workflow_plan_public_data(session=session_name, session_id=name)
        result: Dict[str, Any] = {
            "session": session_name,
            "session_id": name or self._assistant_session_id(session_name),
            "kind": self._clean_text(payload.get("kind")),
            "stage": self._clean_text(payload.get("stage")),
            "updated_at": self._safe_int(payload.get("updated_at"), 0),
            "updated_at_text": self._format_unix_time(payload.get("updated_at")),
            "keyword": self._clean_text(payload.get("keyword")),
            "target_path": self._clean_text(payload.get("target_path")),
            "has_pending_p115": bool(self._clean_text(((payload.get("pending_p115") or {}).get("share_url")))),
            "has_saved_plan": bool(saved_plan.get("has_plan")),
            "has_pending_plan": bool(saved_plan.get("has_pending")),
            "saved_plan": saved_plan.get("latest"),
        }
        if result["kind"] == "assistant_pansou":
            result["result_count"] = len(payload.get("items") or [])
        elif result["kind"] == "assistant_mp_recommend":
            result["result_count"] = len(payload.get("items") or [])
            result["source"] = self._clean_text(payload.get("source"))
        elif result["kind"] == "assistant_hdhive":
            if result["stage"] == "candidate":
                candidates = payload.get("candidates") or []
                page_size = max(1, self._safe_int(payload.get("page_size"), self._hdhive_candidate_page_size))
                current_page = max(1, self._safe_int(payload.get("page"), 1))
                total_pages = max(1, (len(candidates) + page_size - 1) // page_size) if candidates else 1
                result["total_candidates"] = len(candidates)
                result["page"] = current_page
                result["total_pages"] = total_pages
            elif result["stage"] == "resource":
                selected = dict(payload.get("selected_candidate") or {})
                resources = payload.get("resources") or []
                result["selected_title"] = self._clean_text(selected.get("title"))
                result["selected_year"] = self._clean_text(selected.get("year"))
                result["total_resources"] = len(resources)
        elif result["kind"] == "assistant_p115_login":
            result["client_type"] = self._clean_text(payload.get("client_type")) or self._p115_client_type
        result["recovery"] = self._assistant_recovery_public_data(
            session_state={
                **result,
                "pending_p115": self._pending_p115_public_data(payload),
                "saved_plan": saved_plan,
            },
            action_templates=[
                self._assistant_action_template(
                    name="execute_session_latest_plan",
                    description="按 session_id 执行该会话最近一条待执行计划",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/plan/execute",
                    tool="agent_resource_officer_execute_plan",
                    body={"session_id": result.get("session_id"), "prefer_unexecuted": True},
                ),
                self._assistant_action_template(
                    name="inspect_session",
                    description="查看某个会话的详细状态",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/session",
                    tool="agent_resource_officer_session_state",
                    body={"session_id": result.get("session_id")},
                ),
            ],
        )
        return result

    def _assistant_plan_only_session_brief_public_data(self, session_id: str) -> Dict[str, Any]:
        session_name = self._assistant_session_name_from_id(session_id)
        saved_plan = self._session_workflow_plan_public_data(session=session_name, session_id=session_id)
        latest = dict(saved_plan.get("latest") or {})
        return {
            "session": session_name,
            "session_id": self._assistant_session_id(session_name),
            "kind": "assistant_workflow_plan",
            "stage": "planned",
            "updated_at": self._safe_int(latest.get("created_at"), 0),
            "updated_at_text": self._clean_text(latest.get("created_at_text")),
            "keyword": "",
            "target_path": "",
            "has_pending_p115": False,
            "has_saved_plan": bool(saved_plan.get("has_plan")),
            "has_pending_plan": bool(saved_plan.get("has_pending")),
            "saved_plan": latest or None,
            "recovery": {
                "mode": "resume_saved_plan" if saved_plan.get("has_pending") else "inspect_plan_only_session",
                "reason": "当前会话只有 dry_run 计划，尚未生成交互会话缓存",
                "can_resume": bool(saved_plan.get("has_pending")),
                "recommended_action": "execute_session_latest_plan" if saved_plan.get("has_pending") else "inspect_session",
                "recommended_tool": "agent_resource_officer_execute_plan" if saved_plan.get("has_pending") else "agent_resource_officer_session_state",
                "action_template": self._assistant_action_template(
                    name="execute_session_latest_plan" if saved_plan.get("has_pending") else "inspect_session",
                    description="按 session_id 执行该会话最近一条待执行计划" if saved_plan.get("has_pending") else "查看某个会话的详细状态",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/plan/execute" if saved_plan.get("has_pending") else "/api/v1/plugin/AgentResourceOfficer/assistant/session",
                    tool="agent_resource_officer_execute_plan" if saved_plan.get("has_pending") else "agent_resource_officer_session_state",
                    body={"session_id": self._assistant_session_id(session_name), "prefer_unexecuted": True} if saved_plan.get("has_pending") else {"session_id": self._assistant_session_id(session_name)},
                ),
                "alternatives": ["execute_session_latest_plan", "inspect_session"],
            },
        }

    @staticmethod
    def _assistant_action_template(
        *,
        name: str,
        description: str,
        endpoint: str,
        body: Dict[str, Any],
        method: str = "POST",
        tool: str = "",
    ) -> Dict[str, Any]:
        body_payload = dict(body or {})
        compact_paths = [
            "/assistant/action",
            "/assistant/actions",
            "/assistant/workflow",
            "/assistant/plan/execute",
            "/assistant/recover",
            "/assistant/route",
            "/assistant/pick",
            "/assistant/session",
            "/assistant/sessions",
            "/assistant/history",
            "/assistant/plans",
            "/assistant/readiness",
            "/assistant/capabilities",
        ]
        if "compact" not in body_payload and any(path in endpoint for path in compact_paths):
            body_payload["compact"] = True
        action_body: Dict[str, Any] = {"name": name}
        for key in [
            "session",
            "session_id",
            "choice",
            "path",
            "keyword",
            "media_type",
            "year",
            "url",
            "access_code",
            "client_type",
            "status",
            "hash",
            "target",
            "control",
            "downloader",
            "delete_files",
            "kind",
            "has_pending_p115",
            "stale_only",
            "all_sessions",
            "limit",
            "page",
            "plan_id",
            "prefer_unexecuted",
            "preferences",
            "compact",
            "mode",
            "source",
        ]:
            if key in body_payload:
                action_body[key] = body_payload.get(key)
        return {
            "name": name,
            "description": description,
            "endpoint": endpoint,
            "method": method,
            "tool": tool,
            "body": body_payload,
            "action_endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/action",
            "action_tool": "agent_resource_officer_execute_action",
            "action_body": action_body,
        }

    @staticmethod
    def _assistant_compact_action_templates(
        primary: Optional[Dict[str, Any]] = None,
        templates: Optional[List[Dict[str, Any]]] = None,
        *,
        limit: int = 6,
    ) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for item in [primary, *(templates or [])]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            result.append(dict(item))
            if len(result) >= max(1, limit):
                break
        return result

    def _assistant_action_templates(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        session_name = self._clean_text(data.get("session")) or "default"
        session_id = self._clean_text(data.get("session_id")) or self._assistant_session_id(session_name)
        base_route = {
            "session": session_name,
            "session_id": session_id,
        }
        base_pick = {
            "session": session_name,
            "session_id": session_id,
        }
        base_state = {
            "session": session_name,
            "session_id": session_id,
        }
        templates: List[Dict[str, Any]] = []
        preference_status = self._assistant_preferences_status_brief(session=session_name)
        preference_template = self._assistant_action_template(
            name="preferences_save",
            description="保存智能体片源偏好；首次接入建议先询问用户后再保存",
            endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/preferences",
            tool="agent_resource_officer_preferences",
            body={**base_state, "preferences": self._assistant_default_preferences_template()},
        )

        if not data.get("has_session"):
            templates = []
            if preference_status.get("needs_onboarding"):
                templates.append(preference_template)
            saved_plan = dict(data.get("saved_plan") or {})
            if saved_plan.get("has_pending"):
                templates.append(
                    self._assistant_action_template(
                        name="execute_latest_plan",
                        description="执行当前会话最近一条待执行计划",
                        endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/plan/execute",
                        tool="agent_resource_officer_execute_plan",
                        body={**base_state, "prefer_unexecuted": True},
                    )
                )
            templates.extend([
                self._assistant_action_template(
                    name="start_pansou_search",
                    description="发起新的盘搜搜索",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/route",
                    tool="agent_resource_officer_smart_entry",
                    body={**base_route, "mode": "pansou", "keyword": "<关键词>"},
                ),
                self._assistant_action_template(
                    name="start_hdhive_search",
                    description="发起新的影巢候选搜索",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/route",
                    tool="agent_resource_officer_smart_entry",
                    body={**base_route, "mode": "hdhive", "keyword": "<关键词>", "media_type": "auto"},
                ),
                self._assistant_action_template(
                    name="start_mp_media_search",
                    description="发起新的 MP 原生搜索，返回 PT 候选和评分摘要",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/route",
                    tool="agent_resource_officer_smart_entry",
                    body={**base_route, "mode": "mp", "keyword": "<关键词>"},
                ),
                self._assistant_action_template(
                    name="query_mp_media_detail",
                    description="使用 MoviePilot 原生识别确认媒体信息和 TMDB/Douban/IMDB ID",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_route, "name": "query_mp_media_detail", "keyword": "<关键词>", "media_type": "auto"},
                ),
                self._assistant_action_template(
                    name="start_mp_recommendations",
                    description="查看 MP 原生热门推荐，例如 TMDB、豆瓣或 Bangumi",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_route, "name": "start_mp_recommendations", "source": "tmdb_trending", "media_type": "all"},
                ),
                self._assistant_action_template(
                    name="query_mp_download_tasks",
                    description="查看 MP 下载任务状态",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_route, "name": "query_mp_download_tasks", "status": "downloading"},
                ),
                self._assistant_action_template(
                    name="query_mp_download_history",
                    description="查看 MP 下载历史，并关联整理/入库状态",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_route, "name": "query_mp_download_history", "limit": 10},
                ),
                self._assistant_action_template(
                    name="query_mp_lifecycle_status",
                    description="聚合查看 MP 下载任务、下载历史和整理/入库历史",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_route, "name": "query_mp_lifecycle_status", "keyword": "<关键词>", "limit": 5},
                ),
                self._assistant_action_template(
                    name="query_mp_downloaders",
                    description="查看 MP 下载器配置摘要",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_route, "name": "query_mp_downloaders"},
                ),
                self._assistant_action_template(
                    name="query_mp_sites",
                    description="查看 MP 站点启用状态和 Cookie 是否存在，不返回 Cookie 明文",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_route, "name": "query_mp_sites", "status": "active", "limit": 30},
                ),
                self._assistant_action_template(
                    name="query_mp_subscribes",
                    description="查看 MP 订阅列表",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_route, "name": "query_mp_subscribes", "status": "all", "limit": 20},
                ),
                self._assistant_action_template(
                    name="query_mp_transfer_history",
                    description="查看 MP 最近整理/入库历史，用于判断下载后是否已落库",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_route, "name": "query_mp_transfer_history", "status": "all", "limit": 10},
                ),
                self._assistant_action_template(
                    name="start_115_login",
                    description="发起新的 115 扫码登录",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/route",
                    tool="agent_resource_officer_smart_entry",
                    body={**base_route, "action": "p115_qrcode_start"},
                ),
            ])
            return templates

        kind = self._clean_text(data.get("kind"))
        stage = self._clean_text(data.get("stage"))
        pending = dict(data.get("pending_p115") or {})
        saved_plan = dict(data.get("saved_plan") or {})
        target_path = self._clean_text(data.get("target_path"))

        if saved_plan.get("has_pending"):
            templates.append(
                self._assistant_action_template(
                    name="execute_latest_plan",
                    description="执行当前会话最近一条待执行计划",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/plan/execute",
                    tool="agent_resource_officer_execute_plan",
                    body={**base_state, "prefer_unexecuted": True},
                )
            )
        if preference_status.get("needs_onboarding"):
            templates.append(preference_template)

        templates.append(
            self._assistant_action_template(
                name="inspect_session_state",
                description="重新获取当前会话详细状态",
                endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/session",
                tool="agent_resource_officer_session_state",
                body=base_state,
            )
        )

        if kind == "assistant_pansou":
            templates.extend([
                self._assistant_action_template(
                    name="pick_pansou_result",
                    description="按编号选择盘搜结果继续转存",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/pick",
                    tool="agent_resource_officer_smart_pick",
                    body={**base_pick, "choice": "<1-N>", "path": target_path or self._p115_default_path},
                ),
                self._assistant_action_template(
                    name="plan_pansou_result",
                    description="按编号生成盘搜转存计划，不立即写入",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/pick",
                    tool="agent_resource_officer_smart_pick",
                    body={**base_pick, "choice": "<1-N>", "action": "plan", "path": target_path or self._p115_default_path},
                ),
            ])
        elif kind == "assistant_mp":
            templates.extend([
                self._assistant_action_template(
                    name="query_mp_best_result_detail",
                    description="查看当前 MP 搜索结果里评分最高的 PT 候选详情",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_state, "name": "query_mp_best_result_detail"},
                ),
                self._assistant_action_template(
                    name="pick_mp_best_download",
                    description="按当前评分最高的 MP 搜索结果生成下载计划；不会静默下载",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_state, "name": "pick_mp_best_download"},
                ),
                self._assistant_action_template(
                    name="query_mp_search_result_detail",
                    description="按编号查看 MP 原生搜索结果详情和 PT 评分理由",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_state, "name": "query_mp_search_result_detail", "choice": "<1-N>"},
                ),
                self._assistant_action_template(
                    name="pick_mp_download",
                    description="按编号为 MP 原生搜索结果生成下载计划；不会立即下载",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_state, "name": "pick_mp_download", "choice": "<1-N>"},
                ),
                self._assistant_action_template(
                    name="start_mp_subscribe",
                    description="按当前关键词生成 MP 订阅计划",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_state, "name": "start_mp_subscribe", "keyword": data.get("keyword") or "<关键词>"},
                ),
                self._assistant_action_template(
                    name="start_mp_subscribe_search",
                    description="按当前关键词生成“订阅并搜索”计划",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_state, "name": "start_mp_subscribe_search", "keyword": data.get("keyword") or "<关键词>"},
                ),
            ])
        elif kind == "assistant_mp_download_tasks":
            has_items = bool(data.get("items")) or self._safe_int(data.get("result_count"), 0) > 0
            if has_items:
                templates.extend([
                    self._assistant_action_template(
                        name="pause_mp_download",
                        description="按编号暂停下载任务；写入动作建议先 dry_run 生成计划",
                        endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                        tool="agent_resource_officer_execute_action",
                        body={**base_state, "name": "mp_download_control", "control": "pause", "target": "<1-N>"},
                    ),
                    self._assistant_action_template(
                        name="resume_mp_download",
                        description="按编号恢复下载任务；写入动作建议先 dry_run 生成计划",
                        endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                        tool="agent_resource_officer_execute_action",
                        body={**base_state, "name": "mp_download_control", "control": "resume", "target": "<1-N>"},
                    ),
                    self._assistant_action_template(
                        name="delete_mp_download",
                        description="按编号删除下载任务；默认不删除文件",
                        endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                        tool="agent_resource_officer_execute_action",
                        body={**base_state, "name": "mp_download_control", "control": "delete", "target": "<1-N>", "delete_files": False},
                    ),
                ])
            else:
                templates.extend([
                    self._assistant_action_template(
                        name="query_mp_download_history",
                        description="当前没有下载中任务，改查下载历史和整理状态",
                        endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                        tool="agent_resource_officer_execute_action",
                        body={**base_state, "name": "query_mp_download_history", "limit": 10},
                    ),
                    self._assistant_action_template(
                        name="start_mp_media_search",
                        description="重新发起 MP 原生搜索",
                        endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/route",
                        tool="agent_resource_officer_smart_entry",
                        body={**base_route, "mode": "mp", "keyword": "<关键词>"},
                    ),
                ])
        elif kind == "assistant_mp_download_history":
            templates.extend([
                self._assistant_action_template(
                    name="query_mp_lifecycle_status",
                    description="按关键词聚合查看下载任务、下载历史和整理/入库状态",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_state, "name": "query_mp_lifecycle_status", "keyword": data.get("keyword") or "<关键词>", "limit": 5},
                ),
                self._assistant_action_template(
                    name="start_mp_media_search",
                    description="按关键词重新发起 MP 原生搜索",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/route",
                    tool="agent_resource_officer_smart_entry",
                    body={**base_route, "mode": "mp", "keyword": data.get("keyword") or "<关键词>"},
                ),
            ])
        elif kind == "assistant_mp_downloaders":
            templates.extend([
                self._assistant_action_template(
                    name="query_mp_sites",
                    description="查看 PT 站点启用状态和 Cookie 是否存在",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_state, "name": "query_mp_sites", "status": "active", "limit": 30},
                ),
                self._assistant_action_template(
                    name="start_mp_media_search",
                    description="发起新的 MP 原生搜索，返回 PT 候选和评分摘要",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/route",
                    tool="agent_resource_officer_smart_entry",
                    body={**base_route, "mode": "mp", "keyword": "<关键词>"},
                ),
            ])
        elif kind == "assistant_mp_sites":
            templates.extend([
                self._assistant_action_template(
                    name="query_mp_downloaders",
                    description="查看 MP 下载器配置摘要",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_state, "name": "query_mp_downloaders"},
                ),
                self._assistant_action_template(
                    name="start_mp_media_search",
                    description="发起新的 MP 原生搜索，返回 PT 候选和评分摘要",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/route",
                    tool="agent_resource_officer_smart_entry",
                    body={**base_route, "mode": "mp", "keyword": "<关键词>"},
                ),
            ])
        elif kind == "assistant_mp_subscribes":
            has_items = bool(data.get("items")) or self._safe_int(data.get("result_count"), 0) > 0
            if has_items:
                templates.extend([
                    self._assistant_action_template(
                        name="search_mp_subscribe",
                        description="按编号触发订阅搜索；写入动作建议先 dry_run 生成计划",
                        endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                        tool="agent_resource_officer_execute_action",
                        body={**base_state, "name": "mp_subscribe_control", "control": "search", "target": "<1-N>"},
                    ),
                    self._assistant_action_template(
                        name="pause_mp_subscribe",
                        description="按编号暂停订阅；写入动作建议先 dry_run 生成计划",
                        endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                        tool="agent_resource_officer_execute_action",
                        body={**base_state, "name": "mp_subscribe_control", "control": "pause", "target": "<1-N>"},
                    ),
                    self._assistant_action_template(
                        name="resume_mp_subscribe",
                        description="按编号恢复订阅；写入动作建议先 dry_run 生成计划",
                        endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                        tool="agent_resource_officer_execute_action",
                        body={**base_state, "name": "mp_subscribe_control", "control": "resume", "target": "<1-N>"},
                    ),
                    self._assistant_action_template(
                        name="delete_mp_subscribe",
                        description="按编号删除订阅",
                        endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                        tool="agent_resource_officer_execute_action",
                        body={**base_state, "name": "mp_subscribe_control", "control": "delete", "target": "<1-N>"},
                    ),
                ])
            else:
                templates.extend([
                    self._assistant_action_template(
                        name="start_mp_subscribe",
                        description="按关键词生成新的 MP 订阅计划",
                        endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                        tool="agent_resource_officer_execute_action",
                        body={**base_state, "name": "start_mp_subscribe", "keyword": data.get("keyword") or "<关键词>"},
                    ),
                    self._assistant_action_template(
                        name="start_mp_media_search",
                        description="按关键词重新发起 MP 原生搜索",
                        endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/route",
                        tool="agent_resource_officer_smart_entry",
                        body={**base_route, "mode": "mp", "keyword": data.get("keyword") or "<关键词>"},
                    ),
                ])
        elif kind == "assistant_mp_lifecycle_status":
            templates.extend([
                self._assistant_action_template(
                    name="query_mp_download_history",
                    description="继续查看 MP 下载历史",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
                    tool="agent_resource_officer_execute_action",
                    body={**base_state, "name": "query_mp_download_history", "title": data.get("keyword") or "", "limit": 10},
                ),
                self._assistant_action_template(
                    name="start_mp_media_search",
                    description="按当前关键词重新发起 MP 原生搜索",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/route",
                    tool="agent_resource_officer_smart_entry",
                    body={**base_route, "mode": "mp", "keyword": data.get("keyword") or "<关键词>"},
                ),
            ])
        elif kind == "assistant_mp_recommend":
            templates.extend([
                self._assistant_action_template(
                    name="pick_recommend_mp_search",
                    description="按编号选择推荐条目并进入 MP 原生搜索",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/pick",
                    tool="agent_resource_officer_smart_pick",
                    body={**base_pick, "choice": "<1-N>", "mode": "mp"},
                ),
                self._assistant_action_template(
                    name="pick_recommend_hdhive_search",
                    description="按编号选择推荐条目并进入影巢候选搜索",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/pick",
                    tool="agent_resource_officer_smart_pick",
                    body={**base_pick, "choice": "<1-N>", "mode": "hdhive"},
                ),
                self._assistant_action_template(
                    name="pick_recommend_pansou_search",
                    description="按编号选择推荐条目并进入盘搜搜索",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/pick",
                    tool="agent_resource_officer_smart_pick",
                    body={**base_pick, "choice": "<1-N>", "mode": "pansou"},
                ),
            ])
        elif kind == "assistant_hdhive" and stage == "candidate":
            templates.extend([
                self._assistant_action_template(
                    name="pick_hdhive_candidate",
                    description="按编号选择影巢候选影片进入资源列表",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/pick",
                    tool="agent_resource_officer_smart_pick",
                    body={**base_pick, "choice": "<1-N>", "path": target_path or self._hdhive_default_path},
                ),
                self._assistant_action_template(
                    name="candidate_detail",
                    description="补充当前候选页详情，例如主演",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/pick",
                    tool="agent_resource_officer_smart_pick",
                    body={**base_pick, "action": "detail"},
                ),
                self._assistant_action_template(
                    name="candidate_next_page",
                    description="翻到候选下一页",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/pick",
                    tool="agent_resource_officer_smart_pick",
                    body={**base_pick, "action": "next_page"},
                ),
            ])
        elif kind == "assistant_hdhive" and stage == "resource":
            templates.extend([
                self._assistant_action_template(
                    name="pick_hdhive_resource",
                    description="按编号选择影巢资源，解锁并路由到对应网盘",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/pick",
                    tool="agent_resource_officer_smart_pick",
                    body={**base_pick, "choice": "<1-N>", "path": target_path or self._hdhive_default_path},
                ),
                self._assistant_action_template(
                    name="plan_hdhive_resource",
                    description="按编号生成影巢解锁/转存计划，不立即扣分或写入",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/pick",
                    tool="agent_resource_officer_smart_pick",
                    body={**base_pick, "choice": "<1-N>", "action": "plan", "path": target_path or self._hdhive_default_path},
                ),
            ])
        elif kind == "assistant_p115_login":
            templates.extend([
                self._assistant_action_template(
                    name="check_115_login",
                    description="检查 115 扫码是否已确认，并在成功后自动继续待任务",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/route",
                    tool="agent_resource_officer_smart_entry",
                    body={**base_route, "action": "p115_qrcode_check"},
                ),
                self._assistant_action_template(
                    name="show_115_status",
                    description="查看当前 115 状态",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/route",
                    tool="agent_resource_officer_smart_entry",
                    body={**base_route, "action": "p115_status"},
                ),
            ])

        if pending.get("has_pending"):
            templates.extend([
                self._assistant_action_template(
                    name="resume_pending_115",
                    description="继续当前会话里待处理的 115 任务",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/route",
                    tool="agent_resource_officer_smart_entry",
                    body={**base_route, "action": "p115_resume"},
                ),
                self._assistant_action_template(
                    name="cancel_pending_115",
                    description="取消当前会话里待处理的 115 任务",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/route",
                    tool="agent_resource_officer_smart_entry",
                    body={**base_route, "action": "p115_cancel"},
                ),
            ])

        templates.append(
            self._assistant_action_template(
                name="clear_current_session",
                description="清理当前会话缓存",
                endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/session/clear",
                tool="agent_resource_officer_session_clear",
                body=base_state,
            )
        )
        return templates

    def _assistant_sessions_public_data(
        self,
        *,
        kind: str = "",
        has_pending_p115: Optional[bool] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        kind_filter = self._clean_text(kind)
        max_limit = min(max(1, self._safe_int(limit, 20)), 100)
        items_by_session: Dict[str, Dict[str, Any]] = {}
        for session_id, payload in (self._session_cache or {}).items():
            if not str(session_id).startswith("assistant::"):
                continue
            session = dict(payload or {})
            if self._is_session_expired(session):
                continue
            brief = self._assistant_session_brief_public_data(str(session_id), session)
            items_by_session[brief.get("session_id") or str(session_id)] = brief
        for plan in (self._workflow_plans or {}).values():
            current = dict(plan or {})
            plan_session_id = self._clean_text(current.get("session_id"))
            if not plan_session_id:
                continue
            brief = items_by_session.get(plan_session_id)
            if brief:
                if not brief.get("has_saved_plan"):
                    refreshed = self._assistant_session_brief_public_data(plan_session_id, self._load_session(plan_session_id) or {})
                    items_by_session[plan_session_id] = refreshed
                continue
            items_by_session[plan_session_id] = self._assistant_plan_only_session_brief_public_data(plan_session_id)
        items: List[Dict[str, Any]] = []
        for brief in items_by_session.values():
            if kind_filter and brief.get("kind") != kind_filter:
                continue
            if has_pending_p115 is not None and bool(brief.get("has_pending_p115")) != bool(has_pending_p115):
                continue
            items.append(brief)
        items.sort(key=lambda item: self._safe_int(item.get("updated_at"), 0), reverse=True)
        return {
            "total": len(items),
            "limit": max_limit,
            "items": items[:max_limit],
            "filters": {
                "kind": kind_filter,
                "has_pending_p115": has_pending_p115,
            },
            "action_templates": [
                self._assistant_action_template(
                    name="execute_session_latest_plan",
                    description="按 session_id 执行该会话最近一条待执行计划",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/plan/execute",
                    tool="agent_resource_officer_execute_plan",
                    body={"session_id": "<assistant::session_id>", "prefer_unexecuted": True},
                ),
                self._assistant_action_template(
                    name="inspect_session",
                    description="查看某个会话的详细状态",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/session",
                    tool="agent_resource_officer_session_state",
                    body={"session_id": "<assistant::session_id>"},
                ),
                self._assistant_action_template(
                    name="clear_session_by_id",
                    description="按 session_id 清理单个会话",
                    endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/sessions/clear",
                    tool="agent_resource_officer_sessions_clear",
                    body={"session_id": "<assistant::session_id>"},
                ),
            ],
            "recovery": (
                dict((items[:max_limit][0] or {}).get("recovery") or {})
                if (items[:max_limit] and isinstance(items[:max_limit][0], dict))
                else {
                    "mode": "start_new",
                    "reason": "当前没有活跃会话，可直接开始新任务",
                    "can_resume": False,
                    "recommended_action": "",
                    "recommended_tool": "",
                    "action_template": None,
                    "alternatives": [],
                }
            ),
        }

    def _assistant_recover_public_data(
        self,
        *,
        session: str = "",
        session_id: str = "",
        limit: int = 20,
    ) -> Dict[str, Any]:
        requested_session = self._clean_text(session)
        requested_session_id = self._clean_text(session_id)
        max_limit = min(max(1, self._safe_int(limit, 20)), 100)
        if requested_session or requested_session_id:
            session_name, normalized_session_id = self._normalize_assistant_session_ref(
                session=requested_session or "default",
                session_id=requested_session_id,
            )
            state = self._assistant_session_public_data(session=session_name)
            return {
                "scope": "session",
                "session": session_name,
                "session_id": normalized_session_id or state.get("session_id") or self._assistant_session_id(session_name),
                "selected_session": {
                    "session": session_name,
                    "session_id": normalized_session_id or state.get("session_id") or self._assistant_session_id(session_name),
                    "kind": state.get("kind"),
                    "stage": state.get("stage"),
                    "keyword": state.get("keyword"),
                    "has_pending_plan": bool((state.get("saved_plan") or {}).get("has_pending")),
                    "has_pending_p115": bool((state.get("pending_p115") or {}).get("has_pending")),
                },
                "session_state": state,
                "sessions": None,
                "recovery": dict(state.get("recovery") or self._assistant_recovery_public_data(session_state=state)),
            }

        sessions = self._assistant_sessions_public_data(limit=max_limit)
        items = [dict(item or {}) for item in (sessions.get("items") or []) if isinstance(item, dict)]
        selected: Optional[Dict[str, Any]] = None

        current_recovery = dict(sessions.get("recovery") or {})
        template_body = dict(((current_recovery.get("action_template") or {}).get("body") or {}))
        preferred_session_id = self._clean_text(template_body.get("session_id"))
        if preferred_session_id:
            selected = next((item for item in items if self._clean_text(item.get("session_id")) == preferred_session_id), None)
        if not selected:
            selected = next((item for item in items if bool((item.get("recovery") or {}).get("can_resume"))), None)
        if not selected:
            selected = next((item for item in items if item.get("has_pending_plan") or item.get("has_pending_p115")), None)
        if not selected and items:
            selected = items[0]

        if selected:
            session_name = self._clean_text(selected.get("session")) or "default"
            selected_session_id = self._clean_text(selected.get("session_id")) or self._assistant_session_id(session_name)
            state = self._assistant_session_public_data(session=session_name)
            recovery = dict(state.get("recovery") or selected.get("recovery") or current_recovery)
            selected = {**selected, "recovery": recovery}
            return {
                "scope": "global",
                "session": session_name,
                "session_id": selected_session_id,
                "selected_session": selected,
                "session_state": state,
                "sessions": sessions,
                "recovery": recovery,
            }

        state = self._assistant_session_public_data(session="default")
        return {
            "scope": "global",
            "session": "default",
            "session_id": state.get("session_id") or self._assistant_session_id("default"),
            "selected_session": None,
            "session_state": state,
            "sessions": sessions,
            "recovery": dict(state.get("recovery") or current_recovery),
        }

    def _format_assistant_recover_text(self, data: Dict[str, Any]) -> str:
        recovery = dict((data or {}).get("recovery") or {})
        selected = dict((data or {}).get("selected_session") or {})
        lines = [
            "Agent影视助手 恢复入口",
            f"范围：{(data or {}).get('scope') or 'session'}",
            f"会话：{(data or {}).get('session') or 'default'}",
            f"模式：{recovery.get('mode') or 'unknown'}",
            f"原因：{recovery.get('reason') or '-'}",
            f"可恢复：{'是' if recovery.get('can_resume') else '否'}",
        ]
        if recovery.get("recommended_action"):
            lines.append(f"推荐动作：{recovery.get('recommended_action')}")
        if recovery.get("recommended_tool"):
            lines.append(f"推荐 Tool：{recovery.get('recommended_tool')}")
        if selected.get("kind") or selected.get("keyword"):
            detail = " / ".join(
                str(item)
                for item in [
                    selected.get("kind"),
                    selected.get("stage"),
                    selected.get("keyword"),
                ]
                if item
            )
            lines.append(f"当前状态：{detail}")
        if recovery.get("can_resume"):
            lines.append("如需直接恢复，可调用 assistant/recover 并传 execute=true。")
        return "\n".join(lines)

    def _assistant_recover_response_data(self, data: Dict[str, Any], compact: bool = False) -> Dict[str, Any]:
        if not compact:
            return self._assistant_response_data(session=(data or {}).get("session") or "default", data=data)

        payload = dict(data or {})
        session_state = dict(payload.pop("session_state", {}) or {})
        payload.pop("sessions", None)
        recovery = dict(payload.get("recovery") or {})
        selected = payload.get("selected_session")
        if isinstance(selected, dict) and selected.get("recovery"):
            selected = dict(selected)
            selected.pop("recovery", None)
            payload["selected_session"] = selected

        session_name = self._clean_text(payload.get("session") or session_state.get("session")) or "default"
        session_id = self._clean_text(payload.get("session_id") or session_state.get("session_id")) or self._assistant_session_id(session_name)
        action_template = recovery.get("action_template") if isinstance(recovery.get("action_template"), dict) else None
        session_templates = session_state.get("action_templates") if isinstance(session_state.get("action_templates"), list) else []
        payload.update({
            "protocol_version": "assistant.v1",
            "compact": True,
            "session": session_name,
            "session_id": session_id,
            "next_actions": [
                item for item in [
                    recovery.get("recommended_action"),
                    *(session_state.get("suggested_actions") or []),
                ]
                if item
            ][:6],
            "action_templates": self._assistant_compact_action_templates(action_template, session_templates),
        })
        return payload

    def _assistant_session_compact_data(self, session_state: Dict[str, Any]) -> Dict[str, Any]:
        state = dict(session_state or {})
        recovery = dict(state.get("recovery") or {})
        saved_plan = dict(state.get("saved_plan") or {})
        pending_p115 = dict(state.get("pending_p115") or {})
        payload: Dict[str, Any] = {
            "protocol_version": "assistant.v1",
            "action": "session_state",
            "ok": True,
            "compact": True,
            "has_session": bool(state.get("has_session")),
            "session": self._clean_text(state.get("session")) or "default",
            "session_id": self._clean_text(state.get("session_id")),
            "kind": self._clean_text(state.get("kind")),
            "stage": self._clean_text(state.get("stage")),
            "keyword": self._clean_text(state.get("keyword")),
            "target_path": self._clean_text(state.get("target_path")),
            "updated_at": state.get("updated_at"),
            "updated_at_text": state.get("updated_at_text"),
            "saved_plan": {
                "has_pending": bool(saved_plan.get("has_pending")),
                "plan_id": self._clean_text((saved_plan.get("latest") or {}).get("plan_id") or saved_plan.get("plan_id")),
            },
            "pending_p115": {
                "has_pending": bool(pending_p115.get("has_pending")),
                "target_path": self._clean_text(pending_p115.get("target_path")),
                "retry_count": pending_p115.get("retry_count"),
            },
            "recovery": recovery,
            "next_actions": state.get("suggested_actions") or [],
            "action_templates": self._assistant_compact_action_templates(
                recovery.get("action_template") if isinstance(recovery.get("action_template"), dict) else None,
                state.get("action_templates") if isinstance(state.get("action_templates"), list) else [],
            ),
        }
        for key in [
            "result_count",
            "total_candidates",
            "page",
            "total_pages",
            "selected_candidate",
            "total_resources",
            "resource_count_115",
            "resource_count_quark",
            "score_summary",
            "client_type",
        ]:
            if key in state:
                payload[key] = state.get(key)
        return payload

    def _assistant_sessions_compact_data(self, sessions_data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(sessions_data or {})
        items: List[Dict[str, Any]] = []
        for item in data.get("items") or []:
            if not isinstance(item, dict):
                continue
            recovery = dict(item.get("recovery") or {})
            items.append({
                "session": self._clean_text(item.get("session")),
                "session_id": self._clean_text(item.get("session_id")),
                "kind": self._clean_text(item.get("kind")),
                "stage": self._clean_text(item.get("stage")),
                "keyword": self._clean_text(item.get("keyword")),
                "target_path": self._clean_text(item.get("target_path")),
                "updated_at": item.get("updated_at"),
                "updated_at_text": item.get("updated_at_text"),
                "has_pending_plan": bool(item.get("has_pending_plan")),
                "has_pending_p115": bool(item.get("has_pending_p115")),
                "recovery_mode": self._clean_text(recovery.get("mode")),
                "recommended_action": self._clean_text(recovery.get("recommended_action")),
            })
        recovery = dict(data.get("recovery") or {})
        return {
            "protocol_version": "assistant.v1",
            "action": "sessions",
            "ok": True,
            "compact": True,
            "total": data.get("total") or 0,
            "limit": data.get("limit") or len(items),
            "filters": data.get("filters") or {},
            "items": items,
            "recovery": recovery,
            "next_actions": [recovery.get("recommended_action")] if recovery.get("recommended_action") else [],
            "action_templates": [recovery.get("action_template")] if isinstance(recovery.get("action_template"), dict) else [],
        }

    def _assistant_history_compact_data(self, history_data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(history_data or {})
        items: List[Dict[str, Any]] = []
        for item in data.get("items") or []:
            if not isinstance(item, dict):
                continue
            summary = dict(item.get("summary") or {})
            steps = summary.get("steps")
            items.append({
                "time_text": self._clean_text(item.get("time_text")),
                "success": bool(item.get("success")),
                "action": self._clean_text(item.get("action")),
                "workflow": self._clean_text(summary.get("workflow")),
                "session": self._clean_text(item.get("session")),
                "session_id": self._clean_text(item.get("session_id")),
                "message_head": self._clean_text(item.get("message_head")),
                "steps": steps if isinstance(steps, int) else None,
            })
        return {
            "protocol_version": "assistant.v1",
            "action": "history",
            "ok": True,
            "compact": True,
            "total": data.get("total") or 0,
            "limit": data.get("limit") or len(items),
            "session": self._clean_text(data.get("session")),
            "session_id": self._clean_text(data.get("session_id")),
            "items": items,
        }

    def _assistant_plans_compact_data(self, plans_data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(plans_data or {})
        items: List[Dict[str, Any]] = []
        first_pending: Optional[Dict[str, Any]] = None
        for item in data.get("items") or []:
            if not isinstance(item, dict):
                continue
            plan_id = self._clean_text(item.get("plan_id"))
            executed = bool(item.get("executed"))
            compact_item = {
                "plan_id": plan_id,
                "workflow": self._clean_text(item.get("workflow")),
                "session": self._clean_text(item.get("session")),
                "session_id": self._clean_text(item.get("session_id")),
                "executed": executed,
                "action_count": self._safe_int(item.get("action_count"), 0),
                "created_at_text": self._clean_text(item.get("created_at_text")),
                "last_success": item.get("last_success"),
                "last_message": self._clean_text(item.get("last_message")),
            }
            items.append(compact_item)
            if not executed and first_pending is None and plan_id:
                first_pending = compact_item
        templates: List[Dict[str, Any]] = []
        if first_pending:
            templates.append(self._assistant_action_template(
                name="execute_plan",
                description="执行待处理计划",
                endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/plan/execute",
                tool="agent_resource_officer_execute_plan",
                body={
                    "plan_id": first_pending.get("plan_id"),
                    "session": first_pending.get("session"),
                    "session_id": first_pending.get("session_id"),
                    "prefer_unexecuted": True,
                },
            ))
        return {
            "protocol_version": "assistant.v1",
            "action": "plans",
            "ok": True,
            "compact": True,
            "total": data.get("total_matching") if data.get("total_matching") is not None else (data.get("total") or 0),
            "total_matching": data.get("total_matching") if data.get("total_matching") is not None else (data.get("total") or 0),
            "total_all": data.get("total_all") if data.get("total_all") is not None else (data.get("total") or 0),
            "limit": data.get("limit") or len(items),
            "session": self._clean_text(data.get("session")),
            "session_id": self._clean_text(data.get("session_id")),
            "executed": data.get("executed"),
            "include_actions": False,
            "items": items,
            "next_actions": ["execute_plan"] if first_pending else [],
            "action_templates": templates,
        }

    def _assistant_compact_action_results(self, rows: Any) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            results.append({
                "index": item.get("index"),
                "name": self._clean_text(item.get("name")),
                "success": bool(item.get("success")),
                "action": self._clean_text(item.get("action")),
                "ok": bool(item.get("ok")) if "ok" in item else bool(item.get("success")),
                "message_head": self._clean_text(item.get("message_head")),
                "session": self._clean_text(item.get("session")),
                "session_id": self._clean_text(item.get("session_id")),
                "kind": self._clean_text(item.get("kind")),
                "stage": self._clean_text(item.get("stage")),
                "has_pending_p115": bool(item.get("has_pending_p115")),
                "next_actions": item.get("next_actions") or [],
            })
        return results

    def _assistant_actions_compact_data(self, actions_data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(actions_data or {})
        session_state = dict(data.get("session_state") or {})
        results = self._assistant_compact_action_results(data.get("results"))
        payload = {
            "protocol_version": "assistant.v1",
            "action": self._clean_text(data.get("action")) or "execute_actions",
            "ok": bool(data.get("ok")),
            "compact": True,
            "session": self._clean_text(data.get("session") or session_state.get("session")) or "default",
            "session_id": self._clean_text(data.get("session_id") or session_state.get("session_id")),
            "executed_count": data.get("executed_count") or len(results),
            "requested_count": data.get("requested_count") or len(results),
            "stopped_on_error": bool(data.get("stopped_on_error")),
            "halted_at": data.get("halted_at") or 0,
            "results": results,
            "next_actions": data.get("next_actions") or session_state.get("suggested_actions") or [],
            "action_templates": data.get("action_templates") or [],
        }
        if isinstance(data.get("preference_status"), dict):
            payload["preference_status"] = data.get("preference_status")
            payload["needs_onboarding"] = bool(data["preference_status"].get("needs_onboarding"))
        if isinstance(data.get("score_summary"), dict):
            payload["score_summary"] = data.get("score_summary")
        return payload

    def _assistant_plan_execute_compact_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        response = dict(result or {})
        data = dict(response.get("data") or {})
        session_state = dict(data.get("session_state") or {})
        results = self._assistant_compact_action_results(data.get("results"))
        success_count = len([item for item in results if item.get("success")])
        last_result = results[-1] if results else {}
        payload = {
            "protocol_version": "assistant.v1",
            "action": "execute_plan",
            "ok": bool(data.get("ok")) if "ok" in data else bool(response.get("success")),
            "compact": True,
            "write_effect": data.get("write_effect") or "write",
            "error_code": self._clean_text(data.get("error_code")) or ("" if response.get("success") else "assistant_error"),
            "session": self._clean_text(data.get("session") or session_state.get("session")) or "default",
            "session_id": self._clean_text(data.get("session_id") or session_state.get("session_id")),
            "message_head": self._assistant_result_message_head(response.get("message")),
            "plan_id": self._clean_text(data.get("plan_id")),
            "workflow": self._clean_text(data.get("workflow")),
            "plan_auto_selected": bool(data.get("plan_auto_selected")),
            "plan_created_at": data.get("plan_created_at"),
            "plan_created_at_text": data.get("plan_created_at_text"),
            "plan_executed_at": data.get("plan_executed_at"),
            "plan_executed_at_text": data.get("plan_executed_at_text"),
            "executed_count": data.get("executed_count") or len(results),
            "requested_count": data.get("requested_count") or len(results),
            "stopped_on_error": bool(data.get("stopped_on_error")),
            "halted_at": data.get("halted_at") or 0,
            "results": results,
            "result_summary": {
                "success_count": success_count,
                "failure_count": max(len(results) - success_count, 0),
                "last_action": self._clean_text(last_result.get("action")),
                "last_message_head": self._clean_text(last_result.get("message_head")),
            },
            "next_actions": data.get("next_actions") or session_state.get("suggested_actions") or [],
            "action_templates": data.get("action_templates") or [],
        }
        if isinstance(data.get("preference_status"), dict):
            payload["preference_status"] = data.get("preference_status")
            payload["needs_onboarding"] = bool(data["preference_status"].get("needs_onboarding"))
        if isinstance(data.get("score_summary"), dict):
            payload["score_summary"] = data.get("score_summary")
        if isinstance(data.get("recovery"), dict):
            payload["recovery"] = data.get("recovery")
        return {
            "success": bool(response.get("success")),
            "message": response.get("message") or "",
            "data": payload,
        }

    def _assistant_single_action_compact_response(self, name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        response = dict(result or {})
        data = dict(response.get("data") or {})
        session_state = dict(data.get("session_state") or {})
        payload = {
            "protocol_version": "assistant.v1",
            "action": self._clean_text(data.get("action")) or self._clean_text(name) or "execute_action",
            "ok": bool(data.get("ok")) if "ok" in data else bool(response.get("success")),
            "compact": True,
            "name": self._clean_text(name),
            "session": self._clean_text(data.get("session") or session_state.get("session")) or "default",
            "session_id": self._clean_text(data.get("session_id") or session_state.get("session_id")),
            "message_head": self._assistant_result_message_head(response.get("message")),
            "kind": self._clean_text(session_state.get("kind")),
            "stage": self._clean_text(session_state.get("stage")),
            "next_actions": data.get("next_actions") or session_state.get("suggested_actions") or [],
            "action_templates": data.get("action_templates") or [],
        }
        for key in ["plan_id", "workflow", "plan_auto_selected", "has_session", "has_pending"]:
            if key in data:
                payload[key] = data.get(key)
        if isinstance(data.get("preference_status"), dict):
            payload["preference_status"] = data.get("preference_status")
            payload["needs_onboarding"] = bool(data["preference_status"].get("needs_onboarding"))
        if isinstance(data.get("score_summary"), dict):
            payload["score_summary"] = data.get("score_summary")
        pending_p115 = session_state.get("pending_p115") if isinstance(session_state.get("pending_p115"), dict) else {}
        if pending_p115:
            payload["has_pending_p115"] = bool(pending_p115.get("has_pending"))
        return {
            "success": bool(response.get("success")),
            "message": response.get("message") or "",
            "data": payload,
        }

    def _assistant_interaction_compact_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        response = dict(result or {})
        data = dict(response.get("data") or {})
        session_state = dict(data.get("session_state") or {})
        payload = {
            "protocol_version": "assistant.v1",
            "action": self._clean_text(data.get("action")) or "assistant_interaction",
            "ok": bool(data.get("ok")) if "ok" in data else bool(response.get("success")),
            "compact": True,
            "write_effect": data.get("write_effect") or self._assistant_write_effect_for_action(self._clean_text(data.get("action"))),
            "error_code": self._clean_text(data.get("error_code")) or ("" if response.get("success") else "assistant_error"),
            "session": self._clean_text(data.get("session") or session_state.get("session")) or "default",
            "session_id": self._clean_text(data.get("session_id") or session_state.get("session_id")),
            "message_head": self._assistant_result_message_head(response.get("message")),
            "kind": self._clean_text(session_state.get("kind")),
            "stage": self._clean_text(session_state.get("stage")),
            "keyword": self._clean_text(session_state.get("keyword")),
            "target_path": self._clean_text(session_state.get("target_path")),
            "next_actions": data.get("next_actions") or session_state.get("suggested_actions") or [],
            "action_templates": data.get("action_templates") or [],
        }
        if isinstance(data.get("score_summary"), dict):
            payload["score_summary"] = data.get("score_summary")
        for key in ["provider", "page", "total_pages", "selected_candidate", "selected_resource", "plan_id", "workflow"]:
            if key in data:
                payload[key] = data.get(key)
        if isinstance(data.get("preference_status"), dict):
            payload["preference_status"] = data.get("preference_status")
            payload["needs_onboarding"] = bool(data["preference_status"].get("needs_onboarding"))
        for key in ["items", "candidates", "resources"]:
            if isinstance(data.get(key), list):
                payload[f"{key}_count"] = len(data.get(key) or [])
        pending_p115 = session_state.get("pending_p115") if isinstance(session_state.get("pending_p115"), dict) else {}
        if pending_p115:
            payload["has_pending_p115"] = bool(pending_p115.get("has_pending"))
        return {
            "success": bool(response.get("success")),
            "message": response.get("message") or "",
            "data": payload,
        }

    def _assistant_workflow_plan_compact_data(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(plan_data or {})
        session_state = dict(data.get("session_state") or {})
        plan_id = self._clean_text(data.get("plan_id"))
        template = self._assistant_action_template(
            name="execute_plan",
            description="执行刚生成的 dry_run 计划",
            endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/plan/execute",
            tool="agent_resource_officer_execute_plan",
            body={"plan_id": plan_id},
        ) if plan_id else None
        return {
            "protocol_version": "assistant.v1",
            "action": "workflow_plan",
            "ok": bool(data.get("ok")),
            "compact": True,
            "session": self._clean_text(data.get("session") or session_state.get("session")) or "default",
            "session_id": self._clean_text(data.get("session_id") or session_state.get("session_id")),
            "plan_id": plan_id,
            "workflow": self._clean_text(data.get("workflow")),
            "dry_run": True,
            "estimated_steps": data.get("estimated_steps") or 0,
            "ready_to_execute": bool(data.get("ready_to_execute")),
            "execute_plan_endpoint": data.get("execute_plan_endpoint"),
            "execute_plan_body": data.get("execute_plan_body") or {"plan_id": plan_id},
            "plan_created_at": data.get("plan_created_at"),
            "plan_created_at_text": data.get("plan_created_at_text"),
            "preference_status": data.get("preference_status") or {},
            "needs_onboarding": bool((data.get("preference_status") or {}).get("needs_onboarding")),
            "score_summary": data.get("score_summary") or {},
            "next_actions": ["execute_plan"] if plan_id else [],
            "action_templates": [template] if template else [],
        }

    def _format_assistant_sessions_text(
        self,
        *,
        kind: str = "",
        has_pending_p115: Optional[bool] = None,
        limit: int = 20,
    ) -> str:
        data = self._assistant_sessions_public_data(
            kind=kind,
            has_pending_p115=has_pending_p115,
            limit=limit,
        )
        items = data.get("items") or []
        if not items:
            return "当前没有活跃的 Agent影视助手 会话。"
        lines = [
            f"当前活跃会话：{data.get('total') or 0} 个",
            "可直接用 assistant/session 查看单个会话详情，也可按 session_id 直接恢复最近计划。",
        ]
        for idx, item in enumerate(items, 1):
            line = f"{idx}. {item.get('session')} | {item.get('kind') or '-'} | {item.get('stage') or '-'}"
            if item.get("keyword"):
                line = f"{line} | {item.get('keyword')}"
            lines.append(line)
            detail_parts: List[str] = []
            if item.get("target_path"):
                detail_parts.append(f"目录:{item.get('target_path')}")
            if item.get("updated_at_text"):
                detail_parts.append(f"更新:{item.get('updated_at_text')}")
            if item.get("has_pending_p115"):
                detail_parts.append("含待继续115任务")
            if item.get("has_pending_plan"):
                detail_parts.append("含待执行计划")
            if item.get("selected_title"):
                detail_parts.append(f"已选:{item.get('selected_title')}")
            if item.get("result_count"):
                detail_parts.append(f"结果:{item.get('result_count')}")
            if item.get("total_candidates"):
                detail_parts.append(f"候选:{item.get('total_candidates')}")
            if item.get("total_resources"):
                detail_parts.append(f"资源:{item.get('total_resources')}")
            if detail_parts:
                lines.append("   " + " | ".join(detail_parts))
        return "\n".join(lines)

    def _clear_assistant_sessions(
        self,
        *,
        session: str = "",
        session_id: str = "",
        kind: str = "",
        has_pending_p115: Optional[bool] = None,
        stale_only: bool = False,
        all_sessions: bool = False,
        limit: int = 100,
    ) -> Dict[str, Any]:
        max_limit = min(max(1, self._safe_int(limit, 100)), 500)
        cleared_ids: List[str] = []
        if self._clean_text(session_id) or self._clean_text(session):
            _, cache_key = self._normalize_assistant_session_ref(session=session, session_id=session_id)
            if cache_key in self._session_cache:
                self._session_cache.pop(cache_key, None)
                cleared_ids.append(cache_key)
            self._persist_relevant_sessions()
            return {
                "cleared_count": len(cleared_ids),
                "cleared_session_ids": cleared_ids,
                "limit": max_limit,
            }

        kind_filter = self._clean_text(kind)
        for current_session_id, payload in list((self._session_cache or {}).items()):
            if len(cleared_ids) >= max_limit:
                break
            if not str(current_session_id).startswith("assistant::"):
                continue
            current = dict(payload or {})
            expired = self._is_session_expired(current)
            if stale_only and not expired:
                continue
            if not stale_only and expired:
                continue
            if not all_sessions:
                if kind_filter and self._clean_text(current.get("kind")) != kind_filter:
                    continue
                if has_pending_p115 is not None:
                    has_pending = bool(self._clean_text(((current.get("pending_p115") or {}).get("share_url"))))
                    if has_pending != bool(has_pending_p115):
                        continue
                if not kind_filter and has_pending_p115 is None and not stale_only:
                    continue
            self._session_cache.pop(current_session_id, None)
            cleared_ids.append(str(current_session_id))

        self._persist_relevant_sessions()
        return {
            "cleared_count": len(cleared_ids),
            "cleared_session_ids": cleared_ids,
            "limit": max_limit,
        }

    def _format_assistant_session_summary(self, session: str = "default") -> str:
        data = self._assistant_session_public_data(session=session)
        if not data.get("has_session"):
            return "\n".join([
                "当前没有活跃会话。",
                "可直接调用 smart_entry 发起新操作，例如：",
                "1. text=盘搜搜索 大君夫人",
                "2. text=影巢搜索 蜘蛛侠",
                "3. text=链接 https://115cdn.com/s/xxxx path=/待整理",
            ])

        lines = [
            "当前会话状态",
            f"会话：{data.get('session')}",
            f"类型：{data.get('kind') or '-'}",
            f"阶段：{data.get('stage') or '-'}",
        ]
        if data.get("keyword"):
            lines.append(f"关键词：{data.get('keyword')}")
        if data.get("target_path"):
            lines.append(f"目录：{data.get('target_path')}")
        if data.get("updated_at_text"):
            lines.append(f"最近更新：{data.get('updated_at_text')}")
        if data.get("kind") == "assistant_pansou":
            lines.append(f"结果数：{data.get('result_count') or 0}")
            lines.append("下一步：调用 smart_pick，传入 choice=编号")
        elif data.get("kind") == "assistant_hdhive" and data.get("stage") == "candidate":
            lines.append(f"候选数：{data.get('total_candidates') or 0}")
            lines.append(f"页码：{data.get('page')}/{data.get('total_pages')}")
            lines.append("下一步：smart_pick 可传 choice=编号，或 action=详情 / 下一页")
        elif data.get("kind") == "assistant_hdhive" and data.get("stage") == "resource":
            selected = data.get("selected_candidate") or {}
            if selected.get("title"):
                lines.append(f"已选影片：{selected.get('title')} ({selected.get('year') or '-'})")
            lines.append(f"资源数：{data.get('total_resources') or 0}")
            lines.append("下一步：调用 smart_pick，传入 choice=资源编号")
        elif data.get("kind") == "assistant_p115_login":
            lines.append(f"扫码客户端：{data.get('client_type') or self._p115_client_type}")
            lines.append("下一步：调用 smart_entry，传入 text=检查115登录")

        pending = data.get("pending_p115") or {}
        if pending.get("has_pending"):
            lines.append("存在待继续的 115 任务")
            lines.append(f"任务：{pending.get('title')}")
            lines.append(f"待转目录：{pending.get('target_path')}")

        actions = data.get("suggested_actions") or []
        if actions:
            lines.append("建议动作：" + " / ".join(str(item) for item in actions if item))
        return "\n".join(lines)

    def _session_key_for_tool(self, session: str = "default") -> str:
        clean_session = self._clean_text(session) or "default"
        if clean_session.startswith("assistant::"):
            return clean_session
        return self._assistant_session_id(clean_session)

    def _execute_pending_p115_share(
        self,
        *,
        session_id: str,
        state: Dict[str, Any],
        trigger: str,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        pending = dict((state or {}).get("pending_p115") or {})
        share_url = self._clean_text(pending.get("share_url"))
        if not share_url:
            return False, "", {}
        target_path = self._clean_text(pending.get("target_path")) or self._p115_default_path
        transfer_ok, result, transfer_message = self._ensure_p115_service().transfer_share(
            url=share_url,
            access_code=self._clean_text(pending.get("access_code")),
            path=target_path,
            trigger=trigger,
        )
        if transfer_ok:
            self._clear_pending_p115_share(session_id)
            message = "\n".join(
                [
                    "115 转存已完成",
                    f"目录：{result.get('path') or target_path}",
                    f"结果：{transfer_message or result.get('message') or 'success'}",
                ]
            )
            return True, message, {"provider": "115", "result": result}

        failure_message = self._format_p115_transfer_failure(
            detail=transfer_message,
            target_path=target_path,
        )
        current_state = self._load_session(session_id) or dict(state or {})
        pending["retry_count"] = max(0, self._safe_int(pending.get("retry_count"), 0)) + 1
        pending["last_attempt_at"] = int(time.time())
        pending["last_error"] = failure_message
        current_state["pending_p115"] = pending
        if not current_state.get("kind"):
            current_state["kind"] = "assistant_p115_pending"
            current_state["stage"] = "pending_login"
        self._save_session(session_id, current_state)
        return False, failure_message, {"provider": "115", "result": result}

    async def _resume_pending_p115_share(
        self,
        request: Request,
        body: Dict[str, Any],
        *,
        session_id: str,
        state: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any]]:
        return self._execute_pending_p115_share(
            session_id=session_id,
            state=state,
            trigger="Agent影视助手 115 登录后自动继续",
        )

    def _format_p115_status_summary(self, *, title: str = "115 当前状态") -> str:
        status = self._p115_status_snapshot()
        lines = [
            title,
            f"可用状态：{'可用' if status.get('ready') else '待修复'}",
            f"默认目录：{status.get('default_target_path') or self._p115_default_path}",
            f"扫码客户端：{status.get('client_type') or self._p115_client_type}",
        ]
        if status.get("direct_source"):
            lines.append(f"直转来源：{status.get('direct_source')}")
        elif status.get("helper_ready"):
            lines.append("直转来源：P115StrmHelper")
        if status.get("cookie_mode") == "client_cookie":
            lines.append("当前会话：已保存扫码会话")
        elif status.get("cookie_mode") == "invalid_cookie":
            lines.append("当前会话：已配置但看起来不是扫码会话")
        else:
            lines.append("当前会话：复用 115 助手客户端")
        if status.get("message") and not status.get("ready"):
            lines.append(f"详情：{status.get('message')}")
        lines.append(self._format_p115_next_actions(status))
        return "\n".join(lines)

    def _format_p115_help_text(self) -> str:
        status = self._p115_status_snapshot()
        final_path = status.get("default_target_path") or self._p115_default_path
        lines = [
            "115 使用帮助",
            f"当前状态：{'可用' if status.get('ready') else '待登录/待修复'}",
            f"默认目录：{final_path}",
            "如果 115 转存因登录问题失败，我会记住这次任务；扫码成功后回复 检查115登录，会自动继续执行。",
            "常用示例：",
            f"1. 链接 https://115cdn.com/s/xxxx path={final_path}",
            "2. 影巢搜索 蜘蛛侠",
            "3. 盘搜搜索 大君夫人",
            "4. 115登录",
            "5. 检查115登录",
            "6. 115状态",
            "7. 继续115任务 / 取消115任务",
            self._format_p115_next_actions(status),
        ]
        return "\n".join(lines)

    def _format_assistant_help_text(self, session: str = "default") -> str:
        session_name = self._clean_text(session) or "default"
        lines = [
            "Agent影视助手 使用帮助",
            f"当前会话：{session_name}",
            "推荐优先使用原生 Tool：agent_resource_officer_smart_entry 与 agent_resource_officer_smart_pick。",
            "smart_entry 常用示例：",
            "1. text=盘搜搜索 大君夫人",
            "2. text=影巢搜索 蜘蛛侠",
            "3. text=115登录",
            "4. text=检查115登录",
            "5. text=链接 https://115cdn.com/s/xxxx path=/待整理",
            "6. text=链接 https://pan.quark.cn/s/xxxx 位置=分享",
            "7. text=MP搜索 蜘蛛侠；下载1 会先生成计划",
            "8. text=下载任务；暂停下载 1 / 恢复下载 1 / 删除下载 1 会先生成计划",
            "9. text=站点状态；下载器状态 用于排查 PT 搜索/下载环境",
            "10. text=下载历史 片名 用于判断资源是否提交过下载并进入整理流程",
            "11. text=追踪 片名 一次查看下载任务、下载历史和入库历史",
            "12. text=识别 片名 使用 MoviePilot 原生识别确认 TMDB/Douban/IMDB 信息",
            "13. text=订阅列表；搜索订阅 1 / 暂停订阅 1 / 恢复订阅 1 / 删除订阅 1 会先生成计划",
            "14. text=入库历史；入库失败 片名 用于判断下载后是否已经整理落库",
            "15. text=执行计划 执行当前会话最近待执行计划；text=执行 plan-xxxx 精确执行指定计划",
            "16. text=偏好 / 保存偏好 4K 杜比 HDR 中字 全集 做种>=3 影巢积分20 不自动入库 / 重置偏好",
            "smart_pick 常用示例：",
            "1. choice=1",
            "2. action=详情",
            "3. action=下一页",
            "MP 搜索结果里，choice=1 会先展示 PT 详情和评分理由；确认下载再发 text=下载1。",
            "MP 搜索结果里，action=最佳 会展示当前评分最高候选，适合智能体省 token 决策。",
            "MP 搜索结果里，text=下载最佳 会按当前最高分候选生成下载计划，不会静默下载。",
            "说明：同一个 session 会自动串起候选列表、资源列表、115 待任务与扫码续跑。",
            self._format_p115_next_actions(self._p115_status_snapshot()),
        ]
        pending_summary = self._pending_p115_summary(self._load_session(self._assistant_session_id(session_name)) or {})
        if pending_summary:
            lines.extend(["", pending_summary])
        return "\n".join(line for line in lines if line)

    def _assistant_capabilities_public_data(self) -> Dict[str, Any]:
        return {
            "version": self.plugin_version,
            "defaults": {
                "hdhive_path": self._hdhive_default_path,
                "p115_path": self._p115_default_path,
                "quark_path": self._quark_default_path,
                "p115_client_type": self._p115_client_type,
                "hdhive_candidate_page_size": self._hdhive_candidate_page_size,
                "hdhive_resource_enabled": self._hdhive_resource_enabled,
                "hdhive_max_unlock_points": self._hdhive_max_unlock_points,
                "hdhive_checkin_enabled": self._hdhive_checkin_enabled,
                "hdhive_checkin_gambler_mode": self._hdhive_checkin_gambler_mode,
                "pt_min_seeders": self._default_assistant_preferences().get("pt_min_seeders"),
                "auto_ingest": self._default_assistant_preferences().get("auto_ingest"),
                "auto_ingest_score_threshold": self._default_assistant_preferences().get("auto_ingest_score_threshold"),
            },
            "smart_entry": {
                "supports_text": True,
                "supports_structured_fields": True,
                "modes": ["mp", "pansou", "hdhive"],
                "actions": [
                    "assistant_help",
                    "p115_qrcode_start",
                    "p115_qrcode_check",
                    "p115_status",
                    "p115_help",
                    "p115_pending",
                    "p115_resume",
                    "p115_cancel",
                    "hdhive_checkin",
                    "hdhive_checkin_history",
                    "mp_media_detail",
                    "mp_download_tasks",
                    "mp_download_history",
                    "mp_lifecycle_status",
                    "mp_download_control",
                    "mp_downloaders",
                    "mp_sites",
                    "mp_subscribes",
                    "mp_subscribe_control",
                    "mp_transfer_history",
                    "mp_download",
                    "mp_download_best",
                    "mp_subscribe",
                    "mp_subscribe_search",
                    "mp_recommendations",
                    "execute_plan",
                    "plans_list",
                    "plans_clear",
                    "preferences_get",
                    "preferences_save",
                    "preferences_reset",
                ],
                "structured_fields": [
                    "session",
                    "session_id",
                    "path",
                    "mode",
                    "keyword",
                    "url",
                    "access_code",
                    "media_type",
                    "year",
                    "client_type",
                    "is_gambler",
                    "action",
                    "plan_id",
                    "status",
                    "hash",
                    "name",
                    "site_name",
                    "subscribe_id",
                    "subscribe_name",
                    "downloader",
                    "download_control",
                    "subscribe_control",
                    "delete_files",
                    "page",
                    "compact",
                ],
            },
            "assistant_preferences": {
                "fields": ["session", "session_id", "user_key", "preferences", "reset", "compact"],
                "description": "智能体片源偏好画像：云盘与 PT 分源评分都会读取这里；无偏好时建议先完成一次偏好询问。",
            },
            "scoring_policy": self._assistant_scoring_policy_public_data(),
            "smart_pick": {
                "fields": ["session", "session_id", "choice", "action", "path", "compact"],
                "actions": ["detail", "next_page"],
            },
            "assistant_session": {
                "fields": ["session", "session_id", "compact"],
                "description": "compact=true 时返回低 token 会话快照，不嵌套完整 session_state。",
            },
            "assistant_capabilities": {
                "fields": ["compact"],
                "description": "compact=true 时返回低 token 能力清单，不嵌套完整 session_state。",
            },
            "assistant_readiness": {
                "fields": ["compact"],
                "description": "compact=true 时返回低 token 就绪状态，不嵌套完整 session_state。",
            },
            "assistant_sessions": {
                "fields": ["kind", "has_pending_p115", "compact", "limit"],
                "description": "compact=true 时返回低 token 会话列表，不嵌套 default session_state。",
            },
            "assistant_history": {
                "fields": ["session", "session_id", "compact", "limit"],
                "description": "compact=true 时返回低 token 执行历史，不嵌套 default session_state。",
            },
            "assistant_action": {
                "fields": [
                    "name",
                    "session",
                    "session_id",
                    "choice",
                    "path",
                    "keyword",
                    "media_type",
                    "year",
                    "url",
                    "access_code",
                    "client_type",
                    "source",
                    "status",
                    "hash",
                    "target",
                    "name",
                    "site_name",
                    "subscribe_id",
                    "subscribe_name",
                    "control",
                    "subscribe_control",
                    "downloader",
                    "delete_files",
                    "kind",
                    "has_pending_p115",
                    "stale_only",
                    "all_sessions",
                    "limit",
                    "page",
                    "plan_id",
                    "prefer_unexecuted",
                    "compact",
                ],
                "description": "compact=true 时返回低 token 单动作摘要，不嵌套完整 session_state。",
            },
            "assistant_actions": {
                "fields": [
                    "actions",
                    "session",
                    "session_id",
                    "stop_on_error",
                    "include_raw_results",
                    "compact",
                ],
                "description": "compact=true 时返回低 token 批量执行摘要，不嵌套完整 session_state。",
            },
            "assistant_workflow": self._assistant_workflow_catalog(),
            "assistant_plan_execute": {
                "fields": [
                    "plan_id",
                    "session",
                    "session_id",
                    "prefer_unexecuted",
                    "stop_on_error",
                    "include_raw_results",
                    "compact",
                ],
                "description": "compact=true 时返回低 token 计划执行摘要，不嵌套完整 session_state。",
            },
            "assistant_plans": {
                "fields": [
                    "session",
                    "session_id",
                    "executed",
                    "include_actions",
                    "compact",
                    "limit",
                ],
                "description": "compact=true 时返回低 token 计划列表，不嵌套 default session_state。",
            },
            "assistant_plans_clear": {
                "fields": [
                    "plan_id",
                    "session",
                    "session_id",
                    "executed",
                    "all_plans",
                    "limit",
                ],
            },
            "assistant_recover": {
                "fields": [
                    "session",
                    "session_id",
                    "execute",
                    "prefer_unexecuted",
                    "stop_on_error",
                    "include_raw_results",
                    "compact",
                    "limit",
                ],
                "description": "单入口恢复协议：不传 session 时自动挑选最值得恢复的会话或计划；execute=true 时直接执行推荐动作；compact=true 可返回低 token 回执。",
            },
            "assistant_maintain": {
                "fields": [
                    "execute",
                    "limit",
                ],
                "description": "低风险维护入口：execute=false 只返回建议；execute=true 清理过期会话和已执行计划，不清理待执行计划。",
            },
            "assistant_request_templates": {
                "fields": [
                    "limit",
                ],
                "description": "轻量请求模板入口：返回外部智能体常用 assistant 请求模板，适合缓存为调用说明。",
            },
            "session_tools": [
                "assistant/pulse",
                "assistant/startup",
                "assistant/maintain",
                "assistant/toolbox",
                "assistant/request_templates",
                "assistant/selfcheck",
                "assistant/readiness",
                "assistant/history",
                "assistant/action",
                "assistant/actions",
                "assistant/workflow",
                "assistant/preferences",
                "assistant/plan/execute",
                "assistant/plans",
                "assistant/plans/clear",
                "assistant/recover",
                "assistant/sessions",
                "assistant/sessions/clear",
                "assistant/session",
                "assistant/session/clear",
            ],
            "response_envelope": {
                "fields": [
                    "protocol_version",
                    "action",
                    "ok",
                    "session",
                    "session_id",
                    "session_state",
                    "next_actions",
                    "action_templates",
                ],
                "description": "assistant/route 与 assistant/pick 返回的 data 中会统一附带当前会话状态、建议下一步动作与可直接调用的动作模板，上层智能体可直接按结构化字段继续编排。",
            },
            "agent_tools": [
                "agent_resource_officer_capabilities",
                "agent_resource_officer_startup",
                "agent_resource_officer_maintain",
                "agent_resource_officer_pulse",
                "agent_resource_officer_toolbox",
                "agent_resource_officer_request_templates",
                "agent_resource_officer_selfcheck",
                "agent_resource_officer_readiness",
                "agent_resource_officer_feishu_health",
                "agent_resource_officer_history",
                "agent_resource_officer_execute_action",
                "agent_resource_officer_execute_actions",
                "agent_resource_officer_execute_plan",
                "agent_resource_officer_plans",
                "agent_resource_officer_plans_clear",
                "agent_resource_officer_recover",
                "agent_resource_officer_run_workflow",
                "agent_resource_officer_preferences",
                "agent_resource_officer_help",
                "agent_resource_officer_smart_entry",
                "agent_resource_officer_smart_pick",
                "agent_resource_officer_sessions",
                "agent_resource_officer_sessions_clear",
                "agent_resource_officer_session_state",
                "agent_resource_officer_session_clear",
            ],
        }

    def _assistant_capabilities_compact_data(self, capabilities_data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(capabilities_data or {})
        workflow_catalog = dict(data.get("assistant_workflow") or {})
        workflows = [
            self._clean_text(item.get("name"))
            for item in workflow_catalog.get("workflows") or []
            if isinstance(item, dict) and self._clean_text(item.get("name"))
        ]
        compact_endpoints = [
            "assistant/capabilities",
            "assistant/startup",
            "assistant/maintain",
            "assistant/request_templates",
            "assistant/readiness",
            "assistant/recover",
            "assistant/session",
            "assistant/sessions",
            "assistant/history",
            "assistant/actions",
            "assistant/workflow",
            "assistant/preferences",
            "assistant/plan/execute",
            "assistant/plans",
        ]
        return {
            "protocol_version": "assistant.v1",
            "action": "capabilities",
            "ok": True,
            "compact": True,
            "version": data.get("version"),
            "defaults": data.get("defaults") or {},
            "smart_entry_modes": (data.get("smart_entry") or {}).get("modes") or [],
            "smart_entry_actions": (data.get("smart_entry") or {}).get("actions") or [],
            "smart_pick_actions": (data.get("smart_pick") or {}).get("actions") or [],
            "workflows": workflows,
            "request_templates": bool(data.get("assistant_request_templates")),
            "scoring_policy": data.get("scoring_policy") or {},
            "recommended_start": [
                "assistant/pulse",
                "assistant/startup",
                "assistant/maintain",
                "assistant/selfcheck",
                "assistant/toolbox",
                "assistant/request_templates",
                "assistant/readiness?compact=true",
            ],
            "compact_endpoints": compact_endpoints,
            "agent_tools": data.get("agent_tools") or [],
            "next_actions": ["assistant_startup", "assistant_maintain", "assistant_readiness", "smart_entry", "assistant_workflow"],
        }

    def _format_assistant_capabilities_text(self) -> str:
        data = self._assistant_capabilities_public_data()
        defaults = data.get("defaults") or {}
        lines = [
            "Agent影视助手 能力说明",
            f"版本：{data.get('version')}",
            "推荐上层调用顺序：",
            "1. 先看 capabilities 或 assistant/startup",
            "2. 如需恢复会话，可先看 assistant/sessions",
            "3. 再调用 smart_entry",
            "4. 之后用 assistant/session 或 session_state 判断下一步",
            "5. 最后再调用 smart_pick 或 session_clear",
            "默认目录：",
            f"- 影巢：{defaults.get('hdhive_path')}",
            f"- 115：{defaults.get('p115_path')}",
            f"- 夸克：{defaults.get('quark_path')}",
            f"- 115 客户端：{defaults.get('p115_client_type')}",
            f"影巢资源入口：{'开启' if defaults.get('hdhive_resource_enabled') else '关闭'}；单资源积分上限：{defaults.get('hdhive_max_unlock_points')} 分（0 表示不限制）",
            "启动聚合包：assistant/startup，一次返回 pulse、自检、核心工具、端点和恢复建议，适合外部智能体开场调用",
            "轻量启动探针：assistant/pulse，返回版本、关键服务状态与最佳恢复建议，适合外部智能体每次开场调用",
            "轻量工具清单：assistant/toolbox，返回推荐工具、端点、工作流和命令示例，适合外部智能体初始化系统提示",
            "轻量协议自检：assistant/selfcheck，返回 compact 模板、布尔解析和低 token 入口健康状态",
            "启动探针：assistant/readiness，可直接判断外部智能体是否可以开始调用；compact=true 可减少嵌套回执",
            "执行历史：assistant/history，可查看最近 action/workflow 的成功状态和摘要；compact=true 可减少嵌套回执",
            "smart_entry 结构化字段：session / session_id / path / mode / keyword / url / access_code / media_type / year / client_type / action / plan_id",
            "smart_entry 结构化模式：mp / pansou / hdhive",
            "smart_entry 动作：assistant_help / p115_qrcode_start / p115_qrcode_check / p115_status / p115_help / p115_pending / p115_resume / p115_cancel",
            "smart_entry 与 smart_pick 支持 compact=true，可减少搜索与选择链路嵌套回执",
            "smart_pick 字段：session / session_id / choice / action / path / compact",
            "smart_pick 动作：detail / next_page",
            "动作执行入口：assistant/action，可直接执行 action_templates 里的 name + body；compact=true 可减少嵌套回执",
            "批量动作入口：assistant/actions，可一次执行多步 action_body；compact=true 可减少嵌套回执",
            "预设工作流入口：assistant/workflow，可用 pansou_search / pansou_transfer / hdhive_candidates / hdhive_unlock / share_transfer / p115_status 等短参数场景；compact=true 可减少嵌套回执",
            "计划执行入口：assistant/plan/execute，可执行 dry_run 返回的 plan_id；compact=true 可减少嵌套回执",
            "自然语言计划确认：smart_entry 支持“执行计划”和“执行 plan-xxxx”，用于确认已生成的下载、订阅或控制计划",
            "计划管理入口：assistant/plans 与 assistant/plans/clear，可查询或清理 dry_run 保存的计划；compact=true 可减少嵌套回执",
            "单入口恢复：assistant/recover，可自动选择最值得恢复的会话或计划；execute=true 时直接执行推荐动作；compact=true 可减少回执字段",
            "统一回执字段：protocol_version / action / ok / session / session_id / session_state / next_actions / action_templates",
        ]
        return "\n".join(lines)

    def _assistant_readiness_public_data(self) -> Dict[str, Any]:
        p115_status = self._p115_status_snapshot()
        sessions = self._assistant_sessions_public_data(limit=10)
        warnings: List[str] = []
        if not self._enabled:
            warnings.append("插件未启用")
        if not self._hdhive_resource_enabled:
            warnings.append("影巢资源搜索/解锁已关闭，外部智能体应改用 MP 搜索或盘搜")
        if not self._hdhive_api_key:
            warnings.append("影巢 API Key 未配置，影巢相关工作流不可用")
        if not p115_status.get("ready"):
            warnings.append("115 当前不可用，需要先扫码或修复执行层")
        if not self._quark_cookie:
            warnings.append("夸克 Cookie 未配置，夸克转存可能需要先刷新")

        ready_for_external_agent = bool(self._enabled)
        pending_plans = self._assistant_plans_public_data(executed=False, limit=5)
        pending_plan_templates = [
            self._assistant_action_template(
                name="execute_plan",
                description="执行待处理计划",
                endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/plan/execute",
                tool="agent_resource_officer_execute_plan",
                body={
                    "plan_id": item.get("plan_id"),
                    "session": item.get("session"),
                    "session_id": item.get("session_id"),
                    "prefer_unexecuted": True,
                },
            )
            for item in (pending_plans.get("items") or [])
            if isinstance(item, dict) and self._clean_text(item.get("plan_id"))
        ]
        return {
            "version": self.plugin_version,
            "enabled": self._enabled,
            "ready_for_external_agent": ready_for_external_agent,
            "can_start": ready_for_external_agent,
            "services": {
                "p115": p115_status,
                "hdhive": {
                    "configured": bool(self._hdhive_api_key),
                    "base_url": self._hdhive_base_url,
                    "default_path": self._hdhive_default_path,
                },
                "quark": {
                    "configured": bool(self._quark_cookie),
                    "default_path": self._quark_default_path,
                    "auto_import_cookiecloud": self._quark_auto_import_cookiecloud,
                },
            },
            "active_sessions": {
                "total": sessions.get("total") or 0,
                "preview": sessions.get("items") or [],
            },
            "saved_plans": {
                "total": len(self._workflow_plans or {}),
                "pending": len(pending_plans.get("items") or []),
                "pending_preview": pending_plans.get("items") or [],
                "action_templates": pending_plan_templates,
            },
            "recovery": (
                {
                    "mode": "resume_saved_plan",
                    "reason": "当前存在待执行计划，可直接恢复",
                    "can_resume": True,
                    "recommended_action": self._clean_text((pending_plan_templates[0] or {}).get("name")) if pending_plan_templates else "",
                    "recommended_tool": self._clean_text((pending_plan_templates[0] or {}).get("tool")) if pending_plan_templates else "",
                    "action_template": pending_plan_templates[0] if pending_plan_templates else None,
                    "alternatives": [
                        self._clean_text(item.get("name"))
                        for item in pending_plan_templates[:5]
                        if self._clean_text(item.get("name"))
                    ],
                }
                if pending_plan_templates
                else {
                    "mode": "start_new",
                    "reason": "当前没有待恢复计划，可直接开始新任务",
                    "can_resume": False,
                    "recommended_action": "",
                    "recommended_tool": "",
                    "action_template": None,
                    "alternatives": [],
                }
            ),
            "recommended_entrypoints": [
                "GET /api/v1/plugin/AgentResourceOfficer/assistant/startup",
                "GET /api/v1/plugin/AgentResourceOfficer/assistant/readiness",
                "GET /api/v1/plugin/AgentResourceOfficer/assistant/capabilities",
                "POST /api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "POST /api/v1/plugin/AgentResourceOfficer/assistant/actions",
                "POST /api/v1/plugin/AgentResourceOfficer/assistant/plan/execute",
                "POST /api/v1/plugin/AgentResourceOfficer/assistant/route",
            ],
            "recommended_tools": [
                "agent_resource_officer_startup",
                "agent_resource_officer_readiness",
                "agent_resource_officer_feishu_health",
                "agent_resource_officer_run_workflow",
                "agent_resource_officer_execute_actions",
                "agent_resource_officer_execute_plan",
                "agent_resource_officer_smart_entry",
            ],
            "warnings": warnings,
            "suggested_first_call": {
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "body": {
                    "name": "pansou_search",
                    "session": "external-agent-demo",
                    "keyword": "片名",
                },
            },
        }

    def _assistant_readiness_compact_data(self, readiness_data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(readiness_data or {})
        services = dict(data.get("services") or {})
        p115 = dict(services.get("p115") or {})
        hdhive = dict(services.get("hdhive") or {})
        quark = dict(services.get("quark") or {})
        recovery = dict(data.get("recovery") or {})
        saved_plans = dict(data.get("saved_plans") or {})
        template = recovery.get("action_template") if isinstance(recovery.get("action_template"), dict) else None
        return {
            "protocol_version": "assistant.v1",
            "action": "readiness",
            "ok": bool(data.get("can_start")),
            "compact": True,
            "version": data.get("version"),
            "enabled": bool(data.get("enabled")),
            "can_start": bool(data.get("can_start")),
            "services": {
                "p115_ready": bool(p115.get("ready")),
                "hdhive_configured": bool(hdhive.get("configured")),
                "quark_configured": bool(quark.get("configured")),
            },
            "active_sessions_total": (data.get("active_sessions") or {}).get("total") or 0,
            "saved_plans_total": saved_plans.get("total") or 0,
            "saved_plans_pending": saved_plans.get("pending") or 0,
            "recovery": {
                "mode": self._clean_text(recovery.get("mode")),
                "can_resume": bool(recovery.get("can_resume")),
                "recommended_action": self._clean_text(recovery.get("recommended_action")),
                "recommended_tool": self._clean_text(recovery.get("recommended_tool")),
                "reason": self._clean_text(recovery.get("reason")),
            },
            "warnings": data.get("warnings") or [],
            "next_actions": [
                item for item in [
                    recovery.get("recommended_action") if recovery.get("can_resume") else "",
                    "assistant_workflow",
                    "smart_entry",
                ]
                if item
            ],
            "action_templates": [template] if template else [],
        }

    def _format_assistant_readiness_text(self) -> str:
        data = self._assistant_readiness_public_data()
        services = data.get("services") or {}
        p115 = services.get("p115") or {}
        hdhive = services.get("hdhive") or {}
        quark = services.get("quark") or {}
        lines = [
            "Agent影视助手 启动就绪",
            f"版本：{data.get('version')}",
            f"插件：{'已启用' if data.get('enabled') else '未启用'}",
            f"外部智能体：{'可以启动' if data.get('can_start') else '暂不可启动'}",
            f"115：{'可用' if p115.get('ready') else '不可用'}",
            f"影巢：{'已配置' if hdhive.get('configured') else '未配置'}",
            f"夸克：{'已配置' if quark.get('configured') else '未配置'}",
            f"活跃会话：{(data.get('active_sessions') or {}).get('total') or 0}",
            f"待执行计划：{(data.get('saved_plans') or {}).get('pending') or 0}",
            "推荐入口：assistant/workflow 或 assistant/actions",
        ]
        warnings = data.get("warnings") or []
        if warnings:
            lines.append("提示：" + "；".join(str(item) for item in warnings if item))
        return "\n".join(lines)

    def _assistant_pulse_public_data(self) -> Dict[str, Any]:
        p115_status = self._p115_status_snapshot()
        recovery_data = self._assistant_recover_public_data(limit=10)
        recovery_data.update({
            "action": "recover",
            "ok": True,
            "execute_requested": False,
            "executed": False,
        })
        recovery_compact = self._assistant_recover_response_data(recovery_data, compact=True)
        warnings: List[str] = []
        if not self._enabled:
            warnings.append("插件未启用")
        if not self._hdhive_api_key:
            warnings.append("影巢 API Key 未配置")
        if not p115_status.get("ready"):
            warnings.append("115 当前不可用")
        if not self._quark_cookie:
            warnings.append("夸克 Cookie 未配置")
        return {
            "protocol_version": "assistant.v1",
            "action": "pulse",
            "ok": bool(self._enabled),
            "version": self.plugin_version,
            "enabled": self._enabled,
            "can_start": bool(self._enabled),
            "services": {
                "p115_ready": bool(p115_status.get("ready")),
                "p115_direct_ready": bool(p115_status.get("direct_ready")),
                "hdhive_configured": bool(self._hdhive_api_key),
                "quark_configured": bool(self._quark_cookie),
            },
            "warnings": warnings,
            "session": recovery_compact.get("session"),
            "session_id": recovery_compact.get("session_id"),
            "recovery": recovery_compact.get("recovery") or {},
            "selected_session": recovery_compact.get("selected_session"),
            "next_actions": recovery_compact.get("next_actions") or [],
            "action_templates": recovery_compact.get("action_templates") or [],
            "recommended_endpoints": {
                "startup": "/api/v1/plugin/AgentResourceOfficer/assistant/startup",
                "selfcheck": "/api/v1/plugin/AgentResourceOfficer/assistant/selfcheck",
                "toolbox": "/api/v1/plugin/AgentResourceOfficer/assistant/toolbox",
                "recover": "/api/v1/plugin/AgentResourceOfficer/assistant/recover?compact=true",
                "workflow": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "actions": "/api/v1/plugin/AgentResourceOfficer/assistant/actions",
            },
        }

    def _format_assistant_pulse_text(self) -> str:
        data = self._assistant_pulse_public_data()
        services = data.get("services") or {}
        recovery = data.get("recovery") or {}
        lines = [
            "Agent影视助手 轻量启动状态",
            f"版本：{data.get('version')}",
            f"插件：{'已启用' if data.get('enabled') else '未启用'}",
            f"115：{'可用' if services.get('p115_ready') else '不可用'}",
            f"影巢：{'已配置' if services.get('hdhive_configured') else '未配置'}",
            f"夸克：{'已配置' if services.get('quark_configured') else '未配置'}",
            f"恢复模式：{recovery.get('mode') or 'unknown'}",
        ]
        if recovery.get("recommended_action"):
            lines.append(f"推荐动作：{recovery.get('recommended_action')}")
        warnings = data.get("warnings") or []
        if warnings:
            lines.append("提示：" + "；".join(str(item) for item in warnings if item))
        return "\n".join(lines)

    def _assistant_maintenance_snapshot(self, limit: int = 100) -> Dict[str, Any]:
        max_limit = min(max(1, self._safe_int(limit, 100)), 500)
        pending_plan_count = sum(
            1
            for item in (self._workflow_plans or {}).values()
            if isinstance(item, dict) and not bool(item.get("executed"))
        )
        executed_plan_count = sum(
            1
            for item in (self._workflow_plans or {}).values()
            if isinstance(item, dict) and bool(item.get("executed"))
        )
        stale_session_count = sum(
            1
            for item in (self._session_cache or {}).values()
            if isinstance(item, dict) and self._is_session_expired(item)
        )
        action_templates = [
            self._assistant_action_template(
                name="clear_stale_sessions",
                description="清理过期 assistant 会话，不影响仍有效的当前会话",
                endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/sessions/clear",
                tool="agent_resource_officer_sessions_clear",
                body={"stale_only": True, "limit": max_limit},
            ),
            self._assistant_action_template(
                name="clear_executed_plans",
                description="清理已执行的保存计划，不影响待执行计划",
                endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/plans/clear",
                tool="agent_resource_officer_plans_clear",
                body={"executed": True, "limit": max_limit},
            ),
        ]
        recommended_actions = [
            item.get("name")
            for item in action_templates
            if (
                (item.get("name") == "clear_stale_sessions" and stale_session_count > 0)
                or (item.get("name") == "clear_executed_plans" and executed_plan_count > 0)
            )
        ]
        return {
            "active_sessions": len(self._session_cache or {}),
            "stale_sessions": stale_session_count,
            "saved_plans_total": len(self._workflow_plans or {}),
            "saved_plans_pending": pending_plan_count,
            "saved_plans_executed": executed_plan_count,
            "recommended_actions": recommended_actions,
            "action_templates": action_templates,
            "safe_to_execute": bool(recommended_actions),
            "dry_run_method": "GET",
            "execute_method": "POST",
            "execute_endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/maintain",
            "execute_body": {"execute": True, "limit": max_limit},
            "execution_note": "GET 只返回 dry-run；只有 POST execute=true 会实际清理，并写入 assistant/history。",
            "limit": max_limit,
        }

    def _assistant_maintain_public_data(self, execute: bool = False, limit: int = 100) -> Dict[str, Any]:
        before = self._assistant_maintenance_snapshot(limit=limit)
        executed_actions: List[Dict[str, Any]] = []
        if execute:
            if before.get("stale_sessions", 0) > 0:
                result = self._clear_assistant_sessions(stale_only=True, limit=before.get("limit") or limit)
                executed_actions.append({
                    "name": "clear_stale_sessions",
                    "success": True,
                    "removed": result.get("cleared_count") or 0,
                })
            if before.get("saved_plans_executed", 0) > 0:
                result = self._clear_workflow_plans(executed=True, limit=before.get("limit") or limit)
                executed_actions.append({
                    "name": "clear_executed_plans",
                    "success": bool(result.get("ok")),
                    "removed": result.get("removed") or 0,
                })
        after = self._assistant_maintenance_snapshot(limit=limit)
        return {
            "protocol_version": "assistant.v1",
            "action": "maintain",
            "ok": True,
            "compact": True,
            "version": self.plugin_version,
            "execute_requested": bool(execute),
            "executed": bool(executed_actions),
            "executed_actions": executed_actions,
            "before": before,
            "after": after,
            "next_actions": after.get("recommended_actions") or [],
            "action_templates": after.get("action_templates") or [],
        }

    def _format_assistant_maintain_text(self, data: Optional[Dict[str, Any]] = None) -> str:
        payload = data or self._assistant_maintain_public_data(execute=False)
        before = payload.get("before") or {}
        after = payload.get("after") or before
        lines = [
            "Agent影视助手 低风险维护",
            f"版本：{payload.get('version')}",
            f"执行：{'是' if payload.get('execute_requested') else '否'}",
            "维护前：过期会话 {stale_sessions}；已执行计划 {saved_plans_executed}；待执行计划 {saved_plans_pending}".format(**before),
            "维护后：过期会话 {stale_sessions}；已执行计划 {saved_plans_executed}；待执行计划 {saved_plans_pending}".format(**after),
        ]
        executed_actions = payload.get("executed_actions") or []
        if executed_actions:
            lines.append("已执行：" + " / ".join(f"{item.get('name')}({item.get('removed')})" for item in executed_actions))
        recommended = after.get("recommended_actions") or []
        if recommended:
            lines.append("仍建议：" + " / ".join(str(item) for item in recommended if item))
        return "\n".join(lines)

    def _assistant_startup_public_data(self) -> Dict[str, Any]:
        pulse = self._assistant_pulse_public_data()
        selfcheck = self._assistant_selfcheck_public_data()
        toolbox = self._assistant_toolbox_public_data()
        maintenance = self._assistant_maintenance_snapshot(limit=100)
        request_templates = self._assistant_request_templates_public_data(limit=100)
        tools = toolbox.get("tools") or {}
        endpoints = toolbox.get("endpoints") or {}
        key_names = [
            "startup",
            "maintain",
            "pulse",
            "selfcheck",
            "request_templates",
            "recover",
            "workflow",
            "route",
            "pick",
            "execute_action",
            "execute_actions",
        ]
        key_tools = {name: tools.get(name) for name in key_names if tools.get(name)}
        key_endpoints = {
            name: endpoints.get(name)
            for name in ["startup", "maintain", "pulse", "selfcheck", "request_templates", "recover", "workflow", "action", "actions", "route", "pick"]
            if endpoints.get(name)
        }
        recovery = pulse.get("recovery") or {}
        recommended_templates_recipe = "continue" if bool(recovery.get("can_resume")) else "bootstrap"
        recommended_templates_reason = (
            "检测到可恢复会话，优先读取继续会话流程。"
            if recommended_templates_recipe == "continue"
            else "未检测到必须恢复的会话，优先读取安全启动流程。"
        )
        return {
            "protocol_version": "assistant.v1",
            "action": "startup",
            "ok": bool(pulse.get("can_start")) and bool(selfcheck.get("ok")),
            "compact": True,
            "version": self.plugin_version,
            "services": pulse.get("services") or {},
            "warnings": pulse.get("warnings") or [],
            "session": pulse.get("session"),
            "session_id": pulse.get("session_id"),
            "recovery": pulse.get("recovery") or {},
            "selected_session": pulse.get("selected_session"),
            "action_templates": pulse.get("action_templates") or [],
            "maintenance": maintenance,
            "selfcheck": {
                "ok": bool(selfcheck.get("ok")),
                "checks": selfcheck.get("checks") or {},
            },
            "defaults": toolbox.get("defaults") or {},
            "startup_order": toolbox.get("startup_order") or [],
            "tools": key_tools,
            "endpoints": key_endpoints,
            "workflows": [item.get("name") for item in (toolbox.get("workflows") or []) if item.get("name")],
            "actions": toolbox.get("actions") or [],
            "command_examples": (toolbox.get("command_examples") or [])[:6],
            "request_templates": request_templates,
            "request_templates_schema_version": self.request_templates_schema_version,
            "recommended_request_templates": self._assistant_recommended_request_templates_data(
                recipe=recommended_templates_recipe,
                reason=recommended_templates_reason,
            ),
            "next_actions": pulse.get("next_actions") or ["assistant_recover", "assistant_workflow", "smart_entry"],
            "recommended_endpoints": key_endpoints,
        }

    def _assistant_recommended_request_templates_data(self, recipe: str = "bootstrap", reason: str = "") -> Dict[str, Any]:
        recipe_name = self._clean_text(recipe) or "bootstrap"
        return {
            "recipe": recipe_name,
            "reason": self._clean_text(reason),
            "include_templates": False,
            "method": "POST",
            "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/request_templates",
            "url_template": "{base_url}/api/v1/plugin/AgentResourceOfficer/assistant/request_templates?apikey={MP_API_TOKEN}",
            "tool": "agent_resource_officer_request_templates",
            "tool_args": {
                "recipe": recipe_name,
                "include_templates": False,
            },
        }

    def _format_assistant_startup_text(self) -> str:
        data = self._assistant_startup_public_data()
        services = data.get("services") or {}
        recovery = data.get("recovery") or {}
        checks = (data.get("selfcheck") or {}).get("checks") or {}
        failed = [key for key, value in checks.items() if not value]
        lines = [
            "Agent影视助手 启动聚合包",
            f"版本：{data.get('version')}",
            f"可启动：{'是' if data.get('ok') else '否'}",
            f"115：{'可用' if services.get('p115_ready') else '不可用'}；影巢：{'已配' if services.get('hdhive_configured') else '未配'}；夸克：{'已配' if services.get('quark_configured') else '未配'}",
            f"自检：{'通过' if not failed else '失败 ' + ', '.join(failed)}",
            f"恢复模式：{recovery.get('mode') or 'unknown'}",
            f"可执行模板：{len(data.get('action_templates') or [])} 个",
            "状态：活跃会话 {active_sessions}；过期会话 {stale_sessions}；保存计划 {saved_plans_total}；待执行计划 {saved_plans_pending}；已执行计划 {saved_plans_executed}".format(**(data.get("maintenance") or {})),
            "下一步：优先按 recovery 建议执行；没有待恢复任务时使用 workflow 或 smart_entry",
        ]
        warnings = data.get("warnings") or []
        if warnings:
            lines.append("提示：" + "；".join(str(item) for item in warnings if item))
        maintenance = data.get("maintenance") or {}
        recommended_actions = maintenance.get("recommended_actions") or []
        if recommended_actions:
            lines.append("维护建议：" + " / ".join(str(item) for item in recommended_actions if item))
        return "\n".join(lines)

    def _assistant_toolbox_public_data(self) -> Dict[str, Any]:
        workflows = [dict(item or {}) for item in (self._assistant_workflow_catalog().get("workflows") or []) if isinstance(item, dict)]
        return {
            "protocol_version": "assistant.v1",
            "action": "toolbox",
            "ok": True,
            "version": self.plugin_version,
            "defaults": {
                "p115_path": self._p115_default_path,
                "quark_path": self._quark_default_path,
                "hdhive_path": self._hdhive_default_path,
                "p115_client_type": self._p115_client_type,
            },
            "startup_order": [
                "agent_resource_officer_startup",
                "agent_resource_officer_maintain",
                "agent_resource_officer_pulse",
                "agent_resource_officer_selfcheck",
                "agent_resource_officer_request_templates",
                "agent_resource_officer_recover",
                "agent_resource_officer_run_workflow",
                "agent_resource_officer_smart_entry",
                "agent_resource_officer_smart_pick",
            ],
            "endpoints": {
                "pulse": "/api/v1/plugin/AgentResourceOfficer/assistant/pulse",
                "startup": "/api/v1/plugin/AgentResourceOfficer/assistant/startup",
                "maintain": "/api/v1/plugin/AgentResourceOfficer/assistant/maintain",
                "toolbox": "/api/v1/plugin/AgentResourceOfficer/assistant/toolbox",
                "request_templates": "/api/v1/plugin/AgentResourceOfficer/assistant/request_templates",
                "selfcheck": "/api/v1/plugin/AgentResourceOfficer/assistant/selfcheck",
                "recover": "/api/v1/plugin/AgentResourceOfficer/assistant/recover?compact=true",
                "workflow": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "action": "/api/v1/plugin/AgentResourceOfficer/assistant/action",
                "actions": "/api/v1/plugin/AgentResourceOfficer/assistant/actions",
                "route": "/api/v1/plugin/AgentResourceOfficer/assistant/route",
                "pick": "/api/v1/plugin/AgentResourceOfficer/assistant/pick",
            },
            "tools": {
                "startup": "agent_resource_officer_startup",
                "maintain": "agent_resource_officer_maintain",
                "pulse": "agent_resource_officer_pulse",
                "toolbox": "agent_resource_officer_toolbox",
                "request_templates": "agent_resource_officer_request_templates",
                "selfcheck": "agent_resource_officer_selfcheck",
                "recover": "agent_resource_officer_recover",
                "workflow": "agent_resource_officer_run_workflow",
                "route": "agent_resource_officer_smart_entry",
                "pick": "agent_resource_officer_smart_pick",
                "execute_action": "agent_resource_officer_execute_action",
                "execute_actions": "agent_resource_officer_execute_actions",
            },
            "workflows": [
                {
                    "name": item.get("name"),
                    "fields": item.get("fields") or [],
                }
                for item in workflows
            ],
            "actions": [
                "start_pansou_search",
                "pick_pansou_result",
                "start_hdhive_search",
                "pick_hdhive_candidate",
                "candidate_detail",
                "candidate_next_page",
                "pick_hdhive_resource",
                "route_share",
                "start_115_login",
                "check_115_login",
                "show_115_status",
                "resume_pending_115",
                "execute_latest_plan",
                "execute_session_latest_plan",
                "query_mp_download_tasks",
                "query_mp_download_history",
                "query_mp_lifecycle_status",
                "query_mp_media_detail",
                "query_mp_search_result_detail",
                "query_mp_best_result_detail",
                "pick_mp_best_download",
                "query_mp_downloaders",
                "query_mp_sites",
                "query_mp_subscribes",
                "query_mp_transfer_history",
                "clear_stale_sessions",
                "clear_executed_plans",
            ],
            "command_examples": [
                "盘搜搜索 大君夫人",
                "影巢搜索 蜘蛛侠",
                "1大君夫人",
                "2蜘蛛侠",
                "链接 https://pan.quark.cn/s/xxxx path=/飞书",
                "选择 1",
                "详情",
                "下一页",
                "识别 蜘蛛侠",
                "115登录",
            ],
            "request_templates": self._assistant_request_templates_public_data(limit=100),
            "request_templates_schema_version": self.request_templates_schema_version,
        }

    def _assistant_request_templates_public_data(self, limit: int = 100) -> Dict[str, Any]:
        max_limit = min(max(1, self._safe_int(limit, 100)), 500)
        return {
            "startup_probe": {
                "description": "读取启动聚合包，适合外部智能体开场获取状态、端点、工具和恢复建议。",
                "side_effect": "read_only",
                "requires_confirmation": False,
                "cache_scope": "short_lived",
                "cache_ttl_seconds": 30,
                "method": "GET",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/startup",
                "tool": "agent_resource_officer_startup",
                "tool_args": {},
                "query": {},
            },
            "selfcheck_probe": {
                "description": "执行协议自检，确认模板、compact、布尔解析和核心入口是否健康。",
                "side_effect": "read_only",
                "requires_confirmation": False,
                "cache_scope": "short_lived",
                "cache_ttl_seconds": 30,
                "method": "GET",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/selfcheck",
                "tool": "agent_resource_officer_selfcheck",
                "tool_args": {},
                "query": {},
            },
            "maintain_preview": {
                "description": "预览低风险维护建议，不执行清理；适合高频探测。",
                "side_effect": "dry_run",
                "requires_confirmation": False,
                "cache_scope": "short_lived",
                "cache_ttl_seconds": 30,
                "method": "GET",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/maintain",
                "tool": "agent_resource_officer_maintain",
                "tool_args": {"execute": False, "limit": max_limit},
                "query": {"execute": True, "limit": max_limit},
            },
            "maintain_execute": {
                "description": "执行低风险维护，清理过期会话和已执行计划；会写入 assistant/history。",
                "side_effect": "write",
                "requires_confirmation": True,
                "cache_scope": "no_cache",
                "cache_ttl_seconds": 0,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/maintain",
                "tool": "agent_resource_officer_maintain",
                "tool_args": {"execute": True, "limit": max_limit},
                "body": {"execute": True, "limit": max_limit},
            },
            "preferences_get": {
                "description": "读取智能体片源偏好画像；未初始化时应先询问用户偏好。",
                "side_effect": "read_only",
                "requires_confirmation": False,
                "cache_scope": "short_lived",
                "cache_ttl_seconds": 60,
                "method": "GET",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/preferences",
                "tool": "agent_resource_officer_preferences",
                "tool_args": {"session": "assistant", "compact": True},
                "query": {"session": "assistant", "compact": True},
            },
            "preferences_save": {
                "description": "保存智能体片源偏好画像；影响云盘与 PT 评分、自动化建议和安全阈值。",
                "side_effect": "state",
                "requires_confirmation": True,
                "cache_scope": "no_cache",
                "cache_ttl_seconds": 0,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/preferences",
                "tool": "agent_resource_officer_preferences",
                "tool_args": {
                    "session": "assistant",
                    "preferences": self._default_assistant_preferences(),
                    "compact": True,
                },
                "body": {
                    "session": "assistant",
                    "preferences": self._default_assistant_preferences(),
                    "compact": True,
                },
            },
            "scoring_policy": {
                "description": "读取插件内置云盘/PT 评分策略、硬门槛和 score_summary 使用约定；只读，可缓存。",
                "side_effect": "read_only",
                "requires_confirmation": False,
                "cache_scope": "medium_lived",
                "cache_ttl_seconds": 3600,
                "method": "GET",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/capabilities",
                "tool": "agent_resource_officer_capabilities",
                "tool_args": {"compact": True},
                "query": {"compact": True},
                "response_field": "scoring_policy",
            },
            "workflow_dry_run": {
                "description": "生成并保存工作流计划，不实际执行；适合先让用户确认。",
                "side_effect": "plan_write",
                "requires_confirmation": False,
                "cache_scope": "static_template",
                "cache_ttl_seconds": 3600,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {
                    "name": "hdhive_candidates",
                    "keyword": "蜘蛛侠",
                    "media_type": "auto",
                    "session": "assistant",
                    "dry_run": True,
                    "compact": True,
                },
                "body": {
                    "workflow": "hdhive_candidates",
                    "keyword": "蜘蛛侠",
                    "media_type": "auto",
                    "session": "assistant",
                    "dry_run": True,
                    "compact": True,
                },
            },
            "mp_search": {
                "description": "执行 MP 原生搜索，返回 PT 候选与 PT 评分摘要。",
                "side_effect": "read_only",
                "requires_confirmation": False,
                "cache_scope": "session_cache",
                "cache_ttl_seconds": 600,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {"name": "mp_search", "keyword": "蜘蛛侠", "session": "assistant", "compact": True},
                "body": {"workflow": "mp_search", "keyword": "蜘蛛侠", "session": "assistant", "compact": True},
            },
            "mp_media_detail": {
                "description": "使用 MoviePilot 原生识别确认片名、年份、类型和 TMDB/Douban/IMDB ID；适合搜索前消歧。",
                "side_effect": "read_only",
                "requires_confirmation": False,
                "cache_scope": "short_lived",
                "cache_ttl_seconds": 300,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {"name": "mp_media_detail", "keyword": "蜘蛛侠", "media_type": "auto", "session": "assistant", "compact": True},
                "body": {"workflow": "mp_media_detail", "keyword": "蜘蛛侠", "media_type": "auto", "session": "assistant", "compact": True},
            },
            "mp_search_detail": {
                "description": "执行 MP 原生搜索并查看指定编号的 PT 详情和评分理由；只读，不下载。",
                "side_effect": "read_only",
                "requires_confirmation": False,
                "cache_scope": "session_cache",
                "cache_ttl_seconds": 600,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {"name": "mp_search_detail", "keyword": "蜘蛛侠", "choice": 1, "session": "assistant", "compact": True},
                "body": {"workflow": "mp_search_detail", "keyword": "蜘蛛侠", "choice": 1, "session": "assistant", "compact": True},
            },
            "mp_search_best": {
                "description": "执行 MP 原生搜索并展示当前评分最高的 PT 候选详情；只读，不下载。",
                "side_effect": "read_only",
                "requires_confirmation": False,
                "cache_scope": "session_cache",
                "cache_ttl_seconds": 600,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {"name": "mp_search_best", "keyword": "蜘蛛侠", "session": "assistant", "compact": True},
                "body": {"workflow": "mp_search_best", "keyword": "蜘蛛侠", "session": "assistant", "compact": True},
            },
            "mp_best_download_plan": {
                "description": "在已有 MP 搜索会话中按当前最高分候选生成下载计划；不会直接下载。",
                "side_effect": "plan_write",
                "requires_confirmation": False,
                "cache_scope": "no_cache",
                "cache_ttl_seconds": 0,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/action",
                "tool": "agent_resource_officer_execute_action",
                "tool_args": {"name": "pick_mp_best_download", "session": "assistant", "compact": True},
                "body": {"name": "pick_mp_best_download", "session": "assistant", "compact": True},
            },
            "mp_search_download_plan": {
                "description": "MP 原生搜索并选择编号下载；写入动作默认只生成 plan_id，确认后执行。",
                "side_effect": "plan_write",
                "requires_confirmation": False,
                "cache_scope": "no_cache",
                "cache_ttl_seconds": 0,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {"name": "mp_search_download", "keyword": "蜘蛛侠", "choice": 1, "session": "assistant", "dry_run": True, "compact": True},
                "body": {"workflow": "mp_search_download", "keyword": "蜘蛛侠", "choice": 1, "session": "assistant", "dry_run": True, "compact": True},
            },
            "mp_download_tasks": {
                "description": "查询 MP 下载任务状态，可按下载中、等待、已暂停等状态过滤；只返回摘要。",
                "side_effect": "read_only",
                "requires_confirmation": False,
                "cache_scope": "short_lived",
                "cache_ttl_seconds": 60,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {"name": "mp_download_tasks", "status": "downloading", "limit": 10, "session": "assistant", "compact": True},
                "body": {"workflow": "mp_download_tasks", "status": "downloading", "limit": 10, "session": "assistant", "compact": True},
            },
            "mp_download_control_plan": {
                "description": "暂停、恢复或删除 MP 下载任务；默认只生成 plan_id，确认后执行。",
                "side_effect": "plan_write",
                "requires_confirmation": False,
                "cache_scope": "no_cache",
                "cache_ttl_seconds": 0,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {"name": "mp_download_control", "control": "pause", "target": "1", "session": "assistant", "dry_run": True, "compact": True},
                "body": {"workflow": "mp_download_control", "control": "pause", "target": "1", "session": "assistant", "dry_run": True, "compact": True},
            },
            "mp_download_history": {
                "description": "查询 MP 下载历史，并按 hash 关联整理/入库状态；只返回摘要。",
                "side_effect": "read_only",
                "requires_confirmation": False,
                "cache_scope": "short_lived",
                "cache_ttl_seconds": 120,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {"name": "mp_download_history", "keyword": "蜘蛛侠", "limit": 10, "session": "assistant", "compact": True},
                "body": {"workflow": "mp_download_history", "keyword": "蜘蛛侠", "limit": 10, "session": "assistant", "compact": True},
            },
            "mp_lifecycle_status": {
                "description": "一次查询 MP 下载任务、下载历史和整理/入库历史，适合追踪资源当前卡在哪一步。",
                "side_effect": "read_only",
                "requires_confirmation": False,
                "cache_scope": "short_lived",
                "cache_ttl_seconds": 60,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {"name": "mp_lifecycle_status", "keyword": "蜘蛛侠", "limit": 5, "session": "assistant", "compact": True},
                "body": {"workflow": "mp_lifecycle_status", "keyword": "蜘蛛侠", "limit": 5, "session": "assistant", "compact": True},
            },
            "mp_downloaders": {
                "description": "查询 MP 下载器配置摘要，不返回密码、Cookie 或 Token。",
                "side_effect": "read_only",
                "requires_confirmation": False,
                "cache_scope": "short_lived",
                "cache_ttl_seconds": 120,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {"name": "mp_downloaders", "session": "assistant", "compact": True},
                "body": {"workflow": "mp_downloaders", "session": "assistant", "compact": True},
            },
            "mp_sites": {
                "description": "查询 MP PT 站点启用状态、优先级和 Cookie 是否存在，不返回 Cookie 明文。",
                "side_effect": "read_only",
                "requires_confirmation": False,
                "cache_scope": "short_lived",
                "cache_ttl_seconds": 120,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {"name": "mp_sites", "status": "active", "limit": 30, "session": "assistant", "compact": True},
                "body": {"workflow": "mp_sites", "status": "active", "limit": 30, "session": "assistant", "compact": True},
            },
            "mp_subscribe_plan": {
                "description": "按关键词创建 MP 订阅；默认只生成 plan_id，确认后执行。",
                "side_effect": "plan_write",
                "requires_confirmation": False,
                "cache_scope": "no_cache",
                "cache_ttl_seconds": 0,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {"name": "mp_subscribe", "keyword": "蜘蛛侠", "session": "assistant", "dry_run": True, "compact": True},
                "body": {"workflow": "mp_subscribe", "keyword": "蜘蛛侠", "session": "assistant", "dry_run": True, "compact": True},
            },
            "mp_subscribe_search_plan": {
                "description": "创建 MP 订阅并立即触发搜索；默认只生成 plan_id，确认后执行。",
                "side_effect": "plan_write",
                "requires_confirmation": False,
                "cache_scope": "no_cache",
                "cache_ttl_seconds": 0,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {"name": "mp_subscribe_and_search", "keyword": "蜘蛛侠", "session": "assistant", "dry_run": True, "compact": True},
                "body": {"workflow": "mp_subscribe_and_search", "keyword": "蜘蛛侠", "session": "assistant", "dry_run": True, "compact": True},
            },
            "mp_subscribes": {
                "description": "查询 MP 订阅列表，可按状态、类型和关键词过滤；只返回摘要。",
                "side_effect": "read_only",
                "requires_confirmation": False,
                "cache_scope": "short_lived",
                "cache_ttl_seconds": 120,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {"name": "mp_subscribes", "status": "all", "limit": 20, "session": "assistant", "compact": True},
                "body": {"workflow": "mp_subscribes", "status": "all", "limit": 20, "session": "assistant", "compact": True},
            },
            "mp_subscribe_control_plan": {
                "description": "搜索、暂停、恢复或删除 MP 订阅；默认只生成 plan_id，确认后执行。",
                "side_effect": "plan_write",
                "requires_confirmation": False,
                "cache_scope": "no_cache",
                "cache_ttl_seconds": 0,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {"name": "mp_subscribe_control", "control": "search", "target": "1", "session": "assistant", "dry_run": True, "compact": True},
                "body": {"workflow": "mp_subscribe_control", "control": "search", "target": "1", "session": "assistant", "dry_run": True, "compact": True},
            },
            "mp_transfer_history": {
                "description": "查询 MP 最近整理/入库历史，判断下载后是否已经落库；只返回摘要。",
                "side_effect": "read_only",
                "requires_confirmation": False,
                "cache_scope": "short_lived",
                "cache_ttl_seconds": 120,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {"name": "mp_transfer_history", "keyword": "蜘蛛侠", "status": "all", "limit": 10, "session": "assistant", "compact": True},
                "body": {"workflow": "mp_transfer_history", "keyword": "蜘蛛侠", "status": "all", "limit": 10, "session": "assistant", "compact": True},
            },
            "mp_recommend": {
                "description": "读取 MP 原生热门推荐，例如 TMDB、豆瓣或 Bangumi。",
                "side_effect": "read_only",
                "requires_confirmation": False,
                "cache_scope": "short_lived",
                "cache_ttl_seconds": 300,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {"name": "mp_recommend", "source": "tmdb_trending", "media_type": "all", "limit": 20, "session": "assistant", "compact": True},
                "body": {"workflow": "mp_recommend", "source": "tmdb_trending", "media_type": "all", "limit": 20, "session": "assistant", "compact": True},
            },
            "mp_recommend_search": {
                "description": "读取 MP 原生推荐并按编号继续搜索；mode 可选 mp、hdhive、pansou。",
                "side_effect": "read_only",
                "requires_confirmation": False,
                "cache_scope": "session_cache",
                "cache_ttl_seconds": 300,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "tool": "agent_resource_officer_run_workflow",
                "tool_args": {"name": "mp_recommend_search", "source": "tmdb_trending", "choice": 1, "mode": "mp", "limit": 20, "session": "assistant", "compact": True},
                "body": {"workflow": "mp_recommend_search", "source": "tmdb_trending", "choice": 1, "mode": "mp", "limit": 20, "session": "assistant", "compact": True},
            },
            "saved_plan_execute": {
                "description": "执行已保存的 dry_run 工作流计划，可按 session 自动选择未执行计划。",
                "side_effect": "write",
                "requires_confirmation": True,
                "cache_scope": "no_cache",
                "cache_ttl_seconds": 0,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/plan/execute",
                "tool": "agent_resource_officer_execute_plan",
                "tool_args": {
                    "session": "assistant",
                    "prefer_unexecuted": True,
                    "compact": True,
                },
                "body": {
                    "session": "assistant",
                    "prefer_unexecuted": True,
                    "compact": True,
                },
            },
            "action_execute": {
                "description": "按动作名执行单个 action template，适合无映射继续执行。",
                "side_effect": "depends_on_action",
                "requires_confirmation": True,
                "cache_scope": "no_cache",
                "cache_ttl_seconds": 0,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/action",
                "tool": "agent_resource_officer_execute_action",
                "tool_args": {
                    "name": "show_115_status",
                    "session": "assistant",
                    "compact": True,
                },
                "body": {
                    "name": "show_115_status",
                    "session": "assistant",
                    "compact": True,
                },
            },
            "route_text": {
                "description": "统一自然语言入口，适合 WorkBuddy、Hermes、OpenClaw（小龙虾）、微信侧智能体或其他外部智能体直接转发用户文本。",
                "side_effect": "depends_on_text",
                "requires_confirmation": False,
                "cache_scope": "no_cache",
                "cache_ttl_seconds": 0,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/route",
                "tool": "agent_resource_officer_smart_entry",
                "tool_args": {
                    "text": "盘搜搜索 大君夫人",
                    "session": "agent:demo",
                    "compact": True,
                },
                "body": {
                    "text": "盘搜搜索 大君夫人",
                    "session": "agent:demo",
                    "compact": True,
                },
            },
            "pick_continue": {
                "description": "按编号继续当前会话，适合盘搜、影巢候选或资源列表选择。",
                "side_effect": "depends_on_session",
                "requires_confirmation": True,
                "cache_scope": "no_cache",
                "cache_ttl_seconds": 0,
                "method": "POST",
                "endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/pick",
                "tool": "agent_resource_officer_smart_pick",
                "tool_args": {
                    "session": "agent:demo",
                    "choice": 1,
                    "compact": True,
                },
                "body": {
                    "session": "agent:demo",
                    "choice": 1,
                    "compact": True,
                },
            },
        }

    def _assistant_request_template_names(self, value: Any) -> List[str]:
        if isinstance(value, (list, tuple, set)):
            rows = value
        else:
            rows = re.split(r"[,，\s]+", self._clean_text(value))
        names: List[str] = []
        for item in rows:
            name = self._clean_text(item)
            if name and name not in names:
                names.append(name)
        return names

    def _assistant_request_templates_response_data(
        self,
        limit: int = 100,
        names: Any = None,
        recipe: Any = None,
        include_templates: bool = True,
    ) -> Dict[str, Any]:
        all_templates = self._assistant_request_templates_public_data(limit=limit)
        recipe_templates_map = {
            "safe_bootstrap": ["startup_probe", "selfcheck_probe", "maintain_preview"],
            "plan_then_confirm": ["workflow_dry_run", "saved_plan_execute"],
            "continue_existing_session": ["pick_continue"],
            "maintenance_cycle": ["maintain_preview", "maintain_execute"],
            "external_agent_quickstart": ["startup_probe", "route_text", "pick_continue"],
            "workbuddy_quickstart": ["startup_probe", "route_text", "pick_continue"],
            "mp_pt_mainline": [
                "mp_media_detail",
                "mp_search",
                "mp_search_detail",
                "mp_search_best",
                "mp_search_download_plan",
                "mp_best_download_plan",
                "mp_download_tasks",
                "mp_download_control_plan",
                "mp_download_history",
                "mp_lifecycle_status",
                "mp_downloaders",
                "mp_sites",
                "mp_subscribe_plan",
                "mp_subscribe_search_plan",
                "mp_subscribes",
                "mp_subscribe_control_plan",
                "mp_transfer_history",
                "saved_plan_execute",
            ],
            "mp_recommendation": [
                "mp_recommend",
                "mp_recommend_search",
                "mp_search",
                "mp_search_best",
                "mp_search_download_plan",
                "saved_plan_execute",
            ],
        }
        recipe_aliases = {
            "bootstrap": "safe_bootstrap",
            "safe": "safe_bootstrap",
            "start": "safe_bootstrap",
            "启动": "safe_bootstrap",
            "plan": "plan_then_confirm",
            "dry_run": "plan_then_confirm",
            "confirm": "plan_then_confirm",
            "计划": "plan_then_confirm",
            "continue": "continue_existing_session",
            "pick": "continue_existing_session",
            "resume": "continue_existing_session",
            "继续": "continue_existing_session",
            "选择": "continue_existing_session",
            "maintain": "maintenance_cycle",
            "maintenance": "maintenance_cycle",
            "cleanup": "maintenance_cycle",
            "维护": "maintenance_cycle",
            "external_agent": "external_agent_quickstart",
            "external-agent": "external_agent_quickstart",
            "agent": "external_agent_quickstart",
            "外部智能体": "external_agent_quickstart",
            "微信智能体": "external_agent_quickstart",
            "workbuddy": "external_agent_quickstart",
            "work_buddy": "external_agent_quickstart",
            "workbody": "external_agent_quickstart",
            "work_body": "external_agent_quickstart",
            "mp": "mp_pt_mainline",
            "pt": "mp_pt_mainline",
            "mp_native": "mp_pt_mainline",
            "mp-native": "mp_pt_mainline",
            "mp_pt": "mp_pt_mainline",
            "mp-pt": "mp_pt_mainline",
            "pt_mainline": "mp_pt_mainline",
            "pt-mainline": "mp_pt_mainline",
            "原生mp": "mp_pt_mainline",
            "mp原生": "mp_pt_mainline",
            "原生搜索": "mp_pt_mainline",
            "pt下载": "mp_pt_mainline",
            "下载订阅": "mp_pt_mainline",
            "recommend": "mp_recommendation",
            "recommendation": "mp_recommendation",
            "mp_recommend": "mp_recommendation",
            "mp-recommend": "mp_recommendation",
            "推荐": "mp_recommendation",
            "热门": "mp_recommendation",
        }
        requested_recipe = self._clean_text(recipe)
        selected_recipe = recipe_aliases.get(requested_recipe, requested_recipe)
        invalid_recipe = requested_recipe if requested_recipe and selected_recipe not in recipe_templates_map else ""
        selected_names = self._assistant_request_template_names(names)
        if not selected_names and selected_recipe in recipe_templates_map:
            selected_names = list(recipe_templates_map[selected_recipe])
        invalid_names = [name for name in selected_names if name not in all_templates]
        templates = {
            name: all_templates[name]
            for name in selected_names
            if name in all_templates
        } if selected_names else all_templates
        confirmation_required = [
            name
            for name, item in templates.items()
            if bool((item or {}).get("requires_confirmation"))
        ]
        safe_without_confirmation = [
            name
            for name, item in templates.items()
            if not bool((item or {}).get("requires_confirmation"))
        ]
        write_side_effects = [
            name
            for name, item in templates.items()
            if self._clean_text((item or {}).get("side_effect")) in {"write", "depends_on_action", "depends_on_session", "depends_on_text"}
        ]
        cacheable_templates = [
            name
            for name, item in templates.items()
            if self._safe_int((item or {}).get("cache_ttl_seconds"), 0) > 0
        ]
        non_cacheable_templates = [
            name
            for name, item in templates.items()
            if self._safe_int((item or {}).get("cache_ttl_seconds"), 0) <= 0
        ]
        auth = {
            "mode": "query_apikey",
            "query_param": "apikey",
            "url_template": "{base_url}{endpoint}?apikey={MP_API_TOKEN}",
            "description": "调用插件 HTTP 接口时推荐使用 ?apikey=你的MP_API_TOKEN；MP Tool 调用不需要此参数。",
        }
        recommended_sequence = [
            {
                "step": "bootstrap",
                "template": "startup_probe",
                "when": "每次新会话开始时先读取启动聚合包。",
            },
            {
                "step": "healthcheck",
                "template": "selfcheck_probe",
                "when": "当外部智能体需要确认协议健康或怀疑环境变化时执行。",
            },
            {
                "step": "maintenance_preview",
                "template": "maintain_preview",
                "when": "长会话或多轮执行前先看是否有低风险维护建议。",
            },
            {
                "step": "plan",
                "template": "workflow_dry_run",
                "when": "需要先生成计划、等待用户确认或减少重复大 JSON 时使用。",
            },
            {
                "step": "execute_saved_plan",
                "template": "saved_plan_execute",
                "when": "已确认 dry_run 计划后执行。",
            },
            {
                "step": "continue_session",
                "template": "pick_continue",
                "when": "盘搜、影巢候选或资源列表需要按编号继续时使用。",
            },
            {
                "step": "mp_pt_mainline",
                "template": "mp_search",
                "when": "需要 MP 原生 PT 搜索、评分、下载计划、订阅或任务追踪时使用。",
            },
            {
                "step": "mp_recommendation",
                "template": "mp_recommend",
                "when": "需要 TMDB、豆瓣、Bangumi 等 MP 原生推荐，并继续搜索时使用。",
            },
        ]
        recipes = [
            {
                "name": "safe_bootstrap",
                "description": "新会话安全启动：先拿启动聚合包，再自检，再看维护建议。",
                "templates": recipe_templates_map["safe_bootstrap"],
            },
            {
                "name": "plan_then_confirm",
                "description": "先生成计划，等待用户确认后再执行保存计划。",
                "templates": recipe_templates_map["plan_then_confirm"],
            },
            {
                "name": "continue_existing_session",
                "description": "已有盘搜、影巢或资源会话时，直接按编号继续。",
                "templates": recipe_templates_map["continue_existing_session"],
            },
            {
                "name": "maintenance_cycle",
                "description": "先预览维护建议，再在确认后执行低风险维护。",
                "templates": recipe_templates_map["maintenance_cycle"],
            },
            {
                "name": "external_agent_quickstart",
                "description": "外部智能体接入：启动探测后，把用户文本交给统一入口，再按编号继续。",
                "templates": recipe_templates_map["external_agent_quickstart"],
            },
            {
                "name": "workbuddy_quickstart",
                "description": "兼容别名：等同于 external_agent_quickstart。",
                "templates": recipe_templates_map["workbuddy_quickstart"],
            },
            {
                "name": "mp_pt_mainline",
                "description": "MP 原生 PT 主线：识别、搜索、评分、下载计划、任务、订阅、站点和入库追踪。",
                "templates": recipe_templates_map["mp_pt_mainline"],
            },
            {
                "name": "mp_recommendation",
                "description": "MP 原生推荐主线：读取热门推荐，再按编号进入 MP、影巢或盘搜搜索。",
                "templates": recipe_templates_map["mp_recommendation"],
            },
        ]
        recipe_summaries: List[Dict[str, Any]] = []
        for recipe in recipes:
            template_names = [
                self._clean_text(item)
                for item in (recipe.get("templates") or [])
                if self._clean_text(item)
            ]
            current_templates = [
                templates[name]
                for name in template_names
                if isinstance(templates.get(name), dict)
            ]
            recipe_summaries.append({
                **recipe,
                "requires_confirmation": any(bool(item.get("requires_confirmation")) for item in current_templates),
                "has_write_effect": any(
                    self._clean_text(item.get("side_effect")) in {"write", "depends_on_action", "depends_on_session", "depends_on_text"}
                    for item in current_templates
                ),
                "cache_ttl_seconds": min(
                    [self._safe_int(item.get("cache_ttl_seconds"), 0) for item in current_templates] or [0]
                ),
            })
        recommended_recipe = "safe_bootstrap"
        recommended_recipe_reason = "默认优先安全启动，先读取启动聚合包、自检并查看维护建议。"
        selected_set = set(selected_names or [])
        if selected_recipe in recipe_templates_map:
            recommended_recipe = selected_recipe
            recommended_recipe_reason = f"当前请求显式指定 recipe={selected_recipe}。"
        elif {"workflow_dry_run", "saved_plan_execute"} & selected_set:
            recommended_recipe = "plan_then_confirm"
            recommended_recipe_reason = "当前模板集合包含 dry_run 或执行保存计划，更适合先计划后确认。"
        elif "pick_continue" in selected_set:
            recommended_recipe = "continue_existing_session"
            recommended_recipe_reason = "当前模板集合包含 pick_continue，说明更像继续既有会话。"
        elif {"maintain_preview", "maintain_execute"} & selected_set:
            recommended_recipe = "maintenance_cycle"
            recommended_recipe_reason = "当前模板集合包含维护模板，优先推荐维护流程。"
        recommended_recipe_detail = next(
            (item for item in recipe_summaries if item.get("name") == recommended_recipe),
            {},
        )
        recommended_recipe_templates = [
            name
            for name in (recommended_recipe_detail.get("templates") or [])
            if name in all_templates
        ]
        first_template = recommended_recipe_templates[0] if recommended_recipe_templates else ""
        first_template_data = all_templates.get(first_template) or {}
        recommended_recipe_calls = []
        for template_name in recommended_recipe_templates:
            template_data = all_templates.get(template_name) or {}
            if not template_data:
                continue
            recommended_recipe_calls.append({
                "template": template_name,
                "auth": auth,
                "method": template_data.get("method"),
                "endpoint": template_data.get("endpoint"),
                "url_template": "{base_url}{endpoint}?apikey={MP_API_TOKEN}".replace(
                    "{endpoint}",
                    self._clean_text(template_data.get("endpoint")),
                ),
                "query": template_data.get("query") or {},
                "body": template_data.get("body") or {},
                "tool": template_data.get("tool"),
                "tool_args": template_data.get("tool_args") or {},
                "requires_confirmation": bool(template_data.get("requires_confirmation")),
                "side_effect": template_data.get("side_effect"),
            })
        recommended_recipe_detail = {
            **recommended_recipe_detail,
            "templates": recommended_recipe_templates,
            "first_template": first_template,
            "confirmation_required_templates": [
                name
                for name in recommended_recipe_templates
                if bool((all_templates.get(name) or {}).get("requires_confirmation"))
            ],
            "write_templates": [
                name
                for name in recommended_recipe_templates
                if self._clean_text((all_templates.get(name) or {}).get("side_effect")) in {"write", "depends_on_action", "depends_on_session", "depends_on_text"}
            ],
            "first_call": {
                "template": first_template,
                "auth": auth,
                "method": first_template_data.get("method"),
                "endpoint": first_template_data.get("endpoint"),
                "url_template": "{base_url}{endpoint}?apikey={MP_API_TOKEN}".replace(
                    "{endpoint}",
                    self._clean_text(first_template_data.get("endpoint")),
                ),
                "query": first_template_data.get("query") or {},
                "body": first_template_data.get("body") or {},
                "tool": first_template_data.get("tool"),
                "tool_args": first_template_data.get("tool_args") or {},
                "requires_confirmation": bool(first_template_data.get("requires_confirmation")),
                "side_effect": first_template_data.get("side_effect"),
            } if first_template_data else {},
            "calls": recommended_recipe_calls,
        }
        confirmation_templates = recommended_recipe_detail.get("confirmation_required_templates") or []
        recommended_recipe_detail["first_confirmation_template"] = confirmation_templates[0] if confirmation_templates else ""
        recommended_recipe_detail["confirmation_message"] = (
            f"执行 {recommended_recipe} 的 {recommended_recipe_detail['first_confirmation_template']} 前需要用户确认。"
            if confirmation_templates
            else f"{recommended_recipe} 当前推荐流程无需用户确认。"
        )
        return {
            "protocol_version": "assistant.v1",
            "action": "request_templates",
            "ok": True,
            "compact": True,
            "version": self.plugin_version,
            "schema_version": self.request_templates_schema_version,
            "auth": auth,
            "templates_included": bool(include_templates),
            "request_templates": templates if include_templates else {},
            "available_names": list(all_templates.keys()),
            "available_recipes": list(recipe_templates_map.keys()),
            "recipe_aliases": recipe_aliases,
            "selected_names": selected_names,
            "invalid_names": invalid_names,
            "requested_recipe": requested_recipe,
            "selected_recipe": selected_recipe if selected_recipe in recipe_templates_map else "",
            "invalid_recipe": invalid_recipe,
            "execution_policy": {
                "safe_without_confirmation": safe_without_confirmation,
                "confirmation_required": confirmation_required,
                "write_side_effects": write_side_effects,
                "cacheable_templates": cacheable_templates,
                "non_cacheable_templates": non_cacheable_templates,
            },
            "recommended_sequence": recommended_sequence,
            "recipes": recipe_summaries,
            "recommended_recipe": recommended_recipe,
            "recommended_recipe_reason": recommended_recipe_reason,
            "recommended_recipe_detail": recommended_recipe_detail,
        }

    def _format_assistant_request_templates_text(self, data: Optional[Dict[str, Any]] = None) -> str:
        payload = data or self._assistant_request_templates_response_data()
        templates = payload.get("request_templates") or {}
        lines = [
            "Agent影视助手 请求模板",
            f"版本：{payload.get('version')}",
        ]
        detail = payload.get("recommended_recipe_detail") or {}
        first_call = detail.get("first_call") or {}
        if payload.get("recommended_recipe"):
            lines.append(f"推荐流程：{payload.get('recommended_recipe')}")
        if detail.get("first_template"):
            lines.append(
                "首步：{template} -> {method} {endpoint}".format(
                    template=detail.get("first_template"),
                    method=first_call.get("method") or "",
                    endpoint=first_call.get("endpoint") or "",
                ).strip()
            )
        if detail.get("confirmation_message"):
            lines.append(f"确认提示：{detail.get('confirmation_message')}")
        for name in [
            "startup_probe",
            "selfcheck_probe",
            "maintain_preview",
            "maintain_execute",
            "workflow_dry_run",
            "saved_plan_execute",
            "action_execute",
            "pick_continue",
        ]:
            item = templates.get(name) or {}
            if item:
                tool = self._clean_text(item.get("tool"))
                suffix = f" -> {tool}" if tool else ""
                lines.append(f"{name}: {item.get('method')} {item.get('endpoint')}{suffix}")
        return "\n".join(lines)

    def _format_assistant_toolbox_text(self) -> str:
        data = self._assistant_toolbox_public_data()
        workflows = data.get("workflows") or []
        lines = [
            "Agent影视助手 轻量工具清单",
            f"版本：{data.get('version')}",
            "推荐启动顺序：" + " -> ".join(str(item) for item in (data.get("startup_order") or [])[:5]),
            "常用工作流：" + " / ".join(str(item.get("name")) for item in workflows if item.get("name")),
            "默认目录：115={p115_path}；夸克={quark_path}；影巢={hdhive_path}".format(**(data.get("defaults") or {})),
        ]
        return "\n".join(lines)

    def _assistant_selfcheck_public_data(self) -> Dict[str, Any]:
        action_template = self._assistant_action_template(
            name="show_115_status",
            description="自检模板：查看 115 状态",
            endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/action",
            tool="agent_resource_officer_execute_action",
            body={"session": "selfcheck"},
        )
        route_template = self._assistant_action_template(
            name="start_hdhive_search",
            description="自检模板：发起影巢搜索",
            endpoint="/api/v1/plugin/AgentResourceOfficer/assistant/route",
            tool="agent_resource_officer_smart_entry",
            body={"session": "selfcheck", "keyword": "蜘蛛侠", "media_type": "movie"},
        )
        bool_cases = {
            "true": self._parse_bool_value("true", False),
            "false": self._parse_bool_value("false", True),
            "one": self._parse_bool_value("1", False),
            "zero": self._parse_bool_value("0", True),
            "off": self._parse_bool_value("off", True),
            "default_true": self._parse_bool_value(None, True),
            "default_false": self._parse_bool_value(None, False),
        }
        compact_templates_ok = all([
            (action_template.get("body") or {}).get("compact") is True,
            (action_template.get("action_body") or {}).get("compact") is True,
            (route_template.get("body") or {}).get("compact") is True,
            (route_template.get("action_body") or {}).get("compact") is True,
        ])
        bool_parse_ok = (
            bool_cases["true"] is True
            and bool_cases["false"] is False
            and bool_cases["one"] is True
            and bool_cases["zero"] is False
            and bool_cases["off"] is False
            and bool_cases["default_true"] is True
            and bool_cases["default_false"] is False
        )
        pulse = self._assistant_pulse_public_data()
        toolbox = self._assistant_toolbox_public_data()
        startup_request_templates = self._assistant_recommended_request_templates_data()
        startup_continue_request_templates = self._assistant_recommended_request_templates_data(
            recipe="continue",
            reason="selfcheck",
        )
        maintain = self._assistant_maintain_public_data(execute=False)
        request_templates = self._assistant_request_templates_public_data(limit=100)
        filtered_request_templates = self._assistant_request_templates_response_data(
            limit=5,
            names="maintain_execute,missing_template",
        )
        recipe_request_templates = self._assistant_request_templates_response_data(
            limit=5,
            names="startup_probe,maintain_preview,workflow_dry_run,saved_plan_execute,pick_continue,maintain_execute",
            include_templates=False,
        )
        recipe_filtered_request_templates = self._assistant_request_templates_response_data(
            limit=5,
            recipe="plan",
            include_templates=False,
        )
        policy_only_request_templates = self._assistant_request_templates_response_data(
            limit=5,
            names="maintain_execute",
            include_templates=False,
        )
        maintenance_templates = maintain.get("action_templates") or []
        maintenance_template_names = {
            self._clean_text(item.get("name"))
            for item in maintenance_templates
            if isinstance(item, dict)
        }
        maintenance_templates_compact_ok = all(
            (item.get("body") or {}).get("compact") is True
            and (item.get("action_body") or {}).get("compact") is True
            for item in maintenance_templates
            if isinstance(item, dict)
        )
        maintain_dry_run_ok = (
            maintain.get("action") == "maintain"
            and maintain.get("execute_requested") is False
            and maintain.get("executed") is False
            and {"clear_stale_sessions", "clear_executed_plans"}.issubset(maintenance_template_names)
        )
        protocol_ok = (
            pulse.get("protocol_version") == "assistant.v1"
            and toolbox.get("protocol_version") == "assistant.v1"
            and pulse.get("action") == "pulse"
            and toolbox.get("action") == "toolbox"
            and maintain.get("protocol_version") == "assistant.v1"
        )
        startup_request_templates_ok = (
            startup_request_templates.get("recipe") == "bootstrap"
            and startup_request_templates.get("include_templates") is False
            and startup_request_templates.get("tool") == "agent_resource_officer_request_templates"
            and "{MP_API_TOKEN}" in self._clean_text(startup_request_templates.get("url_template"))
            and startup_continue_request_templates.get("recipe") == "continue"
            and ((startup_continue_request_templates.get("tool_args") or {}).get("recipe")) == "continue"
            and bool(self._clean_text(startup_continue_request_templates.get("reason")))
        )
        request_templates_ok = all(
            isinstance(request_templates.get(name), dict)
            and self._clean_text((request_templates.get(name) or {}).get("endpoint"))
            and self._clean_text((request_templates.get(name) or {}).get("method"))
            and self._clean_text((request_templates.get(name) or {}).get("tool"))
            and self._clean_text((request_templates.get(name) or {}).get("description"))
            and self._clean_text((request_templates.get(name) or {}).get("side_effect"))
            and isinstance((request_templates.get(name) or {}).get("requires_confirmation"), bool)
            and self._clean_text((request_templates.get(name) or {}).get("cache_scope"))
            and isinstance((request_templates.get(name) or {}).get("cache_ttl_seconds"), int)
            and isinstance((request_templates.get(name) or {}).get("tool_args"), dict)
            for name in [
                "startup_probe",
                "selfcheck_probe",
                "maintain_preview",
                "maintain_execute",
                "workflow_dry_run",
                "saved_plan_execute",
                "action_execute",
                "route_text",
                "pick_continue",
            ]
        )
        request_templates_filter_ok = (
            list((filtered_request_templates.get("request_templates") or {}).keys()) == ["maintain_execute"]
            and filtered_request_templates.get("selected_names") == ["maintain_execute", "missing_template"]
            and filtered_request_templates.get("invalid_names") == ["missing_template"]
            and (((filtered_request_templates.get("request_templates") or {}).get("maintain_execute") or {}).get("body") or {}).get("limit") == 5
        )
        request_templates_policy_ok = (
            "maintain_execute" in ((filtered_request_templates.get("execution_policy") or {}).get("confirmation_required") or [])
            and "maintain_execute" in ((filtered_request_templates.get("execution_policy") or {}).get("write_side_effects") or [])
        )
        request_templates_schema_ok = filtered_request_templates.get("schema_version") == self.request_templates_schema_version
        request_templates_cache_ok = (
            ((filtered_request_templates.get("request_templates") or {}).get("maintain_execute") or {}).get("cache_scope") == "no_cache"
            and (((filtered_request_templates.get("request_templates") or {}).get("maintain_execute") or {}).get("cache_ttl_seconds")) == 0
        )
        request_templates_sequence_ok = (
            isinstance(filtered_request_templates.get("recommended_sequence"), list)
            and any(
                isinstance(item, dict) and self._clean_text(item.get("template")) == "startup_probe"
                for item in (filtered_request_templates.get("recommended_sequence") or [])
            )
            and any(
                isinstance(item, dict) and self._clean_text(item.get("template")) == "saved_plan_execute"
                for item in (filtered_request_templates.get("recommended_sequence") or [])
            )
        )
        request_templates_recipes_ok = (
            isinstance(recipe_request_templates.get("recipes"), list)
            and any(
                isinstance(item, dict) and self._clean_text(item.get("name")) == "safe_bootstrap"
                for item in (recipe_request_templates.get("recipes") or [])
            )
            and any(
                isinstance(item, dict) and self._clean_text(item.get("name")) == "plan_then_confirm"
                for item in (recipe_request_templates.get("recipes") or [])
            )
        )
        request_templates_recipe_summary_ok = (
            any(
                isinstance(item, dict)
                and self._clean_text(item.get("name")) == "safe_bootstrap"
                and item.get("requires_confirmation") is False
                and item.get("has_write_effect") is False
                for item in (recipe_request_templates.get("recipes") or [])
            )
            and any(
                isinstance(item, dict)
                and self._clean_text(item.get("name")) == "plan_then_confirm"
                and item.get("requires_confirmation") is True
                and item.get("has_write_effect") is True
                for item in (recipe_request_templates.get("recipes") or [])
            )
        )
        request_templates_recommended_recipe_ok = (
            filtered_request_templates.get("recommended_recipe") == "maintenance_cycle"
            and bool(self._clean_text(filtered_request_templates.get("recommended_recipe_reason")))
            and recipe_request_templates.get("recommended_recipe") == "plan_then_confirm"
        )
        request_templates_recipe_filter_ok = (
            recipe_filtered_request_templates.get("requested_recipe") == "plan"
            and recipe_filtered_request_templates.get("selected_recipe") == "plan_then_confirm"
            and recipe_filtered_request_templates.get("selected_names") == ["workflow_dry_run", "saved_plan_execute"]
            and recipe_filtered_request_templates.get("recommended_recipe") == "plan_then_confirm"
            and recipe_filtered_request_templates.get("templates_included") is False
            and "plan_then_confirm" in (recipe_filtered_request_templates.get("available_recipes") or [])
            and ((recipe_filtered_request_templates.get("recipe_aliases") or {}).get("plan")) == "plan_then_confirm"
        )
        recommended_recipe_detail = filtered_request_templates.get("recommended_recipe_detail") or {}
        request_templates_recommended_recipe_detail_ok = (
            recommended_recipe_detail.get("name") == "maintenance_cycle"
            and recommended_recipe_detail.get("first_template") == "maintain_preview"
            and "maintain_execute" in (recommended_recipe_detail.get("confirmation_required_templates") or [])
            and "maintain_execute" in (recommended_recipe_detail.get("write_templates") or [])
            and recommended_recipe_detail.get("first_confirmation_template") == "maintain_execute"
            and "maintain_execute" in self._clean_text(recommended_recipe_detail.get("confirmation_message"))
            and ((recommended_recipe_detail.get("first_call") or {}).get("template")) == "maintain_preview"
            and (((recommended_recipe_detail.get("first_call") or {}).get("auth") or {}).get("mode")) == "query_apikey"
            and self._clean_text((recommended_recipe_detail.get("first_call") or {}).get("url_template")).endswith(
                "/assistant/maintain?apikey={MP_API_TOKEN}"
            )
            and ((recommended_recipe_detail.get("first_call") or {}).get("method")) == "GET"
            and ((recommended_recipe_detail.get("first_call") or {}).get("tool")) == "agent_resource_officer_maintain"
            and [
                (item or {}).get("template")
                for item in (recommended_recipe_detail.get("calls") or [])
            ] == ["maintain_preview", "maintain_execute"]
            and all(
                (((item or {}).get("auth") or {}).get("query_param")) == "apikey"
                for item in (recommended_recipe_detail.get("calls") or [])
            )
            and all(
                "{MP_API_TOKEN}" in self._clean_text((item or {}).get("url_template"))
                for item in (recommended_recipe_detail.get("calls") or [])
            )
        )
        request_templates_policy_only_ok = (
            policy_only_request_templates.get("templates_included") is False
            and (policy_only_request_templates.get("request_templates") or {}) == {}
            and policy_only_request_templates.get("selected_names") == ["maintain_execute"]
            and "maintain_execute" in ((policy_only_request_templates.get("execution_policy") or {}).get("confirmation_required") or [])
            and "maintain_execute" in ((policy_only_request_templates.get("execution_policy") or {}).get("non_cacheable_templates") or [])
        )
        start_new_recovery = self._assistant_recovery_public_data(
            session_state={"has_session": False},
            action_templates=[{"name": "start_pansou_search", "tool": "agent_resource_officer_smart_entry"}],
        )
        start_new_recovery_ok = (
            start_new_recovery.get("mode") == "start_new"
            and start_new_recovery.get("can_resume") is False
            and start_new_recovery.get("recommended_action") == "start_pansou_search"
        )
        checks = {
            "compact_templates": compact_templates_ok,
            "bool_parser": bool_parse_ok,
            "protocol": protocol_ok,
            "maintain_dry_run": maintain_dry_run_ok,
            "maintenance_templates_compact": maintenance_templates_compact_ok,
            "request_templates": request_templates_ok,
            "request_templates_filter": request_templates_filter_ok,
            "request_templates_policy": request_templates_policy_ok,
            "request_templates_schema": request_templates_schema_ok,
            "request_templates_cache": request_templates_cache_ok,
            "request_templates_sequence": request_templates_sequence_ok,
            "request_templates_recipes": request_templates_recipes_ok,
            "request_templates_recipe_summary": request_templates_recipe_summary_ok,
            "request_templates_recommended_recipe": request_templates_recommended_recipe_ok,
            "request_templates_recipe_filter": request_templates_recipe_filter_ok,
            "request_templates_recommended_recipe_detail": request_templates_recommended_recipe_detail_ok,
            "request_templates_policy_only": request_templates_policy_only_ok,
            "startup_request_templates": startup_request_templates_ok,
            "start_new_recovery_not_resumable": start_new_recovery_ok,
            "toolbox_startup_endpoint": bool((toolbox.get("endpoints") or {}).get("startup")),
            "toolbox_maintain_endpoint": bool((toolbox.get("endpoints") or {}).get("maintain")),
            "toolbox_request_templates_endpoint": bool((toolbox.get("endpoints") or {}).get("request_templates")),
            "toolbox_maintain_tool": bool((toolbox.get("tools") or {}).get("maintain")),
            "toolbox_request_templates_tool": bool((toolbox.get("tools") or {}).get("request_templates")),
            "toolbox_selfcheck_endpoint": bool((toolbox.get("endpoints") or {}).get("selfcheck")),
        }
        ok = all(bool(value) for value in checks.values())
        return {
            "protocol_version": "assistant.v1",
            "action": "selfcheck",
            "ok": ok,
            "compact": True,
            "version": self.plugin_version,
            "checks": checks,
            "bool_cases": bool_cases,
            "template_samples": {
                "action": {
                    "name": action_template.get("name"),
                    "body_compact": (action_template.get("body") or {}).get("compact"),
                    "action_body_compact": (action_template.get("action_body") or {}).get("compact"),
                },
                "route": {
                    "name": route_template.get("name"),
                    "body_compact": (route_template.get("body") or {}).get("compact"),
                    "action_body_compact": (route_template.get("action_body") or {}).get("compact"),
                },
                "request_templates": {
                    name: {
                        "method": (request_templates.get(name) or {}).get("method"),
                        "endpoint": (request_templates.get(name) or {}).get("endpoint"),
                    }
                    for name in ["maintain_execute", "workflow_dry_run", "saved_plan_execute"]
                },
            },
            "next_actions": ["assistant_startup", "assistant_maintain", "assistant_pulse", "assistant_toolbox", "assistant_readiness"],
            "recommended_endpoints": {
                "startup": "/api/v1/plugin/AgentResourceOfficer/assistant/startup",
                "maintain": "/api/v1/plugin/AgentResourceOfficer/assistant/maintain",
                "pulse": "/api/v1/plugin/AgentResourceOfficer/assistant/pulse",
                "toolbox": "/api/v1/plugin/AgentResourceOfficer/assistant/toolbox",
                "readiness": "/api/v1/plugin/AgentResourceOfficer/assistant/readiness?compact=true",
            },
        }

    def _format_assistant_selfcheck_text(self) -> str:
        data = self._assistant_selfcheck_public_data()
        checks = data.get("checks") or {}
        failed = [key for key, value in checks.items() if not value]
        lines = [
            "Agent影视助手 协议自检",
            f"版本：{data.get('version')}",
            f"结果：{'通过' if data.get('ok') else '失败'}",
        ]
        if failed:
            lines.append("失败项：" + " / ".join(failed))
        return "\n".join(lines)

    def _assistant_response_data(
        self,
        *,
        session: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = dict(data or {})
        session_name = self._clean_text(session) or "default"
        session_state = self._assistant_session_public_data(session=session_name)
        payload["action"] = self._clean_text(payload.get("action")) or "assistant_response"
        payload["ok"] = bool(payload.get("ok", True))
        payload["write_effect"] = payload.get("write_effect") or self._assistant_write_effect_for_action(payload["action"])
        payload["error_code"] = self._clean_text(payload.get("error_code")) or ("" if payload["ok"] else "assistant_error")
        payload["protocol_version"] = "assistant.v1"
        payload["session"] = session_name
        payload["session_id"] = session_state.get("session_id") or self._assistant_session_id(session_name)
        payload["session_state"] = session_state
        payload["preference_status"] = payload.get("preference_status") or self._assistant_preferences_status_brief(session=session_name)
        payload["next_actions"] = payload.get("next_actions") or session_state.get("suggested_actions") or []
        if payload["preference_status"].get("needs_onboarding") and "preferences.init" not in payload["next_actions"]:
            payload["next_actions"] = ["preferences.init", *list(payload["next_actions"] or [])]
        payload["action_templates"] = payload.get("action_templates") or session_state.get("action_templates") or []
        payload["recovery"] = payload.get("recovery") or session_state.get("recovery") or self._assistant_recovery_public_data(session_state=session_state)
        return payload

    @staticmethod
    def _assistant_write_effect_for_action(action: str) -> str:
        action_name = str(action or "").strip()
        if action_name in {
            "share_route",
            "hdhive_unlock",
            "transfer_115",
            "quark_transfer",
            "p115_resume",
            "p115_cancel",
            "p115_qrcode_start",
            "p115_qrcode_check",
            "hdhive_checkin",
            "mp_download",
            "mp_download_control",
            "mp_subscribe",
            "mp_subscribe_control",
            "mp_subscribe_search",
            "pick_mp_download",
            "start_mp_subscribe",
            "start_mp_subscribe_search",
            "preferences_save",
            "preferences_reset",
            "execute_actions",
            "execute_plan",
            "maintain",
        }:
            return "write"
        if action_name in {"workflow_plan", "plans_clear", "session_clear", "sessions_clear"}:
            return "state"
        return "read"

    def _merge_assistant_structured_input(self, body: Dict[str, Any], parsed: Dict[str, str]) -> Dict[str, str]:
        merged = dict(parsed or {})
        body = dict(body or {})

        mode = self._clean_text(body.get("mode"))
        if mode in {"mp", "pansou", "hdhive"}:
            merged["mode"] = mode
        keyword = self._clean_text(body.get("keyword") or body.get("title"))
        if keyword:
            merged["keyword"] = keyword
        share_url = self._clean_text(body.get("url") or body.get("share_url"))
        if share_url:
            merged["url"] = share_url
        access_code = self._clean_text(body.get("access_code") or body.get("pwd") or body.get("code"))
        if access_code:
            merged["access_code"] = access_code
        path = self._resolve_pan_path_value(self._clean_text(body.get("path") or body.get("target_path")))
        if path:
            merged["path"] = path
        media_type = self._clean_text(body.get("media_type") or body.get("type")).lower()
        if media_type:
            merged["type"] = media_type
        year = self._clean_text(body.get("year"))
        if year:
            merged["year"] = year
        client_type = self._clean_text(body.get("client_type") or body.get("client"))
        if client_type:
            merged["client_type"] = P115TransferService.normalize_qrcode_client_type(client_type)
        if "is_gambler" in body:
            merged["is_gambler"] = "true" if self._parse_bool_value(body.get("is_gambler"), False) else "false"
        action = self._clean_text(body.get("action"))
        if action:
            merged["action"] = action
        plan_id = self._clean_text(body.get("plan_id") or body.get("plan"))
        if plan_id:
            merged["plan_id"] = plan_id
        download_control = self._clean_text(body.get("download_control") or body.get("control") or body.get("operation"))
        if download_control:
            merged["download_control"] = download_control
        subscribe_control = self._clean_text(body.get("subscribe_control") or body.get("control") or body.get("operation"))
        if subscribe_control:
            merged["subscribe_control"] = subscribe_control
        return merged

    @staticmethod
    def _parse_assistant_text(text: str) -> Dict[str, str]:
        raw = str(text or "").strip()
        compact = re.sub(r"\s+", "", raw).lower()
        share_url = AgentResourceOfficer._extract_first_url(raw)
        remain = raw.replace(share_url, " ").strip() if share_url else raw
        mode, query = AgentResourceOfficer._normalize_search_prefix(remain)
        plan_match = re.search(r"\bplan-[a-zA-Z0-9]+\b", raw)
        options: Dict[str, str] = {
            "text": raw,
            "url": share_url,
            "access_code": "",
            "path": "",
            "mode": mode,
            "keyword": query or remain,
            "type": "",
            "year": "",
            "action": "",
            "client_type": "",
            "status": "",
            "hash": "",
            "plan_id": plan_match.group(0) if plan_match else "",
        }
        if options.get("plan_id") and compact.startswith(("执行plan-", "确认plan-", "executeplan-")):
            options["action"] = "execute_plan"
            options["mode"] = ""
            options["keyword"] = ""
        elif options.get("plan_id") and compact.startswith(("取消plan-", "清理plan-", "删除plan-", "clearplan-", "cancelplan-")):
            options["action"] = "plans_clear"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "帮助",
            "使用帮助",
            "命令帮助",
            "help",
            "agenthelp",
            "arohelp",
            "插件帮助",
        }:
            options["action"] = "assistant_help"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "执行计划",
            "执行最新计划",
            "确认计划",
            "确认执行计划",
            "执行plan",
            "执行最新plan",
            "executeplan",
            "executelatestplan",
        }:
            options["action"] = "execute_plan"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "计划列表",
            "查看计划",
            "待执行计划",
            "保存计划",
            "plans",
            "listplans",
        }:
            options["action"] = "plans_list"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "偏好",
            "片源偏好",
            "查看偏好",
            "偏好设置",
            "智能体偏好",
            "preferences",
            "getpreferences",
        }:
            options["action"] = "preferences_get"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "重置偏好",
            "清除偏好",
            "重设偏好",
            "恢复默认偏好",
            "resetpreferences",
        }:
            options["action"] = "preferences_reset"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "取消计划",
            "清理计划",
            "删除计划",
            "cancelplan",
            "clearplan",
            "deleteplan",
        }:
            options["action"] = "plans_clear"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "115登录",
            "115扫码",
            "扫码115",
            "登录115",
            "115login",
            "115qrcode",
            "p115login",
            "p115qrcode",
        }:
            options["action"] = "p115_qrcode_start"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "检查115登录",
            "检查115扫码",
            "检查扫码",
            "115check",
            "check115login",
            "p115check",
        }:
            options["action"] = "p115_qrcode_check"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "115登录状态",
            "115状态",
            "查看115状态",
            "115健康",
            "115status",
            "p115status",
        }:
            options["action"] = "p115_status"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "115帮助",
            "115命令",
            "115使用",
            "115help",
            "p115help",
        }:
            options["action"] = "p115_help"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "115任务",
            "待处理115",
            "待继续115",
            "115pending",
            "p115pending",
        }:
            options["action"] = "p115_pending"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "继续115任务",
            "重试115任务",
            "继续115转存",
            "重试115转存",
            "continue115",
            "resume115",
        }:
            options["action"] = "p115_resume"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "取消115任务",
            "取消115转存",
            "清除115任务",
            "cancel115",
            "clear115",
        }:
            options["action"] = "p115_cancel"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "影巢签到",
            "签到",
            "hdhivecheckin",
            "hdhivesign",
        }:
            options["action"] = "hdhive_checkin"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "影巢签到日志",
            "签到日志",
            "影巢日志",
            "hdhivecheckinhistory",
            "hdhivesignhistory",
        }:
            options["action"] = "hdhive_checkin_history"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "影巢普通签到",
            "普通签到",
            "普通",
            "hdhivenormalcheckin",
        }:
            options["action"] = "hdhive_checkin"
            options["mode"] = ""
            options["keyword"] = ""
            options["is_gambler"] = "false"
        elif compact in {
            "影巢赌狗签到",
            "赌狗签到",
            "赌狗",
            "hdhivegamblercheckin",
            "gamblercheckin",
        }:
            options["action"] = "hdhive_checkin"
            options["mode"] = ""
            options["keyword"] = ""
            options["is_gambler"] = "true"
        elif compact in {
            "下载任务",
            "下载状态",
            "正在下载",
            "下载列表",
            "查看下载",
            "下载进度",
            "downloadtasks",
            "downloadstatus",
        }:
            options["action"] = "mp_download_tasks"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "下载最佳",
            "下载推荐",
            "下载最好",
            "下载最佳片源",
            "下载推荐片源",
            "downloadbest",
        }:
            options["action"] = "mp_download_best"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "下载历史",
            "下载记录",
            "最近下载",
            "历史下载",
            "downloadhistory",
        }:
            options["action"] = "mp_download_history"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "追踪",
            "资源追踪",
            "下载追踪",
            "媒体状态",
            "落库状态",
            "lifecyclestatus",
        }:
            options["action"] = "mp_lifecycle_status"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "识别",
            "媒体识别",
            "媒体详情",
            "mp识别",
            "mp媒体识别",
            "mpmediadetail",
        }:
            options["action"] = "mp_media_detail"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "下载器",
            "下载器状态",
            "下载器列表",
            "查看下载器",
            "downloaders",
        }:
            options["action"] = "mp_downloaders"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "站点",
            "站点状态",
            "站点列表",
            "pt站点",
            "pt站点状态",
            "sites",
        }:
            options["action"] = "mp_sites"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "订阅列表",
            "订阅状态",
            "查看订阅",
            "mp订阅",
            "subscribes",
        }:
            options["action"] = "mp_subscribes"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "入库历史",
            "整理历史",
            "转移历史",
            "最近入库",
            "最近整理",
            "transferhistory",
        }:
            options["action"] = "mp_transfer_history"
            options["mode"] = ""
            options["keyword"] = ""
        elif compact in {
            "入库失败",
            "整理失败",
            "失败入库",
            "失败整理",
            "transferfailed",
        }:
            options["action"] = "mp_transfer_history"
            options["mode"] = ""
            options["keyword"] = ""
            options["status"] = "failed"
        elif compact in {
            "入库成功",
            "整理成功",
            "成功入库",
            "成功整理",
            "transfersuccess",
        }:
            options["action"] = "mp_transfer_history"
            options["mode"] = ""
            options["keyword"] = ""
            options["status"] = "success"
        else:
            for prefix, action in [
                ("执行计划", "execute_plan"),
                ("执行", "execute_plan"),
                ("确认计划", "execute_plan"),
                ("确认", "execute_plan"),
                ("查看计划", "plans_list"),
                ("计划列表", "plans_list"),
                ("取消计划", "plans_clear"),
                ("清理计划", "plans_clear"),
                ("删除计划", "plans_clear"),
                ("保存偏好", "preferences_save"),
                ("设置偏好", "preferences_save"),
                ("更新偏好", "preferences_save"),
                ("偏好设置", "preferences_save"),
                ("偏好", "preferences_save"),
                ("查看偏好", "preferences_get"),
                ("片源偏好", "preferences_get"),
                ("重置偏好", "preferences_reset"),
                ("清除偏好", "preferences_reset"),
            ]:
                if raw.startswith(prefix + " ") or raw.startswith(prefix + "：") or raw.startswith(prefix + ":"):
                    remain_text = raw[len(prefix):].lstrip(" ：:").strip()
                    if action in {"plans_list", "preferences_get", "preferences_reset"} or options.get("plan_id") or remain_text:
                        options["action"] = action
                        options["mode"] = ""
                        options["keyword"] = ""
                        if remain_text and not options.get("plan_id"):
                            match = re.search(r"\bplan-[a-zA-Z0-9]+\b", remain_text)
                            if match:
                                options["plan_id"] = match.group(0)
                        break
            for prefix, control in [
                ("暂停下载", "pause"),
                ("停止下载", "pause"),
                ("恢复下载", "resume"),
                ("继续下载", "resume"),
                ("开始下载", "resume"),
                ("删除下载", "delete"),
                ("移除下载", "delete"),
            ]:
                prefix_match = AgentResourceOfficer._match_command_prefix(raw, [prefix])
                if prefix_match:
                    target_text = prefix_match[1]
                    if target_text:
                        options["action"] = "mp_download_control"
                        options["mode"] = ""
                        options["keyword"] = target_text
                        options["download_control"] = control
                    break
            if not options.get("action"):
                prefix_match = AgentResourceOfficer._match_command_prefix(raw, ["下载任务", "下载状态", "下载列表", "查看下载", "下载进度"])
                if prefix_match:
                    options["action"] = "mp_download_tasks"
                    options["mode"] = ""
                    options["keyword"] = prefix_match[1]
            if not options.get("action"):
                prefix_match = AgentResourceOfficer._match_command_prefix(raw, ["下载历史", "下载记录", "最近下载", "历史下载"])
                if prefix_match:
                    options["action"] = "mp_download_history"
                    options["mode"] = ""
                    options["keyword"] = prefix_match[1]
            if not options.get("action"):
                prefix_match = AgentResourceOfficer._match_command_prefix(raw, ["资源追踪", "下载追踪", "媒体状态", "落库状态", "追踪"])
                if prefix_match:
                    options["action"] = "mp_lifecycle_status"
                    options["mode"] = ""
                    options["keyword"] = prefix_match[1]
            if not options.get("action"):
                prefix_match = AgentResourceOfficer._match_command_prefix(raw, ["MP识别", "mp识别", "媒体识别", "媒体详情", "详情媒体", "识别"])
                if prefix_match:
                    options["action"] = "mp_media_detail"
                    options["mode"] = ""
                    options["keyword"] = prefix_match[1]
            if not options.get("action"):
                prefix_match = AgentResourceOfficer._match_command_prefix(raw, ["站点状态", "站点列表", "PT站点", "pt站点", "站点"])
                if prefix_match:
                    options["action"] = "mp_sites"
                    options["mode"] = ""
                    options["keyword"] = prefix_match[1]
            if not options.get("action"):
                for prefix, control in [
                    ("搜索订阅", "search"),
                    ("刷新订阅", "search"),
                    ("暂停订阅", "pause"),
                    ("恢复订阅", "resume"),
                    ("删除订阅", "delete"),
                    ("移除订阅", "delete"),
                ]:
                    prefix_match = AgentResourceOfficer._match_command_prefix(raw, [prefix])
                    if prefix_match:
                        target_text = prefix_match[1]
                        if target_text:
                            options["action"] = "mp_subscribe_control"
                            options["mode"] = ""
                            options["keyword"] = target_text
                            options["subscribe_control"] = control
                        break
            if not options.get("action"):
                prefix_match = AgentResourceOfficer._match_command_prefix(raw, ["订阅列表", "订阅状态", "查看订阅", "MP订阅", "mp订阅"])
                if prefix_match:
                    options["action"] = "mp_subscribes"
                    options["mode"] = ""
                    options["keyword"] = prefix_match[1]
            if not options.get("action"):
                for prefix, status_name in [
                    ("入库失败", "failed"),
                    ("整理失败", "failed"),
                    ("失败入库", "failed"),
                    ("失败整理", "failed"),
                    ("入库成功", "success"),
                    ("整理成功", "success"),
                    ("成功入库", "success"),
                    ("成功整理", "success"),
                    ("入库历史", "all"),
                    ("整理历史", "all"),
                    ("转移历史", "all"),
                    ("最近入库", "all"),
                    ("最近整理", "all"),
                ]:
                    prefix_match = AgentResourceOfficer._match_command_prefix(raw, [prefix])
                    if prefix_match:
                        options["action"] = "mp_transfer_history"
                        options["mode"] = ""
                        options["keyword"] = prefix_match[1]
                        options["status"] = status_name
                        break
            if not options.get("action"):
                for prefix, action in [
                    ("下载资源", "mp_download"),
                    ("下载", "mp_download"),
                    ("订阅并搜索", "mp_subscribe_search"),
                    ("订阅搜索", "mp_subscribe_search"),
                    ("订阅媒体", "mp_subscribe"),
                    ("订阅", "mp_subscribe"),
                    ("热门推荐", "mp_recommendations"),
                    ("推荐", "mp_recommendations"),
                ]:
                    if raw == prefix:
                        options["action"] = action
                        options["mode"] = ""
                        options["keyword"] = ""
                        break
                    if raw.startswith(prefix + " "):
                        options["action"] = action
                        options["mode"] = ""
                        options["keyword"] = raw[len(prefix):].strip()
                        break
                    if raw.startswith(prefix):
                        remain_text = raw[len(prefix):].strip()
                        if not remain_text:
                            continue
                        if action == "mp_download":
                            download_match = re.search(r"\d+", remain_text)
                            if not download_match:
                                continue
                            options["action"] = action
                            options["mode"] = ""
                            options["keyword"] = download_match.group(0)
                            break
                        options["action"] = action
                        options["mode"] = ""
                        options["keyword"] = remain_text
                        break
            if not options.get("action") and any(
                marker in compact
                for marker in [
                    "热门影视",
                    "热门电影",
                    "热门电视剧",
                    "热门剧集",
                    "最近热门",
                    "有什么热门",
                    "看看热门",
                    "影视推荐",
                    "电影推荐",
                    "剧集推荐",
                    "电视剧推荐",
                    "豆瓣热门",
                    "豆瓣top250",
                    "正在热映",
                    "今日番剧",
                    "每日放送",
                    "bangumi",
                    "tmdb热门",
                ]
            ):
                options["action"] = "mp_recommendations"
                options["mode"] = ""
                options["keyword"] = raw
        for token in remain.split():
            item = token.strip()
            if not item:
                continue
            if "=" in item:
                key, value = item.split("=", 1)
                key = key.strip().lower()
                value = value.strip()
                if key in {"pwd", "passcode", "code", "提取码"} and value:
                    options["access_code"] = value
                    continue
                if key in {"path", "dir", "目录", "位置"} and value:
                    options["path"] = AgentResourceOfficer._resolve_pan_path_value(value)
                    continue
                if key in {"type", "媒体类型"} and value:
                    options["type"] = value.strip().lower()
                    continue
                if key in {"year", "年份"} and value:
                    options["year"] = value.strip()
                    continue
                if key in {"client_type", "client", "客户端"} and value:
                    options["client_type"] = P115TransferService.normalize_qrcode_client_type(value)
                    continue
                if key in {"hash", "download_hash", "任务hash"} and value:
                    options["hash"] = value.strip()
                    continue
            if item.startswith("/") and not options["path"]:
                options["path"] = AgentResourceOfficer._resolve_pan_path_value(item)
        return options

    def _call_pansou_search(self, keyword: str) -> Tuple[bool, Dict[str, Any], str]:
        last_error = ""
        queries = [
            {"kw": keyword, "res": "merge", "src": "all"},
            {"kw": keyword},
            {"keyword": keyword},
        ]
        urls = []
        base_urls = []
        configured_base = self._clean_text(self._pansou_base_url).rstrip("/")
        if configured_base:
            base_urls.append(configured_base)
        for fallback_base in ("http://host.docker.internal:805", "http://127.0.0.1:805"):
            if fallback_base not in base_urls:
                base_urls.append(fallback_base)
        for query in queries:
            for base_url in base_urls:
                urls.append(f"{base_url}/api/search?{urlencode(query)}")
        data: Dict[str, Any] = {}
        for url in urls:
            try:
                request = UrlRequest(url=url, headers={"Accept": "application/json"})
                with urlopen(request, timeout=self._pansou_timeout) as response:
                    data = json.loads(response.read().decode("utf-8", "ignore"))
                break
            except Exception as exc:
                last_error = str(exc)
                data = {}
        if not data:
            return False, {}, f"盘搜请求失败：{last_error or '未知错误'}"
        ok = str(data.get("code")) == "0"
        if not ok:
            return False, data, str(data.get("message") or "盘搜搜索失败")
        return True, data, str(data.get("message") or "success")

    @staticmethod
    def _normalize_pansou_channel_name(channel: str) -> str:
        text = str(channel or "").strip().lower()
        if text == "115" or "115" in text:
            return "115"
        if "quark" in text:
            return "quark"
        return str(channel or "").strip() or "未知"

    def _collect_pansou_channel_items(
        self,
        merged: Dict[str, Any],
        channel_name: str,
        limit: int = 6,
    ) -> List[Dict[str, Any]]:
        raw_items = merged.get(channel_name) or []
        if not isinstance(raw_items, list):
            return []
        results: List[Dict[str, Any]] = []
        seen = set()
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            note = str(item.get("note") or "未命名资源").strip()
            password = str(item.get("password") or "").strip()
            source = str(item.get("source") or "").strip()
            dt = self._format_pansou_datetime(item.get("datetime"))
            key = (url, note)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "channel": self._normalize_pansou_channel_name(channel_name),
                    "url": url,
                    "password": password,
                    "note": note,
                    "source": source,
                    "datetime": dt,
                }
            )
            if len(results) >= limit:
                break
        return results

    def _format_pansou_text(self, keyword: str, items: List[Dict[str, Any]], total: int) -> str:
        count_115 = len([x for x in items if x.get("channel") == "115"])
        count_quark = len([x for x in items if x.get("channel") == "quark"])
        lines = [
            f"盘搜搜索：{keyword}",
            f"共找到 {total} 条结果，当前展示 115 {count_115} 条、夸克 {count_quark} 条：",
        ]
        for cached in items:
            idx = cached["index"]
            channel = cached["channel"]
            if idx == 1:
                lines.append("🟦 115 结果")
            elif channel == "quark" and idx == count_115 + 1:
                lines.append("🟨 夸克结果")
            lines.append(f"{idx}. [{channel}] {cached['note']}")
            detail_parts = []
            if cached.get("source"):
                detail_parts.append(cached["source"])
            if cached.get("datetime"):
                detail_parts.append(cached["datetime"])
            if detail_parts:
                lines.append(f"   {' · '.join(detail_parts)}")
            if cached.get("password"):
                lines.append(f"   提取码：{cached['password']}")
            score_label = self._format_score_label(cached)
            if score_label:
                lines.append(f"   评分：{score_label}")
                score = cached.get("score") if isinstance(cached.get("score"), dict) else {}
                hard_risks = score.get("hard_risk_reasons") or []
                risks = score.get("risk_reasons") or []
                risks = [risk for risk in risks if risk not in hard_risks]
                if hard_risks:
                    lines.append("   硬风险：" + "；".join(str(item) for item in hard_risks[:2]))
                elif risks:
                    lines.append("   提醒：" + "；".join(str(item) for item in risks[:2]))
            lines.append(f"   {cached['url']}")
        next_quark_hint = count_115 + 1 if count_quark else 1
        lines.append("下一步：建议先回复“计划选择 1”生成待确认计划；确认后再回复“执行计划”。")
        if count_quark:
            lines.append(f"夸克结果从 {next_quark_hint} 开始编号；例如“计划选择 {next_quark_hint}”会为第 1 条夸克结果生成计划。")
        lines.append(f"如需改目录，可发“计划选择 1 path=/目录”或“计划选择 {next_quark_hint} path=/目录”。")
        lines.append("只有明确要立即转存时，才直接回复“选择 编号”。")
        return "\n".join(lines)

    @classmethod
    def _read_tmdb_api_key(cls) -> str:
        for value in [
            os.environ.get("TMDB_API_KEY", ""),
            os.environ.get("TMDB_KEY", ""),
            cls._clean_text(getattr(settings, "TMDB_API_KEY", "") if settings is not None else ""),
        ]:
            if cls._clean_text(value):
                return cls._clean_text(value)
        compose_path = Path("/Applications/Dockge/moviepilot-ai-recognizer-gateway/docker-compose.yml")
        if compose_path.exists():
            for line in compose_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if "TMDB_API_KEY" not in line:
                    continue
                _, _, value = line.partition(":")
                key = cls._clean_text(value.strip().strip("'\""))
                if key:
                    return key
        return ""

    @classmethod
    def _fetch_candidate_actors(cls, tmdb_id: Any, media_type: str) -> List[str]:
        clean_tmdb_id = cls._clean_text(tmdb_id)
        clean_media_type = cls._clean_text(media_type).lower()
        if not clean_tmdb_id or clean_media_type not in {"movie", "tv"}:
            return []
        cache_key = f"{clean_media_type}:{clean_tmdb_id}"
        with cls._candidate_actor_cache_lock:
            cached = cls._candidate_actor_cache.get(cache_key)
        if cached is not None:
            return list(cached)
        tmdb_api_key = cls._read_tmdb_api_key()
        if not tmdb_api_key:
            return []
        endpoint = "movie" if clean_media_type == "movie" else "tv"
        url = (
            f"https://api.themoviedb.org/3/{endpoint}/{clean_tmdb_id}?"
            f"{urlencode({'api_key': tmdb_api_key, 'language': 'zh-CN', 'append_to_response': 'credits'})}"
        )
        actors: List[str] = []
        try:
            request = UrlRequest(url=url, headers={"Accept": "application/json"})
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8", "ignore"))
            cast = ((payload.get("credits") or {}).get("cast") or []) if isinstance(payload, dict) else []
            for member in cast[:10]:
                name = cls._clean_text((member or {}).get("name"))
                department = cls._clean_text((member or {}).get("known_for_department"))
                if not name:
                    continue
                if department and department != "Acting":
                    continue
                if name not in actors:
                    actors.append(name)
                if len(actors) >= 2:
                    break
        except Exception:
            actors = []
        with cls._candidate_actor_cache_lock:
            cls._candidate_actor_cache[cache_key] = list(actors)
        return actors

    def _maybe_enrich_hdhive_candidate_with_actors(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(candidate or {})
        if enriched.get("actors"):
            return enriched
        enriched["actors"] = self._fetch_candidate_actors(
            enriched.get("tmdb_id"),
            str(enriched.get("media_type") or enriched.get("type") or ""),
        )
        return enriched

    def _enrich_hdhive_candidates_with_actors(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        indexed = [(idx, dict(item or {})) for idx, item in enumerate(candidates)]
        pending = [(idx, item) for idx, item in indexed if not (item.get("actors") or [])]
        enriched_map: Dict[int, Dict[str, Any]] = {idx: item for idx, item in indexed}
        if pending:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(pending))) as executor:
                future_map = {
                    executor.submit(self._maybe_enrich_hdhive_candidate_with_actors, item): idx
                    for idx, item in pending
                }
                for future in concurrent.futures.as_completed(future_map):
                    idx = future_map[future]
                    try:
                        enriched_map[idx] = future.result()
                    except Exception:
                        enriched_map[idx] = dict(indexed[idx][1])
        return [enriched_map[idx] for idx, _ in indexed]

    @staticmethod
    def _format_candidate_label(item: Dict[str, Any]) -> str:
        title = str(item.get("title") or "未命名")
        year = str(item.get("year") or "?")
        media_type = str(item.get("media_type") or item.get("type") or "?")
        actors = item.get("actors") or []
        parts = [year, media_type]
        actor_text = " / ".join(str(name).strip() for name in actors[:2] if str(name).strip())
        if actor_text:
            parts.append(f"主演:{actor_text}")
        return f"{title} ({' | '.join([part for part in parts if part])})"

    @staticmethod
    def _format_candidate_lines(candidates: List[Dict[str, Any]], page: int = 1, page_size: int = 10) -> str:
        if not candidates:
            return "候选影片：0 个"
        safe_page_size = max(1, int(page_size or 10))
        total_pages = max(1, (len(candidates) + safe_page_size - 1) // safe_page_size)
        safe_page = min(max(1, int(page or 1)), total_pages)
        start = (safe_page - 1) * safe_page_size
        page_items = candidates[start:start + safe_page_size]
        lines = [f"候选影片：{len(candidates)} 个，请先选择影片："]
        if total_pages > 1:
            lines.append(f"当前第 {safe_page}/{total_pages} 页，每页 {safe_page_size} 条：")
        for idx, item in enumerate(page_items, start=start + 1):
            lines.append(f"{idx}. {AgentResourceOfficer._format_candidate_label(item)}")
        lines.append("下一步：回复“选择 编号”查看该影片的影巢资源。")
        lines.append("如需补充当前候选页全部主演，可回复：详情 或 审查。")
        if safe_page < total_pages:
            lines.append("如需继续翻页，可回复：n 下一页")
        return "\n".join(lines)

    @staticmethod
    def _list_text(value: Any, separator: str = "/") -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple, set)):
            parts = [str(item).strip() for item in value if str(item).strip()]
            return separator.join(parts)
        return str(value).strip()

    @staticmethod
    def _truncate_text(value: Any, limit: int = 140) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if not text:
            return ""
        if len(text) <= limit:
            return text
        return f"{text[: max(0, limit - 1)]}…"

    @staticmethod
    def _resource_points_text(item: Dict[str, Any]) -> str:
        points = item.get("unlock_points")
        if points is None:
            points = item.get("cost")
        if points in (0, "0"):
            return "免费"
        if points in (None, "", "未知"):
            return "积分未知"
        return f"{points}分"

    @staticmethod
    def _resource_subtitle_text(item: Dict[str, Any]) -> str:
        language = AgentResourceOfficer._list_text(
            item.get("subtitle_language")
            or item.get("subtitle_languages")
            or item.get("subtitles")
            or item.get("subtitle")
        )
        subtitle_type = AgentResourceOfficer._list_text(item.get("subtitle_type") or item.get("subtitle_types"))
        if language and subtitle_type:
            return f"{language} · {subtitle_type}"
        return language or subtitle_type

    @staticmethod
    def _resource_episode_text(item: Dict[str, Any]) -> str:
        explicit_keys = [
            "episode_range",
            "episodes_range",
            "episode_info",
            "episodes",
            "episode",
            "update_status",
            "update_info",
            "season_episode",
        ]
        for key in explicit_keys:
            text = AgentResourceOfficer._list_text(item.get(key))
            if text:
                return AgentResourceOfficer._truncate_text(text, 40)

        source_text = " ".join(
            str(item.get(key) or "")
            for key in ["title", "remark", "description", "desc", "detail", "note"]
        )
        patterns = [
            r"(全\s*\d+\s*集)",
            r"(全集)",
            r"(更新至\s*第?\s*\d+\s*集)",
            r"(更\s*\d+\s*集)",
            r"(第?\s*\d+\s*[-~到至]\s*\d+\s*集)",
            r"(\d+\s*-\s*\d+\s*集)",
            r"(S\d{1,2}E\d{1,3}(?:\s*[-~]\s*E?\d{1,3})?)",
            r"(EP?\s*\d{1,3}(?:\s*[-~]\s*EP?\s*\d{1,3})?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, source_text, flags=re.IGNORECASE)
            if match:
                return re.sub(r"\s+", "", match.group(1))
        return ""

    @staticmethod
    def _resource_remark_text(item: Dict[str, Any]) -> str:
        for key in ["remark", "description", "desc", "detail", "details", "summary", "note"]:
            text = AgentResourceOfficer._truncate_text(item.get(key), 160)
            if text:
                return text
        return ""

    @staticmethod
    def _format_resource_lines(resources: List[Dict[str, Any]], candidate: Optional[Dict[str, Any]] = None) -> str:
        lines = []
        if candidate:
            candidate_title = str(candidate.get("title") or "未命名")
            candidate_year = str(candidate.get("year") or "?")
            lines.append(f"已选影片：{candidate_title} ({candidate_year})")
        lines.append(f"资源结果：共 {len(resources)} 条")
        current_provider = ""
        for idx, item in enumerate(resources, start=1):
            provider = str(item.get("pan_type") or "?").lower()
            if provider != current_provider:
                current_provider = provider
                if provider == "115":
                    lines.append("115 结果")
                elif provider == "quark":
                    lines.append("夸克结果")
                else:
                    lines.append(f"{provider} 结果")
            points_text = AgentResourceOfficer._resource_points_text(item)
            resolution = "/".join(item.get("video_resolution") or []) or "未知清晰度"
            item_title = str(item.get("title") or "未命名资源")
            share_size = AgentResourceOfficer._list_text(item.get("share_size") or item.get("size"))
            source = AgentResourceOfficer._list_text(item.get("source"))
            subtitle = AgentResourceOfficer._resource_subtitle_text(item)
            episode = AgentResourceOfficer._resource_episode_text(item)
            remark = AgentResourceOfficer._resource_remark_text(item)

            meta = [points_text, resolution]
            if share_size:
                meta.append(share_size)
            if source:
                meta.append(source)
            lines.append(f"{idx}. [{provider}] {item_title}")
            lines.append(f"   {' | '.join(meta)}")
            score_label = AgentResourceOfficer._format_score_label(item)
            score = item.get("score") if isinstance(item.get("score"), dict) else {}
            if score_label:
                lines.append(f"   评分：{score_label}")
                hard_risks = score.get("hard_risk_reasons") or []
                risks = score.get("risk_reasons") or []
                risks = [risk for risk in risks if risk not in hard_risks]
                if hard_risks:
                    lines.append("   硬风险：" + "；".join(str(risk) for risk in hard_risks[:2]))
                elif risks:
                    lines.append("   提醒：" + "；".join(str(risk) for risk in risks[:2]))
            if episode:
                lines.append(f"   集数：{episode}")
            if subtitle:
                lines.append(f"   字幕：{subtitle}")
            if remark:
                lines.append(f"   详情：{remark}")
        lines.append("下一步：建议先回复“计划选择 1”生成待确认计划；确认后再回复“执行计划”。")
        lines.append("只有明确要立即解锁/转存时，才直接回复“选择 编号”。")
        return "\n".join(lines)

    @staticmethod
    def _format_route_result(result: Dict[str, Any]) -> str:
        lines = ["已执行资源路由"]
        route = result.get("route") or {}
        provider = str(route.get("provider") or route.get("pan_type") or "")
        if provider:
            lines.append(f"网盘：{provider}")
        if route.get("message"):
            lines.append(f"结果：{route.get('message')}")
        if route.get("target_path"):
            lines.append(f"目录：{route.get('target_path')}")
        return "\n".join(lines)

    async def _unlock_and_route(
        self,
        slug: str,
        target_path: str = "",
        resource: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Dict[str, Any], str]:
        allowed, disabled = self._ensure_hdhive_resource_enabled()
        if not allowed:
            return False, disabled.get("data") or {}, disabled.get("message") or "影巢资源入口已关闭"
        points_ok, points_message, points_data = self._check_hdhive_unlock_points_limit(resource)
        if not points_ok:
            return False, {"resource_guard": points_data, "resource": resource or {}}, points_message
        service = self._ensure_hdhive_service()
        unlock_ok, result, unlock_message = service.unlock_resource(slug)
        if not unlock_ok:
            return False, result, unlock_message

        unlock_data = result.get("data") or {}
        share_url = self._clean_text(unlock_data.get("full_url") or unlock_data.get("url"))
        access_code = self._clean_text(unlock_data.get("access_code"))
        pan_type = self._clean_text(unlock_data.get("pan_type")).lower()

        route_result: Dict[str, Any] = {
            "unlock": result,
            "route": {
                "pan_type": pan_type or "unknown",
                "share_url": share_url,
                "access_code": access_code,
                "executed": False,
                "message": "",
            },
        }

        if share_url and (pan_type == "quark" or self._is_quark_url(share_url)):
            quark_service = self._ensure_quark_service()
            transfer_ok, transfer_result, transfer_message = quark_service.transfer_share(
                share_url,
                access_code=access_code,
                target_path=target_path or self._quark_default_path,
                trigger="Agent影视助手 影巢解锁后自动路由",
            )
            route_result["route"].update(
                {
                    "executed": True,
                    "provider": "quark",
                    "target_path": target_path or self._quark_default_path,
                    "message": transfer_message,
                    "result": transfer_result,
                }
            )
            if not transfer_ok:
                return False, route_result, f"影巢解锁成功，但夸克转存失败：{transfer_message}"
            return True, route_result, "success"

        if share_url and (pan_type == "115" or self._is_115_url(share_url)):
            p115_service = self._ensure_p115_service()
            transfer_ok, transfer_result, transfer_message = p115_service.transfer_share(
                url=share_url,
                access_code=access_code,
                path=target_path or self._p115_default_path,
                trigger="Agent影视助手 影巢解锁后自动路由",
            )
            route_result["route"].update(
                {
                    "executed": True,
                    "provider": "115",
                    "target_path": target_path or self._p115_default_path,
                    "message": transfer_message,
                    "result": transfer_result,
                }
            )
            if not transfer_ok:
                return False, route_result, self._format_p115_transfer_failure(
                    detail=transfer_message,
                    target_path=target_path or self._p115_default_path,
                    title="影巢解锁成功，但 115 转存失败",
                )
            return True, route_result, "success"

        route_result["route"]["message"] = "当前解锁结果未识别到可自动路由的 115 / 夸克链接"
        return True, route_result, "success"

    @staticmethod
    def _is_quark_url(value: str) -> bool:
        return QuarkTransferService.is_quark_share_url(value)

    @staticmethod
    def _is_115_url(value: str) -> bool:
        host = urlparse(value or "").netloc.lower()
        return host == "115.com" or host.endswith(".115.com") or "115cdn.com" in host

    @staticmethod
    def _run_coroutine_sync(coro):
        try:
            return asyncio.run(coro)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

    def feishu_assistant_route(self, text: str, session: str) -> Dict[str, Any]:
        return self._run_coroutine_sync(
            self.api_assistant_route(
                _JsonRequestShim(
                    _RequestContextShim(),
                    {
                        "text": self._clean_text(text),
                        "session": self._clean_text(session) or "feishu",
                        "compact": False,
                    },
                )
            )
        )

    def feishu_assistant_pick(self, arg: str, session: str) -> Dict[str, Any]:
        index, target_path, action, mode = self._parse_feishu_pick_arg(arg)
        return self._run_coroutine_sync(
            self.api_assistant_pick(
                _JsonRequestShim(
                    _RequestContextShim(),
                    {
                        "session": self._clean_text(session) or "feishu",
                        "index": index,
                        "action": action,
                        "mode": mode,
                        "path": target_path,
                        "compact": False,
                    },
                )
            )
        )

    @classmethod
    def _parse_feishu_pick_arg(cls, arg: str) -> Tuple[int, str, str, str]:
        return cls._parse_pick_text(arg)

    async def tool_hdhive_search_session(
        self,
        keyword: str,
        media_type: str = "auto",
        year: str = "",
        target_path: str = "",
    ) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        allowed, disabled = self._ensure_hdhive_resource_enabled()
        if not allowed:
            return str(disabled.get("message") or "影巢资源入口已关闭")

        service = self._ensure_hdhive_service()
        search_ok, result, search_message = await service.resolve_candidates_by_keyword(
            keyword=self._clean_text(keyword),
            media_type=self._clean_text(media_type or "auto").lower(),
            year=self._clean_text(year),
            candidate_limit=max(30, self._hdhive_candidate_page_size),
        )
        if not search_ok:
            return f"影巢搜索失败：{search_message}"

        candidates = result.get("candidates") or []
        session_id = self._new_session_id("hdhive")
        self._save_session(
            session_id,
            {
                "kind": "hdhive",
                "stage": "candidate",
                "keyword": self._clean_text(keyword),
                "media_type": self._clean_text(media_type or "auto").lower(),
                "year": self._clean_text(year),
                "target_path": self._clean_text(target_path),
                "candidates": candidates,
                "page": 1,
                "page_size": self._hdhive_candidate_page_size,
            },
        )
        return (
            f"{self._format_candidate_lines(candidates, page=1, page_size=self._hdhive_candidate_page_size)}\n"
            f"session_id: {session_id}\n"
            "下一步：调用 agent_resource_officer_hdhive_pick，并传入 session_id 与 choice"
        )

    async def tool_hdhive_pick_session(self, session_id: str, index: int, target_path: str = "", action: str = "") -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        allowed, disabled = self._ensure_hdhive_resource_enabled()
        if not allowed:
            return str(disabled.get("message") or "影巢资源入口已关闭")
        session = self._load_session(self._clean_text(session_id))
        if not session:
            return "会话不存在或已过期"

        stage = session.get("stage")
        service = self._ensure_hdhive_service()
        action = self._normalize_pick_action(action)

        if stage == "candidate":
            candidates = session.get("candidates") or []
            page_size = max(1, self._safe_int(session.get("page_size"), self._hdhive_candidate_page_size))
            current_page = max(1, self._safe_int(session.get("page"), 1))
            if action == "detail":
                start = (current_page - 1) * page_size
                end = start + page_size
                enriched = [dict(item or {}) for item in candidates]
                enriched[start:end] = self._enrich_hdhive_candidates_with_actors(enriched[start:end])
                self._save_session(self._clean_text(session_id), {**session, "candidates": enriched})
                return self._format_candidate_lines(enriched, page=current_page, page_size=page_size)
            if action == "next_page":
                total_pages = max(1, (len(candidates) + page_size - 1) // page_size)
                if current_page >= total_pages:
                    return "已经是最后一页了，可以直接回复编号继续选择。"
                next_page = current_page + 1
                self._save_session(self._clean_text(session_id), {**session, "page": next_page})
                return self._format_candidate_lines(candidates, page=next_page, page_size=page_size)
            if index <= 0 or index > len(candidates):
                return "候选编号超出范围"
            candidate = dict(candidates[index - 1])
            resource_ok, resource_result, resource_message = service.search_resources(
                media_type=candidate.get("media_type") or session.get("media_type") or "movie",
                tmdb_id=str(candidate.get("tmdb_id") or ""),
            )
            if not resource_ok:
                return f"影巢资源查询失败：{resource_message}"
            preferences = self._normalize_assistant_preferences(
                (self._assistant_preferences or {}).get(self._normalize_preference_key(session=self._clean_text(session.get("keyword")) or "default"))
            )
            preview = self._attach_cloud_scores(
                self._group_resource_preview(resource_result.get("data") or [], per_group=6),
                preferences=preferences,
                source_type="hdhive",
                target_path=target_path or session.get("target_path") or "",
            )
            self._save_session(
                self._clean_text(session_id),
                {
                    **session,
                    "stage": "resource",
                    "selected_candidate": candidate,
                    "resources": preview,
                    "target_path": self._clean_text(target_path) or session.get("target_path") or "",
                },
            )
            return self._format_resource_lines(preview, candidate)

        if stage == "resource":
            resources = session.get("resources") or []
            if index <= 0 or index > len(resources):
                return "资源编号超出范围"
            resource = dict(resources[index - 1])
            route_ok, route_result, route_message = await self._unlock_and_route(
                self._clean_text(resource.get("slug")),
                target_path=self._clean_text(target_path) or session.get("target_path") or "",
                resource=resource,
            )
            if not route_ok:
                return f"资源处理失败：{route_message}"
            return self._format_route_result(route_result)

        return f"当前会话阶段不支持继续选择：{stage}"

    async def tool_route_share(self, share_url: str, access_code: str = "", target_path: str = "") -> str:
        share_url = self._clean_text(share_url)
        if not share_url:
            return "缺少分享链接"

        if self._is_quark_url(share_url):
            service = self._ensure_quark_service()
            ok, result, message = service.transfer_share(
                share_url,
                access_code=self._clean_text(access_code),
                target_path=self._clean_text(target_path) or self._quark_default_path,
                trigger="Agent影视助手 Agent Tool",
            )
            if not ok:
                return f"夸克转存失败：{message}"
            return f"夸克转存成功\n目录：{result.get('target_path') or self._quark_default_path}"

        if self._is_115_url(share_url):
            ok, result, message = self._ensure_p115_service().transfer_share(
                url=share_url,
                access_code=self._clean_text(access_code),
                path=self._clean_text(target_path) or self._p115_default_path,
                trigger="Agent影视助手 Agent Tool",
            )
            if not ok:
                return self._format_p115_transfer_failure(
                    detail=message,
                    target_path=self._clean_text(target_path) or self._p115_default_path,
                )
            return f"115 转存成功\n目录：{result.get('path') or self._p115_default_path}"

        return "当前链接不是可识别的 115 / 夸克分享链接"

    async def tool_assistant_route(
        self,
        text: str = "",
        session: str = "default",
        session_id: str = "",
        target_path: str = "",
        mode: str = "",
        keyword: str = "",
        share_url: str = "",
        access_code: str = "",
        media_type: str = "",
        year: str = "",
        client_type: str = "",
        action: str = "",
        compact: bool = True,
    ) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        result = await self.api_assistant_route(
            _JsonRequestShim(
                _RequestContextShim(),
                {
                    "text": self._clean_text(text),
                    "session": self._clean_text(session) or "default",
                    "session_id": self._clean_text(session_id),
                    "path": self._clean_text(target_path),
                    "mode": self._clean_text(mode),
                    "keyword": self._clean_text(keyword),
                    "url": self._clean_text(share_url),
                    "access_code": self._clean_text(access_code),
                    "media_type": self._clean_text(media_type),
                    "year": self._clean_text(year),
                    "client_type": self._clean_text(client_type),
                    "action": self._clean_text(action),
                    "compact": bool(compact),
                },
            )
        )
        return str(result.get("message") or "处理完成")

    async def tool_assistant_pick(
        self,
        session: str = "default",
        session_id: str = "",
        index: int = 0,
        action: str = "",
        mode: str = "",
        target_path: str = "",
        compact: bool = True,
    ) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        result = await self.api_assistant_pick(
            _JsonRequestShim(
                _RequestContextShim(),
                {
                    "session": self._clean_text(session) or "default",
                    "session_id": self._clean_text(session_id),
                    "choice": index,
                    "action": self._clean_text(action),
                    "mode": self._clean_text(mode),
                    "path": self._clean_text(target_path),
                    "compact": bool(compact),
                },
            )
        )
        return str(result.get("message") or "继续处理完成")

    async def tool_assistant_help(self, session: str = "default", session_id: str = "") -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        session_name, _ = self._normalize_assistant_session_ref(session=session, session_id=session_id)
        return self._format_assistant_help_text(session=session_name)

    async def tool_assistant_capabilities(self, compact: bool = True) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        if compact:
            data = self._assistant_capabilities_compact_data(self._assistant_capabilities_public_data())
            return (
                f"Agent影视助手：{data.get('version')}；"
                f"工作流 {len(data.get('workflows') or [])} 个；"
                f"Tool {len(data.get('agent_tools') or [])} 个"
            )
        return self._format_assistant_capabilities_text()

    async def tool_assistant_readiness(self, compact: bool = True) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        if compact:
            data = self._assistant_readiness_compact_data(self._assistant_readiness_public_data())
            services = data.get("services") or {}
            return (
                f"就绪：{'是' if data.get('can_start') else '否'}；"
                f"115：{'可用' if services.get('p115_ready') else '不可用'}；"
                f"影巢：{'已配' if services.get('hdhive_configured') else '未配'}；"
                f"夸克：{'已配' if services.get('quark_configured') else '未配'}；"
                f"待计划：{data.get('saved_plans_pending') or 0}"
            )
        return self._format_assistant_readiness_text()

    async def tool_feishu_health(self, compact: bool = True) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        channel = self._ensure_feishu_channel()
        data = {
            "plugin_version": self.plugin_version,
            "plugin_enabled": self._enabled,
            **channel.health(),
        }
        if not compact:
            return json.dumps(data, ensure_ascii=False, indent=2)
        return (
            f"飞书入口：{'已开启' if data.get('enabled') else '未开启'}；"
            f"长连接：{'运行中' if data.get('running') else '未运行'}；"
            f"SDK：{'可用' if data.get('sdk_available') else '缺失'}；"
            f"AppID：{'已填' if data.get('app_id_configured') else '未填'}；"
            f"AppSecret：{'已填' if data.get('app_secret_configured') else '未填'}；"
            f"白名单：chat {data.get('allowed_chat_count') or 0} / user {data.get('allowed_user_count') or 0}；"
            f"其他飞书入口：{'检测到运行中' if data.get('legacy_bridge_running') else '未检测到'}"
        )

    async def tool_assistant_pulse(self) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        return self._format_assistant_pulse_text()

    async def tool_assistant_startup(self) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        return self._format_assistant_startup_text()

    async def tool_assistant_maintain(self, execute: bool = False, limit: int = 100) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        data = self._assistant_maintain_public_data(execute=execute, limit=limit)
        return self._format_assistant_maintain_text(data)

    async def tool_assistant_toolbox(self) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        return self._format_assistant_toolbox_text()

    async def tool_assistant_request_templates(
        self,
        limit: int = 100,
        names: Any = None,
        recipe: Any = None,
        include_templates: bool = True,
    ) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        data = self._assistant_request_templates_response_data(
            limit=limit,
            names=names,
            recipe=recipe,
            include_templates=include_templates,
        )
        return self._format_assistant_request_templates_text(data)

    async def tool_assistant_selfcheck(self) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        return self._format_assistant_selfcheck_text()

    async def tool_assistant_history(
        self,
        session: str = "",
        session_id: str = "",
        compact: bool = True,
        limit: int = 20,
    ) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        if compact:
            data = self._assistant_history_compact_data(
                self._assistant_history_public_data(session=session, session_id=session_id, limit=limit)
            )
            failed = sum(1 for item in (data.get("items") or []) if not item.get("success"))
            return f"最近执行历史：{len(data.get('items') or [])} 条；失败 {failed} 条"
        return self._format_assistant_history_text(session=session, session_id=session_id, limit=limit)

    async def tool_assistant_execute_action(
        self,
        name: str,
        session: str = "default",
        session_id: str = "",
        choice: Optional[int] = None,
        target_path: str = "",
        keyword: str = "",
        media_type: str = "",
        year: str = "",
        share_url: str = "",
        access_code: str = "",
        client_type: str = "",
        source: str = "",
        kind: str = "",
        has_pending_p115: Optional[bool] = None,
        stale_only: bool = False,
        all_sessions: bool = False,
        limit: int = 100,
        plan_id: str = "",
        prefer_unexecuted: bool = True,
        compact: bool = True,
    ) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        result = await self.api_assistant_action(
            _JsonRequestShim(
                _RequestContextShim(),
                {
                    "name": self._clean_text(name),
                    "session": self._clean_text(session) or "default",
                    "session_id": self._clean_text(session_id),
                    "choice": choice,
                    "path": self._clean_text(target_path),
                    "keyword": self._clean_text(keyword),
                    "media_type": self._clean_text(media_type),
                    "year": self._clean_text(year),
                    "url": self._clean_text(share_url),
                    "access_code": self._clean_text(access_code),
                    "client_type": self._clean_text(client_type),
                    "source": self._clean_text(source),
                    "kind": self._clean_text(kind),
                    "has_pending_p115": has_pending_p115,
                    "stale_only": bool(stale_only),
                    "all_sessions": bool(all_sessions),
                    "limit": self._safe_int(limit, 100),
                    "plan_id": self._clean_text(plan_id),
                    "prefer_unexecuted": bool(prefer_unexecuted),
                    "compact": bool(compact),
                },
            )
        )
        return str(result.get("message") or "动作执行完成")

    async def tool_assistant_execute_actions(
        self,
        actions: List[Dict[str, Any]],
        session: str = "default",
        session_id: str = "",
        stop_on_error: bool = True,
        include_raw_results: bool = False,
        compact: bool = True,
    ) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        result = await self.api_assistant_actions(
            _JsonRequestShim(
                _RequestContextShim(),
                {
                    "actions": actions or [],
                    "session": self._clean_text(session) or "default",
                    "session_id": self._clean_text(session_id),
                    "stop_on_error": bool(stop_on_error),
                    "include_raw_results": bool(include_raw_results),
                    "compact": bool(compact),
                },
            )
        )
        return str(result.get("message") or "批量动作执行完成")

    async def tool_assistant_workflow(
        self,
        name: str,
        session: str = "default",
        session_id: str = "",
        keyword: str = "",
        choice: Optional[int] = None,
        candidate_choice: Optional[int] = None,
        resource_choice: Optional[int] = None,
        target_path: str = "",
        share_url: str = "",
        access_code: str = "",
        media_type: str = "",
        year: str = "",
        client_type: str = "",
        source: str = "",
        limit: int = 20,
        dry_run: Optional[bool] = None,
        stop_on_error: bool = True,
        include_raw_results: bool = False,
        compact: bool = True,
    ) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        payload = {
            "name": self._clean_text(name),
            "session": self._clean_text(session) or "default",
            "session_id": self._clean_text(session_id),
            "keyword": self._clean_text(keyword),
            "choice": choice,
            "candidate_choice": candidate_choice,
            "resource_choice": resource_choice,
            "path": self._clean_text(target_path),
            "url": self._clean_text(share_url),
            "access_code": self._clean_text(access_code),
            "media_type": self._clean_text(media_type),
            "year": self._clean_text(year),
            "client_type": self._clean_text(client_type),
            "source": self._clean_text(source),
            "limit": self._safe_int(limit, 20),
            "stop_on_error": bool(stop_on_error),
            "include_raw_results": bool(include_raw_results),
            "compact": bool(compact),
        }
        if dry_run is not None:
            payload["dry_run"] = bool(dry_run)
        result = await self.api_assistant_workflow(
            _JsonRequestShim(_RequestContextShim(), payload)
        )
        return str(result.get("message") or "工作流执行完成")

    async def tool_assistant_preferences(
        self,
        session: str = "default",
        session_id: str = "",
        user_key: str = "",
        preferences: Optional[Dict[str, Any]] = None,
        reset: bool = False,
        compact: bool = True,
    ) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        method = "DELETE" if reset else "POST" if preferences else "GET"
        result = await self.api_assistant_preferences(
            _JsonRequestShim(
                _RequestContextShim(),
                {
                    "session": self._clean_text(session) or "default",
                    "session_id": self._clean_text(session_id),
                    "user_key": self._clean_text(user_key),
                    "preferences": preferences or {},
                    "compact": bool(compact),
                },
                method=method,
            )
        )
        return str(result.get("message") or "偏好画像处理完成")

    async def tool_assistant_execute_plan(
        self,
        plan_id: str = "",
        session: str = "",
        session_id: str = "",
        prefer_unexecuted: bool = True,
        stop_on_error: bool = True,
        include_raw_results: bool = False,
        compact: bool = True,
    ) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        result = await self.api_assistant_plan_execute(
            _JsonRequestShim(
                _RequestContextShim(),
                {
                    "plan_id": self._clean_text(plan_id),
                    "session": self._clean_text(session),
                    "session_id": self._clean_text(session_id),
                    "prefer_unexecuted": bool(prefer_unexecuted),
                    "stop_on_error": bool(stop_on_error),
                    "include_raw_results": bool(include_raw_results),
                    "compact": bool(compact),
                },
            )
        )
        return str(result.get("message") or "计划执行完成")

    async def tool_assistant_plans(
        self,
        session: str = "",
        session_id: str = "",
        executed: Optional[bool] = None,
        include_actions: bool = False,
        compact: bool = True,
        limit: int = 20,
    ) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        if compact:
            data = self._assistant_plans_compact_data(
                self._assistant_plans_public_data(
                    session=session,
                    session_id=session_id,
                    executed=executed,
                    include_actions=False,
                    limit=limit,
                )
            )
            pending = sum(1 for item in (data.get("items") or []) if not item.get("executed"))
            return f"已保存计划：{len(data.get('items') or [])} 条；待执行 {pending} 条"
        return self._format_assistant_plans_text(
            session=session,
            session_id=session_id,
            executed=executed,
            include_actions=include_actions,
            limit=limit,
        )

    async def tool_assistant_plans_clear(
        self,
        plan_id: str = "",
        session: str = "",
        session_id: str = "",
        executed: Optional[bool] = None,
        all_plans: bool = False,
        limit: int = 100,
    ) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        result = self._clear_workflow_plans(
            plan_id=plan_id,
            session=session,
            session_id=session_id,
            executed=executed,
            all_plans=all_plans,
            limit=limit,
        )
        return str(result.get("message") or "计划清理完成")

    async def tool_assistant_recover(
        self,
        session: str = "",
        session_id: str = "",
        execute: bool = False,
        prefer_unexecuted: bool = True,
        stop_on_error: bool = True,
        include_raw_results: bool = False,
        compact: bool = True,
        limit: int = 20,
    ) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        result = await self.api_assistant_recover(
            _JsonRequestShim(
                _RequestContextShim(),
                {
                    "session": self._clean_text(session),
                    "session_id": self._clean_text(session_id),
                    "execute": bool(execute),
                    "prefer_unexecuted": bool(prefer_unexecuted),
                    "stop_on_error": bool(stop_on_error),
                    "include_raw_results": bool(include_raw_results),
                    "compact": bool(compact),
                    "limit": self._safe_int(limit, 20),
                },
            )
        )
        return str(result.get("message") or "恢复检查完成")

    async def tool_assistant_session_state(self, session: str = "default", session_id: str = "", compact: bool = True) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        session_name, _ = self._normalize_assistant_session_ref(session=session, session_id=session_id)
        if compact:
            state = self._assistant_session_compact_data(self._assistant_session_public_data(session=session_name))
            recovery = state.get("recovery") or {}
            parts = [
                f"会话：{state.get('session')}",
                f"阶段：{state.get('kind') or '-'} / {state.get('stage') or '-'}",
                f"恢复：{recovery.get('mode') or '-'}",
            ]
            if recovery.get("recommended_action"):
                parts.append(f"推荐动作：{recovery.get('recommended_action')}")
            return "\n".join(parts)
        return self._format_assistant_session_summary(session=session_name)

    async def tool_assistant_sessions(
        self,
        kind: str = "",
        has_pending_p115: Optional[bool] = None,
        compact: bool = True,
        limit: int = 20,
    ) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        if compact:
            data = self._assistant_sessions_compact_data(
                self._assistant_sessions_public_data(kind=kind, has_pending_p115=has_pending_p115, limit=limit)
            )
            return f"活跃会话：{data.get('total') or 0} 个；展示 {len(data.get('items') or [])} 个"
        return self._format_assistant_sessions_text(
            kind=kind,
            has_pending_p115=has_pending_p115,
            limit=limit,
        )

    async def tool_assistant_session_clear(self, session: str = "default", session_id: str = "") -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        session_name, cache_key = self._normalize_assistant_session_ref(session=session, session_id=session_id)
        existing = self._load_session(cache_key)
        if not existing:
            return "当前没有需要清理的会话。"
        self._session_cache.pop(cache_key, None)
        self._persist_relevant_sessions()
        return f"已清理会话：{session_name}"

    async def tool_assistant_sessions_clear(
        self,
        session: str = "",
        session_id: str = "",
        kind: str = "",
        has_pending_p115: Optional[bool] = None,
        stale_only: bool = False,
        all_sessions: bool = False,
        limit: int = 100,
    ) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        result = await self.api_assistant_sessions_clear(
            _JsonRequestShim(
                _RequestContextShim(),
                {
                    "session": self._clean_text(session),
                    "session_id": self._clean_text(session_id),
                    "kind": self._clean_text(kind),
                    "has_pending_p115": has_pending_p115,
                    "stale_only": bool(stale_only),
                    "all_sessions": bool(all_sessions),
                    "limit": self._safe_int(limit, 100),
                },
            )
        )
        return str(result.get("message") or "会话清理完成")

    async def tool_p115_qrcode_start(self, client_type: str = "alipaymini") -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        final_client_type = P115TransferService.normalize_qrcode_client_type(client_type or self._p115_client_type)
        qr_ok, data, qr_message = self._ensure_p115_service().create_qrcode_login(client_type=final_client_type)
        if not qr_ok:
            return f"115 扫码二维码生成失败：{qr_message}"
        return (
            "115 扫码二维码已生成\n"
            f"client_type: {data.get('client_type')}\n"
            f"uid: {data.get('uid')}\n"
            f"time: {data.get('time')}\n"
            f"sign: {data.get('sign')}\n"
            f"qrcode: {data.get('qrcode')}\n"
            "下一步：调用 agent_resource_officer_p115_qrcode_check，并传入 uid、time、sign 和 client_type"
        )

    async def tool_p115_qrcode_check(
        self,
        uid: str,
        time_value: str,
        sign: str,
        client_type: str = "alipaymini",
    ) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        qr_ok, data, qr_message = self._ensure_p115_service().check_qrcode_login(
            uid=self._clean_text(uid),
            time_value=self._clean_text(time_value),
            sign=self._clean_text(sign),
            client_type=P115TransferService.normalize_qrcode_client_type(client_type or self._p115_client_type),
        )
        if qr_ok and data.get("status") == "success":
            cookie = self._clean_text(data.pop("cookie"))
            if cookie:
                self._p115_cookie = cookie
                self._p115_client_type = P115TransferService.normalize_qrcode_client_type(client_type or self._p115_client_type)
                self._apply_runtime_config({
                    "p115_cookie": cookie,
                    "p115_client_type": self._p115_client_type,
                })
                data["cookie_saved"] = True
        status = self._clean_text(data.get("status"))
        lines = [
            "115 扫码状态",
            f"status: {status or 'unknown'}",
            f"message: {qr_message}",
        ]
        if data.get("cookie_saved"):
            lines.append("cookie_saved: true")
            lines.append(self._format_p115_status_summary(title="115 登录完成"))
        if data.get("cookie_keys"):
            lines.append(f"cookie_keys: {', '.join(data.get('cookie_keys') or [])}")
        return "\n".join(lines)

    async def tool_p115_status(self) -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        return self._format_p115_status_summary()

    async def tool_p115_pending(self, session: str = "default") -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        session_id = self._session_key_for_tool(session)
        summary = self._pending_p115_summary(self._load_session(session_id))
        return summary or "当前没有待继续的 115 任务。"

    async def tool_p115_resume(self, session: str = "default") -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        session_id = self._session_key_for_tool(session)
        state = self._load_session(session_id) or {}
        if not self._pending_p115_summary(state):
            return "当前没有待继续的 115 任务。"
        if not self._p115_status_snapshot().get("ready"):
            return f"{self._pending_p115_summary(state)}\n当前 115 还不可用，请先完成 115 登录。"
        resume_ok, resume_message, _ = self._execute_pending_p115_share(
            session_id=session_id,
            state=state,
            trigger="Agent影视助手 Agent Tool 手动继续 115 任务",
        )
        lines = ["已手动继续 115 任务", resume_message]
        if not resume_ok:
            lines.append("任务仍未成功，保留待继续状态。")
        return "\n".join(line for line in lines if line)

    async def tool_p115_cancel(self, session: str = "default") -> str:
        if not self._enabled:
            return "Agent影视助手 插件未启用"
        session_id = self._session_key_for_tool(session)
        summary = self._pending_p115_summary(self._load_session(session_id))
        if not summary:
            return "当前没有待取消的 115 任务。"
        self._clear_pending_p115_share(session_id)
        return f"{summary}\n已取消并清除这次待继续的 115 任务。"

    async def api_p115_health(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}

        service = self._ensure_p115_service()
        health_ok, result, health_message = service.health()
        cookie_state = result.get("cookie_state") or {}
        return {
            "success": True,
            "data": {
                "plugin_version": self.plugin_version,
                "enabled": self._enabled,
                "p115_ready": health_ok,
                "p115_direct_ready": bool(result.get("direct_ready")),
                "p115_direct_source": result.get("direct_source") or "",
                "p115_helper_ready": bool(result.get("helper_ready")),
                "default_target_path": self._p115_default_path,
                "p115_client_type": self._p115_client_type,
                "p115_cookie_configured": bool(cookie_state.get("configured")),
                "p115_cookie_valid": bool(cookie_state.get("valid")),
                "p115_cookie_mode": cookie_state.get("mode") or "none",
                "p115_cookie_keys": cookie_state.get("cookie_keys") or [],
                "message": "" if health_ok else health_message,
                "raw": result,
            },
        }

    async def api_p115_qrcode(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        client_type = P115TransferService.normalize_qrcode_client_type(
            request.query_params.get("client_type") or self._p115_client_type
        )
        qr_ok, data, qr_message = self._ensure_p115_service().create_qrcode_login(client_type=client_type)
        if not qr_ok:
            return {"success": False, "message": qr_message}
        return {"success": True, "message": qr_message, "data": data}

    async def api_p115_qrcode_check(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        uid = self._clean_text(request.query_params.get("uid"))
        time_value = self._clean_text(request.query_params.get("time"))
        sign = self._clean_text(request.query_params.get("sign"))
        if not uid or not time_value or not sign:
            return {"success": False, "message": "缺少 uid/time/sign，无法检查扫码状态"}
        client_type = P115TransferService.normalize_qrcode_client_type(
            request.query_params.get("client_type") or self._p115_client_type
        )
        qr_ok, data, qr_message = self._ensure_p115_service().check_qrcode_login(
            uid=uid,
            time_value=time_value,
            sign=sign,
            client_type=client_type,
        )
        if qr_ok and (data.get("status") == "success"):
            cookie = self._clean_text(data.pop("cookie"))
            if cookie:
                self._p115_cookie = cookie
                self._p115_client_type = client_type
                self._apply_runtime_config({
                    "p115_cookie": cookie,
                    "p115_client_type": client_type,
                })
                data["cookie_saved"] = True
                data["cookie_mode"] = "client_cookie"
                data["status_summary"] = self._format_p115_status_summary(title="115 登录完成")
        if not qr_ok:
            return {"success": False, "message": qr_message, "data": data}
        return {"success": True, "message": qr_message, "data": data}

    async def api_p115_transfer(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        url = self._clean_text(body.get("url") or body.get("share_url"))
        access_code = self._clean_text(body.get("access_code") or body.get("pwd") or body.get("code"))
        target_path = self._clean_text(body.get("path") or body.get("target_path"))
        trigger = self._clean_text(body.get("trigger") or "Agent影视助手 API")

        service = self._ensure_p115_service()
        transfer_ok, result, transfer_message = service.transfer_share(
            url=url,
            access_code=access_code,
            path=target_path or self._p115_default_path,
            trigger=trigger,
        )
        if not transfer_ok:
            return {
                "success": False,
                "message": self._format_p115_transfer_failure(
                    detail=transfer_message,
                    target_path=target_path or self._p115_default_path,
                ),
                "data": result,
            }
        return {"success": True, "message": transfer_message, "data": result}

    async def api_p115_pending(self, request: Request):
        body = await self._request_payload(request)
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        session = self._clean_text(
            body.get("session")
            or body.get("session_id")
            or request.query_params.get("session")
            or request.query_params.get("session_id")
            or "default"
        )
        session_id = self._session_key_for_tool(session)
        state = self._load_session(session_id) or {}
        summary = self._pending_p115_summary(state)
        data = self._pending_p115_public_data(state)
        data["session_id"] = session_id
        return {
            "success": True,
            "message": summary or "当前没有待继续的 115 任务。",
            "data": data,
        }

    async def api_p115_pending_resume(self, request: Request):
        body = await self._request_payload(request)
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        session = self._clean_text(
            body.get("session")
            or body.get("session_id")
            or request.query_params.get("session")
            or request.query_params.get("session_id")
            or "default"
        )
        session_id = self._session_key_for_tool(session)
        state = self._load_session(session_id) or {}
        if not self._pending_p115_summary(state):
            return {
                "success": False,
                "message": "当前没有待继续的 115 任务。",
                "data": {"session_id": session_id, "has_pending": False},
            }
        if not self._p115_status_snapshot().get("ready"):
            return {
                "success": False,
                "message": f"{self._pending_p115_summary(state)}\n当前 115 还不可用，请先完成 115 登录。",
                "data": {"session_id": session_id, **self._pending_p115_public_data(state)},
            }
        resume_ok, resume_message, resume_data = self._execute_pending_p115_share(
            session_id=session_id,
            state=state,
            trigger="Agent影视助手 API 手动继续 115 任务",
        )
        message_text = "已手动继续 115 任务"
        if resume_message:
            message_text = f"{message_text}\n{resume_message}"
        if not resume_ok:
            message_text = f"{message_text}\n任务仍未成功，保留待继续状态。"
        return {
            "success": resume_ok,
            "message": message_text,
            "data": {
                "session_id": session_id,
                "result": resume_data,
                "pending": self._pending_p115_public_data(self._load_session(session_id) or {}),
            },
        }

    async def api_p115_pending_cancel(self, request: Request):
        body = await self._request_payload(request)
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        session = self._clean_text(
            body.get("session")
            or body.get("session_id")
            or request.query_params.get("session")
            or request.query_params.get("session_id")
            or "default"
        )
        session_id = self._session_key_for_tool(session)
        state = self._load_session(session_id) or {}
        summary = self._pending_p115_summary(state)
        if not summary:
            return {
                "success": True,
                "message": "当前没有待取消的 115 任务。",
                "data": {"session_id": session_id, "has_pending": False},
            }
        pending_data = self._pending_p115_public_data(state)
        self._clear_pending_p115_share(session_id)
        return {
            "success": True,
            "message": f"{summary}\n已取消并清除这次待继续的 115 任务。",
            "data": {"session_id": session_id, "cancelled": True, "pending": pending_data},
        }

    async def api_hdhive_unlock_and_route(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        allowed, disabled = self._ensure_hdhive_resource_enabled()
        if not allowed:
            return disabled

        slug = self._clean_text(body.get("slug"))
        target_path = self._clean_text(body.get("path") or body.get("target_path"))
        route_ok, route_result, route_message = await self._unlock_and_route(slug, target_path=target_path, resource=body)
        if not route_ok:
            return {"success": False, "message": route_message, "data": route_result}
        return {"success": True, "message": route_message, "data": route_result}

    async def api_share_route(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        share_url = self._clean_text(body.get("url") or body.get("share_url") or body.get("share_text"))
        access_code = self._clean_text(body.get("access_code") or body.get("pwd") or body.get("code"))
        target_path = self._clean_text(body.get("path") or body.get("target_path"))
        trigger = self._clean_text(body.get("trigger") or "Agent影视助手 自动路由")

        if self._is_quark_url(share_url):
            quark_service = self._ensure_quark_service()
            transfer_ok, result, transfer_message = quark_service.transfer_share(
                share_url,
                access_code=access_code,
                target_path=target_path or self._quark_default_path,
                trigger=trigger,
            )
            if not transfer_ok:
                return {
                    "success": False,
                    "message": f"夸克转存失败：{transfer_message}",
                    "data": {
                        "provider": "quark",
                        "result": result,
                    },
                }
            return {
                "success": True,
                "message": transfer_message,
                "data": {
                    "provider": "quark",
                    "result": result,
                },
            }

        if self._is_115_url(share_url):
            p115_service = self._ensure_p115_service()
            transfer_ok, result, transfer_message = p115_service.transfer_share(
                url=share_url,
                access_code=access_code,
                path=target_path or self._p115_default_path,
                trigger=trigger,
            )
            if not transfer_ok:
                return {
                    "success": False,
                    "message": self._format_p115_transfer_failure(
                        detail=transfer_message,
                        target_path=target_path or self._p115_default_path,
                    ),
                    "data": {
                        "provider": "115",
                        "result": result,
                    },
                }
            return {
                "success": True,
                "message": transfer_message,
                "data": {
                    "provider": "115",
                    "result": result,
                },
            }

        return {
            "success": False,
            "message": "当前链接不是可识别的 115 / 夸克分享链接",
            "data": {"provider": "unknown", "url": share_url},
        }

    async def api_assistant_preferences(self, request: Request):
        body: Dict[str, Any] = {}
        try:
            body = await request.json()
        except Exception:
            body = {}
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        session = self._clean_text(body.get("session") or request.query_params.get("session") or "default")
        user_key = self._clean_text(body.get("user_key") or request.query_params.get("user_key"))
        if request.method.upper() == "DELETE" or self._parse_bool_value(body.get("reset"), False):
            preferences_data = self._reset_assistant_preferences(session=session, user_key=user_key)
            return {
                "success": True,
                "message": "智能体片源偏好已重置，下一次启动会重新进入偏好询问。",
                "data": self._assistant_response_data(session=session, data={
                    "action": "preferences_reset",
                    "ok": True,
                    "preferences": preferences_data,
                    "write_effect": "state",
                }),
            }
        if request.method.upper() == "POST":
            preferences = body.get("preferences") if isinstance(body.get("preferences"), dict) else {
                key: value
                for key, value in body.items()
                if key not in {"apikey", "session", "session_id", "user_key", "compact", "reset"}
            }
            preferences_data = self._save_assistant_preferences(session=session, user_key=user_key, preferences=preferences)
            return {
                "success": True,
                "message": "智能体片源偏好已保存。",
                "data": self._assistant_response_data(session=session, data={
                    "action": "preferences_save",
                    "ok": True,
                    "preferences": preferences_data,
                    "write_effect": "state",
                }),
            }

        preferences_data = self._assistant_preferences_public_data(session=session, user_key=user_key)
        message_text = "智能体片源偏好未初始化，请先询问用户偏好。" if preferences_data.get("needs_onboarding") else "智能体片源偏好已初始化。"
        return {
            "success": True,
            "message": message_text,
            "data": self._assistant_response_data(session=session, data={
                "action": "preferences",
                "ok": True,
                "preferences": preferences_data,
            }),
        }

    async def api_assistant_route(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        session, cache_key = self._normalize_assistant_session_ref(
            session=(
                body.get("session")
                or body.get("chat_id")
                or body.get("user_id")
                or body.get("conversation_id")
                or "default"
            ),
            session_id=body.get("session_id"),
        )
        text = self._clean_text(body.get("text") or body.get("query") or body.get("message") or "")
        parsed = self._merge_assistant_structured_input(body, self._parse_assistant_text(text))
        state = self._load_session(cache_key) or {}
        target_path = parsed.get("path") or ""
        compact = self._parse_bool_value(body.get("compact"), False)

        def finish(result: Dict[str, Any]) -> Dict[str, Any]:
            return self._assistant_interaction_compact_response(result) if compact else result

        def immediate(result: Dict[str, Any]) -> Dict[str, Any]:
            return result

        pick_index, pick_path, pick_action, pick_mode = self._parse_pick_text(text)
        if pick_index > 0 or pick_action:
            pick_result = await self.api_assistant_pick(
                _JsonRequestShim(request, {
                    "session": session,
                    "index": pick_index,
                    "action": pick_action,
                    "mode": pick_mode,
                    "path": target_path or pick_path,
                    "compact": compact,
                    "apikey": self._extract_apikey(request, body),
                })
            )
            return pick_result

        route_action = self._normalize_pick_action(text)
        if route_action:
            pick_result = await self.api_assistant_pick(
                _JsonRequestShim(request, {
                    "session": session,
                    "index": 0,
                    "action": route_action,
                    "path": target_path,
                    "compact": compact,
                    "apikey": self._extract_apikey(request, body),
                })
            )
            return pick_result

        if not text and not any(parsed.get(key) for key in ["mode", "keyword", "url", "action"]):
            summary = self._format_assistant_help_text(session=session)
            return finish({
                "success": True,
                "message": summary,
                "data": self._assistant_response_data(session=session, data={
                    "action": "assistant_help",
                    "ok": True,
                    "status_summary": summary,
                }),
            })

        assistant_action = self._clean_text(parsed.get("action"))
        keyword = self._clean_text(parsed.get("keyword"))
        if assistant_action == "assistant_help":
            summary = self._format_assistant_help_text(session=session)
            return finish({
                "success": True,
                "message": summary,
                "data": self._assistant_response_data(session=session, data={
                    "action": "assistant_help",
                    "ok": True,
                    "status_summary": summary,
                }),
            })
        if assistant_action == "execute_plan":
            return finish(await self.api_assistant_plan_execute(
                _JsonRequestShim(request, {
                    "session": session,
                    "session_id": cache_key,
                    "plan_id": self._clean_text(parsed.get("plan_id")),
                    "prefer_unexecuted": True,
                    "stop_on_error": self._parse_bool_value(body.get("stop_on_error"), True),
                    "include_raw_results": self._parse_bool_value(body.get("include_raw_results"), False),
                    "compact": compact,
                    "apikey": self._extract_apikey(request, body),
                })
            ))
        if assistant_action == "plans_list":
            include_actions = self._parse_bool_value(body.get("include_actions"), False)
            executed = self._parse_optional_bool(body.get("executed"))
            limit = self._safe_int(body.get("limit"), 10)
            plans_data = self._assistant_plans_public_data(
                session=session,
                session_id=cache_key,
                executed=executed,
                include_actions=include_actions,
                limit=limit,
            )
            return finish({
                "success": True,
                "message": self._format_assistant_plans_text(
                    session=session,
                    session_id=cache_key,
                    executed=executed,
                    include_actions=include_actions,
                    limit=limit,
                ),
                "data": self._assistant_response_data(session=session, data={
                    "action": "plans_list",
                    "ok": True,
                    **plans_data,
                }),
            })
        if assistant_action == "plans_clear":
            plan_id = self._clean_text(parsed.get("plan_id"))
            if not plan_id:
                return finish({
                    "success": False,
                    "message": "取消或清理计划需要指定 plan_id，例如：取消计划 plan-xxxx。",
                    "data": self._assistant_response_data(session=session, data={
                        "action": "plans_clear",
                        "ok": False,
                        "error_code": "missing_plan_id",
                    }),
                })
            clear_result = self._clear_workflow_plans(plan_id=plan_id, limit=1)
            return finish({
                "success": bool(clear_result.get("ok")),
                "message": str(clear_result.get("message") or "计划清理完成"),
                "data": self._assistant_response_data(session=session, data={
                    "action": "plans_clear",
                    "ok": bool(clear_result.get("ok")),
                    **clear_result,
                }),
            })
        if assistant_action in {"preferences_get", "preferences_save", "preferences_reset"}:
            if assistant_action == "preferences_save":
                preferences = body.get("preferences") if isinstance(body.get("preferences"), dict) else self._parse_assistant_preferences_text(text)
                if not preferences:
                    return finish({
                        "success": False,
                        "message": (
                            "保存偏好缺少可识别内容。示例：保存偏好 4K 杜比 HDR 中字 全集 "
                            "做种>=3 影巢积分20 不自动入库"
                        ),
                        "data": self._assistant_response_data(session=session, data={
                            "action": "preferences_save",
                            "ok": False,
                            "error_code": "missing_preferences",
                        }),
                    })
                payload = {
                    "session": session,
                    "user_key": self._clean_text(body.get("user_key")),
                    "preferences": preferences,
                    "compact": compact,
                    "apikey": self._extract_apikey(request, body),
                }
                return finish(await self.api_assistant_preferences(_JsonRequestShim(request, payload, method="POST")))
            if assistant_action == "preferences_reset":
                return finish(await self.api_assistant_preferences(_JsonRequestShim(request, {
                    "session": session,
                    "user_key": self._clean_text(body.get("user_key")),
                    "compact": compact,
                    "apikey": self._extract_apikey(request, body),
                }, method="DELETE")))
            return finish(await self.api_assistant_preferences(_JsonRequestShim(request, {
                "session": session,
                "user_key": self._clean_text(body.get("user_key")),
                "compact": compact,
                "apikey": self._extract_apikey(request, body),
            }, method="GET")))
        if assistant_action == "hdhive_checkin":
            is_gambler = self._parse_bool_value(parsed.get("is_gambler"), self._hdhive_checkin_gambler_mode)
            result = self._run_hdhive_checkin(is_gambler=is_gambler, trigger="Agent影视助手 智能入口")
            data = result.get("data") if isinstance(result.get("data"), dict) else {}
            status = data.get("status") or ("签到成功" if result.get("success") else "签到失败")
            mode_text = "赌狗签到" if is_gambler else "普通签到"
            summary = f"影巢{mode_text}：{status}\n{result.get('message') or ''}".strip()
            return finish({
                "success": bool(result.get("success")),
                "message": summary,
                "data": self._assistant_response_data(session=session, data={
                    "action": "hdhive_checkin",
                    "ok": bool(result.get("success")),
                    "is_gambler": is_gambler,
                    "status_summary": summary,
                    "result": data,
                }),
            })
        if assistant_action == "hdhive_checkin_history":
            summary = self._format_hdhive_checkin_history_text(limit=10)
            return finish({
                "success": True,
                "message": summary,
                "data": self._assistant_response_data(session=session, data={
                    "action": "hdhive_checkin_history",
                    "ok": True,
                    "status_summary": summary,
                    "history": self._hdhive_checkin_history_public_data(limit=10),
                }),
            })
        if assistant_action == "mp_media_detail":
            if not keyword:
                return finish({
                    "success": False,
                    "message": "媒体识别失败：缺少片名。用法：识别 蜘蛛侠",
                    "data": self._assistant_response_data(session=session, data={
                        "action": "mp_media_detail",
                        "ok": False,
                        "error_code": "missing_keyword",
                    }),
                })
            return finish(await self._assistant_mp_media_detail(
                keyword=keyword,
                session=session,
                cache_key=cache_key,
                media_type=self._clean_text(body.get("media_type") or body.get("type") or parsed.get("type") or "auto"),
                year=self._clean_text(body.get("year") or parsed.get("year")),
            ))
        if assistant_action == "mp_downloaders":
            return finish(await self._assistant_mp_downloaders(session=session, cache_key=cache_key))
        if assistant_action == "mp_sites":
            return finish(await self._assistant_mp_sites(
                session=session,
                cache_key=cache_key,
                status=self._clean_text(body.get("status") or parsed.get("status") or "active"),
                name=keyword,
                limit=self._safe_int(body.get("limit"), 30),
            ))
        if assistant_action == "mp_subscribes":
            return finish(await self._assistant_mp_subscribes(
                session=session,
                cache_key=cache_key,
                status=self._clean_text(body.get("status") or parsed.get("status") or "all"),
                media_type=self._clean_text(body.get("media_type") or body.get("type") or parsed.get("type") or "all"),
                name=keyword,
                limit=self._safe_int(body.get("limit"), 20),
            ))
        if assistant_action == "mp_transfer_history":
            return finish(await self._assistant_mp_transfer_history(
                session=session,
                cache_key=cache_key,
                title=keyword,
                status=self._clean_text(body.get("status") or parsed.get("status") or "all"),
                limit=self._safe_int(body.get("limit"), 10),
                page=self._safe_int(body.get("page"), 1),
            ))
        if assistant_action == "mp_subscribe_control":
            control = self._clean_text(parsed.get("subscribe_control") or body.get("subscribe_control") or body.get("control") or body.get("operation")).lower()
            control_aliases = {
                "搜索": "search",
                "刷新": "search",
                "search": "search",
                "run": "search",
                "暂停": "pause",
                "停止": "pause",
                "pause": "pause",
                "stop": "pause",
                "恢复": "resume",
                "继续": "resume",
                "resume": "resume",
                "start": "resume",
                "删除": "delete",
                "移除": "delete",
                "delete": "delete",
                "remove": "delete",
            }
            control = control_aliases.get(control, control)
            allow_raw_subscribe_id = body.get("subscribe_id") is not None
            target = self._clean_text(keyword or body.get("target") or body.get("subscribe_id") or body.get("index") or body.get("choice"))
            if control not in {"search", "pause", "resume", "delete"} or not target:
                return finish({
                    "success": False,
                    "message": "用法：先发“订阅列表”，再发“搜索订阅 1”“暂停订阅 1”“恢复订阅 1”或“删除订阅 1”。",
                    "data": self._assistant_response_data(session=session, data={
                        "action": "mp_subscribe_control",
                        "ok": False,
                        "error_code": "invalid_subscribe_control_args",
                    }),
                })
            if not self._resolve_mp_subscribe_target(target=target, cache_key=cache_key, allow_raw_id=allow_raw_subscribe_id):
                return finish({
                    "success": False,
                    "message": "未找到可操作的订阅。请先发送“订阅列表”获取列表，再按编号操作；也可以直接传订阅 ID。",
                    "data": self._assistant_response_data(session=session, data={
                        "action": "mp_subscribe_control",
                        "ok": False,
                        "error_code": "subscribe_target_not_found",
                        "target": target,
                    }),
                })
            if not self._parse_bool_value(body.get("confirmed") or body.get("execute"), False):
                return finish(immediate(self._assistant_mp_subscribe_control_plan_response(
                    control=control,
                    target=target,
                    session=session,
                    cache_key=cache_key,
                    allow_raw_id=allow_raw_subscribe_id,
                )))
            return finish(await self._assistant_mp_subscribe_control(
                session=session,
                cache_key=cache_key,
                control=control,
                target=target,
                allow_raw_id=allow_raw_subscribe_id,
            ))
        if assistant_action == "mp_download_tasks":
            return finish(await self._assistant_mp_download_tasks(
                session=session,
                cache_key=cache_key,
                status=self._clean_text(body.get("status") or parsed.get("status") or "downloading"),
                title=keyword,
                hash_value=self._clean_text(body.get("hash") or body.get("hash_value")),
                downloader=self._clean_text(body.get("downloader")),
                limit=self._safe_int(body.get("limit"), 10),
            ))
        if assistant_action == "mp_download_history":
            return finish(await self._assistant_mp_download_history(
                session=session,
                cache_key=cache_key,
                title=keyword,
                hash_value=self._clean_text(body.get("hash") or body.get("hash_value") or parsed.get("hash")),
                limit=self._safe_int(body.get("limit"), 10),
                page=self._safe_int(body.get("page"), 1),
            ))
        if assistant_action == "mp_lifecycle_status":
            return finish(await self._assistant_mp_lifecycle_status(
                session=session,
                cache_key=cache_key,
                title=keyword,
                hash_value=self._clean_text(body.get("hash") or body.get("hash_value") or parsed.get("hash")),
                limit=self._safe_int(body.get("limit"), 5),
            ))
        if assistant_action == "mp_download_control":
            control = self._clean_text(parsed.get("download_control") or body.get("download_control") or body.get("control") or body.get("operation")).lower()
            control_aliases = {
                "暂停": "pause",
                "停止": "pause",
                "pause": "pause",
                "stop": "pause",
                "恢复": "resume",
                "继续": "resume",
                "开始": "resume",
                "resume": "resume",
                "start": "resume",
                "删除": "delete",
                "移除": "delete",
                "delete": "delete",
                "remove": "delete",
            }
            control = control_aliases.get(control, control)
            target = self._clean_text(keyword or body.get("target") or body.get("hash") or body.get("index") or body.get("choice"))
            if control not in {"pause", "resume", "delete"} or not target:
                return finish({
                    "success": False,
                    "message": "用法：先发“下载任务”，再发“暂停下载 1”“恢复下载 1”或“删除下载 1”。",
                    "data": self._assistant_response_data(session=session, data={
                        "action": "mp_download_control",
                        "ok": False,
                        "error_code": "invalid_download_control_args",
                    }),
                })
            if not self._resolve_mp_download_task_target(target=target, cache_key=cache_key):
                return finish({
                    "success": False,
                    "message": "未找到可操作的下载任务。请先发送“下载任务”获取列表，再按编号操作；也可以直接传 40 位任务 hash。",
                    "data": self._assistant_response_data(session=session, data={
                        "action": "mp_download_control",
                        "ok": False,
                        "error_code": "download_task_target_not_found",
                        "target": target,
                    }),
                })
            if not self._parse_bool_value(body.get("confirmed") or body.get("execute"), False):
                return finish(immediate(self._assistant_mp_download_control_plan_response(
                    control=control,
                    target=target,
                    session=session,
                    cache_key=cache_key,
                    downloader=self._clean_text(body.get("downloader")),
                    delete_files=self._parse_bool_value(body.get("delete_files"), False),
                )))
            return finish(await self._assistant_mp_download_control(
                session=session,
                cache_key=cache_key,
                control=control,
                target=target,
                downloader=self._clean_text(body.get("downloader")),
                delete_files=self._parse_bool_value(body.get("delete_files"), False),
            ))
        if assistant_action == "mp_download_best":
            preferences = self._normalize_assistant_preferences((self._assistant_preferences or {}).get(self._normalize_preference_key(session=session)))
            return finish(await self._assistant_mp_best_download_plan(
                session=session,
                cache_key=cache_key,
                preferences=preferences,
            ))
        if assistant_action == "mp_download":
            choice = self._safe_int(parsed.get("keyword") or body.get("choice") or body.get("index"), 0)
            if choice <= 0:
                return finish({
                    "success": False,
                    "message": "用法：下载资源 1",
                        "data": self._assistant_response_data(session=session, data={"action": "mp_download", "ok": False}),
                })
            preferences = self._normalize_assistant_preferences((self._assistant_preferences or {}).get(self._normalize_preference_key(session=session)))
            if not self._parse_bool_value(body.get("confirmed") or body.get("execute"), False):
                return finish(immediate(self._assistant_mp_download_plan_response(
                    choice=choice,
                    session=session,
                    cache_key=cache_key,
                    preferences=preferences,
                )))
            return finish(await self._assistant_mp_download(
                choice=choice,
                session=session,
                cache_key=cache_key,
                preferences=preferences,
            ))
        if assistant_action in {"mp_subscribe", "mp_subscribe_search"}:
            if not keyword:
                return finish({
                    "success": False,
                    "message": "用法：订阅媒体 片名 或 订阅并搜索 片名",
                    "data": self._assistant_response_data(session=session, data={"action": assistant_action, "ok": False}),
                })
            if not self._parse_bool_value(body.get("confirmed") or body.get("execute"), False):
                return finish(immediate(self._assistant_mp_subscribe_plan_response(
                    keyword=keyword,
                    session=session,
                    cache_key=cache_key,
                    immediate_search=assistant_action == "mp_subscribe_search",
                )))
            return finish(await self._assistant_mp_subscribe(
                keyword=keyword,
                session=session,
                immediate_search=assistant_action == "mp_subscribe_search",
            ))
        if assistant_action == "mp_recommendations":
            source, inferred_media_type = self._normalize_mp_recommend_request(
                body.get("source") or parsed.get("keyword") or text or "tmdb_trending"
            )
            return finish(await self._assistant_mp_recommendations(
                source=source,
                media_type=self._clean_text(body.get("media_type") or body.get("type") or parsed.get("type") or inferred_media_type or "all"),
                limit=self._safe_int(body.get("limit"), 20),
                session=session,
                cache_key=cache_key,
            ))
        if assistant_action == "p115_help":
            summary = self._format_p115_help_text()
            pending_summary = self._pending_p115_summary(state)
            if pending_summary:
                summary = f"{summary}\n{pending_summary}"
            return {
                "success": True,
                "message": summary,
                "data": self._assistant_response_data(session=session, data={
                    "action": "p115_help",
                    "ok": True,
                    "status_summary": summary,
                    "status": self._p115_status_snapshot(),
                }),
            }
        if assistant_action == "p115_status":
            summary = self._format_p115_status_summary()
            pending_summary = self._pending_p115_summary(state)
            if pending_summary:
                summary = f"{summary}\n{pending_summary}"
            return finish({
                "success": True,
                "message": summary,
                "data": self._assistant_response_data(session=session, data={
                    "action": "p115_status",
                    "ok": True,
                    "status_summary": summary,
                    "status": self._p115_status_snapshot(),
                }),
            })
        if assistant_action == "p115_pending":
            pending_summary = self._pending_p115_summary(state)
            if not pending_summary:
                return {
                    "success": True,
                    "message": "当前没有待继续的 115 任务。",
                    "data": self._assistant_response_data(session=session, data={"action": "p115_pending", "ok": True}),
                }
            return {
                "success": True,
                "message": pending_summary,
                "data": self._assistant_response_data(session=session, data={"action": "p115_pending", "ok": True}),
            }
        if assistant_action == "p115_resume":
            pending_summary = self._pending_p115_summary(state)
            if not pending_summary:
                summary = self._format_p115_status_summary()
                return {
                    "success": False,
                    "message": f"当前没有待继续的 115 任务。\n{summary}",
                    "data": self._assistant_response_data(session=session, data={"action": "p115_resume", "ok": False}),
                }
            if not self._p115_status_snapshot().get("ready"):
                return {
                    "success": False,
                    "message": f"{pending_summary}\n当前 115 还不可用，请先回复：115登录",
                    "data": self._assistant_response_data(session=session, data={"action": "p115_resume", "ok": False}),
                }
            resume_ok, resume_message, resume_data = await self._resume_pending_p115_share(
                request,
                body,
                session_id=cache_key,
                state=state,
            )
            message_text = "已手动继续 115 任务"
            if resume_message:
                message_text = f"{message_text}\n{resume_message}"
            if not resume_ok:
                message_text = f"{message_text}\n任务仍未成功，保留待继续状态。"
            return {
                "success": resume_ok,
                "message": message_text,
                "data": self._assistant_response_data(session=session, data={"action": "p115_resume", "ok": resume_ok, "result": resume_data}),
            }
        if assistant_action == "p115_cancel":
            pending_summary = self._pending_p115_summary(state)
            if not pending_summary:
                return {
                    "success": True,
                    "message": "当前没有待取消的 115 任务。",
                    "data": self._assistant_response_data(session=session, data={"action": "p115_cancel", "ok": True}),
                }
            self._clear_pending_p115_share(cache_key)
            return {
                "success": True,
                "message": f"{pending_summary}\n已取消并清除这次待继续的 115 任务。",
                "data": self._assistant_response_data(session=session, data={"action": "p115_cancel", "ok": True}),
            }
        if assistant_action == "p115_qrcode_start":
            previous_state = state
            client_type = P115TransferService.normalize_qrcode_client_type(
                parsed.get("client_type") or self._p115_client_type
            )
            qr_ok, data, qr_message = self._ensure_p115_service().create_qrcode_login(client_type=client_type)
            if not qr_ok:
                return {"success": False, "message": f"115 扫码二维码生成失败：{qr_message}"}
            self._save_session(
                cache_key,
                {
                    **previous_state,
                    "kind": "assistant_p115_login",
                    "stage": "qrcode",
                    "client_type": client_type,
                    "uid": self._clean_text(data.get("uid")),
                    "time": self._clean_text(data.get("time")),
                    "sign": self._clean_text(data.get("sign")),
                },
            )
            pending_text = ""
            if (previous_state.get("pending_p115") or {}).get("share_url"):
                pending_text = "\n检测到有待继续的 115 任务，登录成功后我会自动继续执行。"
            return {
                "success": True,
                "message": (
                    "115 扫码二维码已生成\n"
                    f"客户端：{client_type}\n"
                    "请使用 115 App 扫码确认后，再回复：检查115登录"
                    f"{pending_text}"
                ),
                "data": self._assistant_response_data(session=session, data={
                    "action": "p115_qrcode_start",
                    "ok": True,
                    "qrcode": data.get("qrcode"),
                    "uid": data.get("uid"),
                    "time": data.get("time"),
                    "sign": data.get("sign"),
                    "client_type": client_type,
                }),
            }
        if assistant_action == "p115_qrcode_check":
            if not state or str(state.get("kind") or "").strip() != "assistant_p115_login":
                pending_summary = self._pending_p115_summary(state)
                if pending_summary and self._p115_status_snapshot().get("ready"):
                    resume_ok, resume_message, resume_data = await self._resume_pending_p115_share(
                        request,
                        body,
                        session_id=cache_key,
                        state=state,
                    )
                    message_text = "没有待检查的扫码会话，但检测到待继续的 115 任务。"
                    if resume_message:
                        message_text = f"{message_text}\n{resume_message}"
                    if not resume_ok:
                        message_text = f"{message_text}\n任务仍未成功，继续保留待处理状态。"
                    return {
                        "success": resume_ok,
                        "message": message_text,
                        "data": self._assistant_response_data(session=session, data={"action": "p115_qrcode_check", "ok": resume_ok, "result": resume_data}),
                    }
                summary = self._format_p115_status_summary()
                if pending_summary:
                    summary = f"{summary}\n{pending_summary}"
                return {
                    "success": True,
                    "message": (
                        "没有待检查的 115 登录会话。\n"
                        f"{summary}\n"
                        "如需重新扫码登录，请回复：115登录"
                    ),
                    "data": {
                        **self._assistant_response_data(session=session, data={
                            "action": "p115_qrcode_check",
                            "ok": True,
                            "status_summary": summary,
                            "status": self._p115_status_snapshot(),
                        }),
                    },
                }
            client_type = P115TransferService.normalize_qrcode_client_type(
                state.get("client_type") or parsed.get("client_type") or self._p115_client_type
            )
            qr_ok, data, qr_message = self._ensure_p115_service().check_qrcode_login(
                uid=self._clean_text(state.get("uid")),
                time_value=self._clean_text(state.get("time")),
                sign=self._clean_text(state.get("sign")),
                client_type=client_type,
            )
            if qr_ok and data.get("status") == "success":
                cookie = self._clean_text(data.pop("cookie"))
                if cookie:
                    self._p115_cookie = cookie
                    self._p115_client_type = client_type
                    self._apply_runtime_config({
                        "p115_cookie": cookie,
                        "p115_client_type": client_type,
                    })
                    data["cookie_saved"] = True
                    data["cookie_mode"] = "client_cookie"
                    self._save_session(cache_key, {**state, "stage": "success", "client_type": client_type})
            if not qr_ok:
                return {
                    "success": False,
                    "message": f"115 扫码状态：{qr_message}",
                    "data": self._assistant_response_data(session=session, data={"action": "p115_qrcode_check", "ok": False, **data}),
                }
            status = self._clean_text(data.get("status"))
            lines = [
                "115 扫码状态",
                f"状态：{status or 'unknown'}",
                f"结果：{qr_message}",
            ]
            if data.get("cookie_saved"):
                lines.append(self._format_p115_status_summary(title="115 登录完成"))
                resume_ok, resume_message, resume_data = await self._resume_pending_p115_share(
                    request,
                    body,
                    session_id=cache_key,
                    state=state,
                )
                if resume_message:
                    lines.append("已自动继续刚才未完成的 115 任务")
                    lines.append(resume_message)
                    data["resume_ok"] = resume_ok
                    data["resume_result"] = resume_data
                    if not resume_ok:
                        lines.append("任务仍未成功，已继续保留待处理状态。")
            elif status in {"waiting", "scanned"}:
                lines.append("如果还没确认登录，请在 115 App 里点确认后再次回复：检查115登录")
            message_text = "\n".join(line for line in lines if line).strip()
            return {
                "success": True,
                "message": message_text,
                "data": self._assistant_response_data(session=session, data={"action": "p115_qrcode_check", "ok": True, **data}),
            }

        if parsed.get("url"):
            provider = "quark" if self._is_quark_url(parsed["url"]) else "115" if self._is_115_url(parsed["url"]) else "unknown"
            result = await self.api_share_route(
                _JsonRequestShim(request, {
                    "url": parsed["url"],
                    "access_code": parsed.get("access_code") or "",
                    "path": target_path,
                    "trigger": "Agent影视助手 智能入口",
                    "apikey": self._extract_apikey(request, body),
                })
            )
            if provider == "115":
                if result.get("success"):
                    self._clear_pending_p115_share(cache_key)
                else:
                    self._save_pending_p115_share(
                        cache_key,
                        share_url=parsed["url"],
                        access_code=parsed.get("access_code") or "",
                        target_path=target_path or self._p115_default_path,
                        source="assistant_link",
                        last_error=str(result.get("message") or ""),
                    )
            return finish({
                "success": bool(result.get("success")),
                "message": (
                    f"{'夸克' if provider == 'quark' else '115' if provider == '115' else '分享'}转存已完成\n目录："
                    f"{((result.get('data') or {}).get('result') or {}).get('target_path') or ((result.get('data') or {}).get('result') or {}).get('path') or target_path or '-'}"
                    if result.get("success")
                    else (
                        f"{str(result.get('message') or '处理失败')}\n{self._format_p115_resume_hint()}"
                        if provider == "115"
                        else str(result.get("message") or "处理失败")
                    )
                ),
                "data": self._assistant_response_data(session=session, data={
                    "action": "share_route",
                    "ok": bool(result.get("success")),
                    "provider": provider,
                    "result": result.get("data") or {},
                }),
            })

        mode = parsed.get("mode") or "hdhive"
        media_type = self._clean_text(parsed.get("type") or "auto").lower() or "auto"
        year = self._clean_text(parsed.get("year"))

        if mode == "mp":
            if not keyword:
                return finish({
                    "success": False,
                    "message": "用法：MP搜索 片名",
                    "data": self._assistant_response_data(session=session, data={
                        "action": "media_search",
                        "ok": False,
                    }),
                })
            preferences = self._normalize_assistant_preferences((self._assistant_preferences or {}).get(self._normalize_preference_key(session=session)))
            return finish(await self._assistant_mp_media_search(
                keyword=keyword,
                session=session,
                cache_key=cache_key,
                preferences=preferences,
            ))

        if mode == "pansou":
            search_ok, payload, search_message = self._call_pansou_search(keyword)
            if not search_ok:
                return {"success": False, "message": f"盘搜搜索失败：{keyword}\n错误：{search_message}"}
            data = payload.get("data") or {}
            merged = data.get("merged_by_type") or {}
            channel_115 = self._collect_pansou_channel_items(merged, "115", 6)
            channel_quark = self._collect_pansou_channel_items(merged, "quark", 6)
            items: List[Dict[str, Any]] = []
            for item in channel_115 + channel_quark:
                items.append({**item, "index": len(items) + 1})
            if not items:
                return {"success": False, "message": f"盘搜暂无结果：{keyword}"}
            preferences = self._normalize_assistant_preferences((self._assistant_preferences or {}).get(self._normalize_preference_key(session=session)))
            items = self._attach_cloud_scores(
                items,
                preferences=preferences,
                source_type="pansou",
                target_path=target_path or self._hdhive_default_path,
            )
            self._save_session(
                cache_key,
                {
                    "kind": "assistant_pansou",
                    "stage": "result",
                    "keyword": keyword,
                    "target_path": target_path or self._hdhive_default_path,
                    "items": items,
                },
            )
            text_message = self._format_pansou_text(keyword, items, int(data.get("total") or len(items)))
            return finish({
                "success": True,
                "message": text_message,
                "data": self._assistant_response_data(session=session, data={
                "action": "pansou_search",
                "ok": True,
                "items": items,
                "score_summary": self._score_summary(items, limit=5),
            }),
        })

        allowed, disabled = self._ensure_hdhive_resource_enabled()
        if not allowed:
            return finish({
                "success": False,
                "message": disabled.get("message") or "影巢资源入口已关闭",
                "data": self._assistant_response_data(session=session, data={
                    "action": "hdhive_candidates",
                    "ok": False,
                    "error_code": "hdhive_resource_disabled",
                    "resource_enabled": False,
                }),
            })

        service = self._ensure_hdhive_service()
        search_ok, result, search_message = await service.resolve_candidates_by_keyword(
            keyword=keyword,
            media_type=media_type,
            year=year,
            candidate_limit=max(30, self._hdhive_candidate_page_size),
        )
        if not search_ok:
            return {"success": False, "message": f"影巢搜索失败：{search_message}", "data": result}
        candidates = result.get("candidates") or []
        self._save_session(
            cache_key,
            {
                "kind": "assistant_hdhive",
                "stage": "candidate",
                "keyword": keyword,
                "media_type": media_type,
                "year": year,
                "target_path": target_path or self._hdhive_default_path,
                "candidates": candidates,
                "page": 1,
                "page_size": self._hdhive_candidate_page_size,
            },
        )
        text_message = self._format_candidate_lines(candidates, page=1, page_size=self._hdhive_candidate_page_size)
        return finish({
            "success": True,
            "message": text_message,
            "data": self._assistant_response_data(session=session, data={
                "action": "hdhive_candidates",
                "ok": True,
                "candidates": candidates,
            }),
        })

    async def api_assistant_action(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        name = self._clean_text(body.get("name") or body.get("action_name"))
        if not name:
            return {"success": False, "message": "缺少动作名 name"}
        compact = self._parse_bool_value(body.get("compact"), False)

        async def finish(awaitable):
            result = await awaitable
            return self._assistant_single_action_compact_response(name, result) if compact else result

        async def immediate(result: Dict[str, Any]) -> Dict[str, Any]:
            return result

        route_payload = {
            "session": body.get("session"),
            "session_id": body.get("session_id"),
            "path": body.get("path") or body.get("target_path"),
            "apikey": self._extract_apikey(request, body),
        }
        pick_payload = {
            "session": body.get("session"),
            "session_id": body.get("session_id"),
            "path": body.get("path") or body.get("target_path"),
            "apikey": self._extract_apikey(request, body),
        }

        if name == "start_pansou_search":
            route_payload.update({
                "mode": "pansou",
                "keyword": body.get("keyword"),
            })
            return await finish(self.api_assistant_route(_JsonRequestShim(request, route_payload)))
        if name == "start_hdhive_search":
            route_payload.update({
                "mode": "hdhive",
                "keyword": body.get("keyword"),
                "media_type": body.get("media_type") or "auto",
                "year": body.get("year"),
            })
            return await finish(self.api_assistant_route(_JsonRequestShim(request, route_payload)))
        if name == "start_mp_media_search":
            route_payload.update({
                "mode": "mp",
                "keyword": body.get("keyword"),
            })
            return await finish(self.api_assistant_route(_JsonRequestShim(request, route_payload)))
        if name == "query_mp_media_detail":
            session_name, cache_key = self._normalize_assistant_session_ref(
                session=body.get("session") or "default",
                session_id=body.get("session_id"),
            )
            return await finish(self._assistant_mp_media_detail(
                keyword=self._clean_text(body.get("keyword") or body.get("title")),
                session=session_name,
                cache_key=cache_key,
                media_type=self._clean_text(body.get("media_type") or body.get("type") or "auto"),
                year=self._clean_text(body.get("year")),
            ))
        if name == "query_mp_search_result_detail":
            session_name, cache_key = self._normalize_assistant_session_ref(
                session=body.get("session") or "default",
                session_id=body.get("session_id"),
            )
            prefs = self._assistant_preferences_public_data(session=session_name).get("preferences") or self._default_assistant_preferences()
            return await finish(self._assistant_mp_result_detail(
                choice=self._safe_int(body.get("choice") or body.get("index"), 0),
                session=session_name,
                cache_key=cache_key,
                preferences=prefs,
            ))
        if name == "query_mp_best_result_detail":
            session_name, cache_key = self._normalize_assistant_session_ref(
                session=body.get("session") or "default",
                session_id=body.get("session_id"),
            )
            prefs = self._assistant_preferences_public_data(session=session_name).get("preferences") or self._default_assistant_preferences()
            return await finish(self._assistant_mp_best_result_detail(
                session=session_name,
                cache_key=cache_key,
                preferences=prefs,
            ))
        if name == "pick_mp_best_download":
            session_name, cache_key = self._normalize_assistant_session_ref(
                session=body.get("session") or "default",
                session_id=body.get("session_id"),
            )
            prefs = self._assistant_preferences_public_data(session=session_name).get("preferences") or self._default_assistant_preferences()
            return await finish(self._assistant_mp_best_download_plan(
                session=session_name,
                cache_key=cache_key,
                preferences=prefs,
            ))
        if name == "pick_mp_download":
            session_name, cache_key = self._normalize_assistant_session_ref(
                session=body.get("session") or "default",
                session_id=body.get("session_id"),
            )
            prefs = self._assistant_preferences_public_data(session=session_name).get("preferences") or self._default_assistant_preferences()
            execute_requested = self._parse_bool_value(body.get("execute") or body.get("confirmed"), False)
            choice = self._safe_int(body.get("choice") or body.get("index"), 0)
            if not execute_requested:
                return await finish(immediate(self._assistant_mp_download_plan_response(
                    choice=choice,
                    session=session_name,
                    cache_key=cache_key,
                    preferences=prefs,
                )))
            return await finish(self._assistant_mp_download(
                choice=choice,
                session=session_name,
                cache_key=cache_key,
                preferences=prefs,
            ))
        if name == "query_mp_download_tasks":
            session_name, cache_key = self._normalize_assistant_session_ref(
                session=body.get("session") or "default",
                session_id=body.get("session_id"),
            )
            return await finish(self._assistant_mp_download_tasks(
                session=session_name,
                cache_key=cache_key,
                status=self._clean_text(body.get("status") or "downloading"),
                title=self._clean_text(body.get("title") or body.get("keyword")),
                hash_value=self._clean_text(body.get("hash") or body.get("hash_value")),
                downloader=self._clean_text(body.get("downloader")),
                limit=self._safe_int(body.get("limit"), 10),
            ))
        if name == "query_mp_download_history":
            session_name, cache_key = self._normalize_assistant_session_ref(
                session=body.get("session") or "default",
                session_id=body.get("session_id"),
            )
            return await finish(self._assistant_mp_download_history(
                session=session_name,
                cache_key=cache_key,
                title=self._clean_text(body.get("title") or body.get("keyword")),
                hash_value=self._clean_text(body.get("hash") or body.get("hash_value")),
                limit=self._safe_int(body.get("limit"), 10),
                page=self._safe_int(body.get("page"), 1),
            ))
        if name == "query_mp_lifecycle_status":
            session_name, cache_key = self._normalize_assistant_session_ref(
                session=body.get("session") or "default",
                session_id=body.get("session_id"),
            )
            return await finish(self._assistant_mp_lifecycle_status(
                session=session_name,
                cache_key=cache_key,
                title=self._clean_text(body.get("title") or body.get("keyword")),
                hash_value=self._clean_text(body.get("hash") or body.get("hash_value")),
                limit=self._safe_int(body.get("limit"), 5),
            ))
        if name == "query_mp_downloaders":
            session_name, cache_key = self._normalize_assistant_session_ref(
                session=body.get("session") or "default",
                session_id=body.get("session_id"),
            )
            return await finish(self._assistant_mp_downloaders(session=session_name, cache_key=cache_key))
        if name == "query_mp_sites":
            session_name, cache_key = self._normalize_assistant_session_ref(
                session=body.get("session") or "default",
                session_id=body.get("session_id"),
            )
            return await finish(self._assistant_mp_sites(
                session=session_name,
                cache_key=cache_key,
                status=self._clean_text(body.get("status") or "active"),
                name=self._clean_text(body.get("site_name") or body.get("keyword") or body.get("title")),
                limit=self._safe_int(body.get("limit"), 30),
            ))
        if name == "query_mp_subscribes":
            session_name, cache_key = self._normalize_assistant_session_ref(
                session=body.get("session") or "default",
                session_id=body.get("session_id"),
            )
            return await finish(self._assistant_mp_subscribes(
                session=session_name,
                cache_key=cache_key,
                status=self._clean_text(body.get("status") or "all"),
                media_type=self._clean_text(body.get("media_type") or body.get("type") or "all"),
                name=self._clean_text(body.get("subscribe_name") or body.get("keyword") or body.get("title")),
                limit=self._safe_int(body.get("limit"), 20),
            ))
        if name == "query_mp_transfer_history":
            session_name, cache_key = self._normalize_assistant_session_ref(
                session=body.get("session") or "default",
                session_id=body.get("session_id"),
            )
            return await finish(self._assistant_mp_transfer_history(
                session=session_name,
                cache_key=cache_key,
                title=self._clean_text(body.get("title") or body.get("keyword")),
                status=self._clean_text(body.get("status") or "all"),
                limit=self._safe_int(body.get("limit"), 10),
                page=self._safe_int(body.get("page"), 1),
            ))
        if name == "mp_subscribe_control":
            session_name, cache_key = self._normalize_assistant_session_ref(
                session=body.get("session") or "default",
                session_id=body.get("session_id"),
            )
            control = self._clean_text(body.get("control") or body.get("subscribe_control") or body.get("operation"))
            target = self._clean_text(body.get("target") or body.get("subscribe_id") or body.get("index") or body.get("choice"))
            allow_raw_subscribe_id = body.get("subscribe_id") is not None
            execute_requested = self._parse_bool_value(body.get("execute") or body.get("confirmed"), False)
            if not execute_requested:
                return await finish(immediate(self._assistant_mp_subscribe_control_plan_response(
                    control=control,
                    target=target,
                    session=session_name,
                    cache_key=cache_key,
                    allow_raw_id=allow_raw_subscribe_id,
                )))
            return await finish(self._assistant_mp_subscribe_control(
                session=session_name,
                cache_key=cache_key,
                control=control,
                target=target,
                allow_raw_id=allow_raw_subscribe_id,
            ))
        if name == "mp_download_control":
            session_name, cache_key = self._normalize_assistant_session_ref(
                session=body.get("session") or "default",
                session_id=body.get("session_id"),
            )
            control = self._clean_text(body.get("control") or body.get("download_control") or body.get("operation"))
            target = self._clean_text(body.get("target") or body.get("hash") or body.get("index") or body.get("choice"))
            downloader = self._clean_text(body.get("downloader"))
            delete_files = self._parse_bool_value(body.get("delete_files"), False)
            execute_requested = self._parse_bool_value(body.get("execute") or body.get("confirmed"), False)
            if not execute_requested:
                return await finish(immediate(self._assistant_mp_download_control_plan_response(
                    control=control,
                    target=target,
                    session=session_name,
                    cache_key=cache_key,
                    downloader=downloader,
                    delete_files=delete_files,
                )))
            return await finish(self._assistant_mp_download_control(
                session=session_name,
                cache_key=cache_key,
                control=control,
                target=target,
                downloader=downloader,
                delete_files=delete_files,
            ))
        if name in {"start_mp_subscribe", "start_mp_subscribe_search"}:
            session_name, cache_key = self._normalize_assistant_session_ref(
                session=body.get("session") or "default",
                session_id=body.get("session_id"),
            )
            keyword = self._clean_text(body.get("keyword") or body.get("title"))
            if not keyword:
                state = self._load_session(cache_key) or {}
                keyword = self._clean_text(state.get("keyword"))
            execute_requested = self._parse_bool_value(body.get("execute") or body.get("confirmed"), False)
            if not execute_requested:
                return await finish(immediate(self._assistant_mp_subscribe_plan_response(
                    keyword=keyword,
                    session=session_name,
                    cache_key=cache_key,
                    immediate_search=name == "start_mp_subscribe_search",
                )))
            return await finish(self._assistant_mp_subscribe(
                keyword=keyword,
                session=session_name,
                immediate_search=name == "start_mp_subscribe_search",
            ))
        if name == "start_mp_recommendations":
            recommend_session, recommend_cache_key = self._normalize_assistant_session_ref(
                session=self._clean_text(body.get("session")) or "default",
                session_id=body.get("session_id"),
            )
            source_name, inferred_media_type = self._normalize_mp_recommend_request(
                body.get("source") or "tmdb_trending"
            )
            return await finish(self._assistant_mp_recommendations(
                source=source_name,
                media_type=self._clean_text(body.get("media_type") or body.get("type") or inferred_media_type) or "all",
                limit=self._safe_int(body.get("limit"), 20),
                session=recommend_session,
                cache_key=recommend_cache_key,
            ))
        if name == "pick_recommend_search":
            pick_payload.update({
                "choice": body.get("choice") or body.get("index"),
                "mode": body.get("mode") or body.get("search_mode") or "mp",
            })
            return await finish(self.api_assistant_pick(_JsonRequestShim(request, pick_payload)))
        if name in {"preferences_get", "preferences_save", "preferences_reset"}:
            method = "GET" if name == "preferences_get" else "DELETE" if name == "preferences_reset" else "POST"
            payload = {
                "session": body.get("session"),
                "session_id": body.get("session_id"),
                "user_key": body.get("user_key"),
                "preferences": body.get("preferences") or {},
                "compact": body.get("compact", True),
                "apikey": self._extract_apikey(request, body),
            }
            return await finish(self.api_assistant_preferences(_JsonRequestShim(request, payload, method=method)))
        if name == "start_115_login":
            route_payload.update({
                "action": "p115_qrcode_start",
                "client_type": body.get("client_type"),
            })
            return await finish(self.api_assistant_route(_JsonRequestShim(request, route_payload)))
        if name == "route_share":
            route_payload.update({
                "url": body.get("url") or body.get("share_url"),
                "access_code": body.get("access_code"),
            })
            return await finish(self.api_assistant_route(_JsonRequestShim(request, route_payload)))
        if name == "unlock_hdhive_resource":
            session_name, cache_key = self._normalize_assistant_session_ref(
                session=body.get("session") or "default",
                session_id=body.get("session_id"),
            )
            resource = body.get("resource") if isinstance(body.get("resource"), dict) else {}
            slug = self._clean_text(body.get("slug") or resource.get("slug"))
            final_path = self._resolve_pan_path_value(
                self._clean_text(body.get("path") or body.get("target_path"))
            ) or self._hdhive_default_path
            if not slug:
                return await finish(immediate({
                    "success": False,
                    "message": "影巢解锁动作缺少 slug",
                    "data": self._assistant_response_data(session=session_name, data={
                        "action": "hdhive_unlock",
                        "ok": False,
                        "error_code": "missing_slug",
                    }),
                }))
            route_ok, route_result, route_message = await self._unlock_and_route(
                slug,
                target_path=final_path,
                resource=resource,
            )
            if not route_ok:
                route = dict((route_result or {}).get("route") or {})
                share_url = self._clean_text(route.get("share_url"))
                if self._is_115_url(share_url) or self._clean_text(route.get("provider")) == "115":
                    self._save_pending_p115_share(
                        cache_key,
                        share_url=share_url,
                        access_code=route.get("access_code") or "",
                        target_path=route.get("target_path") or final_path,
                        source="assistant_hdhive_plan",
                        title=resource.get("title") or resource.get("matched_title") or "",
                        last_error=route_message,
                    )
                return await finish(immediate({
                    "success": False,
                    "message": route_message,
                    "data": self._assistant_response_data(session=session_name, data={
                        "action": "hdhive_unlock",
                        "ok": False,
                        "selected_resource": resource,
                        "result": route_result,
                    }),
                }))
            return await finish(immediate({
                "success": True,
                "message": self._format_route_result(route_result),
                "data": self._assistant_response_data(session=session_name, data={
                    "action": "hdhive_unlock",
                    "ok": True,
                    "selected_resource": resource,
                    "result": route_result,
                }),
            }))
        if name == "inspect_session_state":
            return await finish(self.api_assistant_session_state(_JsonRequestShim(request, {
                "session": body.get("session"),
                "session_id": body.get("session_id"),
                "apikey": self._extract_apikey(request, body),
            })))
        if name in {"execute_latest_plan", "execute_plan", "execute_session_latest_plan"}:
            return await finish(self.api_assistant_plan_execute(_JsonRequestShim(request, {
                "plan_id": body.get("plan_id"),
                "session": body.get("session"),
                "session_id": body.get("session_id"),
                "prefer_unexecuted": body.get("prefer_unexecuted", True),
                "stop_on_error": body.get("stop_on_error", True),
                "include_raw_results": body.get("include_raw_results", False),
                "apikey": self._extract_apikey(request, body),
            })))
        if name in {"pick_pansou_result", "pick_hdhive_candidate", "pick_hdhive_resource"}:
            pick_payload.update({"choice": body.get("choice") or body.get("index")})
            return await finish(self.api_assistant_pick(_JsonRequestShim(request, pick_payload)))
        if name in {"plan_pansou_result", "plan_hdhive_resource", "plan_pick_result"}:
            pick_payload.update({
                "choice": body.get("choice") or body.get("index"),
                "action": "plan",
            })
            return await finish(self.api_assistant_pick(_JsonRequestShim(request, pick_payload)))
        if name == "candidate_detail":
            pick_payload.update({"action": "detail"})
            return await finish(self.api_assistant_pick(_JsonRequestShim(request, pick_payload)))
        if name == "candidate_next_page":
            pick_payload.update({"action": "next_page"})
            return await finish(self.api_assistant_pick(_JsonRequestShim(request, pick_payload)))
        if name == "check_115_login":
            route_payload.update({"action": "p115_qrcode_check"})
            return await finish(self.api_assistant_route(_JsonRequestShim(request, route_payload)))
        if name == "show_115_status":
            route_payload.update({"action": "p115_status"})
            return await finish(self.api_assistant_route(_JsonRequestShim(request, route_payload)))
        if name == "resume_pending_115":
            route_payload.update({"action": "p115_resume"})
            return await finish(self.api_assistant_route(_JsonRequestShim(request, route_payload)))
        if name == "cancel_pending_115":
            route_payload.update({"action": "p115_cancel"})
            return await finish(self.api_assistant_route(_JsonRequestShim(request, route_payload)))
        if name == "clear_current_session":
            return await finish(self.api_assistant_session_clear(_JsonRequestShim(request, {
                "session": body.get("session"),
                "session_id": body.get("session_id"),
                "apikey": self._extract_apikey(request, body),
            })))
        if name == "inspect_session":
            return await finish(self.api_assistant_session_state(_JsonRequestShim(request, {
                "session": body.get("session"),
                "session_id": body.get("session_id"),
                "apikey": self._extract_apikey(request, body),
            })))
        if name == "clear_session_by_id":
            return await finish(self.api_assistant_sessions_clear(_JsonRequestShim(request, {
                "session_id": body.get("session_id"),
                "apikey": self._extract_apikey(request, body),
            })))
        if name == "clear_stale_sessions":
            return await finish(self.api_assistant_sessions_clear(_JsonRequestShim(request, {
                "stale_only": True,
                "limit": body.get("limit") or 100,
                "apikey": self._extract_apikey(request, body),
            })))
        if name == "clear_executed_plans":
            return await finish(self.api_assistant_plans_clear(_JsonRequestShim(request, {
                "executed": True,
                "limit": body.get("limit") or 100,
                "apikey": self._extract_apikey(request, body),
            })))

        return {"success": False, "message": f"不支持的动作模板：{name}"}

    @staticmethod
    def _assistant_result_message_head(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return text.splitlines()[0][:200]

    def _assistant_action_result_summary(
        self,
        *,
        index: int,
        name: str,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        data = dict((result or {}).get("data") or {})
        session_state = dict(data.get("session_state") or {})
        if not session_state and (
            "has_session" in data
            or "kind" in data
            or "stage" in data
            or "suggested_actions" in data
        ):
            session_state = dict(data)
        summary = {
            "index": index,
            "name": self._clean_text(name),
            "success": bool((result or {}).get("success")),
            "action": self._clean_text(data.get("action")) or self._clean_text(name),
            "ok": bool(data.get("ok")) if "ok" in data else bool((result or {}).get("success")),
            "message_head": self._assistant_result_message_head((result or {}).get("message")),
            "session": self._clean_text(data.get("session") or session_state.get("session")),
            "session_id": self._clean_text(data.get("session_id") or session_state.get("session_id")),
            "kind": self._clean_text(session_state.get("kind")),
            "stage": self._clean_text(session_state.get("stage")),
            "next_actions": data.get("next_actions") or session_state.get("suggested_actions") or [],
            "has_pending_p115": bool(((session_state.get("pending_p115") or {}).get("has_pending"))),
        }
        if isinstance(data.get("score_summary"), dict):
            summary["score_summary"] = data.get("score_summary")
        return summary

    async def api_assistant_actions(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        actions = body.get("actions") or []
        if not isinstance(actions, list) or not actions:
            return {"success": False, "message": "缺少 actions 数组"}

        apikey = self._extract_apikey(request, body)
        requested_count = min(len(actions), 20)
        stop_on_error = self._parse_bool_value(body.get("stop_on_error"), True)
        include_raw_results = self._parse_bool_value(body.get("include_raw_results"), False)
        compact = self._parse_bool_value(body.get("compact"), False)
        batch_session = self._clean_text(body.get("session")) or "default"
        batch_session_id = self._clean_text(body.get("session_id"))

        summaries: List[Dict[str, Any]] = []
        raw_results: List[Dict[str, Any]] = []
        halted = False
        halted_at = 0

        for idx, item in enumerate(actions[:requested_count], 1):
            payload = dict(item or {}) if isinstance(item, dict) else {"name": self._clean_text(item)}
            if not payload.get("session") and batch_session:
                payload["session"] = batch_session
            if not payload.get("session_id") and batch_session_id:
                payload["session_id"] = batch_session_id
            if "execute" not in payload and "execute" in body:
                payload["execute"] = body.get("execute")
            if apikey and not payload.get("apikey") and not payload.get("api_key"):
                payload["apikey"] = apikey
            action_name = self._clean_text(payload.get("name") or payload.get("action_name"))
            result = await self.api_assistant_action(_JsonRequestShim(request, payload))
            summaries.append(self._assistant_action_result_summary(index=idx, name=action_name, result=result))
            if include_raw_results:
                raw_results.append(result)
            if not result.get("success") and stop_on_error:
                halted = True
                halted_at = idx
                break

        final_session = batch_session
        final_session_id = batch_session_id
        if summaries:
            final_session = self._clean_text(summaries[-1].get("session")) or final_session
            final_session_id = self._clean_text(summaries[-1].get("session_id")) or final_session_id
        session_name, _ = self._normalize_assistant_session_ref(session=final_session, session_id=final_session_id)

        success = bool(summaries) and all(item.get("success") for item in summaries)
        if halted:
            success = False

        message_lines = [
            f"批量动作执行完成：{len(summaries)}/{requested_count} 步",
            f"成功：{len([item for item in summaries if item.get('success')])} 步",
        ]
        if halted:
            message_lines.append(f"已在第 {halted_at} 步停止")
        else:
            message_lines.append("已按顺序执行完毕")
        if summaries:
            last_head = self._clean_text(summaries[-1].get("message_head"))
            if last_head:
                message_lines.append(f"最后结果：{last_head}")

        data = {
            "action": "execute_actions",
            "ok": success,
            "executed_count": len(summaries),
            "requested_count": requested_count,
            "stopped_on_error": halted,
            "halted_at": halted_at,
            "results": summaries,
        }
        if include_raw_results:
            data["raw_results"] = raw_results
        self._record_assistant_execution(
            action=self._clean_text(body.get("workflow")) or "execute_actions",
            session=session_name,
            success=success,
            message="\n".join(message_lines),
            summary={
                "executed_count": len(summaries),
                "requested_count": requested_count,
                "stopped_on_error": halted,
                "halted_at": halted_at,
                "results": summaries,
            },
        )
        full_data = self._assistant_response_data(session=session_name, data=data)
        return {
            "success": success,
            "message": "\n".join(message_lines),
            "data": self._assistant_actions_compact_data(full_data) if compact else full_data,
        }

    @staticmethod
    def _assistant_workflow_catalog() -> Dict[str, Any]:
        return {
            "workflows": [
                {
                    "name": "pansou_search",
                    "description": "按关键词执行盘搜，只返回候选结果并保留会话",
                    "fields": ["session", "keyword", "compact"],
                },
                {
                    "name": "pansou_transfer",
                    "description": "按关键词盘搜并直接选择指定编号转存，choice 默认 1",
                    "fields": ["session", "keyword", "choice", "path", "compact"],
                },
                {
                    "name": "hdhive_candidates",
                    "description": "按关键词搜索影巢候选影片，等待下一步选片",
                    "fields": ["session", "keyword", "media_type", "year", "path", "compact"],
                },
                {
                    "name": "hdhive_unlock",
                    "description": "按关键词搜索影巢，选择候选影片，再选择资源解锁落盘",
                    "fields": ["session", "keyword", "candidate_choice", "resource_choice", "media_type", "year", "path", "compact"],
                },
                {
                    "name": "mp_search",
                    "description": "执行 MP 原生搜索，返回 PT 候选结果和评分摘要",
                    "fields": ["session", "keyword", "compact"],
                },
                {
                    "name": "mp_media_detail",
                    "description": "使用 MoviePilot 原生识别确认媒体详情、年份、类型和 TMDB/Douban/IMDB ID",
                    "fields": ["session", "keyword", "media_type", "year", "compact"],
                },
                {
                    "name": "mp_search_detail",
                    "description": "执行 MP 原生搜索并按编号查看 PT 详情与评分理由，只读",
                    "fields": ["session", "keyword", "choice", "compact"],
                },
                {
                    "name": "mp_search_best",
                    "description": "执行 MP 原生搜索并查看当前评分最高的 PT 候选详情，只读",
                    "fields": ["session", "keyword", "compact"],
                },
                {
                    "name": "mp_search_download",
                    "description": "执行 MP 原生搜索并按编号下载，默认先生成 plan_id",
                    "fields": ["session", "keyword", "choice", "compact", "dry_run"],
                },
                {
                    "name": "mp_download_tasks",
                    "description": "查询 MP 下载任务状态，可按 status/title/hash/downloader 过滤",
                    "fields": ["session", "status", "title", "hash", "downloader", "limit", "compact"],
                },
                {
                    "name": "mp_download_history",
                    "description": "查询 MP 下载历史，并按 hash 关联整理/入库状态，只读",
                    "fields": ["session", "keyword", "hash", "limit", "page", "compact"],
                },
                {
                    "name": "mp_lifecycle_status",
                    "description": "聚合查询 MP 下载任务、下载历史和整理/入库历史，只读",
                    "fields": ["session", "keyword", "hash", "limit", "compact"],
                },
                {
                    "name": "mp_downloaders",
                    "description": "查询 MP 下载器配置摘要，不返回敏感字段",
                    "fields": ["session", "compact"],
                },
                {
                    "name": "mp_sites",
                    "description": "查询 MP 站点启用状态、优先级和 Cookie 是否存在，不返回 Cookie 明文",
                    "fields": ["session", "status", "keyword", "limit", "compact"],
                },
                {
                    "name": "mp_download_control",
                    "description": "暂停、恢复或删除 MP 下载任务，默认先生成 plan_id",
                    "fields": ["session", "control", "target", "downloader", "delete_files", "compact", "dry_run"],
                },
                {
                    "name": "mp_subscribe",
                    "description": "按关键词创建 MP 订阅，默认先生成 plan_id",
                    "fields": ["session", "keyword", "compact", "dry_run"],
                },
                {
                    "name": "mp_subscribe_and_search",
                    "description": "创建订阅并立即触发搜索，默认先生成 plan_id",
                    "fields": ["session", "keyword", "compact", "dry_run"],
                },
                {
                    "name": "mp_subscribes",
                    "description": "查询 MP 订阅列表，可按 status/media_type/keyword 过滤",
                    "fields": ["session", "status", "media_type", "keyword", "limit", "compact"],
                },
                {
                    "name": "mp_subscribe_control",
                    "description": "触发订阅搜索、暂停、恢复或删除订阅，默认先生成 plan_id",
                    "fields": ["session", "control", "target", "compact", "dry_run"],
                },
                {
                    "name": "mp_transfer_history",
                    "description": "查询 MP 最近整理/入库历史，可按标题和成功/失败状态过滤，只读",
                    "fields": ["session", "keyword", "status", "limit", "page", "compact"],
                },
                {
                    "name": "mp_recommend",
                    "description": "读取 MP 原生推荐，例如 TMDB、豆瓣、Bangumi",
                    "fields": ["session", "source", "media_type", "limit", "compact"],
                },
                {
                    "name": "mp_recommend_search",
                    "description": "读取 MP 推荐并按编号继续搜索；mode 可选 mp / hdhive / pansou，传 keyword 时直接 MP 搜索",
                    "fields": ["session", "source", "keyword", "choice", "mode", "media_type", "limit", "compact"],
                },
                {
                    "name": "share_transfer",
                    "description": "识别 115 或夸克分享链接并直接转存",
                    "fields": ["session", "url", "access_code", "path", "compact"],
                },
                {
                    "name": "p115_login_start",
                    "description": "发起 115 扫码登录",
                    "fields": ["session", "client_type", "compact"],
                },
                {
                    "name": "p115_status",
                    "description": "查看 115 当前可用状态",
                    "fields": ["session", "compact"],
                },
            ]
        }

    def _assistant_workflow_actions(self, name: str, body: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
        workflow_name = self._clean_text(name).lower()
        session = self._clean_text(body.get("session")) or "default"
        session_id = self._clean_text(body.get("session_id"))
        path = self._clean_text(body.get("path") or body.get("target_path"))
        keyword = self._clean_text(body.get("keyword") or body.get("title"))
        media_type = self._clean_text(body.get("media_type") or "auto")
        year = self._clean_text(body.get("year"))
        source = self._clean_text(body.get("source")) or "tmdb_trending"
        limit = self._safe_int(body.get("limit"), 20)

        def base(payload: Dict[str, Any]) -> Dict[str, Any]:
            current = dict(payload)
            current.setdefault("session", session)
            if session_id:
                current.setdefault("session_id", session_id)
            if path and "path" not in current:
                current["path"] = path
            return current

        if workflow_name == "pansou_search":
            if not keyword:
                return [], "pansou_search 缺少 keyword"
            return [base({"name": "start_pansou_search", "keyword": keyword})], ""

        if workflow_name == "pansou_transfer":
            if not keyword:
                return [], "pansou_transfer 缺少 keyword"
            choice = self._safe_int(body.get("choice"), 1)
            return [
                base({"name": "start_pansou_search", "keyword": keyword}),
                base({"name": "pick_pansou_result", "choice": max(1, choice)}),
            ], ""

        if workflow_name == "hdhive_candidates":
            if not keyword:
                return [], "hdhive_candidates 缺少 keyword"
            return [
                base({
                    "name": "start_hdhive_search",
                    "keyword": keyword,
                    "media_type": media_type,
                    "year": year,
                })
            ], ""

        if workflow_name == "hdhive_unlock":
            if not keyword:
                return [], "hdhive_unlock 缺少 keyword"
            candidate_choice = self._safe_int(body.get("candidate_choice") or body.get("choice"), 0)
            resource_choice = self._safe_int(body.get("resource_choice"), 0)
            if candidate_choice <= 0 or resource_choice <= 0:
                return [], "hdhive_unlock 需要 candidate_choice 和 resource_choice"
            return [
                base({
                    "name": "start_hdhive_search",
                    "keyword": keyword,
                    "media_type": media_type,
                    "year": year,
                }),
                base({"name": "pick_hdhive_candidate", "choice": candidate_choice}),
                base({"name": "pick_hdhive_resource", "choice": resource_choice}),
            ], ""

        if workflow_name == "mp_search":
            if not keyword:
                return [], "mp_search 缺少 keyword"
            return [base({"name": "start_mp_media_search", "keyword": keyword})], ""

        if workflow_name == "mp_media_detail":
            if not keyword:
                return [], "mp_media_detail 缺少 keyword"
            return [base({
                "name": "query_mp_media_detail",
                "keyword": keyword,
                "media_type": media_type,
                "year": year,
            })], ""

        if workflow_name == "mp_search_detail":
            if not keyword:
                return [], "mp_search_detail 缺少 keyword"
            choice = self._safe_int(body.get("choice"), 1)
            return [
                base({"name": "start_mp_media_search", "keyword": keyword}),
                base({"name": "query_mp_search_result_detail", "choice": max(1, choice)}),
            ], ""

        if workflow_name == "mp_search_best":
            if not keyword:
                return [], "mp_search_best 缺少 keyword"
            return [
                base({"name": "start_mp_media_search", "keyword": keyword}),
                base({"name": "query_mp_best_result_detail"}),
            ], ""

        if workflow_name == "mp_search_download":
            if not keyword:
                return [], "mp_search_download 缺少 keyword"
            choice = self._safe_int(body.get("choice"), 1)
            return [
                base({"name": "start_mp_media_search", "keyword": keyword}),
                base({"name": "pick_mp_download", "choice": max(1, choice)}),
            ], ""

        if workflow_name == "mp_download_tasks":
            return [base({
                "name": "query_mp_download_tasks",
                "status": self._clean_text(body.get("status")) or "downloading",
                "title": self._clean_text(body.get("title") or body.get("keyword")),
                "hash": self._clean_text(body.get("hash") or body.get("hash_value")),
                "downloader": self._clean_text(body.get("downloader")),
                "limit": self._safe_int(body.get("limit"), 10),
            })], ""

        if workflow_name == "mp_download_history":
            return [base({
                "name": "query_mp_download_history",
                "keyword": keyword,
                "hash": self._clean_text(body.get("hash") or body.get("hash_value")),
                "limit": self._safe_int(body.get("limit"), 10),
                "page": self._safe_int(body.get("page"), 1),
            })], ""

        if workflow_name == "mp_lifecycle_status":
            return [base({
                "name": "query_mp_lifecycle_status",
                "keyword": keyword,
                "hash": self._clean_text(body.get("hash") or body.get("hash_value")),
                "limit": self._safe_int(body.get("limit"), 5),
            })], ""

        if workflow_name == "mp_downloaders":
            return [base({"name": "query_mp_downloaders"})], ""

        if workflow_name == "mp_sites":
            return [base({
                "name": "query_mp_sites",
                "status": self._clean_text(body.get("status")) or "active",
                "keyword": keyword,
                "limit": self._safe_int(body.get("limit"), 30),
            })], ""

        if workflow_name == "mp_download_control":
            control = self._clean_text(body.get("control") or body.get("download_control") or body.get("operation"))
            target = self._clean_text(body.get("target") or body.get("hash") or body.get("index") or body.get("choice"))
            if not control or not target:
                return [], "mp_download_control 需要 control 和 target"
            return [base({
                "name": "mp_download_control",
                "control": control,
                "target": target,
                "downloader": self._clean_text(body.get("downloader")),
                "delete_files": self._parse_bool_value(body.get("delete_files"), False),
            })], ""

        if workflow_name == "mp_subscribe":
            if not keyword:
                return [], "mp_subscribe 缺少 keyword"
            return [base({"name": "start_mp_subscribe", "keyword": keyword})], ""

        if workflow_name == "mp_subscribe_and_search":
            if not keyword:
                return [], "mp_subscribe_and_search 缺少 keyword"
            return [base({"name": "start_mp_subscribe_search", "keyword": keyword})], ""

        if workflow_name == "mp_subscribes":
            return [base({
                "name": "query_mp_subscribes",
                "status": self._clean_text(body.get("status")) or "all",
                "media_type": self._clean_text(body.get("media_type") or body.get("type")) or "all",
                "keyword": keyword,
                "limit": self._safe_int(body.get("limit"), 20),
            })], ""

        if workflow_name == "mp_subscribe_control":
            control = self._clean_text(body.get("control") or body.get("subscribe_control") or body.get("operation"))
            target = self._clean_text(body.get("target") or body.get("subscribe_id") or body.get("index") or body.get("choice"))
            if not control or not target:
                return [], "mp_subscribe_control 需要 control 和 target"
            return [base({
                "name": "mp_subscribe_control",
                "control": control,
                "target": target,
            })], ""

        if workflow_name == "mp_transfer_history":
            return [base({
                "name": "query_mp_transfer_history",
                "keyword": keyword,
                "status": self._clean_text(body.get("status")) or "all",
                "limit": self._safe_int(body.get("limit"), 10),
                "page": self._safe_int(body.get("page"), 1),
            })], ""

        if workflow_name == "mp_recommend":
            source_name, inferred_media_type = self._normalize_mp_recommend_request(source)
            return [
                base({
                    "name": "start_mp_recommendations",
                    "source": source_name,
                    "media_type": self._clean_text(body.get("media_type")) or inferred_media_type or "all",
                    "limit": max(1, min(50, limit)),
                })
            ], ""

        if workflow_name == "mp_recommend_search":
            if keyword:
                return [base({"name": "start_mp_media_search", "keyword": keyword})], ""
            source_name, inferred_media_type = self._normalize_mp_recommend_request(source)
            actions = [
                base({
                    "name": "start_mp_recommendations",
                    "source": source_name,
                    "media_type": self._clean_text(body.get("media_type")) or inferred_media_type or "all",
                    "limit": max(1, min(50, limit)),
                })
            ]
            choice = self._safe_int(body.get("choice"), 0)
            if choice > 0:
                actions.append(base({
                    "name": "pick_recommend_search",
                    "choice": choice,
                    "mode": self._clean_text(body.get("mode")) or "mp",
                }))
            return actions, ""

        if workflow_name == "share_transfer":
            share_url = self._clean_text(body.get("url") or body.get("share_url"))
            if not share_url:
                return [], "share_transfer 缺少 url"
            return [
                base({
                    "name": "route_share",
                    "url": share_url,
                    "access_code": self._clean_text(body.get("access_code")),
                })
            ], ""

        if workflow_name == "p115_login_start":
            return [
                base({
                    "name": "start_115_login",
                    "client_type": self._clean_text(body.get("client_type")),
                })
            ], ""

        if workflow_name == "p115_status":
            return [base({"name": "show_115_status"})], ""

        return [], f"不支持的工作流：{name}"

    async def api_assistant_workflow(self, request: Request):
        if request.method.upper() == "GET":
            ok, message = self._check_api_access(request)
            if not ok:
                return {"success": False, "message": message}
            return {
                "success": True,
                "message": "Agent影视助手 预设工作流目录",
                "data": self._assistant_response_data(session="default", data={
                    "action": "workflow_catalog",
                    "ok": True,
                    **self._assistant_workflow_catalog(),
                }),
            }

        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        workflow_name = self._clean_text(body.get("name") or body.get("workflow"))
        compact = self._parse_bool_value(body.get("compact"), False)
        if not workflow_name:
            return {"success": False, "message": "缺少工作流名 name"}
        actions, build_error = self._assistant_workflow_actions(workflow_name, body)
        if build_error:
            return {"success": False, "message": build_error}

        session = self._clean_text(body.get("session")) or "default"
        write_workflows = {
            "pansou_transfer",
            "hdhive_unlock",
            "share_transfer",
            "mp_search_download",
            "mp_download_control",
            "mp_subscribe",
            "mp_subscribe_control",
            "mp_subscribe_and_search",
        }
        dry_run = self._parse_bool_value(
            body.get("dry_run"),
            self._clean_text(workflow_name).lower() in write_workflows,
        )
        if dry_run:
            if workflow_name == "mp_download_control":
                control = self._clean_text(body.get("control") or body.get("download_control") or body.get("operation"))
                target = self._clean_text(body.get("target") or body.get("hash") or body.get("index") or body.get("choice"))
                result = self._assistant_mp_download_control_plan_response(
                    control=control,
                    target=target,
                    session=session,
                    cache_key=self._clean_text(body.get("session_id")),
                    downloader=self._clean_text(body.get("downloader")),
                    delete_files=self._parse_bool_value(body.get("delete_files"), False),
                )
                if not result.get("success"):
                    return result
            if workflow_name == "mp_subscribe_control":
                control = self._clean_text(body.get("control") or body.get("subscribe_control") or body.get("operation"))
                target = self._clean_text(body.get("target") or body.get("subscribe_id") or body.get("index") or body.get("choice"))
                allow_raw_id = self._parse_bool_value(body.get("allow_raw_id"), False)
                result = self._assistant_mp_subscribe_control_plan_response(
                    control=control,
                    target=target,
                    session=session,
                    cache_key=self._clean_text(body.get("session_id")),
                    allow_raw_id=allow_raw_id,
                )
                if not result.get("success"):
                    return result
            execute_body = {
                **{key: value for key, value in body.items() if key not in {"apikey", "dry_run"}},
                "dry_run": False,
            }
            plan = self._save_workflow_plan(
                workflow=workflow_name,
                session=session,
                session_id=self._clean_text(body.get("session_id")),
                actions=actions,
                execute_body=execute_body,
            )
            full_data = self._assistant_response_data(session=session, data={
                "action": "workflow_plan",
                "ok": True,
                "plan_id": plan.get("plan_id"),
                "workflow": workflow_name,
                "dry_run": True,
                "workflow_actions": actions,
                "estimated_steps": len(actions),
                "ready_to_execute": True,
                "execute_endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/workflow",
                "execute_plan_endpoint": "/api/v1/plugin/AgentResourceOfficer/assistant/plan/execute",
                "execute_plan_body": {"plan_id": plan.get("plan_id")},
                "execute_body": execute_body,
                "plan_created_at": plan.get("created_at"),
                "plan_created_at_text": plan.get("created_at_text"),
            })
            return {
                "success": True,
                "message": f"工作流 {workflow_name} 计划已生成：{plan.get('plan_id')}，共 {len(actions)} 步，未实际执行。",
                "data": self._assistant_workflow_plan_compact_data(full_data) if compact else full_data,
            }

        result = await self.api_assistant_actions(
            _JsonRequestShim(
                request,
                {
                    "actions": actions,
                    "workflow": workflow_name,
                    "session": session,
                    "session_id": self._clean_text(body.get("session_id")),
                    "execute": True,
                    "stop_on_error": self._parse_bool_value(body.get("stop_on_error"), True),
                    "include_raw_results": self._parse_bool_value(body.get("include_raw_results"), False),
                    "compact": compact,
                    "apikey": self._extract_apikey(request, body),
                },
            )
        )
        data = dict(result.get("data") or {})
        data["workflow"] = workflow_name
        if not compact:
            data["workflow_actions"] = actions
        return {
            "success": bool(result.get("success")),
            "message": f"工作流 {workflow_name} 执行完成\n{result.get('message') or ''}".strip(),
            "data": data,
        }

    async def api_assistant_plan_execute(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        plan_id = self._clean_text(body.get("plan_id"))
        session = self._clean_text(body.get("session"))
        session_id = self._clean_text(body.get("session_id"))
        prefer_unexecuted = self._parse_bool_value(body.get("prefer_unexecuted"), True)
        compact = self._parse_bool_value(body.get("compact"), False)
        plan = self._find_workflow_plan(
            plan_id=plan_id,
            session=session,
            session_id=session_id,
            executed=False if prefer_unexecuted and not plan_id else None,
        )
        if not plan and not plan_id and (session or session_id) and prefer_unexecuted:
            plan = self._find_workflow_plan(
                session=session,
                session_id=session_id,
                executed=None,
            )
        if not plan:
            result = {
                "success": False,
                "message": f"计划不存在或已过期：{plan_id}" if plan_id else "没有匹配到可执行计划，请先生成 dry_run 计划或改传 plan_id。",
                "data": self._assistant_response_data(session=session or "default", data={
                    "action": "execute_plan",
                    "ok": False,
                    "plan_id": plan_id,
                    "error_code": "plan_not_found",
                }),
            }
            return self._assistant_plan_execute_compact_response(result) if compact else result
        plan_id = self._clean_text(plan.get("plan_id"))

        actions = plan.get("actions") or []
        if not isinstance(actions, list) or not actions:
            result = {
                "success": False,
                "message": f"计划没有可执行动作：{plan_id}",
                "data": self._assistant_response_data(session=session or "default", data={
                    "action": "execute_plan",
                    "ok": False,
                    "plan_id": plan_id,
                    "error_code": "plan_has_no_actions",
                }),
            }
            return self._assistant_plan_execute_compact_response(result) if compact else result

        workflow_name = self._clean_text(plan.get("workflow")) or "saved_plan"
        session = self._clean_text(plan.get("session")) or "default"
        session_id = self._clean_text(plan.get("session_id"))
        action_result = await self.api_assistant_actions(
            _JsonRequestShim(
                request,
                {
                    "actions": actions,
                    "workflow": workflow_name,
                    "session": session,
                    "session_id": session_id,
                    "execute": True,
                    "stop_on_error": self._parse_bool_value(body.get("stop_on_error"), True),
                    "include_raw_results": self._parse_bool_value(body.get("include_raw_results"), False),
                    "compact": False,
                    "apikey": self._extract_apikey(request, body),
                },
            )
        )

        executed_at = int(time.time())
        plan.update({
            "executed": True,
            "executed_at": executed_at,
            "executed_at_text": self._format_unix_time(executed_at),
            "last_success": bool(action_result.get("success")),
            "last_message": self._assistant_result_message_head(action_result.get("message")),
        })
        self._workflow_plans[plan_id] = plan
        self._persist_workflow_plans()

        data = dict(action_result.get("data") or {})
        data.update({
            "action": "execute_plan",
            "plan_id": plan_id,
            "workflow": workflow_name,
            "plan_auto_selected": not bool(self._clean_text(body.get("plan_id"))),
            "plan_created_at": plan.get("created_at"),
            "plan_created_at_text": plan.get("created_at_text"),
            "plan_executed_at": executed_at,
            "plan_executed_at_text": plan.get("executed_at_text"),
        })
        if not compact:
            data["workflow_actions"] = actions
        result = {
            "success": bool(action_result.get("success")),
            "message": f"计划 {plan_id} 执行完成\n{action_result.get('message') or ''}".strip(),
            "data": data,
        }
        return self._assistant_plan_execute_compact_response(result) if compact else result

    async def api_assistant_pick(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        session, cache_key = self._normalize_assistant_session_ref(
            session=(
                body.get("session")
                or body.get("chat_id")
                or body.get("user_id")
                or body.get("conversation_id")
                or "default"
            ),
            session_id=body.get("session_id"),
        )
        index = self._safe_int(
            body.get("index")
            or body.get("choice")
            or body.get("selection")
            or body.get("number"),
            0,
        )
        action = self._normalize_pick_action(body.get("action") or body.get("pick_action"))
        target_path = self._resolve_pan_path_value(self._clean_text(body.get("path") or body.get("target_path")))
        compact = self._parse_bool_value(body.get("compact"), False)

        def finish(result: Dict[str, Any]) -> Dict[str, Any]:
            return self._assistant_interaction_compact_response(result) if compact else result

        state = self._load_session(cache_key)
        if not state:
            return {"success": False, "message": "没有可继续的缓存，请先发起搜索或发送分享链接。"}
        if index <= 0 and not action:
            return {"success": False, "message": "请选择有效序号，例如：选择 1"}

        kind = str(state.get("kind") or "").strip()
        if kind == "assistant_pansou":
            items = state.get("items") or []
            if action == "best":
                best = self._best_scored_source_item(items)
                if not best:
                    return finish({
                        "success": False,
                        "message": "当前盘搜结果没有可评分条目，请直接回复编号选择。",
                        "data": self._assistant_response_data(session=session, data={
                            "action": "pansou_best_detail",
                            "ok": False,
                            "error_code": "best_item_not_found",
                        }),
                    })
                return finish({
                    "success": True,
                    "message": self._format_cloud_item_detail_text(best, title="盘搜当前最佳候选"),
                    "data": self._assistant_response_data(session=session, data={
                        "action": "pansou_best_detail",
                        "ok": True,
                        "item": best,
                        "score_summary": self._score_summary([best], limit=1),
                    }),
                })
            if action == "detail":
                if index <= 0:
                    return {"success": False, "message": "盘搜详情需要编号，例如：选择 1 详情。"}
                if index > len(items):
                    return {"success": False, "message": f"序号超出范围，请输入 1 到 {len(items)} 之间的数字。"}
                selected = dict(items[index - 1])
                return finish({
                    "success": True,
                    "message": self._format_cloud_item_detail_text(selected, title="盘搜资源详情"),
                    "data": self._assistant_response_data(session=session, data={
                        "action": "pansou_result_detail",
                        "ok": True,
                        "choice": index,
                        "item": selected,
                        "score_summary": self._score_summary([selected], limit=1),
                    }),
                })
            if action == "plan":
                if index <= 0:
                    return {"success": False, "message": "盘搜计划需要编号，例如：计划选择 1。"}
                if index > len(items):
                    return {"success": False, "message": f"序号超出范围，请输入 1 到 {len(items)} 之间的数字。"}
                selected = dict(items[index - 1])
                share_url = self._clean_text(selected.get("url"))
                if not share_url:
                    return {"success": False, "message": "选中的盘搜结果缺少分享链接，无法生成计划。"}
                access_code = self._clean_text(selected.get("password"))
                final_path = target_path or (
                    self._p115_default_path if self._is_115_url(share_url) else self._quark_default_path
                )
                actions = [{
                    "name": "route_share",
                    "session": session,
                    "session_id": cache_key,
                    "url": share_url,
                    "access_code": access_code,
                    "path": final_path,
                }]
                return finish(self._save_assistant_pick_plan_response(
                    workflow="pansou_transfer_selected",
                    session=session,
                    session_id=cache_key,
                    actions=actions,
                    execute_body={
                        "workflow": "pansou_transfer_selected",
                        "session": session,
                        "session_id": cache_key,
                        "choice": index,
                        "path": final_path,
                    },
                    message="盘搜转存计划已生成",
                    score_items=[selected],
                    extra_data={
                        "choice": index,
                        "provider": "115" if self._is_115_url(share_url) else "quark" if self._is_quark_url(share_url) else selected.get("channel"),
                        "target_path": final_path,
                        "selected_item": selected,
                    },
                ))
            if action:
                return {"success": False, "message": "盘搜结果当前只支持：选择 编号、计划选择 编号、选择 编号 详情、最佳片源。"}
            if index <= 0:
                return {"success": False, "message": "请选择有效序号，例如：选择 1"}
            if index > len(items):
                return {"success": False, "message": f"序号超出范围，请输入 1 到 {len(items)} 之间的数字。"}
            selected = dict(items[index - 1])
            share_url = self._clean_text(selected.get("url"))
            access_code = self._clean_text(selected.get("password"))
            final_path = target_path or (
                self._p115_default_path if self._is_115_url(share_url) else self._quark_default_path
            )
            route_result = await self.api_share_route(
                _JsonRequestShim(request, {
                    "url": share_url,
                    "access_code": access_code,
                    "path": final_path,
                    "trigger": "Agent影视助手 智能入口盘搜选择",
                    "apikey": self._extract_apikey(request, body),
                })
            )
            if not route_result.get("success"):
                if self._is_115_url(share_url):
                    self._save_pending_p115_share(
                        cache_key,
                        share_url=share_url,
                        access_code=access_code,
                        target_path=final_path,
                        source="assistant_pansou_pick",
                        title=selected.get("note") or "",
                        last_error=str(route_result.get("message") or ""),
                    )
                    return finish({
                        "success": False,
                        "message": (
                            f"{str(route_result.get('message') or '转存失败')}\n"
                            f"{self._format_p115_resume_hint(selected.get('note') or '')}"
                        ),
                        "data": self._assistant_response_data(session=session, data=route_result.get("data") or {}),
                    })
                return finish({
                    "success": False,
                    "message": str(route_result.get('message') or '转存失败'),
                    "data": self._assistant_response_data(session=session, data=route_result.get("data") or {}),
                })
            if self._is_115_url(share_url):
                self._clear_pending_p115_share(cache_key)
            provider = ((route_result.get("data") or {}).get("provider") or "").lower()
            result_payload = (route_result.get("data") or {}).get("result") or {}
            directory = (result_payload.get("result") or {}).get("target_path") or (result_payload.get("result") or {}).get("path") or final_path
            text_message = "\n".join([
                "盘搜结果已执行转存",
                f"资源：{selected.get('note') or '未命名资源'}",
                f"类型：{provider or selected.get('channel') or '-'}",
                f"目录：{directory or '-'}",
            ])
            return finish({
                "success": True,
                "message": text_message,
                "data": self._assistant_response_data(session=session, data={"action": "share_route", "ok": True}),
            })

        if kind == "assistant_mp_recommend":
            items = state.get("items") or []
            if index > len(items):
                return {"success": False, "message": f"序号超出范围，请输入 1 到 {len(items)} 之间的数字。"}
            selected = dict(items[index - 1])
            title = self._clean_text(selected.get("title"))
            if not title:
                return {"success": False, "message": "选中的推荐条目缺少标题，无法继续搜索。"}
            next_mode = self._clean_text(
                body.get("mode")
                or body.get("search_mode")
                or body.get("target")
                or "mp"
            ).lower()
            mode_aliases = {
                "原生": "mp",
                "mp搜索": "mp",
                "影巢": "hdhive",
                "yc": "hdhive",
                "盘搜": "pansou",
                "ps": "pansou",
            }
            next_mode = mode_aliases.get(next_mode, next_mode)
            if next_mode not in {"mp", "hdhive", "pansou"}:
                return {"success": False, "message": "推荐选择只支持 mode=mp、mode=hdhive 或 mode=pansou。"}
            selected_media_type = self._clean_text(selected.get("type") or state.get("media_type") or "auto").lower()
            media_type_aliases = {
                "电影": "movie",
                "movie": "movie",
                "movies": "movie",
                "电视剧": "tv",
                "剧集": "tv",
                "番剧": "tv",
                "tv": "tv",
                "series": "tv",
                "all": "auto",
                "全部": "auto",
            }
            selected_media_type = media_type_aliases.get(selected_media_type, "auto")
            return finish(await self.api_assistant_route(
                _JsonRequestShim(request, {
                    "session": session,
                    "session_id": cache_key,
                    "mode": next_mode,
                    "keyword": title,
                    "media_type": selected_media_type,
                    "path": target_path,
                    "apikey": self._extract_apikey(request, body),
                })
            ))

        if kind == "assistant_mp":
            if action == "best":
                preferences = self._normalize_assistant_preferences((self._assistant_preferences or {}).get(self._normalize_preference_key(session=session)))
                return finish(await self._assistant_mp_best_result_detail(
                    session=session,
                    cache_key=cache_key,
                    preferences=preferences,
                ))
            if action == "detail" and index <= 0:
                return {"success": False, "message": "MP 搜索结果详情需要编号，例如：选择 1。"}
            preferences = self._normalize_assistant_preferences((self._assistant_preferences or {}).get(self._normalize_preference_key(session=session)))
            return finish(await self._assistant_mp_result_detail(
                choice=index,
                session=session,
                cache_key=cache_key,
                preferences=preferences,
            ))

        if kind == "assistant_hdhive":
            allowed, disabled = self._ensure_hdhive_resource_enabled()
            if not allowed:
                return finish({
                    "success": False,
                    "message": disabled.get("message") or "影巢资源入口已关闭",
                    "data": self._assistant_response_data(session=session, data={
                        "action": "hdhive_pick",
                        "ok": False,
                        "error_code": "hdhive_resource_disabled",
                        "resource_enabled": False,
                    }),
                })
            stage = str(state.get("stage") or "").strip()
            service = self._ensure_hdhive_service()
            final_path = target_path or state.get("target_path") or self._hdhive_default_path
            if stage == "candidate":
                candidates = state.get("candidates") or []
                page_size = max(1, self._safe_int(state.get("page_size"), self._hdhive_candidate_page_size))
                current_page = max(1, self._safe_int(state.get("page"), 1))
                if action == "detail":
                    start = (current_page - 1) * page_size
                    end = start + page_size
                    enriched = [dict(item or {}) for item in candidates]
                    enriched[start:end] = self._enrich_hdhive_candidates_with_actors(enriched[start:end])
                    self._save_session(cache_key, {**state, "candidates": enriched, "target_path": final_path})
                    return finish({
                        "success": True,
                        "message": self._format_candidate_lines(enriched, page=current_page, page_size=page_size),
                        "data": self._assistant_response_data(session=session, data={
                            "action": "hdhive_candidates_detail",
                            "ok": True,
                            "page": current_page,
                            "candidates": enriched,
                        }),
                    })
                if action == "next_page":
                    total_pages = max(1, (len(candidates) + page_size - 1) // page_size)
                    if current_page >= total_pages:
                        return {"success": False, "message": "已经是最后一页了，可以直接回复编号继续选择。"}
                    next_page = current_page + 1
                    self._save_session(cache_key, {**state, "page": next_page, "target_path": final_path})
                    return finish({
                        "success": True,
                        "message": self._format_candidate_lines(candidates, page=next_page, page_size=page_size),
                        "data": self._assistant_response_data(session=session, data={
                            "action": "hdhive_candidates_next_page",
                            "ok": True,
                            "page": next_page,
                            "total_pages": total_pages,
                        }),
                    })
                if action == "best":
                    return {"success": False, "message": "影巢候选影片阶段没有评分，不能用“最佳片源”；请先回复编号选择影片，进入资源列表后再用“最佳片源”。"}
                if action == "plan":
                    return {"success": False, "message": "影巢候选影片阶段不能生成资源计划；请先回复编号选择影片，进入资源列表后再发：计划选择 1。"}
                if action:
                    return {"success": False, "message": "影巢候选阶段只支持：选择 编号、详情/审查、下一页。"}
                if index <= 0:
                    return {"success": False, "message": "请选择有效影片编号，例如：选择 1"}
                if index > len(candidates):
                    return {"success": False, "message": f"序号超出范围，请输入 1 到 {len(candidates)} 之间的数字。"}
                candidate = dict(candidates[index - 1])
                resource_ok, resource_result, resource_message = service.search_resources(
                    media_type=candidate.get("media_type") or state.get("media_type") or "movie",
                    tmdb_id=str(candidate.get("tmdb_id") or ""),
                )
                if not resource_ok:
                    return {"success": False, "message": f"影巢资源查询失败：{resource_message}", "data": resource_result}
                preferences = self._normalize_assistant_preferences((self._assistant_preferences or {}).get(self._normalize_preference_key(session=session)))
                preview = self._attach_cloud_scores(
                    self._group_resource_preview(resource_result.get("data") or [], per_group=6),
                    preferences=preferences,
                    source_type="hdhive",
                    target_path=final_path,
                )
                self._save_session(
                    cache_key,
                    {
                        **state,
                        "stage": "resource",
                        "selected_candidate": candidate,
                        "resources": preview,
                        "target_path": final_path,
                    },
                )
                return finish({
                    "success": True,
                    "message": self._format_resource_lines(preview, candidate),
                    "data": self._assistant_response_data(session=session, data={
                        "action": "hdhive_search",
                        "ok": True,
                        "selected_candidate": candidate,
                        "resources": preview,
                        "score_summary": self._score_summary(preview, limit=5),
                    }),
                })
            resources = state.get("resources") or []
            if action == "best":
                best = self._best_scored_source_item(resources)
                if not best:
                    return finish({
                        "success": False,
                        "message": "当前影巢资源没有可评分条目，请直接回复编号选择。",
                        "data": self._assistant_response_data(session=session, data={
                            "action": "hdhive_best_resource_detail",
                            "ok": False,
                            "error_code": "best_item_not_found",
                        }),
                    })
                return finish({
                    "success": True,
                    "message": self._format_cloud_item_detail_text(best, title="影巢当前最佳资源"),
                    "data": self._assistant_response_data(session=session, data={
                        "action": "hdhive_best_resource_detail",
                        "ok": True,
                        "item": best,
                        "score_summary": self._score_summary([best], limit=1),
                    }),
                })
            if action == "detail":
                if index <= 0:
                    return {"success": False, "message": "影巢资源详情需要编号，例如：选择 1 详情。"}
                if index > len(resources):
                    return {"success": False, "message": f"序号超出范围，请输入 1 到 {len(resources)} 之间的数字。"}
                resource = dict(resources[index - 1])
                return finish({
                    "success": True,
                    "message": self._format_cloud_item_detail_text(resource, title="影巢资源详情"),
                    "data": self._assistant_response_data(session=session, data={
                        "action": "hdhive_resource_detail",
                        "ok": True,
                        "choice": index,
                        "item": resource,
                        "score_summary": self._score_summary([resource], limit=1),
                    }),
                })
            if action == "plan":
                if index <= 0:
                    return {"success": False, "message": "影巢资源计划需要编号，例如：计划选择 1。"}
                if index > len(resources):
                    return {"success": False, "message": f"序号超出范围，请输入 1 到 {len(resources)} 之间的数字。"}
                resource = dict(resources[index - 1])
                slug = self._clean_text(resource.get("slug"))
                if not slug:
                    return {"success": False, "message": "选中的影巢资源缺少 slug，无法生成计划。"}
                actions = [{
                    "name": "unlock_hdhive_resource",
                    "session": session,
                    "session_id": cache_key,
                    "slug": slug,
                    "path": final_path,
                    "resource": resource,
                }]
                return finish(self._save_assistant_pick_plan_response(
                    workflow="hdhive_unlock_selected",
                    session=session,
                    session_id=cache_key,
                    actions=actions,
                    execute_body={
                        "workflow": "hdhive_unlock_selected",
                        "session": session,
                        "session_id": cache_key,
                        "choice": index,
                        "path": final_path,
                    },
                    message="影巢解锁/转存计划已生成",
                    score_items=[resource],
                    extra_data={
                        "choice": index,
                        "target_path": final_path,
                        "selected_resource": resource,
                    },
                ))
            if action:
                return {"success": False, "message": "影巢资源阶段只支持：选择 编号、计划选择 编号、选择 编号 详情、最佳片源。"}
            if index <= 0:
                return {"success": False, "message": "请选择有效资源编号，例如：选择 1"}
            if index > len(resources):
                return {"success": False, "message": f"序号超出范围，请输入 1 到 {len(resources)} 之间的数字。"}
            resource = dict(resources[index - 1])
            route_ok, route_result, route_message = await self._unlock_and_route(
                self._clean_text(resource.get("slug")),
                target_path=final_path,
                resource=resource,
            )
            if not route_ok:
                route = dict((route_result or {}).get("route") or {})
                share_url = self._clean_text(route.get("share_url"))
                if self._is_115_url(share_url) or self._clean_text(route.get("provider")) == "115":
                    self._save_pending_p115_share(
                        cache_key,
                        share_url=share_url,
                        access_code=route.get("access_code") or "",
                        target_path=route.get("target_path") or final_path,
                        source="assistant_hdhive_unlock",
                        title=resource.get("title") or resource.get("matched_title") or "",
                        last_error=route_message,
                    )
                    return finish({
                        "success": False,
                        "message": f"{route_message}\n{self._format_p115_resume_hint(resource.get('title') or resource.get('matched_title') or '')}",
                        "data": self._assistant_response_data(session=session, data=route_result),
                    })
                return finish({
                    "success": False,
                    "message": route_message,
                    "data": self._assistant_response_data(session=session, data=route_result),
                })
            return finish({
                "success": True,
                "message": self._format_route_result(route_result),
                "data": self._assistant_response_data(session=session, data={
                    "action": "hdhive_unlock",
                    "ok": True,
                    "selected_resource": resource,
                    "result": route_result,
                }),
            })

        return {"success": False, "message": f"当前会话阶段不支持继续选择：{kind or 'unknown'}"}

    async def api_assistant_capabilities(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        compact = bool(self._parse_optional_bool(request.query_params.get("compact")) or False)
        data = self._assistant_capabilities_public_data()
        return {
            "success": True,
            "message": self._format_assistant_capabilities_text(),
            "data": self._assistant_capabilities_compact_data(data) if compact else self._assistant_response_data(
                session="default",
                data=data,
            ),
        }

    async def api_assistant_readiness(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        compact = bool(self._parse_optional_bool(request.query_params.get("compact")) or False)
        data = self._assistant_readiness_public_data()
        response_data = {
            "action": "readiness",
            "ok": bool(data.get("can_start")),
            **data,
        }
        return {
            "success": bool(data.get("can_start")),
            "message": self._format_assistant_readiness_text(),
            "data": self._assistant_readiness_compact_data(response_data) if compact else self._assistant_response_data(
                session="default",
                data=response_data,
            ),
        }

    async def api_assistant_pulse(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        data = self._assistant_pulse_public_data()
        return {
            "success": bool(data.get("can_start")),
            "message": self._format_assistant_pulse_text(),
            "data": data,
        }

    async def api_assistant_startup(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        data = self._assistant_startup_public_data()
        return {
            "success": bool(data.get("ok")),
            "message": self._format_assistant_startup_text(),
            "data": data,
        }

    async def api_assistant_maintain(self, request: Request):
        body: Dict[str, Any] = {}
        if request.method.upper() != "GET":
            try:
                body = await request.json()
            except Exception:
                body = {}
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        requested_execute = self._parse_bool_value(
            body.get("execute") if "execute" in body else request.query_params.get("execute"),
            False,
        )
        execute = requested_execute and request.method.upper() != "GET"
        limit = self._safe_int(body.get("limit") or request.query_params.get("limit"), 100)
        data = self._assistant_maintain_public_data(execute=execute, limit=limit)
        if requested_execute and request.method.upper() == "GET":
            data["execute_ignored"] = True
            data["warning"] = "GET 请求只返回 dry-run 维护建议；如需执行维护请使用 POST execute=true。"
        if execute:
            executed_actions = data.get("executed_actions") or []
            self._record_assistant_execution(
                action="maintain",
                session=self._clean_text(body.get("session")) or "default",
                session_id=self._clean_text(body.get("session_id")),
                success=bool(data.get("ok")),
                message=self._format_assistant_maintain_text(data),
                summary={
                    "executed": bool(data.get("executed")),
                    "executed_actions": [
                        {
                            "name": self._clean_text(item.get("name")),
                            "removed": self._safe_int(item.get("removed"), 0),
                        }
                        for item in executed_actions
                        if isinstance(item, dict)
                    ],
                    "after": {
                        "stale_sessions": (data.get("after") or {}).get("stale_sessions"),
                        "saved_plans_executed": (data.get("after") or {}).get("saved_plans_executed"),
                        "saved_plans_pending": (data.get("after") or {}).get("saved_plans_pending"),
                    },
                },
            )
        return {
            "success": bool(data.get("ok")),
            "message": self._format_assistant_maintain_text(data),
            "data": data,
        }

    async def api_assistant_toolbox(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        data = self._assistant_toolbox_public_data()
        return {
            "success": True,
            "message": self._format_assistant_toolbox_text(),
            "data": data,
        }

    async def api_assistant_request_templates(self, request: Request):
        body: Dict[str, Any] = {}
        if request.method.upper() != "GET":
            try:
                body = await request.json()
            except Exception:
                body = {}
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        limit = self._safe_int(body.get("limit") or request.query_params.get("limit"), 100)
        names = (
            body.get("names")
            or body.get("name")
            or body.get("template")
            or request.query_params.get("names")
            or request.query_params.get("name")
            or request.query_params.get("template")
        )
        recipe = (
            body.get("recipe")
            or body.get("recommended_recipe")
            or request.query_params.get("recipe")
            or request.query_params.get("recommended_recipe")
        )
        include_templates = self._parse_bool_value(
            body.get("include_templates") if "include_templates" in body else request.query_params.get("include_templates"),
            True,
        )
        data = self._assistant_request_templates_response_data(
            limit=limit,
            names=names,
            recipe=recipe,
            include_templates=include_templates,
        )
        return {
            "success": True,
            "message": self._format_assistant_request_templates_text(data),
            "data": data,
        }

    async def api_assistant_selfcheck(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        data = self._assistant_selfcheck_public_data()
        return {
            "success": bool(data.get("ok")),
            "message": self._format_assistant_selfcheck_text(),
            "data": data,
        }

    async def api_assistant_history(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        session = self._clean_text(request.query_params.get("session"))
        session_id = self._clean_text(request.query_params.get("session_id"))
        compact = bool(self._parse_optional_bool(request.query_params.get("compact")) or False)
        limit = self._safe_int(request.query_params.get("limit"), 20)
        data = self._assistant_history_public_data(session=session, session_id=session_id, limit=limit)
        response_data = self._assistant_history_compact_data(data) if compact else self._assistant_response_data(
            session=session or "default",
            data={
                "action": "history",
                "ok": True,
                **data,
            },
        )
        return {
            "success": True,
            "message": self._format_assistant_history_text(session=session, session_id=session_id, limit=limit),
            "data": response_data,
        }

    async def api_assistant_plans(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        session = self._clean_text(request.query_params.get("session"))
        session_id = self._clean_text(request.query_params.get("session_id"))
        executed = self._parse_optional_bool(request.query_params.get("executed"))
        include_actions = bool(self._parse_optional_bool(request.query_params.get("include_actions")) or False)
        compact = bool(self._parse_optional_bool(request.query_params.get("compact")) or False)
        limit = self._safe_int(request.query_params.get("limit"), 20)
        data = self._assistant_plans_public_data(
            session=session,
            session_id=session_id,
            executed=executed,
            include_actions=include_actions,
            limit=limit,
        )
        response_data = self._assistant_plans_compact_data(data) if compact else self._assistant_response_data(
            session=session or "default",
            data={
                "action": "plans",
                "ok": True,
                **data,
            },
        )
        return {
            "success": True,
            "message": self._format_assistant_plans_text(
                session=session,
                session_id=session_id,
                executed=executed,
                include_actions=include_actions,
                limit=limit,
            ),
            "data": response_data,
        }

    async def api_assistant_plans_clear(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        result = self._clear_workflow_plans(
            plan_id=body.get("plan_id"),
            session=body.get("session"),
            session_id=body.get("session_id"),
            executed=self._parse_optional_bool(body.get("executed")),
            all_plans=self._parse_bool_value(body.get("all_plans"), False),
            limit=self._safe_int(body.get("limit"), 100),
        )
        if not result.get("ok"):
            return {
                "success": False,
                "message": str(result.get("message") or "计划清理参数无效"),
                "data": result,
            }
        return {
            "success": True,
            "message": str(result.get("message") or "计划清理完成"),
            "data": self._assistant_response_data(session=body.get("session") or "default", data={
                "action": "plans_clear",
                "ok": True,
                **result,
            }),
        }

    async def api_assistant_recover(self, request: Request):
        body: Dict[str, Any] = {}
        if request.method.upper() != "GET":
            try:
                body = await request.json()
            except Exception:
                body = {}
        ok, message = self._check_api_access(request, body or None)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        session = self._clean_text(body.get("session") or request.query_params.get("session"))
        session_id = self._clean_text(body.get("session_id") or request.query_params.get("session_id"))
        execute = self._parse_bool_value(
            body.get("execute") if "execute" in body else request.query_params.get("execute"),
            False,
        )
        prefer_unexecuted = self._parse_bool_value(
            body.get("prefer_unexecuted") if "prefer_unexecuted" in body else None,
            True,
        )
        stop_on_error = self._parse_bool_value(
            body.get("stop_on_error") if "stop_on_error" in body else None,
            True,
        )
        include_raw_results = self._parse_bool_value(
            body.get("include_raw_results") if "include_raw_results" in body else None,
            False,
        )
        compact = bool(
            self._parse_optional_bool(body.get("compact"))
            if "compact" in body
            else self._parse_optional_bool(request.query_params.get("compact"))
        )
        limit = self._safe_int(body.get("limit") or request.query_params.get("limit"), 20)
        data = self._assistant_recover_public_data(
            session=session,
            session_id=session_id,
            limit=limit,
        )
        data.update({
            "action": "recover",
            "ok": True,
            "execute_requested": execute,
            "executed": False,
        })

        if not execute:
            return {
                "success": True,
                "message": self._format_assistant_recover_text(data),
                "data": self._assistant_recover_response_data(data, compact=compact),
            }

        recovery = dict(data.get("recovery") or {})
        if not recovery.get("can_resume"):
            data["ok"] = False
            data["execute_error"] = recovery.get("reason") or "当前没有可直接恢复的动作"
            return {
                "success": False,
                "message": str(data["execute_error"]),
                "data": self._assistant_recover_response_data(data, compact=compact),
            }

        template = dict(recovery.get("action_template") or {})
        action_body = dict(template.get("action_body") or {})
        if not action_body and template.get("name"):
            action_body = {"name": template.get("name"), **dict(template.get("body") or {})}
        if not self._clean_text(action_body.get("name")):
            data["ok"] = False
            data["execute_error"] = "恢复模板缺少可执行动作名"
            return {
                "success": False,
                "message": data["execute_error"],
                "data": self._assistant_recover_response_data(data, compact=compact),
            }

        action_body.setdefault("session", data.get("session") or "default")
        if data.get("session_id"):
            action_body.setdefault("session_id", data.get("session_id"))
        action_body.setdefault("prefer_unexecuted", prefer_unexecuted)
        action_body.setdefault("stop_on_error", stop_on_error)
        action_body.setdefault("include_raw_results", include_raw_results)
        action_body["apikey"] = self._extract_apikey(request, body)
        result = await self.api_assistant_action(_JsonRequestShim(request, action_body))
        result_data = dict(result.get("data") or {})
        data.update({
            "ok": bool(result.get("success")),
            "executed": True,
            "execute_success": bool(result.get("success")),
            "execute_action": action_body.get("name"),
            "execute_message": result.get("message") or "",
            "execute_result": result if include_raw_results else {
                "success": bool(result.get("success")),
                "message": result.get("message") or "",
                "data": {
                    "action": result_data.get("action"),
                    "ok": result_data.get("ok"),
                    "session": result_data.get("session"),
                    "session_id": result_data.get("session_id"),
                    "plan_id": result_data.get("plan_id"),
                    "workflow": result_data.get("workflow"),
                },
            },
        })
        return {
            "success": bool(result.get("success")),
            "message": f"恢复动作 {action_body.get('name')} 执行完成\n{result.get('message') or ''}".strip(),
            "data": self._assistant_recover_response_data(data, compact=compact),
        }

    async def api_assistant_session_state(self, request: Request):
        body: Dict[str, Any] = {}
        if request.method.upper() != "GET":
            try:
                body = await request.json()
            except Exception:
                body = {}
        ok, message = self._check_api_access(request, body or None)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        session, _ = self._normalize_assistant_session_ref(
            session=(
                (body or {}).get("session")
                or request.query_params.get("session")
                or request.query_params.get("chat_id")
                or request.query_params.get("user_id")
                or "default"
            ),
            session_id=(body or {}).get("session_id") or request.query_params.get("session_id"),
        )
        compact = bool(
            self._parse_optional_bool((body or {}).get("compact"))
            if "compact" in (body or {})
            else self._parse_optional_bool(request.query_params.get("compact"))
        )
        summary = self._format_assistant_session_summary(session=session)
        session_state = self._assistant_session_public_data(session=session)
        if compact:
            return {
                "success": True,
                "message": summary,
                "data": self._assistant_session_compact_data(session_state),
            }
        data = self._assistant_response_data(session=session, data={
            "action": "session_state",
            "ok": True,
            "session_snapshot": session_state,
            **session_state,
        })
        return {"success": True, "message": summary, "data": data}

    async def api_assistant_session_clear(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        session, cache_key = self._normalize_assistant_session_ref(
            session=(
                body.get("session")
                or body.get("chat_id")
                or body.get("user_id")
                or body.get("conversation_id")
                or "default"
            ),
            session_id=body.get("session_id"),
        )
        existing = self._load_session(cache_key)
        if not existing:
            return {
                "success": True,
                "message": "当前没有需要清理的会话。",
                "data": self._assistant_response_data(session=session, data={"cleared": False}),
            }
        self._session_cache.pop(cache_key, None)
        self._persist_relevant_sessions()
        return {
            "success": True,
            "message": f"已清理会话：{session}",
            "data": self._assistant_response_data(session=session, data={"cleared": True}),
        }

    async def api_assistant_sessions(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        kind = self._clean_text(request.query_params.get("kind"))
        has_pending_p115_raw = request.query_params.get("has_pending_p115")
        has_pending_p115: Optional[bool] = None
        if has_pending_p115_raw is not None:
            has_pending_p115 = str(has_pending_p115_raw).strip().lower() in {"1", "true", "yes", "y"}
        compact = bool(self._parse_optional_bool(request.query_params.get("compact")))
        limit = self._safe_int(request.query_params.get("limit"), 20)
        data = self._assistant_sessions_public_data(
            kind=kind,
            has_pending_p115=has_pending_p115,
            limit=limit,
        )
        if compact:
            return {
                "success": True,
                "message": self._format_assistant_sessions_text(
                    kind=kind,
                    has_pending_p115=has_pending_p115,
                    limit=limit,
                ),
                "data": self._assistant_sessions_compact_data(data),
            }
        return {
            "success": True,
            "message": self._format_assistant_sessions_text(
                kind=kind,
                has_pending_p115=has_pending_p115,
                limit=limit,
            ),
            "data": self._assistant_response_data(session="default", data={
                "action": "sessions",
                "ok": True,
                **data,
            }),
        }

    async def api_assistant_sessions_clear(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        result = self._clear_assistant_sessions(
            session=body.get("session"),
            session_id=body.get("session_id"),
            kind=body.get("kind"),
            has_pending_p115=body.get("has_pending_p115"),
            stale_only=self._parse_bool_value(body.get("stale_only"), False),
            all_sessions=self._parse_bool_value(body.get("all_sessions"), False),
            limit=self._safe_int(body.get("limit"), 100),
        )
        cleared_count = self._safe_int(result.get("cleared_count"), 0)
        if cleared_count <= 0:
            return {
                "success": True,
                "message": "没有匹配到需要清理的 assistant 会话。",
                "data": result,
            }
        return {
            "success": True,
            "message": f"已清理 {cleared_count} 个 assistant 会话。",
            "data": result,
        }

    async def api_session_hdhive_search(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        allowed, disabled = self._ensure_hdhive_resource_enabled()
        if not allowed:
            return disabled

        keyword = self._clean_text(body.get("keyword") or body.get("title"))
        media_type = self._clean_text(body.get("media_type") or body.get("type") or "auto").lower()
        year = self._clean_text(body.get("year"))
        target_path = self._clean_text(body.get("path") or body.get("target_path"))
        service = self._ensure_hdhive_service()
        search_ok, result, search_message = await service.resolve_candidates_by_keyword(
            keyword=keyword,
            media_type=media_type,
            year=year,
            candidate_limit=max(30, self._hdhive_candidate_page_size),
        )
        if not search_ok:
            return {"success": False, "message": search_message, "data": result}

        session_id = self._new_session_id("hdhive")
        self._save_session(
            session_id,
            {
                "kind": "hdhive",
                "stage": "candidate",
                "keyword": keyword,
                "media_type": media_type,
                "year": year,
                "target_path": target_path,
                "candidates": result.get("candidates") or [],
                "page": 1,
                "page_size": self._hdhive_candidate_page_size,
            },
        )
        return {
            "success": True,
            "message": "success",
            "data": {
                "text": self._format_candidate_lines(result.get("candidates") or [], page=1, page_size=self._hdhive_candidate_page_size),
                "session_id": session_id,
                "stage": "candidate",
                "keyword": keyword,
                "candidates": result.get("candidates") or [],
                "candidate_count": len(result.get("candidates") or []),
                "meta": result.get("meta") or {},
            },
        }

    async def api_session_hdhive_pick(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        allowed, disabled = self._ensure_hdhive_resource_enabled()
        if not allowed:
            return disabled

        session_id = self._clean_text(body.get("session_id"))
        index = self._safe_int(
            body.get("index")
            or body.get("choice")
            or body.get("selection")
            or body.get("number"),
            0,
        )
        action = self._normalize_pick_action(body.get("action") or body.get("pick_action"))
        target_path = self._clean_text(body.get("path") or body.get("target_path"))
        if not session_id or (index <= 0 and not action):
            return {"success": False, "message": "session_id 和选择编号必填；详情/翻页动作可传 action"}

        session = self._load_session(session_id)
        if not session:
            return {"success": False, "message": "会话不存在或已过期"}

        stage = session.get("stage")
        service = self._ensure_hdhive_service()

        if stage == "candidate":
            candidates = session.get("candidates") or []
            page_size = max(1, self._safe_int(session.get("page_size"), self._hdhive_candidate_page_size))
            current_page = max(1, self._safe_int(session.get("page"), 1))
            if action == "detail":
                start = (current_page - 1) * page_size
                end = start + page_size
                enriched = [dict(item or {}) for item in candidates]
                enriched[start:end] = self._enrich_hdhive_candidates_with_actors(enriched[start:end])
                self._save_session(session_id, {**session, "candidates": enriched, "target_path": target_path or session.get("target_path") or ""})
                return {
                    "success": True,
                    "message": "success",
                    "data": {
                        "text": self._format_candidate_lines(enriched, page=current_page, page_size=page_size),
                        "session_id": session_id,
                        "stage": "candidate",
                        "page": current_page,
                        "candidates": enriched,
                    },
                }
            if action == "next_page":
                total_pages = max(1, (len(candidates) + page_size - 1) // page_size)
                if current_page >= total_pages:
                    return {"success": False, "message": "已经是最后一页了，可以直接回复编号继续选择。"}
                next_page = current_page + 1
                self._save_session(session_id, {**session, "page": next_page, "target_path": target_path or session.get("target_path") or ""})
                return {
                    "success": True,
                    "message": "success",
                    "data": {
                        "text": self._format_candidate_lines(candidates, page=next_page, page_size=page_size),
                        "session_id": session_id,
                        "stage": "candidate",
                        "page": next_page,
                        "total_pages": total_pages,
                    },
                }
            if index > len(candidates):
                return {"success": False, "message": "候选编号超出范围"}
            candidate = dict(candidates[index - 1])
            resource_ok, resource_result, resource_message = service.search_resources(
                media_type=candidate.get("media_type") or session.get("media_type") or "movie",
                tmdb_id=str(candidate.get("tmdb_id") or ""),
            )
            if not resource_ok:
                return {"success": False, "message": resource_message, "data": resource_result}
            preview = self._group_resource_preview(resource_result.get("data") or [], per_group=6)
            self._save_session(
                session_id,
                {
                    **session,
                    "stage": "resource",
                    "selected_candidate": candidate,
                    "resources": preview,
                    "target_path": target_path or session.get("target_path") or "",
                },
            )
            return {
                "success": True,
                "message": "success",
                "data": {
                    "text": self._format_resource_lines(preview, candidate),
                    "session_id": session_id,
                    "stage": "resource",
                    "selected_candidate": candidate,
                    "resources": preview,
                    "meta": {
                        "total": len(preview),
                        "count_115": len([x for x in preview if str(x.get("pan_type") or "").lower() == "115"]),
                        "count_quark": len([x for x in preview if str(x.get("pan_type") or "").lower() == "quark"]),
                    },
                },
            }

        if stage == "resource":
            resources = session.get("resources") or []
            if index > len(resources):
                return {"success": False, "message": "资源编号超出范围"}
            resource = dict(resources[index - 1])
            slug = self._clean_text(resource.get("slug"))
            route_ok, route_result, route_message = await self._unlock_and_route(
                slug,
                target_path=target_path or session.get("target_path") or "",
                resource=resource,
            )
            if not route_ok:
                return {"success": False, "message": route_message, "data": route_result}
            return {
                "success": True,
                "message": route_message,
                "data": {
                    "text": self._format_route_result(route_result),
                    "session_id": session_id,
                    "selected_resource": resource,
                    "result": route_result,
                },
            }

        return {"success": False, "message": f"当前会话阶段不支持继续选择: {stage}"}
