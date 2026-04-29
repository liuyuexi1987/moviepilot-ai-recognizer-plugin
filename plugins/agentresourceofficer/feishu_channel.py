import asyncio
import copy
import fcntl
import importlib
import json
import re
import sqlite3
import sys
import threading
import time
import traceback
from base64 import b64decode
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

for _site_path in (
    "/usr/local/lib/python3.12/site-packages",
    "/usr/local/lib/python3.11/site-packages",
):
    if Path(_site_path).exists() and _site_path not in sys.path:
        sys.path.append(_site_path)

try:
    import lark_oapi as lark
except Exception:
    lark = None

try:
    from app.chain.download import DownloadChain
    from app.chain.media import MediaChain
    from app.chain.search import SearchChain
    from app.chain.subscribe import SubscribeChain
    from app.core.event import eventmanager
    from app.core.metainfo import MetaInfo
    from app.core.plugin import PluginManager
    from app.log import logger
    from app.scheduler import Scheduler
    from app.schemas.types import EventType
    from app.utils.http import RequestUtils
    from app.utils.string import StringUtils
except Exception:
    DownloadChain = None
    MediaChain = None
    SearchChain = None
    SubscribeChain = None
    eventmanager = None
    MetaInfo = None
    PluginManager = None
    Scheduler = None
    EventType = None
    RequestUtils = None
    StringUtils = None

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


_EVENT_CACHE_FILE = Path("/config/plugins/AgentResourceOfficer/.feishu_event_cache.json")


class _FeishuLongConnectionRuntime:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._fingerprint = ""
        self._channel: Optional["FeishuChannel"] = None

    def start(self, channel: "FeishuChannel") -> None:
        global lark
        if lark is None:
            try:
                import lark_oapi as runtime_lark
                lark = runtime_lark
            except Exception as exc:
                logger.error(f"[AgentResourceOfficer][Feishu] 缺少依赖 lark-oapi：{exc}")
                return

        if not channel.enabled or not channel.app_id or not channel.app_secret:
            return

        fingerprint = channel.connection_fingerprint()
        with self._lock:
            self._channel = channel
            if self._thread and self._thread.is_alive():
                if fingerprint != self._fingerprint:
                    logger.warning("[AgentResourceOfficer][Feishu] 长连接已在运行，飞书凭证变更需重启 MoviePilot 后生效")
                return
            self._fingerprint = fingerprint
            self._thread = threading.Thread(
                target=self._run,
                name="agent-resource-officer-feishu",
                daemon=True,
            )
            self._thread.start()

    def _run(self) -> None:
        channel = self._channel
        if channel is None or lark is None:
            return

        def _on_message(data) -> None:
            current = self._channel
            if current is not None:
                current.handle_long_connection_event(data)

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            import lark_oapi.ws.client as lark_ws_client

            lark_ws_client.loop = loop
            event_handler = (
                lark.EventDispatcherHandler.builder("", "")
                .register_p2_im_message_receive_v1(_on_message)
                .build()
            )
            ws_client = lark.ws.Client(
                channel.app_id,
                channel.app_secret,
                log_level=lark.LogLevel.DEBUG if channel.debug else lark.LogLevel.INFO,
                event_handler=event_handler,
            )
            logger.info("[AgentResourceOfficer][Feishu] 正在启动飞书长连接")
            ws_client.start()
        except Exception as exc:
            logger.error(f"[AgentResourceOfficer][Feishu] 长连接退出：{exc}\n{traceback.format_exc()}")

    def is_running(self) -> bool:
        with self._lock:
            return bool(self._thread and self._thread.is_alive())

    def stop(self) -> None:
        with self._lock:
            self._channel = None


