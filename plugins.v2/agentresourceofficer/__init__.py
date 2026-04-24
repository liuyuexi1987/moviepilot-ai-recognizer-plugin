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
    HDHiveSearchSessionTool,
    HDHiveSessionPickTool,
    P115QRCodeCheckTool,
    P115QRCodeStartTool,
    ShareRouteTool,
)


class _JsonRequestShim:
    def __init__(self, request: Request, body: Dict[str, Any]) -> None:
        self.headers = request.headers
        self.query_params = request.query_params
        self._body = body

    async def json(self) -> Dict[str, Any]:
        return self._body


class AgentResourceOfficer(_PluginBase):
    plugin_name = "Agent资源官"
    plugin_desc = "重构中的资源工作流主插件，后续统一承接影巢、夸克、飞书与智能体入口。"
    plugin_icon = "https://raw.githubusercontent.com/liuyuexi1987/MoviePilot-Plugins/main/icons/world.png"
    plugin_version = "0.1.13"
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
        self._agent_tools_reloaded = False

    def get_state(self) -> bool:
        if self._enabled and not self._agent_tools_reloaded:
            self._reload_agent_tools()
            self._agent_tools_reloaded = True
        return self._enabled

    def get_agent_tools(self) -> List[type]:
        return [
            HDHiveSearchSessionTool,
            HDHiveSessionPickTool,
            ShareRouteTool,
            P115QRCodeStartTool,
            P115QRCodeCheckTool,
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
                            "Agent资源官正在重构中，当前已经接入夸克执行层，以及影巢的基础搜索/解锁服务骨架。"
                            f"\n当前夸克配置状态：{quark_ready}"
                            f"\n默认目录：{self._quark_default_path}"
                            f"\n当前影巢配置状态：{hdhive_ready}"
                            f"\n影巢默认目录：{self._hdhive_default_path}"
                            f"\n115 默认目录：{self._p115_default_path}"
                            f"\n115 执行方式：{p115_ready}"
                            f"\n115 扫码客户端：{self._p115_client_type_title(self._p115_client_type)}"
                            f"\n115 运行状态：{'可用' if p115_health_ok else '待修复'}"
                            f"\n115 扫码接口：/p115/qrcode  /p115/qrcode/check"
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
                                            "text": "当前版本仍属于重构阶段，但已经开始承接夸克执行层，以及影巢基础搜索/解锁 API。后续会继续迁入签到、会话选择和飞书入口。",
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
                                            "label": "启用骨架插件",
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

    def _load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self._session_cache.get(session_id)
        if not session:
            return None
        return dict(session)

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

    @staticmethod
    def _parse_assistant_text(text: str) -> Dict[str, str]:
        raw = str(text or "").strip()
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
        }
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
                return False, route_result, f"影巢解锁成功，但 115 转存失败：{transfer_message}"
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
                return f"115 转存失败：{message}"
            return f"115 转存成功\n目录：{result.get('path') or self._p115_default_path}"

        return "当前链接不是可识别的 115 / 夸克分享链接"

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
        if data.get("cookie_keys"):
            lines.append(f"cookie_keys: {', '.join(data.get('cookie_keys') or [])}")
        return "\n".join(lines)

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
            return {"success": False, "message": transfer_message, "data": result}
        return {"success": True, "message": transfer_message, "data": result}

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
                    "message": f"115 转存失败：{transfer_message}",
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
        parsed = self._parse_assistant_text(text)
        cache_key = self._assistant_session_id(session)
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
            return {
                "success": bool(result.get("success")),
                "message": (
                    f"{'夸克' if provider == 'quark' else '115' if provider == '115' else '分享'}转存已完成\n目录："
                    f"{((result.get('data') or {}).get('result') or {}).get('target_path') or ((result.get('data') or {}).get('result') or {}).get('path') or target_path or '-'}"
                    if result.get("success")
                    else str(result.get("message") or "处理失败")
                ),
                "data": {
                    "action": "share_route",
                    "ok": bool(result.get("success")),
                    "provider": provider,
                    "result": result.get("data") or {},
                },
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
                "data": {
                    "action": "pansou_search",
                    "ok": True,
                    "session_id": cache_key,
                    "items": items,
                },
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
            "data": {
                "action": "hdhive_candidates",
                "ok": True,
                "session_id": cache_key,
                "candidates": candidates,
            },
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
                return {"success": False, "message": str(route_result.get('message') or '转存失败'), "data": route_result.get("data") or {}}
            provider = ((route_result.get("data") or {}).get("provider") or "").lower()
            result_payload = (route_result.get("data") or {}).get("result") or {}
            directory = (result_payload.get("result") or {}).get("target_path") or (result_payload.get("result") or {}).get("path") or final_path
            text_message = "\n".join([
                "盘搜结果已执行转存",
                f"资源：{selected.get('note') or '未命名资源'}",
                f"类型：{provider or selected.get('channel') or '-'}",
                f"目录：{directory or '-'}",
            ])
            return {"success": True, "message": text_message, "data": {"action": "share_route", "ok": True}}

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
                        "data": {
                            "action": "hdhive_candidates_detail",
                            "ok": True,
                            "session_id": cache_key,
                            "page": current_page,
                            "candidates": enriched,
                        },
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
                        "data": {
                            "action": "hdhive_candidates_next_page",
                            "ok": True,
                            "session_id": cache_key,
                            "page": next_page,
                            "total_pages": total_pages,
                        },
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
                    "data": {
                        "action": "hdhive_search",
                        "ok": True,
                        "selected_candidate": candidate,
                        "resources": preview,
                    },
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
                return {"success": False, "message": route_message, "data": route_result}
            return {
                "success": True,
                "message": self._format_route_result(route_result),
                "data": {
                    "action": "hdhive_unlock",
                    "ok": True,
                    "selected_resource": resource,
                    "result": route_result,
                },
            }

        return {"success": False, "message": f"当前会话阶段不支持继续选择：{kind or 'unknown'}"}

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
