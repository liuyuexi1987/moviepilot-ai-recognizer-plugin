import concurrent.futures
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
    from app.core.config import settings
except Exception:
    settings = None
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
from .agenttool import (
    AssistantCapabilitiesTool,
    AssistantHelpTool,
    AssistantPickTool,
    AssistantRouteTool,
    AssistantSessionClearTool,
    AssistantSessionsTool,
    AssistantSessionStateTool,
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
    def __init__(self, request: Request, body: Dict[str, Any]) -> None:
        self.headers = request.headers
        self.query_params = request.query_params
        self._body = body

    async def json(self) -> Dict[str, Any]:
        return self._body


class _RequestContextShim:
    def __init__(self, headers: Optional[Dict[str, Any]] = None, query_params: Optional[Dict[str, Any]] = None) -> None:
        self.headers = headers or {}
        self.query_params = query_params or {}


class AgentResourceOfficer(_PluginBase):
    plugin_name = "Agent资源官"
    plugin_desc = "统一承接影巢、115、夸克、飞书与智能体入口的资源工作流主插件。"
    plugin_icon = "https://raw.githubusercontent.com/liuyuexi1987/MoviePilot-Plugins/main/icons/world.png"
    plugin_version = "0.1.33"
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
    _hdhive_api_key = ""
    _hdhive_base_url = "https://hdhive.com"
    _hdhive_timeout = 30
    _hdhive_default_path = "/待整理"
    _hdhive_candidate_page_size = 10
    _p115_default_path = "/待整理"
    _p115_client_type = "alipaymini"
    _p115_cookie = ""
    _p115_prefer_direct = True

    _quark_service: Optional[QuarkTransferService] = None
    _hdhive_service: Optional[HDHiveOpenApiService] = None
    _p115_service: Optional[P115TransferService] = None
    _session_cache: Dict[str, Dict[str, Any]] = {}
    _agent_tools_reloaded = False
    _candidate_actor_cache: Dict[str, List[str]] = {}
    _candidate_actor_cache_lock = threading.Lock()
    _session_store_key = "assistant_session_cache"
    _session_retention_seconds = 7 * 24 * 60 * 60

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
        if text in {"n", "next", "next_page", "下一页", "下页"} or text.startswith("n "):
            return "next_page"
        return ""

    def init_plugin(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._notify = bool(config.get("notify", True))
        self._debug = bool(config.get("debug", False))
        self._quark_cookie = self._clean_text(config.get("quark_cookie"))
        self._quark_default_path = self._normalize_path(config.get("quark_default_path") or "/飞书")
        self._quark_timeout = self._safe_int(config.get("quark_timeout"), 30)
        self._quark_auto_import_cookiecloud = bool(config.get("quark_auto_import_cookiecloud", True))
        self._hdhive_api_key = self._clean_text(config.get("hdhive_api_key"))
        self._hdhive_base_url = self._clean_text(config.get("hdhive_base_url") or "https://hdhive.com").rstrip("/")
        self._hdhive_timeout = self._safe_int(config.get("hdhive_timeout"), 30)
        self._hdhive_default_path = self._normalize_path(config.get("hdhive_default_path") or "/待整理")
        self._hdhive_candidate_page_size = max(5, min(20, self._safe_int(config.get("hdhive_candidate_page_size"), 10)))
        self._p115_default_path = self._normalize_path(config.get("p115_default_path") or "/待整理")
        self._p115_client_type = P115TransferService.normalize_qrcode_client_type(config.get("p115_client_type"))
        self._p115_cookie = self._clean_text(config.get("p115_cookie"))
        self._p115_prefer_direct = bool(config.get("p115_prefer_direct", True))
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
        self._agent_tools_reloaded = False

    def get_state(self) -> bool:
        if self._enabled and not self._agent_tools_reloaded:
            self._reload_agent_tools()
            self._agent_tools_reloaded = True
        return self._enabled

    def get_agent_tools(self) -> List[type]:
        return [
            AssistantCapabilitiesTool,
            AssistantHelpTool,
            AssistantRouteTool,
            AssistantPickTool,
            AssistantSessionsTool,
            AssistantSessionStateTool,
            AssistantSessionClearTool,
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
    def _normalize_path(value: Any) -> str:
        return QuarkTransferService.normalize_path(value)

    @staticmethod
    def _friendly_hdhive_error(message: str, capability: str) -> str:
        text = str(message or "").strip()
        lowered = text.lower()
        if "premium" in lowered or "仅对 premium 用户开放" in text:
            if capability == "checkin":
                return "影巢 OpenAPI 签到当前需要 Premium 用户；非 Premium 用户仍建议继续使用 HDHiveDailySign 网页签到链路。"
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
        config = self._load_hdhive_daily_sign_config()
        return self._clean_text(config.get("cookie"))

    def _build_config(self, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        config = {
            "enabled": self._enabled,
            "notify": self._notify,
            "debug": self._debug,
            "quark_cookie": self._quark_cookie,
            "quark_default_path": self._quark_default_path,
            "quark_timeout": self._quark_timeout,
            "quark_auto_import_cookiecloud": self._quark_auto_import_cookiecloud,
            "hdhive_api_key": self._hdhive_api_key,
            "hdhive_base_url": self._hdhive_base_url,
            "hdhive_timeout": self._hdhive_timeout,
            "hdhive_default_path": self._hdhive_default_path,
            "hdhive_candidate_page_size": self._hdhive_candidate_page_size,
            "p115_default_path": self._p115_default_path,
            "p115_client_type": self._p115_client_type,
            "p115_cookie": self._p115_cookie,
            "p115_prefer_direct": self._p115_prefer_direct,
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
        return

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/quark/health",
                "endpoint": self.api_quark_health,
                "methods": ["GET"],
                "summary": "检查 Agent资源官 的夸克配置",
            },
            {
                "path": "/quark/transfer",
                "endpoint": self.api_quark_transfer,
                "methods": ["POST"],
                "summary": "通过 Agent资源官 执行夸克分享转存",
            },
            {
                "path": "/hdhive/health",
                "endpoint": self.api_hdhive_health,
                "methods": ["GET"],
                "summary": "检查 Agent资源官 的影巢配置",
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
                "summary": "通过 Agent资源官 执行影巢资源搜索",
            },
            {
                "path": "/hdhive/search_by_keyword",
                "endpoint": self.api_hdhive_search_by_keyword,
                "methods": ["POST"],
                "summary": "通过 Agent资源官 执行影巢关键词候选搜索",
            },
            {
                "path": "/hdhive/unlock",
                "endpoint": self.api_hdhive_unlock,
                "methods": ["POST"],
                "summary": "通过 Agent资源官 执行影巢资源解锁",
            },
            {
                "path": "/hdhive/unlock_and_route",
                "endpoint": self.api_hdhive_unlock_and_route,
                "methods": ["POST"],
                "summary": "通过 Agent资源官 解锁影巢资源并尝试自动路由到对应网盘执行层",
            },
            {
                "path": "/p115/health",
                "endpoint": self.api_p115_health,
                "methods": ["GET"],
                "summary": "检查 Agent资源官 的 115 转存依赖状态",
            },
            {
                "path": "/p115/qrcode",
                "endpoint": self.api_p115_qrcode,
                "methods": ["GET"],
                "summary": "获取 Agent资源官 的 115 扫码登录二维码",
            },
            {
                "path": "/p115/qrcode/check",
                "endpoint": self.api_p115_qrcode_check,
                "methods": ["GET"],
                "summary": "检查 Agent资源官 的 115 扫码登录状态",
            },
            {
                "path": "/p115/transfer",
                "endpoint": self.api_p115_transfer,
                "methods": ["POST"],
                "summary": "通过 Agent资源官 执行 115 分享转存",
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
                "summary": "通过 Agent资源官 自动识别 115 / 夸克分享链接并执行对应转存",
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
        return [
            {
                "component": "VCard",
                "content": [
                    {
                        "component": "VCardText",
                        "text": (
                            "Agent资源官 已接入影巢搜索/解锁、115 扫码登录与转存、夸克转存，以及统一智能入口。"
                            f"\n当前夸克配置状态：{quark_ready}"
                            f"\n默认目录：{self._quark_default_path}"
                            f"\n当前影巢配置状态：{hdhive_ready}"
                            f"\n影巢默认目录：{self._hdhive_default_path}"
                            f"\n115 默认目录：{self._p115_default_path}"
                            f"\n115 执行方式：{p115_ready}"
                            f"\n115 扫码客户端：{self._p115_client_type_title(self._p115_client_type)}"
                            f"\n115 运行状态：{'可用' if p115_health_ok else '待修复'}"
                            f"\n115 扫码接口：/p115/qrcode  /p115/qrcode/check"
                            "\n统一智能入口：/assistant/route  /assistant/pick"
                            "\n原生 Agent Tool：影巢会话搜索/选择、115 扫码、115 待任务查看/继续/取消、通用分享路由"
                            "\n\n已支持的影巢用户态 API：/hdhive/account /hdhive/checkin /hdhive/quota /hdhive/usage_today /hdhive/weekly_free_quota"
                            f"\n115 Cookie 判定：{cookie_state.get('message') or '当前会话可直接用于 115 直转'}"
                            f"\n\n{hdhive_summary}"
                        ),
                    }
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
                                            "text": "当前版本已经接通影巢搜索/解锁、115 扫码登录与待任务续跑、夸克转存、统一智能入口，以及 MP 原生 Agent Tool。这里主要配置默认目录、影巢 OpenAPI 和夸克会话。",
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
                                "props": {"cols": 6},
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
                                "props": {"cols": 6},
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
                                "props": {"cols": 6},
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
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "hdhive_api_key",
                                            "label": "影巢 API Key",
                                            "rows": 2,
                                            "placeholder": "填写影巢 OpenAPI 的 API Key",
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
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": "115 建议走扫码会话，不建议填网页版 Cookie。Agent资源官 已支持 /p115/qrcode 和 /p115/qrcode/check 两步扫码登录；手填 Cookie 仅作为高级兜底。",
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
                ],
            }
        ]
        return form, self._build_config()

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
        trigger = self._clean_text(body.get("trigger") or "Agent资源官 API")

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
                        "message": "当前返回的是 HDHiveDailySign 保存的网页用户快照",
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

        service = self._ensure_hdhive_service()
        checkin_ok, result, checkin_message = service.perform_checkin(
            is_gambler=bool(body.get("is_gambler")),
            trigger="Agent资源官 API",
        )
        if not checkin_ok:
            if self._is_hdhive_premium_limited(result.get("message") or checkin_message):
                fallback_cookie = self._get_hdhive_fallback_cookie()
                if fallback_cookie:
                    fallback_ok, fallback_result, fallback_message = service.perform_web_checkin_with_fallback(
                        cookie_string=fallback_cookie,
                        is_gambler=bool(body.get("is_gambler")),
                        trigger="Agent资源官 网页兜底",
                    )
                    if fallback_ok:
                        return {
                            "success": True,
                            "message": fallback_result.get("message") or fallback_message or "签到成功",
                            "data": fallback_result,
                        }
                    return {
                        "success": False,
                        "message": f"影巢 OpenAPI 签到受 Premium 限制，且网页兜底签到失败：{fallback_result.get('message') or fallback_message}",
                        "data": {
                            "openapi": result,
                            "web_fallback": fallback_result,
                        },
                    }
            return {
                "success": False,
                "message": self._friendly_hdhive_error(result.get("message") or checkin_message, "checkin"),
                "data": result,
            }
        return {"success": True, "message": result.get("message") or "success", "data": result}

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

        keyword = self._clean_text(body.get("keyword") or body.get("title"))
        media_type = self._clean_text(body.get("media_type") or body.get("type") or "movie").lower()
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

        slug = self._clean_text(body.get("slug"))
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
        ordered = groups["115"] + groups["quark"] + groups["other"]
        preview: List[Dict[str, Any]] = []
        for index, item in enumerate(ordered, 1):
            row = dict(item)
            row["pick_index"] = index
            preview.append(row)
        return preview

    def _assistant_session_id(self, session: str) -> str:
        session = self._clean_text(session) or "default"
        return f"assistant::{session}"

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

    def _assistant_session_public_data(self, session: str = "default") -> Dict[str, Any]:
        session_name = self._clean_text(session) or "default"
        session_id = self._assistant_session_id(session_name)
        state = self._load_session(session_id) or {}
        if not state:
            return {
                "has_session": False,
                "session": session_name,
                "session_id": session_id,
                "suggested_actions": ["smart_entry"],
            }

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
                "suggested_actions": ["smart_pick.choice", "session_clear"],
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
                            "points": item.get("cost"),
                            "quality": self._clean_text(item.get("quality")),
                            "size": self._clean_text(item.get("size")),
                        }
                        for idx, item in enumerate(resources[:8])
                        if isinstance(item, dict)
                    ],
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
        return payload

    def _assistant_session_brief_public_data(self, session_id: str, state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        payload = dict(state or {})
        name = str(session_id or "")
        session_name = name.split("assistant::", 1)[1] if name.startswith("assistant::") else name or "default"
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
        }
        if result["kind"] == "assistant_pansou":
            result["result_count"] = len(payload.get("items") or [])
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
        return result

    def _assistant_sessions_public_data(
        self,
        *,
        kind: str = "",
        has_pending_p115: Optional[bool] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        kind_filter = self._clean_text(kind)
        max_limit = min(max(1, self._safe_int(limit, 20)), 100)
        items: List[Dict[str, Any]] = []
        for session_id, payload in (self._session_cache or {}).items():
            if not str(session_id).startswith("assistant::"):
                continue
            session = dict(payload or {})
            if self._is_session_expired(session):
                continue
            brief = self._assistant_session_brief_public_data(str(session_id), session)
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
            return "当前没有活跃的 Agent资源官 会话。"
        lines = [
            f"当前活跃会话：{data.get('total') or 0} 个",
            "可直接用 assistant/session 查看单个会话详情，或继续用 smart_pick 接着执行。",
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
            trigger="Agent资源官 115 登录后自动继续",
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
            "Agent资源官 使用帮助",
            f"当前会话：{session_name}",
            "推荐优先使用原生 Tool：agent_resource_officer_smart_entry 与 agent_resource_officer_smart_pick。",
            "smart_entry 常用示例：",
            "1. text=盘搜搜索 大君夫人",
            "2. text=影巢搜索 蜘蛛侠",
            "3. text=115登录",
            "4. text=检查115登录",
            "5. text=链接 https://115cdn.com/s/xxxx path=/待整理",
            "6. text=链接 https://pan.quark.cn/s/xxxx 位置=分享",
            "smart_pick 常用示例：",
            "1. choice=1",
            "2. action=详情",
            "3. action=下一页",
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
            },
            "smart_entry": {
                "supports_text": True,
                "supports_structured_fields": True,
                "modes": ["pansou", "hdhive"],
                "actions": [
                    "assistant_help",
                    "p115_qrcode_start",
                    "p115_qrcode_check",
                    "p115_status",
                    "p115_help",
                    "p115_pending",
                    "p115_resume",
                    "p115_cancel",
                ],
                "structured_fields": [
                    "session",
                    "path",
                    "mode",
                    "keyword",
                    "url",
                    "access_code",
                    "media_type",
                    "year",
                    "client_type",
                    "action",
                ],
            },
            "smart_pick": {
                "fields": ["session", "choice", "action", "path"],
                "actions": ["detail", "next_page"],
            },
            "session_tools": [
                "assistant/sessions",
                "assistant/session",
                "assistant/session/clear",
            ],
            "response_envelope": {
                "fields": [
                    "action",
                    "ok",
                    "session",
                    "session_id",
                    "session_state",
                    "next_actions",
                ],
                "description": "assistant/route 与 assistant/pick 返回的 data 中会统一附带当前会话状态和建议下一步动作，上层智能体可直接按结构化字段继续编排。",
            },
            "agent_tools": [
                "agent_resource_officer_capabilities",
                "agent_resource_officer_help",
                "agent_resource_officer_smart_entry",
                "agent_resource_officer_smart_pick",
                "agent_resource_officer_sessions",
                "agent_resource_officer_session_state",
                "agent_resource_officer_session_clear",
            ],
        }

    def _format_assistant_capabilities_text(self) -> str:
        data = self._assistant_capabilities_public_data()
        defaults = data.get("defaults") or {}
        lines = [
            "Agent资源官 能力说明",
            f"版本：{data.get('version')}",
            "推荐上层调用顺序：",
            "1. 先看 capabilities",
            "2. 如需恢复旧流程，可先看 assistant/sessions",
            "3. 再调用 smart_entry",
            "4. 之后用 assistant/session 或 session_state 判断下一步",
            "5. 最后再调用 smart_pick 或 session_clear",
            "默认目录：",
            f"- 影巢：{defaults.get('hdhive_path')}",
            f"- 115：{defaults.get('p115_path')}",
            f"- 夸克：{defaults.get('quark_path')}",
            f"- 115 客户端：{defaults.get('p115_client_type')}",
            "smart_entry 结构化字段：session / path / mode / keyword / url / access_code / media_type / year / client_type / action",
            "smart_entry 结构化模式：pansou / hdhive",
            "smart_entry 动作：assistant_help / p115_qrcode_start / p115_qrcode_check / p115_status / p115_help / p115_pending / p115_resume / p115_cancel",
            "smart_pick 字段：session / choice / action / path",
            "smart_pick 动作：detail / next_page",
            "统一回执字段：action / ok / session / session_id / session_state / next_actions",
        ]
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
        payload["session"] = session_name
        payload["session_id"] = session_state.get("session_id") or self._assistant_session_id(session_name)
        payload["session_state"] = session_state
        payload["next_actions"] = session_state.get("suggested_actions") or []
        return payload

    def _merge_assistant_structured_input(self, body: Dict[str, Any], parsed: Dict[str, str]) -> Dict[str, str]:
        merged = dict(parsed or {})
        body = dict(body or {})

        mode = self._clean_text(body.get("mode"))
        if mode in {"pansou", "hdhive"}:
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
        action = self._clean_text(body.get("action"))
        if action:
            merged["action"] = action
        return merged

    @staticmethod
    def _parse_assistant_text(text: str) -> Dict[str, str]:
        raw = str(text or "").strip()
        compact = re.sub(r"\s+", "", raw).lower()
        share_url = AgentResourceOfficer._extract_first_url(raw)
        remain = raw.replace(share_url, " ").strip() if share_url else raw
        mode, query = AgentResourceOfficer._normalize_search_prefix(remain)
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
        }
        if compact in {
            "帮助",
            "使用帮助",
            "命令帮助",
            "help",
            "agenthelp",
            "arohelp",
            "资源官帮助",
        }:
            options["action"] = "assistant_help"
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
        for query in queries:
            urls.append(f"http://host.docker.internal:805/api/search?{urlencode(query)}")
            urls.append(f"http://127.0.0.1:805/api/search?{urlencode(query)}")
        data: Dict[str, Any] = {}
        for url in urls:
            try:
                request = UrlRequest(url=url, headers={"Accept": "application/json"})
                with urlopen(request, timeout=20) as response:
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
            lines.append(f"   {cached['url']}")
        next_quark_hint = count_115 + 1 if count_quark else 1
        lines.append("下一步：回复“选择 1”即可直接转存支持的 115 / 夸克结果。")
        if count_quark:
            lines.append(f"夸克结果从 {next_quark_hint} 开始编号；例如“选择 {next_quark_hint}”可直接处理第 1 条夸克结果。")
        lines.append(f"如需改目录，可发“选择 1 path=/目录”或“选择 {next_quark_hint} path=/目录”。")
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
    def _format_resource_lines(resources: List[Dict[str, Any]], candidate: Optional[Dict[str, Any]] = None) -> str:
        lines = []
        if candidate:
            candidate_title = str(candidate.get("title") or "未命名")
            candidate_year = str(candidate.get("year") or "?")
            lines.append(f"已选影片：{candidate_title} ({candidate_year})")
        lines.append(f"资源结果：共 {len(resources)} 条")
        for idx, item in enumerate(resources, start=1):
            provider = str(item.get("pan_type") or "?").lower()
            points = item.get("unlock_points")
            if points in (0, "0"):
                points_text = "免费"
            elif points in (None, "", "未知"):
                points_text = "积分未知"
            else:
                points_text = f"{points}分"
            resolution = "/".join(item.get("video_resolution") or []) or "未知清晰度"
            item_title = str(item.get("title") or "未命名资源")
            lines.append(f"{idx}. [{provider}][{points_text}] {item_title} | {resolution}")
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

    async def _unlock_and_route(self, slug: str, target_path: str = "") -> Tuple[bool, Dict[str, Any], str]:
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
                trigger="Agent资源官 影巢解锁后自动路由",
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
                trigger="Agent资源官 影巢解锁后自动路由",
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

    async def tool_hdhive_search_session(
        self,
        keyword: str,
        media_type: str = "movie",
        year: str = "",
        target_path: str = "",
    ) -> str:
        if not self._enabled:
            return "Agent资源官 插件未启用"

        service = self._ensure_hdhive_service()
        search_ok, result, search_message = await service.resolve_candidates_by_keyword(
            keyword=self._clean_text(keyword),
            media_type=self._clean_text(media_type or "movie").lower(),
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
                "media_type": self._clean_text(media_type or "movie").lower(),
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
            return "Agent资源官 插件未启用"
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
            preview = self._group_resource_preview(resource_result.get("data") or [], per_group=6)
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
                trigger="Agent资源官 Agent Tool",
            )
            if not ok:
                return f"夸克转存失败：{message}"
            return f"夸克转存成功\n目录：{result.get('target_path') or self._quark_default_path}"

        if self._is_115_url(share_url):
            ok, result, message = self._ensure_p115_service().transfer_share(
                url=share_url,
                access_code=self._clean_text(access_code),
                path=self._clean_text(target_path) or self._p115_default_path,
                trigger="Agent资源官 Agent Tool",
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
        target_path: str = "",
        mode: str = "",
        keyword: str = "",
        share_url: str = "",
        access_code: str = "",
        media_type: str = "",
        year: str = "",
        client_type: str = "",
        action: str = "",
    ) -> str:
        if not self._enabled:
            return "Agent资源官 插件未启用"
        result = await self.api_assistant_route(
            _JsonRequestShim(
                _RequestContextShim(),
                {
                    "text": self._clean_text(text),
                    "session": self._clean_text(session) or "default",
                    "path": self._clean_text(target_path),
                    "mode": self._clean_text(mode),
                    "keyword": self._clean_text(keyword),
                    "url": self._clean_text(share_url),
                    "access_code": self._clean_text(access_code),
                    "media_type": self._clean_text(media_type),
                    "year": self._clean_text(year),
                    "client_type": self._clean_text(client_type),
                    "action": self._clean_text(action),
                },
            )
        )
        return str(result.get("message") or "处理完成")

    async def tool_assistant_pick(
        self,
        session: str = "default",
        index: int = 0,
        action: str = "",
        target_path: str = "",
    ) -> str:
        if not self._enabled:
            return "Agent资源官 插件未启用"
        result = await self.api_assistant_pick(
            _JsonRequestShim(
                _RequestContextShim(),
                {
                    "session": self._clean_text(session) or "default",
                    "choice": index,
                    "action": self._clean_text(action),
                    "path": self._clean_text(target_path),
                },
            )
        )
        return str(result.get("message") or "继续处理完成")

    async def tool_assistant_help(self, session: str = "default") -> str:
        if not self._enabled:
            return "Agent资源官 插件未启用"
        return self._format_assistant_help_text(session=session)

    async def tool_assistant_capabilities(self) -> str:
        if not self._enabled:
            return "Agent资源官 插件未启用"
        return self._format_assistant_capabilities_text()

    async def tool_assistant_session_state(self, session: str = "default") -> str:
        if not self._enabled:
            return "Agent资源官 插件未启用"
        return self._format_assistant_session_summary(session=session)

    async def tool_assistant_sessions(
        self,
        kind: str = "",
        has_pending_p115: Optional[bool] = None,
        limit: int = 20,
    ) -> str:
        if not self._enabled:
            return "Agent资源官 插件未启用"
        return self._format_assistant_sessions_text(
            kind=kind,
            has_pending_p115=has_pending_p115,
            limit=limit,
        )

    async def tool_assistant_session_clear(self, session: str = "default") -> str:
        if not self._enabled:
            return "Agent资源官 插件未启用"
        session_name = self._clean_text(session) or "default"
        session_id = self._assistant_session_id(session_name)
        existing = self._load_session(session_id)
        if not existing:
            return "当前没有需要清理的会话。"
        self._session_cache.pop(session_id, None)
        self._persist_relevant_sessions()
        return f"已清理会话：{session_name}"

    async def tool_p115_qrcode_start(self, client_type: str = "alipaymini") -> str:
        if not self._enabled:
            return "Agent资源官 插件未启用"
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
            return "Agent资源官 插件未启用"
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
            return "Agent资源官 插件未启用"
        return self._format_p115_status_summary()

    async def tool_p115_pending(self, session: str = "default") -> str:
        if not self._enabled:
            return "Agent资源官 插件未启用"
        session_id = self._session_key_for_tool(session)
        summary = self._pending_p115_summary(self._load_session(session_id))
        return summary or "当前没有待继续的 115 任务。"

    async def tool_p115_resume(self, session: str = "default") -> str:
        if not self._enabled:
            return "Agent资源官 插件未启用"
        session_id = self._session_key_for_tool(session)
        state = self._load_session(session_id) or {}
        if not self._pending_p115_summary(state):
            return "当前没有待继续的 115 任务。"
        if not self._p115_status_snapshot().get("ready"):
            return f"{self._pending_p115_summary(state)}\n当前 115 还不可用，请先完成 115 登录。"
        resume_ok, resume_message, _ = self._execute_pending_p115_share(
            session_id=session_id,
            state=state,
            trigger="Agent资源官 Agent Tool 手动继续 115 任务",
        )
        lines = ["已手动继续 115 任务", resume_message]
        if not resume_ok:
            lines.append("任务仍未成功，保留待继续状态。")
        return "\n".join(line for line in lines if line)

    async def tool_p115_cancel(self, session: str = "default") -> str:
        if not self._enabled:
            return "Agent资源官 插件未启用"
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
        trigger = self._clean_text(body.get("trigger") or "Agent资源官 API")

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
            trigger="Agent资源官 API 手动继续 115 任务",
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

        slug = self._clean_text(body.get("slug"))
        target_path = self._clean_text(body.get("path") or body.get("target_path"))
        route_ok, route_result, route_message = await self._unlock_and_route(slug, target_path=target_path)
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
        trigger = self._clean_text(body.get("trigger") or "Agent资源官 自动路由")

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

    async def api_assistant_route(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        session = self._clean_text(
            body.get("session")
            or body.get("chat_id")
            or body.get("user_id")
            or body.get("conversation_id")
            or "default"
        )
        text = self._clean_text(body.get("text") or body.get("query") or body.get("message") or "")
        parsed = self._merge_assistant_structured_input(body, self._parse_assistant_text(text))
        cache_key = self._assistant_session_id(session)
        state = self._load_session(cache_key) or {}
        target_path = parsed.get("path") or ""
        route_action = self._normalize_pick_action(text)
        if route_action:
            pick_result = await self.api_assistant_pick(
                _JsonRequestShim(request, {
                    "session": session,
                    "index": 0,
                    "action": route_action,
                    "path": target_path,
                    "apikey": self._extract_apikey(request, body),
                })
            )
            return pick_result

        if not text and not any(parsed.get(key) for key in ["mode", "keyword", "url", "action"]):
            summary = self._format_assistant_help_text(session=session)
            return {
                "success": True,
                "message": summary,
                "data": self._assistant_response_data(session=session, data={
                    "action": "assistant_help",
                    "ok": True,
                    "status_summary": summary,
                }),
            }

        assistant_action = self._clean_text(parsed.get("action"))
        if assistant_action == "assistant_help":
            summary = self._format_assistant_help_text(session=session)
            return {
                "success": True,
                "message": summary,
                "data": self._assistant_response_data(session=session, data={
                    "action": "assistant_help",
                    "ok": True,
                    "status_summary": summary,
                }),
            }
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
            return {
                "success": True,
                "message": summary,
                "data": self._assistant_response_data(session=session, data={
                    "action": "p115_status",
                    "ok": True,
                    "status_summary": summary,
                    "status": self._p115_status_snapshot(),
                }),
            }
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
                    "trigger": "Agent资源官 智能入口",
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
            return {
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
            }

        mode = parsed.get("mode") or "hdhive"
        keyword = self._clean_text(parsed.get("keyword"))
        media_type = self._clean_text(parsed.get("type") or "movie").lower() or "movie"
        year = self._clean_text(parsed.get("year"))

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
            return {
                "success": True,
                "message": text_message,
                "data": self._assistant_response_data(session=session, data={
                    "action": "pansou_search",
                    "ok": True,
                    "items": items,
                }),
            }

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
        return {
            "success": True,
            "message": text_message,
            "data": self._assistant_response_data(session=session, data={
                "action": "hdhive_candidates",
                "ok": True,
                "candidates": candidates,
            }),
        }

    async def api_assistant_pick(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        session = self._clean_text(
            body.get("session")
            or body.get("chat_id")
            or body.get("user_id")
            or body.get("conversation_id")
            or "default"
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
        cache_key = self._assistant_session_id(session)
        state = self._load_session(cache_key)
        if not state:
            return {"success": False, "message": "没有可继续的缓存，请先发起搜索或发送分享链接。"}
        if index <= 0 and not action:
            return {"success": False, "message": "请选择有效序号，例如：选择 1"}

        kind = str(state.get("kind") or "").strip()
        if kind == "assistant_pansou":
            items = state.get("items") or []
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
                    "trigger": "Agent资源官 智能入口盘搜选择",
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
                    return {
                        "success": False,
                        "message": (
                            f"{str(route_result.get('message') or '转存失败')}\n"
                            f"{self._format_p115_resume_hint(selected.get('note') or '')}"
                        ),
                        "data": self._assistant_response_data(session=session, data=route_result.get("data") or {}),
                    }
                return {
                    "success": False,
                    "message": str(route_result.get('message') or '转存失败'),
                    "data": self._assistant_response_data(session=session, data=route_result.get("data") or {}),
                }
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
            return {
                "success": True,
                "message": text_message,
                "data": self._assistant_response_data(session=session, data={"action": "share_route", "ok": True}),
            }

        if kind == "assistant_hdhive":
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
                    return {
                        "success": True,
                        "message": self._format_candidate_lines(enriched, page=current_page, page_size=page_size),
                        "data": self._assistant_response_data(session=session, data={
                            "action": "hdhive_candidates_detail",
                            "ok": True,
                            "page": current_page,
                            "candidates": enriched,
                        }),
                    }
                if action == "next_page":
                    total_pages = max(1, (len(candidates) + page_size - 1) // page_size)
                    if current_page >= total_pages:
                        return {"success": False, "message": "已经是最后一页了，可以直接回复编号继续选择。"}
                    next_page = current_page + 1
                    self._save_session(cache_key, {**state, "page": next_page, "target_path": final_path})
                    return {
                        "success": True,
                        "message": self._format_candidate_lines(candidates, page=next_page, page_size=page_size),
                        "data": self._assistant_response_data(session=session, data={
                            "action": "hdhive_candidates_next_page",
                            "ok": True,
                            "page": next_page,
                            "total_pages": total_pages,
                        }),
                    }
                if index > len(candidates):
                    return {"success": False, "message": f"序号超出范围，请输入 1 到 {len(candidates)} 之间的数字。"}
                candidate = dict(candidates[index - 1])
                resource_ok, resource_result, resource_message = service.search_resources(
                    media_type=candidate.get("media_type") or state.get("media_type") or "movie",
                    tmdb_id=str(candidate.get("tmdb_id") or ""),
                )
                if not resource_ok:
                    return {"success": False, "message": f"影巢资源查询失败：{resource_message}", "data": resource_result}
                preview = self._group_resource_preview(resource_result.get("data") or [], per_group=6)
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
                return {
                    "success": True,
                    "message": self._format_resource_lines(preview, candidate),
                    "data": self._assistant_response_data(session=session, data={
                        "action": "hdhive_search",
                        "ok": True,
                        "selected_candidate": candidate,
                        "resources": preview,
                    }),
                }
            resources = state.get("resources") or []
            if index > len(resources):
                return {"success": False, "message": f"序号超出范围，请输入 1 到 {len(resources)} 之间的数字。"}
            resource = dict(resources[index - 1])
            route_ok, route_result, route_message = await self._unlock_and_route(
                self._clean_text(resource.get("slug")),
                target_path=final_path,
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
                    return {
                        "success": False,
                        "message": f"{route_message}\n{self._format_p115_resume_hint(resource.get('title') or resource.get('matched_title') or '')}",
                        "data": self._assistant_response_data(session=session, data=route_result),
                    }
                return {
                    "success": False,
                    "message": route_message,
                    "data": self._assistant_response_data(session=session, data=route_result),
                }
            return {
                "success": True,
                "message": self._format_route_result(route_result),
                "data": self._assistant_response_data(session=session, data={
                    "action": "hdhive_unlock",
                    "ok": True,
                    "selected_resource": resource,
                    "result": route_result,
                }),
            }

        return {"success": False, "message": f"当前会话阶段不支持继续选择：{kind or 'unknown'}"}

    async def api_assistant_capabilities(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        return {
            "success": True,
            "message": self._format_assistant_capabilities_text(),
            "data": self._assistant_response_data(session="default", data=self._assistant_capabilities_public_data()),
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
        session = self._clean_text(
            (body or {}).get("session")
            or request.query_params.get("session")
            or request.query_params.get("chat_id")
            or request.query_params.get("user_id")
            or "default"
        )
        summary = self._format_assistant_session_summary(session=session)
        data = self._assistant_session_public_data(session=session)
        return {"success": True, "message": summary, "data": data}

    async def api_assistant_session_clear(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        session = self._clean_text(
            body.get("session")
            or body.get("chat_id")
            or body.get("user_id")
            or body.get("conversation_id")
            or "default"
        )
        session_id = self._assistant_session_id(session)
        existing = self._load_session(session_id)
        if not existing:
            return {
                "success": True,
                "message": "当前没有需要清理的会话。",
                "data": {"session": session, "session_id": session_id, "cleared": False},
            }
        self._session_cache.pop(session_id, None)
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
        limit = self._safe_int(request.query_params.get("limit"), 20)
        data = self._assistant_sessions_public_data(
            kind=kind,
            has_pending_p115=has_pending_p115,
            limit=limit,
        )
        return {
            "success": True,
            "message": self._format_assistant_sessions_text(
                kind=kind,
                has_pending_p115=has_pending_p115,
                limit=limit,
            ),
            "data": data,
        }

    async def api_session_hdhive_search(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}

        keyword = self._clean_text(body.get("keyword") or body.get("title"))
        media_type = self._clean_text(body.get("media_type") or body.get("type") or "movie").lower()
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