class FeishuChannel:
    def __init__(self, plugin: Any) -> None:
        self.plugin = plugin
        self.runtime = _FeishuLongConnectionRuntime()
        self.enabled = False
        self.allow_all = False
        self.reply_enabled = True
        self.reply_receive_id_type = "chat_id"
        self.app_id = ""
        self.app_secret = ""
        self.verification_token = ""
        self.allowed_chat_ids: List[str] = []
        self.allowed_user_ids: List[str] = []
        self.command_whitelist: List[str] = []
        self.command_aliases = ""
        self.command_mode = "resource_officer"
        self.debug = False
        self._token_cache: Dict[str, Any] = {}
        self._token_lock = threading.Lock()
        self._event_cache: Dict[str, float] = {}
        self._event_lock = threading.Lock()
        self._search_cache: Dict[str, Dict[str, Any]] = {}
        self._search_cache_lock = threading.Lock()

    @classmethod
    def default_command_whitelist(cls) -> List[str]:
        return [
            "/p115_manual_transfer",
            "/p115_inc_sync",
            "/p115_full_sync",
            "/p115_strm",
            "/quark_save",
            "/pansou_search",
            "/smart_entry",
            "/smart_pick",
            "/media_search",
            "/media_download",
            "/media_subscribe",
            "/media_subscribe_search",
            "/version",
        ]

    @classmethod
    def default_command_aliases(cls) -> str:
        return (
            "刮削=/p115_manual_transfer\n"
            "搜索=/media_search\n"
            "MP搜索=/media_search\n"
            "原生搜索=/media_search\n"
            "盘搜搜索=/pansou_search\n"
            "盘搜=/pansou_search\n"
            "ps=/pansou_search\n"
            "1=/pansou_search\n"
            "影巢搜索=/smart_entry\n"
            "yc=/smart_entry\n"
            "2=/smart_entry\n"
            "下载=/media_download\n"
            "订阅=/media_subscribe\n"
            "订阅搜索=/media_subscribe_search\n"
            "生成STRM=/p115_inc_sync\n"
            "全量STRM=/p115_full_sync\n"
            "指定路径STRM=/p115_strm\n"
            "夸克转存=/quark_save\n"
            "夸克=/quark_save\n"
            "链接=/smart_entry\n"
            "处理=/smart_entry\n"
            "115登录=/smart_entry\n"
            "115扫码=/smart_entry\n"
            "检查115登录=/smart_entry\n"
            "115登录状态=/smart_entry\n"
            "115状态=/smart_entry\n"
            "115帮助=/smart_entry\n"
            "115任务=/smart_entry\n"
            "继续115任务=/smart_entry\n"
            "取消115任务=/smart_entry\n"
            "影巢签到=/smart_entry\n"
            "影巢普通签到=/smart_entry\n"
            "普通签到=/smart_entry\n"
            "签到=/smart_entry\n"
            "赌狗签到=/smart_entry\n"
            "签到日志=/smart_entry\n"
            "影巢签到日志=/smart_entry\n"
            "选择=/smart_pick\n"
            "详情=/smart_pick\n"
            "审查=/smart_pick\n"
            "选=/smart_pick\n"
            "继续=/smart_pick\n"
            "影巢=/smart_entry\n"
            "搜索资源=/media_search\n"
            "下载资源=/media_download\n"
            "订阅媒体=/media_subscribe\n"
            "订阅并搜索=/media_subscribe_search\n"
            "版本=/version"
        )

    @staticmethod
    def clean(value: Any) -> str:
        if value is None:
            return ""
        text = str(value)
        for ch in ("\ufeff", "\u200b", "\u200c", "\u200d", "\u2060", "\ufffc"):
            text = text.replace(ch, "")
        return text.strip()

    @staticmethod
    def split_lines(value: Any) -> List[str]:
        return [line.strip() for line in str(value or "").splitlines() if line.strip()]

    @staticmethod
    def split_commands(value: Any) -> List[str]:
        raw = str(value or "").replace("\n", ",")
        return [item.strip() for item in raw.split(",") if item.strip()]

    @classmethod
    def parse_alias_text(cls, text: str) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for line in str(text or "").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key and value.startswith("/"):
                result[key] = value
        return result

    @classmethod
    def merge_command_aliases(cls, configured_text: str) -> str:
        merged = cls.parse_alias_text(cls.default_command_aliases())
        for key, value in cls.parse_alias_text(configured_text).items():
            merged[key] = value
        return "\n".join(f"{key}={value}" for key, value in merged.items())

    @classmethod
    def merge_command_whitelist(cls, configured: List[str]) -> List[str]:
        merged: List[str] = []
        seen = set()
        for cmd in configured or []:
            if cmd and cmd not in seen:
                merged.append(cmd)
                seen.add(cmd)
        for cmd in cls.default_command_whitelist():
            if cmd not in seen:
                merged.append(cmd)
                seen.add(cmd)
        return merged

    def configure(self, config: Dict[str, Any]) -> None:
        self.enabled = bool(config.get("feishu_enabled", False))
        self.allow_all = bool(config.get("feishu_allow_all", False))
        self.reply_enabled = bool(config.get("feishu_reply_enabled", True))
        self.reply_receive_id_type = self.clean(config.get("feishu_reply_receive_id_type") or "chat_id")
        self.app_id = self.clean(config.get("feishu_app_id"))
        self.app_secret = self.clean(config.get("feishu_app_secret"))
        self.verification_token = self.clean(config.get("feishu_verification_token"))
        self.allowed_chat_ids = self.split_lines(config.get("feishu_allowed_chat_ids"))
        self.allowed_user_ids = self.split_lines(config.get("feishu_allowed_user_ids"))
        self.command_whitelist = self.merge_command_whitelist(self.split_commands(config.get("feishu_command_whitelist")))
        self.command_aliases = self.merge_command_aliases(self.clean(config.get("feishu_command_aliases")))
        self.command_mode = self.clean(config.get("feishu_command_mode") or "resource_officer")
        self.debug = bool(config.get("debug", False))

    def start(self) -> None:
        if self.enabled:
            self.runtime.start(self)

    def stop(self) -> None:
        self.runtime.stop()

    def is_running(self) -> bool:
        return self.runtime.is_running()

    @staticmethod
    def is_legacy_bridge_running() -> bool:
        if PluginManager is None:
            return False
        try:
            running_plugins = PluginManager().running_plugins or {}
            plugin = (
                running_plugins.get("FeishuCommandBridgeLong")
                or running_plugins.get("feishucommandbridgelong")
            )
            if not plugin:
                return False
            config_db = Path("/config/user.db")
            if config_db.exists():
                try:
                    with sqlite3.connect(str(config_db)) as conn:
                        row = conn.execute(
                            "select value from systemconfig where key=?",
                            ("plugin.FeishuCommandBridgeLong",),
                        ).fetchone()
                    if row and row[0]:
                        config = json.loads(row[0])
                        if not bool(config.get("enabled")):
                            return False
                except Exception:
                    pass
            # MoviePilot may keep disabled plugins in running_plugins after loading.
            # Treat the legacy bridge as a conflict only when it is actually enabled.
            if hasattr(plugin, "health"):
                try:
                    health = plugin.health()
                    if isinstance(health, dict):
                        return bool(health.get("enabled") and health.get("running"))
                except Exception:
                    pass
            if hasattr(plugin, "_enabled"):
                return bool(getattr(plugin, "_enabled", False))
            if hasattr(plugin, "get_state"):
                try:
                    return bool(plugin.get_state())
                except Exception:
                    return False
            return False
        except Exception:
            return False

    def connection_fingerprint(self) -> str:
        return "|".join([self.app_id, self.app_secret, self.verification_token])

    def health(self) -> Dict[str, Any]:
        legacy_bridge_running = self.is_legacy_bridge_running()
        sdk_available = lark is not None
        app_id_configured = bool(self.app_id)
        app_secret_configured = bool(self.app_secret)
        verification_token_configured = bool(self.verification_token)
        missing_requirements = []
        if not sdk_available:
            missing_requirements.append("lark-oapi")
        if not app_id_configured:
            missing_requirements.append("feishu_app_id")
        if not app_secret_configured:
            missing_requirements.append("feishu_app_secret")
        conflict_warning = bool(self.enabled and legacy_bridge_running)
        ready_to_start = bool(self.enabled and sdk_available and app_id_configured and app_secret_configured and not conflict_warning)
        safe_to_enable = bool((not legacy_bridge_running) and sdk_available and app_id_configured and app_secret_configured)
        if conflict_warning:
            recommended_action = "disable_legacy_bridge_or_use_different_app"
            migration_hint = "内置飞书入口和旧飞书桥接同时运行，建议关闭旧桥接或使用不同飞书 App。"
        elif not self.enabled and legacy_bridge_running:
            recommended_action = "keep_legacy_or_disable_it_before_migration"
            migration_hint = "内置飞书入口关闭，旧飞书桥接运行中；迁移前先关闭旧桥接。"
        elif not self.enabled:
            recommended_action = "configure_and_enable_feishu_channel"
            migration_hint = "内置飞书入口关闭；配置飞书凭证后可开启。"
        elif missing_requirements:
            recommended_action = "complete_feishu_requirements"
            migration_hint = "内置飞书入口已启用，但依赖或飞书凭证不完整。"
        elif not self.is_running():
            recommended_action = "restart_moviepilot_or_resave_config"
            migration_hint = "内置飞书入口已启用但长连接未运行，建议保存配置或重启 MoviePilot。"
        else:
            recommended_action = "none"
            migration_hint = "内置飞书入口运行正常。"
        return {
            "enabled": self.enabled,
            "running": self.is_running(),
            "sdk_available": sdk_available,
            "app_id_configured": app_id_configured,
            "app_secret_configured": app_secret_configured,
            "verification_token_configured": verification_token_configured,
            "allow_all": self.allow_all,
            "reply_enabled": self.reply_enabled,
            "allowed_chat_count": len(self.allowed_chat_ids),
            "allowed_user_count": len(self.allowed_user_ids),
            "command_mode": self.command_mode,
            "command_whitelist": self.command_whitelist,
            "alias_count": len(self.parse_alias_text(self.command_aliases)),
            "legacy_bridge_running": legacy_bridge_running,
            "conflict_warning": conflict_warning,
            "ready_to_start": ready_to_start,
            "safe_to_enable": safe_to_enable,
            "missing_requirements": missing_requirements,
            "recommended_action": recommended_action,
            "migration_hint": migration_hint,
        }

    def handle_long_connection_event(self, data: Any) -> None:
        if not self.enabled:
            return
        event = getattr(data, "event", None)
        header = getattr(data, "header", None)
        message = getattr(event, "message", None)
        sender = getattr(event, "sender", None)
        sender_id = getattr(sender, "sender_id", None)

        event_id = str(getattr(header, "event_id", "") or "").strip()
        if event_id and self._is_duplicate_event(event_id):
            return
        if not message or str(getattr(message, "message_type", "")).strip() != "text":
            return

        raw_text = self._extract_text(getattr(message, "content", None))
        if not raw_text:
            return
        sender_open_id = str(getattr(sender_id, "open_id", "") or "").strip()
        chat_id = str(getattr(message, "chat_id", "") or "").strip()
        if self.debug:
            logger.info(f"[AgentResourceOfficer][Feishu] event_id={event_id} chat_id={chat_id}")

        if not self._is_allowed(chat_id=chat_id, user_open_id=sender_open_id):
            self.reply_text(chat_id, sender_open_id, "该会话未在白名单中，命令已拒绝。")
            return
        if self._is_help_request(raw_text):
            self.reply_text(chat_id, sender_open_id, self._build_help_text())
            return
        if self._is_menu_request(raw_text):
            self.reply_text(chat_id, sender_open_id, self._build_menu_text())
            return

        command_text = self._map_text_to_command(raw_text)
        if not command_text:
            return
        cmd = command_text.split()[0]
        if cmd not in self.command_whitelist:
            self.reply_text(chat_id, sender_open_id, f"命令 {cmd} 不在白名单中。\n\n{self._build_help_text()}")
            return
        if not self._handle_builtin_command(command_text, chat_id, sender_open_id):
            self._submit_moviepilot_command(command_text, chat_id, sender_open_id)

    def _handle_builtin_command(self, command_text: str, chat_id: str, open_id: str) -> bool:
        parts = command_text.split(maxsplit=1)
        cmd = parts[0].strip()
        arg = parts[1].strip() if len(parts) > 1 else ""
        cache_key = self._cache_key(chat_id, open_id)

        if cmd == "/version":
            self.reply_text(chat_id, open_id, f"Agent资源官 {getattr(self.plugin, 'plugin_version', '')}\n飞书入口：{'运行中' if self.is_running() else '未运行'}")
            return True

        if cmd == "/media_search":
            if not arg:
                self.reply_text(chat_id, open_id, "用法：MP搜索 片名")
                return True
            self.reply_text(chat_id, open_id, f"正在使用 MP 原生搜索：{arg}")
            self._run_thread("feishu-media-search", self._run_media_search, arg, chat_id, open_id)
            return True

        if cmd == "/media_download":
            if not arg or not arg.isdigit():
                self.reply_text(chat_id, open_id, "用法：下载资源 序号\n示例：下载资源 1")
                return True
            self.reply_text(chat_id, open_id, f"正在提交第 {arg} 条资源到下载器，请稍候。")
            self._run_thread("feishu-media-download", self._run_media_download, int(arg), chat_id, open_id)
            return True

        if cmd in {"/media_subscribe", "/media_subscribe_search"}:
            if not arg:
                self.reply_text(chat_id, open_id, "用法：订阅媒体 片名\n示例：订阅媒体 流浪地球2")
                return True
            immediate = cmd == "/media_subscribe_search"
            self.reply_text(chat_id, open_id, f"正在{'订阅并搜索' if immediate else '订阅'}：{arg}")
            self._run_thread("feishu-media-subscribe", self._run_media_subscribe, arg, immediate, chat_id, open_id)
            return True

        if cmd == "/pansou_search":
            if not arg:
                self.reply_text(chat_id, open_id, "用法：盘搜搜索 片名\n示例：盘搜搜索 流浪地球2")
                return True
            self.reply_text(chat_id, open_id, f"正在使用盘搜搜索：{arg}")
            self._run_thread("feishu-pansou-search", self._run_assistant_route, f"盘搜搜索 {arg}", cache_key, chat_id, open_id)
            return True

        if cmd in {"/smart_entry", "/quark_save"}:
            if not arg:
                self.reply_text(chat_id, open_id, "用法：处理 片名 或 处理 分享链接")
                return True
            self.reply_text(chat_id, open_id, f"正在智能处理：{arg}")
            self._run_thread("feishu-smart-entry", self._run_assistant_route, arg, cache_key, chat_id, open_id)
            return True

        if cmd == "/smart_pick":
            if not arg:
                self.reply_text(chat_id, open_id, "用法：选择 序号\n示例：选择 1\n也支持：详情、审查、n 下一页")
                return True
            self.reply_text(chat_id, open_id, f"正在继续执行：{arg}")
            self._run_thread("feishu-smart-pick", self._run_assistant_pick, arg, cache_key, chat_id, open_id)
            return True

        if cmd == "/p115_manual_transfer":
            if not arg:
                paths = self._get_p115_manual_transfer_paths()
                if not paths:
                    self.reply_text(chat_id, open_id, "未配置待整理目录。请先在 P115StrmHelper 中配置 pan_transfer_paths，或发送：刮削 /待整理/")
                    return True
                self.reply_text(chat_id, open_id, f"已开始刮削 {len(paths)} 个目录：\n" + "\n".join(f"- {path}" for path in paths))
                self._run_thread("feishu-p115-manual-transfer-batch", self._run_p115_manual_transfer_batch, paths, chat_id, open_id)
                return True
            self.reply_text(chat_id, open_id, f"已开始刮削：{arg}")
            self._run_thread("feishu-p115-manual-transfer", self._run_p115_manual_transfer, arg, chat_id, open_id)
            return True

        if cmd in {"/p115_inc_sync", "/p115_full_sync", "/p115_strm"}:
            final_command = "/p115_full_sync" if cmd == "/p115_strm" and not arg else command_text
            self._submit_p115_command(final_command, chat_id, open_id)
            return True

        return False

    @staticmethod
    def _run_thread(name: str, target: Any, *args: Any) -> None:
        threading.Thread(target=target, args=args, name=name, daemon=True).start()

    def _run_assistant_route(self, text: str, session: str, chat_id: str, open_id: str) -> None:
        result = self.plugin.feishu_assistant_route(text=text, session=session)
        self._reply_result(chat_id, open_id, result)

    def _run_assistant_pick(self, arg: str, session: str, chat_id: str, open_id: str) -> None:
        result = self.plugin.feishu_assistant_pick(arg=arg, session=session)
        self._reply_result(chat_id, open_id, result)

    def _reply_result(self, chat_id: str, open_id: str, result: Dict[str, Any]) -> None:
        message = str(result.get("message") or "处理完成").strip()
        self.reply_text(chat_id, open_id, message)
        qrcode = self._find_nested_value(result.get("data"), "qrcode")
        if isinstance(qrcode, str):
            self.reply_qrcode_data_url(chat_id, open_id, qrcode)

    @classmethod
    def _find_nested_value(cls, payload: Any, key: str) -> Any:
        if isinstance(payload, dict):
            if key in payload:
                return payload.get(key)
            for value in payload.values():
                found = cls._find_nested_value(value, key)
                if found:
                    return found
        elif isinstance(payload, list):
            for value in payload:
                found = cls._find_nested_value(value, key)
                if found:
                    return found
        return None

    def _run_media_search(self, keyword: str, chat_id: str, open_id: str) -> None:
        self.reply_text(chat_id, open_id, self._execute_media_search(keyword, self._cache_key(chat_id, open_id)))

    def _run_media_download(self, index: int, chat_id: str, open_id: str) -> None:
        self.reply_text(chat_id, open_id, self._execute_media_download(index, self._cache_key(chat_id, open_id)))

    def _run_media_subscribe(self, keyword: str, immediate: bool, chat_id: str, open_id: str) -> None:
        self.reply_text(chat_id, open_id, self._execute_media_subscribe(keyword, immediate))

    def _execute_media_search(self, keyword: str, cache_key: str) -> str:
        if not all([MetaInfo, MediaChain, SearchChain, StringUtils]):
            return "MP 原生搜索失败：当前环境缺少 MoviePilot 搜索依赖。"
        try:
            meta = MetaInfo(keyword)
            mediainfo = MediaChain().recognize_media(meta=meta)
            if not mediainfo:
                return f"未识别到媒体信息：{keyword}"
            season = meta.begin_season if meta.begin_season else mediainfo.season
            results = SearchChain().search_by_id(
                tmdbid=mediainfo.tmdb_id,
                doubanid=mediainfo.douban_id,
                mtype=mediainfo.type,
                season=season,
                cache_local=False,
            ) or []
            if not results:
                return f"已识别 {self._format_media_label(mediainfo, season)}，但暂未搜索到资源。"
            self._set_search_cache(cache_key, keyword, mediainfo, results)
            lines = [
                f"已识别：{self._format_media_label(mediainfo, season)}",
                f"共找到 {len(results)} 条资源，展示前 {min(len(results), 10)} 条：",
            ]
            for idx, context in enumerate(results[:10], start=1):
                torrent = context.torrent_info
                title = str(torrent.title or "").strip()
                size = StringUtils.str_filesize(torrent.size) if torrent.size else "未知"
                seeders = torrent.seeders if torrent.seeders is not None else "?"
                site = torrent.site_name or "未知站点"
                volume = torrent.volume_factor if getattr(torrent, "volume_factor", None) else "未知"
                lines.append(f"{idx}. [{site}] {title}")
                lines.append(f"   大小：{size} | 做种：{seeders} | 促销：{volume}")
            lines.append("下一步：回复“下载资源 序号”即可下载选中项。")
            lines.append("如需长期跟踪，回复“订阅媒体 片名”或“订阅并搜索 片名”。")
            return "\n".join(lines)
        except Exception as exc:
            logger.error(f"[AgentResourceOfficer][Feishu] 搜索资源失败：{keyword} {exc}\n{traceback.format_exc()}")
            return f"搜索资源失败：{keyword}\n错误：{exc}"

    def _execute_media_download(self, index: int, cache_key: str) -> str:
        if DownloadChain is None:
            return "下载资源失败：当前环境缺少 MoviePilot 下载依赖。"
        cache = self._get_search_cache(cache_key)
        if not cache:
            return "没有可用的搜索缓存，请先发送：MP搜索 片名"
        results = cache.get("results") or []
        if index < 1 or index > len(results):
            return f"序号超出范围，请输入 1 到 {len(results)} 之间的数字。"
        context = copy.deepcopy(results[index - 1])
        torrent = context.torrent_info
        try:
            download_id = DownloadChain().download_single(
                context=context,
                username="agentresourceofficer-feishu",
                source="AgentResourceOfficer",
            )
            if not download_id:
                return f"下载提交失败：{torrent.title}"
            return f"已提交下载：{torrent.title}\n站点：{torrent.site_name or '未知站点'}\n任务ID：{download_id}"
        except Exception as exc:
            logger.error(f"[AgentResourceOfficer][Feishu] 下载资源失败：{torrent.title} {exc}\n{traceback.format_exc()}")
            return f"下载资源失败：{torrent.title}\n错误：{exc}"

    def _execute_media_subscribe(self, keyword: str, immediate_search: bool) -> str:
        if not all([MetaInfo, SubscribeChain]):
            return "订阅失败：当前环境缺少 MoviePilot 订阅依赖。"
        meta = MetaInfo(keyword)
        try:
            sid, message = SubscribeChain().add(
                title=keyword,
                year=meta.year,
                mtype=meta.type,
                season=meta.begin_season,
                username="agentresourceofficer-feishu",
                exist_ok=True,
                message=False,
            )
            if not sid:
                return f"订阅失败：{keyword}\n原因：{message}"
            lines = [f"已创建订阅：{keyword}", f"订阅ID：{sid}", f"结果：{message}"]
            if immediate_search and Scheduler is not None:
                Scheduler().start(job_id="subscribe_search", **{"sid": sid, "state": None, "manual": True})
                lines.append("已触发一次订阅搜索。")
            return "\n".join(lines)
        except Exception as exc:
            logger.error(f"[AgentResourceOfficer][Feishu] 订阅媒体失败：{keyword} {exc}\n{traceback.format_exc()}")
            return f"订阅失败：{keyword}\n错误：{exc}"

    @staticmethod
    def _format_media_label(mediainfo: Any, season: Optional[int] = None) -> str:
        title = getattr(mediainfo, "title", "") or "未知媒体"
        year = getattr(mediainfo, "year", None)
        label = f"{title} ({year})" if year else title
        media_type = getattr(mediainfo, "type", None)
        media_type_name = getattr(media_type, "name", "")
        if media_type_name == "TV" and season:
            return f"{label} 第{season}季"
        return label

    def _set_search_cache(self, cache_key: str, keyword: str, mediainfo: Any, results: List[Any]) -> None:
        with self._search_cache_lock:
            self._search_cache[cache_key] = {
                "ts": time.time(),
                "keyword": keyword,
                "mediainfo": mediainfo,
                "results": results[:10],
            }

    def _get_search_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        with self._search_cache_lock:
            item = self._search_cache.get(cache_key)
            if not item:
                return None
            if time.time() - float(item.get("ts") or 0) > 1800:
                self._search_cache.pop(cache_key, None)
                return None
            return item

    def _run_p115_manual_transfer_batch(self, paths: List[str], chat_id: str, open_id: str) -> None:
        summaries = [self._execute_p115_manual_transfer(path) for path in paths]
        self.reply_text(chat_id, open_id, "\n\n".join(item for item in summaries if item))

    def _run_p115_manual_transfer(self, path: str, chat_id: str, open_id: str) -> None:
        self.reply_text(chat_id, open_id, self._execute_p115_manual_transfer(path))

    def _get_p115_manual_transfer_paths(self) -> List[str]:
        try:
            config = self.plugin.systemconfig.get("plugin.P115StrmHelper") or {}
            raw = str(config.get("pan_transfer_paths") or "").strip()
            return [line.strip() for line in raw.splitlines() if line.strip()]
        except Exception as exc:
            logger.warning(f"[AgentResourceOfficer][Feishu] 获取待整理目录失败：{exc}")
            return []

    def _execute_p115_manual_transfer(self, path: str) -> str:
        log_path = Path("/config/logs/plugins/P115StrmHelper.log")
        log_offset = self._safe_log_offset(log_path)
        try:
            service_module = importlib.import_module("app.plugins.p115strmhelper.service")
            servicer = getattr(service_module, "servicer", None)
            if not servicer or not getattr(servicer, "monitorlife", None):
                return "刮削失败：P115StrmHelper 未初始化或未启用。"
            result = servicer.monitorlife.once_transfer(path)
            summary = self._format_p115_manual_transfer_result(result)
            return summary or self._build_p115_manual_transfer_summary(log_path, log_offset, path) or f"刮削完成：{path}"
        except Exception as exc:
            logger.error(f"[AgentResourceOfficer][Feishu] 手动刮削失败：{path} {exc}\n{traceback.format_exc()}")
            return f"刮削失败：{path}\n错误：{exc}"

    def _format_p115_manual_transfer_result(self, result: Any) -> Optional[str]:
        if not isinstance(result, dict):
            return None
        path = result.get("path") or ""
        failed_items = result.get("failed_items") or []
        lines = [
            f"刮削完成：{path}",
            f"总计：{result.get('total', 0)} 个项目（文件 {result.get('files', 0)}，文件夹 {result.get('dirs', 0)}）",
            f"成功：{result.get('success', 0)} 个",
            f"失败：{result.get('failed', 0)} 个",
            f"跳过：{result.get('skipped', 0)} 个",
        ]
        if result.get("error"):
            lines.append(f"错误：{result.get('error')}")
        if failed_items:
            lines.append("失败示例：")
            lines.extend(f"- {item}" for item in failed_items[:3])
            if len(failed_items) > 3:
                lines.append(f"- 还有 {len(failed_items) - 3} 项未展示")
        lines.extend(self._p115_strm_followup_lines(path))
        return "\n".join(lines)

    def _p115_strm_followup_lines(self, path: str) -> List[str]:
        hint = self._get_p115_strm_hint_path() or path
        return [
            "如需增量生成 STRM，请再发送：生成STRM",
            "如需按全部媒体库全量生成，请再发送：全量STRM",
            f"如需指定路径全量生成，请再发送：指定路径STRM {hint}",
        ]

    def _get_p115_strm_hint_path(self) -> Optional[str]:
        try:
            config = self.plugin.systemconfig.get("plugin.P115StrmHelper") or {}
            paths = str(config.get("full_sync_strm_paths") or "").strip()
            first_line = next((line.strip() for line in paths.splitlines() if line.strip()), "")
            if not first_line:
                return None
            parts = first_line.split("#")
            return parts[1].strip() if len(parts) >= 2 and parts[1].strip() else None
        except Exception:
            return None

    @staticmethod
    def _safe_log_offset(log_path: Path) -> int:
        try:
            return log_path.stat().st_size if log_path.exists() else 0
        except Exception:
            return 0

    def _build_p115_manual_transfer_summary(self, log_path: Path, start_offset: int, path: str) -> Optional[str]:
        try:
            if not log_path.exists():
                return None
            with log_path.open("r", encoding="utf-8", errors="ignore") as f:
                f.seek(start_offset)
                chunk = f.read()
            if not chunk:
                return None
            path_re = re.escape(path)
            pattern = re.compile(
                rf"手动网盘整理完成 - 路径: {path_re}\n"
                rf"\s*总计: (?P<total>\d+) 个项目 \(文件: (?P<files>\d+), 文件夹: (?P<dirs>\d+)\)\n"
                rf"\s*成功: (?P<success>\d+) 个\n"
                rf"\s*失败: (?P<failed>\d+) 个\n"
                rf"\s*跳过: (?P<skipped>\d+) 个",
                re.S,
            )
            match = pattern.search(chunk)
            if not match:
                return None
            summary = (
                f"刮削完成：{path}\n"
                f"总计：{match.group('total')} 个项目（文件 {match.group('files')}，文件夹 {match.group('dirs')}）\n"
                f"成功：{match.group('success')} 个\n"
                f"失败：{match.group('failed')} 个\n"
                f"跳过：{match.group('skipped')} 个"
            )
            return summary + "\n" + "\n".join(self._p115_strm_followup_lines(path))
        except Exception:
            return None

    def _submit_p115_command(self, command_text: str, chat_id: str, open_id: str) -> None:
        if PluginManager is not None:
            try:
                if not PluginManager().running_plugins.get("P115StrmHelper"):
                    self.reply_text(chat_id, open_id, "P115StrmHelper 未加载或未启用，无法执行 STRM 命令。")
                    return
            except Exception:
                pass
        self._submit_moviepilot_command(command_text, chat_id, open_id)

    def _submit_moviepilot_command(self, command_text: str, chat_id: str, open_id: str) -> None:
        if eventmanager is None or EventType is None:
            self.reply_text(chat_id, open_id, "当前环境缺少 MoviePilot 事件总线，无法转发该命令。")
            return
        eventmanager.send_event(
            EventType.CommandExcute,
            {"cmd": command_text, "source": None, "user": open_id or chat_id or "feishu"},
        )
        self.reply_text(chat_id, open_id, f"已接收命令：{command_text}\n任务已提交给 MoviePilot。")

    def _map_text_to_command(self, text: str) -> Optional[str]:
        text = self._sanitize_text(text)
        if not text:
            return None
        if text.startswith("/"):
            return text
        normalized = text.strip().lower()
        if normalized in {"n", "next", "下一页", "下页"} or normalized.startswith("n "):
            return f"/smart_pick {text}".strip()
        shortcut_match = re.fullmatch(r"(\d+)(?:\s+(.+))?", text)
        if shortcut_match:
            rest = str(shortcut_match.group(2) or "").strip()
            if not rest or "=" in rest or rest.startswith("/"):
                return f"/smart_pick {text}".strip()
        first_url = self.plugin._extract_first_url(text)
        if first_url and (self.plugin._is_115_url(first_url) or self.plugin._is_quark_url(first_url)):
            return f"/smart_entry {text}".strip()

        alias_map = self.parse_alias_text(self.command_aliases)
        parts = text.split(maxsplit=1)
        alias = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        target = alias_map.get(alias)
        if not target:
            for alias_key in sorted(alias_map.keys(), key=len, reverse=True):
                if not text.startswith(alias_key):
                    continue
                remain = text[len(alias_key):].strip()
                target = alias_map.get(alias_key)
                if target:
                    if target == "/smart_pick" and alias_key in {"详情", "审查"}:
                        return f"{target} {alias_key} {remain}".strip()
                    return f"{target} {remain}".strip()
            return None
        if target == "/smart_pick" and alias in {"详情", "审查"}:
            return f"{target} {alias} {rest}".strip()
        return f"{target} {rest}".strip()

    def _is_duplicate_event(self, event_id: str) -> bool:
        now = time.time()
        with self._event_lock:
            expired = [key for key, ts in self._event_cache.items() if now - ts > 600]
            for key in expired:
                self._event_cache.pop(key, None)
            if event_id in self._event_cache:
                return True
            self._event_cache[event_id] = now
        return self._is_duplicate_event_cross_instance(event_id, now)

    @staticmethod
    def _is_duplicate_event_cross_instance(event_id: str, now: float) -> bool:
        try:
            _EVENT_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with _EVENT_CACHE_FILE.open("a+", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.seek(0)
                raw = f.read().strip()
                cache = json.loads(raw) if raw else {}
                cache = {key: ts for key, ts in cache.items() if isinstance(ts, (int, float)) and now - float(ts) <= 600}
                if event_id in cache:
                    f.seek(0)
                    f.truncate()
                    json.dump(cache, f, ensure_ascii=False)
                    f.flush()
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    return True
                cache[event_id] = now
                f.seek(0)
                f.truncate()
                json.dump(cache, f, ensure_ascii=False)
                f.flush()
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception as exc:
            logger.warning(f"[AgentResourceOfficer][Feishu] 跨实例事件去重失败：{exc}")
        return False

    def _is_allowed(self, chat_id: str, user_open_id: str) -> bool:
        return bool(
            self.allow_all
            or (chat_id and chat_id in self.allowed_chat_ids)
            or (user_open_id and user_open_id in self.allowed_user_ids)
        )

    @staticmethod
    def _extract_text(content: Any) -> str:
        if isinstance(content, dict):
            return str(content.get("text") or "").strip()
        if isinstance(content, str):
            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                return content.strip()
            return str(payload.get("text") or "").strip()
        return ""

    @staticmethod
    def _sanitize_text(text: str) -> str:
        text = re.sub(r"<at[^>]*>.*?</at>", " ", text or "", flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _is_help_request(text: str) -> bool:
        return FeishuChannel._sanitize_text(text) in {"帮助", "/help", "help"}

    @staticmethod
    def _is_menu_request(text: str) -> bool:
        return FeishuChannel._sanitize_text(text) in {"菜单", "/menu", "menu", "面板", "控制面板"}

    def _build_help_text(self) -> str:
        aliases = self.parse_alias_text(self.command_aliases)
        alias_text = "\n".join(f"{key} -> {value}" for key, value in aliases.items()) or "未配置别名"
        return (
            "可用命令：\n"
            f"{', '.join(self.command_whitelist)}\n\n"
            "别名：\n"
            f"{alias_text}\n\n"
            "快捷入口：发送“菜单”可查看可复制的快捷命令。"
        )

    @staticmethod
    def _build_menu_text() -> str:
        return (
            "快捷菜单\n"
            "1. MP搜索 片名\n"
            "2. 影巢搜索 片名\n"
            "3. 盘搜搜索 片名\n"
            "4. 直接发 115 / 夸克链接\n"
            "5. 选择 序号\n"
            "6. 刮削\n"
            "7. 生成STRM\n"
            "8. 全量STRM\n"
            "9. 订阅媒体 片名\n"
            "10. 订阅并搜索 片名\n"
            "11. 115登录 / 115状态 / 115任务"
        )

    @staticmethod
    def _cache_key(chat_id: str, open_id: str) -> str:
        return f"feishu::{chat_id or ''}::{open_id or ''}"

    def reply_text(self, chat_id: str, open_id: str, text: str) -> None:
        if not self.reply_enabled or not self.app_id or not self.app_secret:
            return
        receive_id = chat_id if self.reply_receive_id_type == "chat_id" else open_id
        if not receive_id:
            return
        access_token = self._get_tenant_access_token()
        if not access_token or RequestUtils is None:
            return
        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={self.reply_receive_id_type}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        payload = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        }
        response = RequestUtils(headers=headers).post(url=url, json=payload)
        if response is None:
            logger.error("[AgentResourceOfficer][Feishu] 发送文本失败：无响应")
            return
        try:
            data = response.json()
        except Exception:
            data = {}
        if response.status_code != 200 or data.get("code") not in (0, None):
            logger.error(f"[AgentResourceOfficer][Feishu] 发送文本失败: status={response.status_code} body={data}")

    def reply_qrcode_data_url(self, chat_id: str, open_id: str, data_url: str) -> None:
        text = str(data_url or "").strip()
        if not text.startswith("data:image/") or ";base64," not in text:
            return
        _, _, payload = text.partition(";base64,")
        try:
            image_bytes = b64decode(payload)
        except Exception as exc:
            logger.error(f"[AgentResourceOfficer][Feishu] 解码二维码失败：{exc}")
            return
        image_key = self._upload_image(image_bytes=image_bytes, file_name="p115-qrcode.png")
        if image_key:
            self._reply_image(chat_id, open_id, image_key)

    def _upload_image(self, image_bytes: bytes, file_name: str) -> Optional[str]:
        if not image_bytes or RequestUtils is None:
            return None
        access_token = self._get_tenant_access_token()
        if not access_token:
            return None
        response = RequestUtils(headers={"Authorization": f"Bearer {access_token}"}).post(
            url="https://open.feishu.cn/open-apis/im/v1/images",
            data={"image_type": "message"},
            files={"image": (file_name, image_bytes, "image/png")},
        )
        if response is None:
            logger.error("[AgentResourceOfficer][Feishu] 上传图片失败：无响应")
            return None
        try:
            data = response.json()
        except Exception:
            data = {}
        if response.status_code != 200 or data.get("code") not in (0, None):
            logger.error(f"[AgentResourceOfficer][Feishu] 上传图片失败: status={response.status_code} body={data}")
            return None
        return str(((data.get("data") or {}).get("image_key")) or "").strip() or None

    def _reply_image(self, chat_id: str, open_id: str, image_key: str) -> None:
        if not image_key or RequestUtils is None:
            return
        receive_id = chat_id if self.reply_receive_id_type == "chat_id" else open_id
        if not receive_id:
            return
        access_token = self._get_tenant_access_token()
        if not access_token:
            return
        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={self.reply_receive_id_type}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        payload = {
            "receive_id": receive_id,
            "msg_type": "image",
            "content": json.dumps({"image_key": image_key}, ensure_ascii=False),
        }
        response = RequestUtils(headers=headers).post(url=url, json=payload)
        if response is None:
            logger.error("[AgentResourceOfficer][Feishu] 发送图片失败：无响应")
            return
        try:
            data = response.json()
        except Exception:
            data = {}
        if response.status_code != 200 or data.get("code") not in (0, None):
            logger.error(f"[AgentResourceOfficer][Feishu] 发送图片失败: status={response.status_code} body={data}")

    def _get_tenant_access_token(self) -> Optional[str]:
        if RequestUtils is None:
            return None
        now = time.time()
        with self._token_lock:
            token = self._token_cache.get("token")
            expires_at = float(self._token_cache.get("expires_at") or 0)
            if token and now < expires_at - 60:
                return token
            response = RequestUtils(content_type="application/json").post(
                url="https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            if response is None:
                logger.error("[AgentResourceOfficer][Feishu] 获取 tenant_access_token 失败：无响应")
                return None
            try:
                data = response.json()
            except Exception as exc:
                logger.error(f"[AgentResourceOfficer][Feishu] token 响应解析失败：{exc}")
                return None
            token = data.get("tenant_access_token")
            expire = int(data.get("expire") or 0)
            if not token:
                logger.error(f"[AgentResourceOfficer][Feishu] token 缺失：{data}")
                return None
            self._token_cache = {"token": token, "expires_at": now + expire}
            return token
