import importlib
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from zoneinfo import ZoneInfo

try:
    from app.core.config import settings
except Exception:
    settings = None
try:
    from app.core.plugin import PluginManager
except Exception:
    PluginManager = None


class P115TransferService:
    """Reusable 115 share transfer execution layer for Agent资源官."""

    def __init__(self, *, default_target_path: str = "/待整理") -> None:
        self.default_target_path = self.normalize_pan_path(default_target_path) or "/待整理"

    @staticmethod
    def normalize_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def normalize_pan_path(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if not text.startswith("/"):
            text = f"/{text}"
        return text.rstrip("/") or "/"

    @staticmethod
    def is_115_share_url(url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return host == "115.com" or host.endswith(".115.com") or "115cdn.com" in host

    def ensure_115_share_url(self, url: str, access_code: str = "") -> str:
        clean_url = self.normalize_text(url)
        if not clean_url:
            return ""
        access_code = self.normalize_text(access_code)
        parsed = urlparse(clean_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        if access_code and "password" not in query:
            query["password"] = access_code
            clean_url = urlunparse(parsed._replace(query=urlencode(query)))
        return clean_url

    @staticmethod
    def jsonable(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool, list, dict)):
            return value
        if is_dataclass(value):
            return asdict(value)
        if hasattr(value, "model_dump"):
            try:
                return value.model_dump()
            except Exception:
                pass
        if hasattr(value, "__dict__"):
            return {k: v for k, v in vars(value).items() if not k.startswith("_")}
        return str(value)

    def tz_now(self) -> datetime:
        if settings is not None:
            try:
                return datetime.now(ZoneInfo(getattr(settings, "TZ", "Asia/Shanghai")))
            except Exception:
                pass
        return datetime.now()

    @staticmethod
    def _resolve_servicer_from_loaded_plugin() -> Tuple[Optional[Any], Optional[str]]:
        if PluginManager is None:
            return None, "PluginManager 不可用"
        try:
            plugin = PluginManager().running_plugins.get("P115StrmHelper")
        except Exception as exc:
            return None, f"读取 P115StrmHelper 运行态失败: {exc}"
        if not plugin:
            return None, "P115StrmHelper 未加载"

        module_names = []
        plugin_module = getattr(plugin.__class__, "__module__", "") or ""
        if plugin_module:
            module_names.append(f"{plugin_module}.service")
        module_names.extend(
            [
                "app.plugins.p115strmhelper.service",
                "p115strmhelper.service",
            ]
        )

        for module_name in module_names:
            try:
                module = sys.modules.get(module_name) or importlib.import_module(module_name)
                servicer = getattr(module, "servicer", None)
                if servicer is not None:
                    return servicer, None
            except Exception:
                continue
        return None, "P115StrmHelper 运行态已加载，但未找到 service.servicer"

    @classmethod
    def _import_servicer_fallback(cls) -> Tuple[Optional[Any], Optional[str]]:
        last_error = ""
        for module_name in [
            "app.plugins.p115strmhelper.service",
            "p115strmhelper.service",
        ]:
            try:
                service_module = importlib.import_module(module_name)
                servicer = getattr(service_module, "servicer", None)
                if servicer is not None:
                    return servicer, None
                last_error = f"{module_name} 未暴露 servicer"
            except Exception as exc:
                last_error = f"{module_name} 导入失败: {exc}"
        return None, last_error or "P115StrmHelper 未安装或无法导入"

    def get_share_helper(self) -> Tuple[Optional[Any], Optional[str]]:
        servicer, helper_error = self._resolve_servicer_from_loaded_plugin()
        if not servicer:
            servicer, helper_error = self._import_servicer_fallback()
        if not servicer:
            return None, f"P115StrmHelper 未安装或无法导入: {helper_error}"
        if not servicer:
            return None, "P115StrmHelper 未初始化"
        if not getattr(servicer, "client", None):
            return None, "P115StrmHelper 未登录 115 或客户端不可用"
        helper = getattr(servicer, "sharetransferhelper", None)
        if not helper:
            return None, "P115StrmHelper 分享转存模块不可用"
        return helper, None

    def health(self) -> Tuple[bool, Dict[str, Any], str]:
        helper, helper_error = self.get_share_helper()
        if helper_error or not helper:
            return False, {"helper_ready": False, "message": helper_error or "P115StrmHelper 不可用"}, helper_error or "P115StrmHelper 不可用"
        return True, {"helper_ready": True, "message": "success"}, ""

    def transfer_share(
        self,
        *,
        url: str = "",
        access_code: str = "",
        path: str = "",
        trigger: str = "Agent资源官",
    ) -> Tuple[bool, Dict[str, Any], str]:
        transfer_path = self.normalize_pan_path(path) or self.default_target_path or "/待整理"
        share_url = self.ensure_115_share_url(url or "", access_code or "")
        result = {
            "time": self.tz_now().strftime("%Y-%m-%d %H:%M:%S"),
            "ok": False,
            "trigger": trigger,
            "path": transfer_path,
            "url": share_url,
            "message": "",
            "data": {},
        }
        if not share_url:
            result["message"] = "没有可用于 115 转存的分享链接"
            return False, result, result["message"]
        if not self.is_115_share_url(share_url):
            result["message"] = "当前链接不是 115 分享链接，无法直接转存到 115"
            return False, result, result["message"]

        helper, helper_error = self.get_share_helper()
        if helper_error or not helper:
            result["message"] = helper_error or "P115StrmHelper 不可用"
            return False, result, result["message"]

        try:
            transfer_result = helper.add_share_115(
                share_url,
                notify=False,
                pan_path=transfer_path,
            )
        except Exception as exc:
            result["message"] = f"调用 P115StrmHelper 转存失败: {exc}"
            return False, result, result["message"]

        if not transfer_result or not transfer_result[0]:
            error_message = ""
            if isinstance(transfer_result, tuple):
                if len(transfer_result) > 2:
                    error_message = self.normalize_text(transfer_result[2])
                elif len(transfer_result) > 1:
                    error_message = self.normalize_text(transfer_result[1])
            result["message"] = error_message or "115 转存失败"
            result["data"] = {"raw": self.jsonable(transfer_result)}
            return False, result, result["message"]

        media_info = transfer_result[1] if len(transfer_result) > 1 else None
        save_parent = transfer_result[2] if len(transfer_result) > 2 else transfer_path
        parent_id = transfer_result[3] if len(transfer_result) > 3 else None
        result.update(
            {
                "ok": True,
                "message": "115 转存成功",
                "data": {
                    "media_info": self.jsonable(media_info),
                    "save_parent": save_parent,
                    "parent_id": parent_id,
                },
            }
        )
        return True, result, result["message"]
