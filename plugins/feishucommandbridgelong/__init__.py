import asyncio
import fcntl
import importlib
import json
import re
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.event import eventmanager
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType
from app.utils.http import RequestUtils

for _plugin_dir in (
    str(Path(__file__).resolve().parent),
    "/config/plugins/FeishuCommandBridge",
):
    if Path(_plugin_dir).exists() and _plugin_dir not in sys.path:
        sys.path.insert(0, _plugin_dir)

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


class _LongConnectionRuntime:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._fingerprint = ""
        self._plugin: Optional["FeishuCommandBridge"] = None

    def start(self, plugin: "FeishuCommandBridge") -> None:
        global lark
        if lark is None:
            try:
                import lark_oapi as runtime_lark
                lark = runtime_lark
            except Exception as exc:
                logger.error(
                    f"[FeishuCommandBridge] 缺少依赖 lark-oapi，请先安装插件依赖：{exc}"
                )
                return

        if not plugin._enabled or not plugin._app_id or not plugin._app_secret:
            return

        fingerprint = plugin._connection_fingerprint()
        with self._lock:
            self._plugin = plugin
            if self._thread and self._thread.is_alive():
                if fingerprint != self._fingerprint:
                    logger.warning(
                        "[FeishuCommandBridge] 长连接已在运行，App ID / App Secret / Token 变更需要重启 MoviePilot 后生效"
                    )
                return

            self._fingerprint = fingerprint
            self._thread = threading.Thread(
                target=self._run,
                name="feishu-command-bridge-long",
                daemon=True,
            )
            self._thread.start()

    def _run(self) -> None:
        plugin = self._plugin
        if plugin is None:
            return

        def _on_message(data) -> None:
            current_plugin = self._plugin
            if current_plugin is None:
                return
            current_plugin._handle_long_connection_event(data)

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
                plugin._app_id,
                plugin._app_secret,
                log_level=lark.LogLevel.DEBUG if plugin._debug else lark.LogLevel.INFO,
                event_handler=event_handler,
            )
            logger.info("[FeishuCommandBridge] 正在启动飞书长连接")
            ws_client.start()
        except Exception as exc:
            logger.error(f"[FeishuCommandBridge] 长连接退出：{exc}\n{traceback.format_exc()}")

    def is_running(self) -> bool:
        with self._lock:
            return bool(self._thread and self._thread.is_alive())


_runtime = _LongConnectionRuntime()
_EVENT_CACHE_FILE = Path("/config/plugins/FeishuCommandBridge/.event_cache.json")


class FeishuCommandBridge(_PluginBase):
    plugin_name = "飞书命令桥接"
    plugin_desc = "使用飞书长连接接收消息事件并转发为 MoviePilot 命令执行。"
    plugin_icon = "https://raw.githubusercontent.com/jxxghp/MoviePilot-Plugins/main/icons/world.png"
    plugin_version = "0.2.2"
    plugin_author = "liuyuexi1987"
    author_url = "https://github.com/liuyuexi1987"
    plugin_config_prefix = "feishucommandbridge_"
    plugin_order = 29
    auth_level = 1

    _enabled = False
    _allow_all = False
    _verification_token = ""
    _app_id = ""
    _app_secret = ""
    _allowed_chat_ids: List[str] = []
    _allowed_user_ids: List[str] = []
    _reply_enabled = True
    _reply_receive_id_type = "chat_id"
    _command_whitelist: List[str] = []
    _command_aliases = ""
    _debug = False

    _token_cache: Dict[str, Any] = {}
    _token_lock = threading.Lock()
    _event_cache: Dict[str, float] = {}
    _event_lock = threading.Lock()

    @staticmethod
    def _clean_input(value: Any) -> str:
        if value is None:
            return ""
        text = str(value)
        for ch in ("\ufeff", "\u200b", "\u200c", "\u200d", "\u2060", "\ufffc"):
            text = text.replace(ch, "")
        return text.strip()

    def init_plugin(self, config: dict = None):
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._allow_all = bool(config.get("allow_all"))
        self._verification_token = self._clean_input(config.get("verification_token"))
        self._app_id = self._clean_input(config.get("app_id"))
        self._app_secret = self._clean_input(config.get("app_secret"))
        self._allowed_chat_ids = self._split_lines(config.get("allowed_chat_ids"))
        self._allowed_user_ids = self._split_lines(config.get("allowed_user_ids"))
        self._reply_enabled = bool(config.get("reply_enabled", True))
        self._reply_receive_id_type = str(
            config.get("reply_receive_id_type") or "chat_id"
        ).strip()
        self._command_whitelist = self._split_commands(config.get("command_whitelist"))
        self._command_aliases = str(config.get("command_aliases") or "").strip()
        self._debug = bool(config.get("debug"))

        if not self._command_whitelist:
            self._command_whitelist = ["/p115_manual_transfer", "/p115_inc_sync", "/p115_full_sync", "/p115_strm", "/version"]

        _runtime.start(self)

    def get_state(self) -> bool:
        return self._enabled and bool(self._app_id) and bool(self._app_secret)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/health",
                "endpoint": self.health,
                "methods": ["GET"],
                "summary": "健康检查",
                "description": "返回飞书长连接插件当前状态与基础配置",
                "auth": "bear",
            },
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
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
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "allow_all",
                                            "label": "允许所有飞书会话",
                                        },
                                    },
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
                                        "component": "VTextField",
                                        "props": {
                                            "model": "verification_token",
                                            "label": "Verification Token",
                                            "placeholder": "飞书事件订阅 Token",
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
                                        "component": "VTextField",
                                        "props": {
                                            "model": "app_id",
                                            "label": "App ID",
                                            "placeholder": "cli_xxxxxxxxx",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "app_secret",
                                            "label": "App Secret",
                                            "placeholder": "飞书应用凭证",
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
                                            "model": "allowed_chat_ids",
                                            "label": "允许的群聊 Chat ID",
                                            "rows": 4,
                                            "placeholder": "一个一行；留空时仅允许 allow_all 或允许的用户",
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
                                            "model": "allowed_user_ids",
                                            "label": "允许的用户 Open ID",
                                            "rows": 4,
                                            "placeholder": "一个一行",
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
                                        "component": "VTextField",
                                        "props": {
                                            "model": "command_whitelist",
                                            "label": "命令白名单",
                                            "placeholder": "/p115_manual_transfer,/p115_inc_sync,/p115_full_sync,/p115_strm,/version",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "reply_enabled",
                                            "label": "发送即时回执",
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
                                            "model": "command_aliases",
                                            "label": "命令别名",
                                            "rows": 6,
                                            "placeholder": "刮削=/p115_manual_transfer\n生成STRM=/p115_inc_sync\n全量STRM=/p115_full_sync\n指定路径STRM=/p115_strm\n版本=/version",
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
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "debug",
                                            "label": "输出调试日志",
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ], {
            "enabled": self._enabled,
            "allow_all": self._allow_all,
            "verification_token": self._verification_token,
            "app_id": self._app_id,
            "app_secret": self._app_secret,
            "allowed_chat_ids": "\n".join(self._allowed_chat_ids),
            "allowed_user_ids": "\n".join(self._allowed_user_ids),
            "reply_enabled": self._reply_enabled,
            "reply_receive_id_type": self._reply_receive_id_type,
            "command_whitelist": ",".join(self._command_whitelist) if self._command_whitelist else "/p115_manual_transfer,/p115_inc_sync,/p115_full_sync,/p115_strm,/version",
            "command_aliases": self._command_aliases or "刮削=/p115_manual_transfer\n生成STRM=/p115_inc_sync\n全量STRM=/p115_full_sync\n指定路径STRM=/p115_strm\n版本=/version",
            "debug": self._debug,
        }

    def get_page(self) -> Optional[List[dict]]:
        aliases = self._parse_aliases()
        alias_lines = [
            {
                "component": "div",
                "props": {"class": "text-body-2 py-1"},
                "text": f"{key} -> {value}",
            }
            for key, value in aliases.items()
        ] or [
            {
                "component": "div",
                "props": {"class": "text-body-2 py-1"},
                "text": "未配置别名",
            }
        ]

        command_lines = [
            {
                "component": "div",
                "props": {"class": "text-body-2 py-1"},
                "text": cmd,
            }
            for cmd in (self._command_whitelist or [])
        ] or [
            {
                "component": "div",
                "props": {"class": "text-body-2 py-1"},
                "text": "未配置命令白名单",
            }
        ]

        return [
            {
                "component": "VContainer",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VCard",
                                        "props": {"border": True, "flat": True},
                                        "content": [
                                            {
                                                "component": "VCardTitle",
                                                "text": "运行状态",
                                            },
                                            {
                                                "component": "VCardText",
                                                "content": [
                                                    {
                                                        "component": "div",
                                                        "props": {"class": "text-body-2 py-1"},
                                                        "text": f"启用状态：{'是' if self._enabled else '否'}",
                                                    },
                                                    {
                                                        "component": "div",
                                                        "props": {"class": "text-body-2 py-1"},
                                                        "text": f"长连接运行中：{'是' if _runtime.is_running() else '否'}",
                                                    },
                                                    {
                                                        "component": "div",
                                                        "props": {"class": "text-body-2 py-1"},
                                                        "text": f"允许所有会话：{'是' if self._allow_all else '否'}",
                                                    },
                                                    {
                                                        "component": "div",
                                                        "props": {"class": "text-body-2 py-1"},
                                                        "text": f"App ID：{self._app_id or '未填写'}",
                                                    },
                                                    {
                                                        "component": "div",
                                                        "props": {"class": "text-body-2 py-1"},
                                                        "text": f"Token：{self._mask_secret(self._verification_token) or '未填写'}",
                                                    },
                                                ],
                                            },
                                        ],
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VCard",
                                        "props": {"border": True, "flat": True},
                                        "content": [
                                            {
                                                "component": "VCardTitle",
                                                "text": "可用命令",
                                            },
                                            {
                                                "component": "VCardText",
                                                "content": command_lines,
                                            },
                                        ],
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
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VCard",
                                        "props": {"border": True, "flat": True},
                                        "content": [
                                            {
                                                "component": "VCardTitle",
                                                "text": "命令别名",
                                            },
                                            {
                                                "component": "VCardText",
                                                "content": alias_lines,
                                            },
                                        ],
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VCard",
                                        "props": {"border": True, "flat": True},
                                        "content": [
                                            {
                                                "component": "VCardTitle",
                                                "text": "使用示例",
                                            },
                                            {
                                                "component": "VCardText",
                                                "content": [
                                                    {
                                                        "component": "div",
                                                        "props": {"class": "text-body-2 py-1"},
                                                        "text": "版本",
                                                    },
                                                    {
                                                        "component": "div",
                                                        "props": {"class": "text-body-2 py-1"},
                                                        "text": "刮削 /待整理/",
                                                    },
                                                    {
                                                        "component": "div",
                                                        "props": {"class": "text-body-2 py-1"},
                                                        "text": "/p115_strm /待整理/",
                                                    },
                                                    {
                                                        "component": "div",
                                                        "props": {"class": "text-body-2 py-1"},
                                                        "text": "帮助",
                                                    },
                                                ],
                                            },
                                        ],
                                    }
                                ],
                            },
                        ],
                    },
                ],
            }
        ]

    def health(self):
        return {
            "enabled": self._enabled,
            "running": _runtime.is_running(),
            "allow_all": self._allow_all,
            "reply_enabled": self._reply_enabled,
            "allowed_chat_count": len(self._allowed_chat_ids),
            "allowed_user_count": len(self._allowed_user_ids),
            "command_whitelist": self._command_whitelist,
            "sdk_available": lark is not None,
        }

    def stop_service(self):
        logger.info("[FeishuCommandBridge] 当前版本未实现长连接主动停止；如需彻底停掉，请重启 MoviePilot")

    def _connection_fingerprint(self) -> str:
        return "|".join([
            self._app_id,
            self._app_secret,
            self._verification_token,
        ])

    def _handle_long_connection_event(self, data) -> None:
        if not self._enabled:
            return

        event_context = data
        event = getattr(event_context, "event", None)
        header = getattr(event_context, "header", None)
        message = getattr(event, "message", None)
        sender = getattr(event, "sender", None)
        sender_id = getattr(sender, "sender_id", None)

        event_id = str(getattr(header, "event_id", "") or "").strip()
        if event_id and self._is_duplicate_event(event_id):
            return

        if self._debug:
            logger.info(
                f"[FeishuCommandBridge] event_id={event_id} "
                f"event_type={getattr(header, 'event_type', '')} "
                f"chat_id={getattr(message, 'chat_id', '')}"
            )

        if not message or str(getattr(message, "message_type", "")).strip() != "text":
            return

        raw_text = self._extract_text(getattr(message, "content", None))
        if not raw_text:
            return

        sender_open_id = str(getattr(sender_id, "open_id", "") or "").strip()
        chat_id = str(getattr(message, "chat_id", "") or "").strip()

        if not self._is_allowed(chat_id=chat_id, user_open_id=sender_open_id):
            self._reply_if_needed(
                receive_chat_id=chat_id,
                receive_open_id=sender_open_id,
                text="该会话未在白名单中，命令已拒绝。",
            )
            return

        if self._is_help_request(raw_text):
            self._reply_if_needed(
                receive_chat_id=chat_id,
                receive_open_id=sender_open_id,
                text=self._build_help_text(),
            )
            return

        if self._is_menu_request(raw_text):
            self._reply_if_needed(
                receive_chat_id=chat_id,
                receive_open_id=sender_open_id,
                text=self._build_menu_text(),
            )
            return

        command_text = self._map_text_to_command(raw_text)
        if not command_text:
            return

        cmd = command_text.split()[0]
        if cmd not in self._command_whitelist:
            self._reply_if_needed(
                receive_chat_id=chat_id,
                receive_open_id=sender_open_id,
                text=f"命令 {cmd} 不在白名单中。\n\n{self._build_help_text()}",
            )
            return

        if self._handle_builtin_command(
            command_text=command_text,
            receive_chat_id=chat_id,
            receive_open_id=sender_open_id,
        ):
            return

        logger.info(f"[FeishuCommandBridge] 转发命令：{command_text}")
        eventmanager.send_event(
            EventType.CommandExcute,
            {
                "cmd": command_text,
                "source": None,
                "user": sender_open_id or chat_id or "feishu",
            },
        )
        self._reply_if_needed(
            receive_chat_id=chat_id,
            receive_open_id=sender_open_id,
            text=f"已接收命令：{command_text}\n任务已提交给 MoviePilot。",
        )

    def _handle_builtin_command(
        self,
        command_text: str,
        receive_chat_id: str,
        receive_open_id: str,
    ) -> bool:
        parts = command_text.split(maxsplit=1)
        cmd = parts[0].strip()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "/p115_strm" and not arg:
            command_text = "/p115_full_sync"
            logger.info(f"[FeishuCommandBridge] 转发命令：{command_text}")
            eventmanager.send_event(
                EventType.CommandExcute,
                {
                    "cmd": command_text,
                    "source": None,
                    "user": receive_open_id or receive_chat_id or "feishu",
                },
            )
            self._reply_if_needed(
                receive_chat_id=receive_chat_id,
                receive_open_id=receive_open_id,
                text=f"已接收命令：{command_text}\n任务已提交给 MoviePilot。",
            )
            return True

        if cmd != "/p115_manual_transfer":
            return False

        if not arg:
            paths = self._get_p115_manual_transfer_paths()
            if not paths:
                self._reply_if_needed(
                    receive_chat_id=receive_chat_id,
                    receive_open_id=receive_open_id,
                    text="未配置待整理目录。\n请先在 P115StrmHelper 中配置 pan_transfer_paths，或直接发送：刮削 /待整理/",
                )
                return True
            self._reply_if_needed(
                receive_chat_id=receive_chat_id,
                receive_open_id=receive_open_id,
                text=(
                    f"已开始刮削 {len(paths)} 个目录：\n"
                    + "\n".join(f"- {path}" for path in paths)
                    + "\n正在调用 115 整理流程，请稍候。"
                ),
            )
            threading.Thread(
                target=self._run_p115_manual_transfer_batch,
                args=(paths, receive_chat_id, receive_open_id),
                name="feishu-p115-manual-transfer-batch",
                daemon=True,
            ).start()
            return True

        self._reply_if_needed(
            receive_chat_id=receive_chat_id,
            receive_open_id=receive_open_id,
            text=f"已开始刮削：{arg}\n正在调用 115 整理流程，请稍候。",
        )

        threading.Thread(
            target=self._run_p115_manual_transfer,
            args=(arg, receive_chat_id, receive_open_id),
            name="feishu-p115-manual-transfer",
            daemon=True,
        ).start()
        return True

    def _get_p115_manual_transfer_paths(self) -> List[str]:
        try:
            config = self.systemconfig.get("plugin.P115StrmHelper") or {}
            raw = str(config.get("pan_transfer_paths") or "").strip()
            if not raw:
                return []
            return [line.strip() for line in raw.splitlines() if line.strip()]
        except Exception as exc:
            logger.warning(f"[FeishuCommandBridge] 获取待整理目录失败：{exc}")
            return []

    def _run_p115_manual_transfer_batch(
        self,
        paths: List[str],
        receive_chat_id: str,
        receive_open_id: str,
    ) -> None:
        summaries: List[str] = []
        for path in paths:
            summaries.append(self._execute_p115_manual_transfer(path))
        self._reply_if_needed(
            receive_chat_id=receive_chat_id,
            receive_open_id=receive_open_id,
            text="\n\n".join(summary for summary in summaries if summary),
        )

    def _run_p115_manual_transfer(
        self,
        path: str,
        receive_chat_id: str,
        receive_open_id: str,
    ) -> None:
        summary_text = self._execute_p115_manual_transfer(path)
        self._reply_if_needed(
            receive_chat_id=receive_chat_id,
            receive_open_id=receive_open_id,
            text=summary_text,
        )

    def _execute_p115_manual_transfer(self, path: str) -> str:
        log_path = Path("/config/logs/plugins/P115StrmHelper.log")
        log_offset = self._safe_log_offset(log_path)
        try:
            service_module = importlib.import_module(
                "app.plugins.p115strmhelper.service"
            )
            servicer = getattr(service_module, "servicer", None)
            if not servicer or not getattr(servicer, "monitorlife", None):
                return "刮削失败：P115StrmHelper 未初始化或未启用。"

            logger.info(f"[FeishuCommandBridge] 开始执行手动刮削：{path}")
            result = servicer.monitorlife.once_transfer(path)
            logger.info(f"[FeishuCommandBridge] 手动刮削完成：{path}")
            summary_text = self._format_p115_manual_transfer_result(result)
            if not summary_text:
                summary_text = self._build_p115_manual_transfer_summary(log_path, log_offset, path)
            return summary_text or f"刮削完成：{path}"
        except Exception as exc:
            logger.error(
                f"[FeishuCommandBridge] 手动刮削失败：{path} {exc}\n{traceback.format_exc()}"
            )
            return f"刮削失败：{path}\n错误：{exc}"

    def _format_p115_manual_transfer_result(self, result: Any) -> Optional[str]:
        if not isinstance(result, dict):
            return None

        path = result.get("path") or ""
        total = result.get("total", 0)
        files = result.get("files", 0)
        dirs = result.get("dirs", 0)
        success = result.get("success", 0)
        failed = result.get("failed", 0)
        skipped = result.get("skipped", 0)
        error = result.get("error")
        failed_items = result.get("failed_items") or []

        lines = [
            f"刮削完成：{path}",
            f"总计：{total} 个项目（文件 {files}，文件夹 {dirs}）",
            f"成功：{success} 个",
            f"失败：{failed} 个",
            f"跳过：{skipped} 个",
        ]
        if error:
            lines.append(f"错误：{error}")
        if failed_items:
            lines.append("失败示例：")
            lines.extend(f"- {item}" for item in failed_items[:3])
            remain = len(failed_items) - 3
            if remain > 0:
                lines.append(f"- 还有 {remain} 项未展示")
        strm_hint_path = self._get_p115_strm_hint_path() or path
        lines.append("如需增量生成 STRM，请再发送：生成STRM")
        lines.append("如需按全部媒体库全量生成，请再发送：全量STRM")
        lines.append(f"如需指定路径全量生成，请再发送：指定路径STRM {strm_hint_path}")
        return "\n".join(lines)

    def _get_p115_strm_hint_path(self) -> Optional[str]:
        try:
            config = self.systemconfig.get("plugin.P115StrmHelper") or {}
            paths = str(config.get("full_sync_strm_paths") or "").strip()
            if not paths:
                return None
            first_line = next(
                (line.strip() for line in paths.splitlines() if line.strip()),
                "",
            )
            if not first_line:
                return None
            parts = first_line.split("#")
            if len(parts) >= 2 and parts[1].strip():
                return parts[1].strip()
        except Exception as exc:
            logger.warning(f"[FeishuCommandBridge] 获取 P115 STRM 提示路径失败：{exc}")
        return None

    def _safe_log_offset(self, log_path: Path) -> int:
        try:
            if log_path.exists():
                return log_path.stat().st_size
        except Exception:
            pass
        return 0

    def _build_p115_manual_transfer_summary(
        self,
        log_path: Path,
        start_offset: int,
        path: str,
    ) -> Optional[str]:
        try:
            if not log_path.exists():
                return None

            with log_path.open("r", encoding="utf-8", errors="ignore") as f:
                f.seek(start_offset)
                chunk = f.read()

            if not chunk:
                return None

            path_re = re.escape(path)
            summary_pattern = re.compile(
                rf"手动网盘整理完成 - 路径: {path_re}\n"
                rf"\s*总计: (?P<total>\d+) 个项目 \(文件: (?P<files>\d+), 文件夹: (?P<dirs>\d+)\)\n"
                rf"\s*成功: (?P<success>\d+) 个\n"
                rf"\s*失败: (?P<failed>\d+) 个\n"
                rf"\s*跳过: (?P<skipped>\d+) 个",
                re.S,
            )
            match = summary_pattern.search(chunk)
            if not match:
                return None

            summary = (
                f"刮削完成：{path}\n"
                f"总计：{match.group('total')} 个项目"
                f"（文件 {match.group('files')}，文件夹 {match.group('dirs')}）\n"
                f"成功：{match.group('success')} 个\n"
                f"失败：{match.group('failed')} 个\n"
                f"跳过：{match.group('skipped')} 个"
            )

            failed_pattern = re.compile(
                r"失败项目详情 \((?P<count>\d+) 个\):\n(?P<items>(?:\s*-\s.*(?:\n|$))*)",
                re.S,
            )
            failed_match = failed_pattern.search(chunk, match.end())
            if failed_match:
                items = [
                    item.strip()[2:].strip()
                    for item in failed_match.group("items").splitlines()
                    if item.strip().startswith("- ")
                ]
                if items:
                    preview = "\n".join(f"- {item}" for item in items[:3])
                    remain = len(items) - 3
                    summary += f"\n失败示例：\n{preview}"
                    if remain > 0:
                        summary += f"\n- 还有 {remain} 项未展示"

            strm_hint_path = self._get_p115_strm_hint_path() or path
            summary += "\n如需增量生成 STRM，请再发送：生成STRM"
            summary += "\n如需按全部媒体库全量生成，请再发送：全量STRM"
            summary += f"\n如需指定路径全量生成，请再发送：指定路径STRM {strm_hint_path}"
            return summary
        except Exception as exc:
            logger.warning(f"[FeishuCommandBridge] 解析 P115 刮削结果失败：{exc}")
            return None

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

    def _is_duplicate_event_cross_instance(self, event_id: str, now: float) -> bool:
        try:
            _EVENT_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with _EVENT_CACHE_FILE.open("a+", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.seek(0)
                raw = f.read().strip()
                cache = json.loads(raw) if raw else {}
                cache = {
                    key: ts
                    for key, ts in cache.items()
                    if isinstance(ts, (int, float)) and now - float(ts) <= 600
                }
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
            logger.warning(f"[FeishuCommandBridge] 跨实例事件去重失败：{exc}")
        return False

    def _is_allowed(self, chat_id: str, user_open_id: str) -> bool:
        if self._allow_all:
            return True
        if chat_id and chat_id in self._allowed_chat_ids:
            return True
        if user_open_id and user_open_id in self._allowed_user_ids:
            return True
        return False

    def _map_text_to_command(self, text: str) -> Optional[str]:
        text = self._sanitize_text(text)
        if not text:
            return None
        if text.startswith("/"):
            return text

        alias_map = self._parse_aliases()
        parts = text.split(maxsplit=1)
        alias = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        target = alias_map.get(alias)
        if not target:
            return None
        return f"{target} {rest}".strip()

    def _is_help_request(self, text: str) -> bool:
        text = self._sanitize_text(text)
        return text in {"帮助", "/help", "help"}

    def _is_menu_request(self, text: str) -> bool:
        text = self._sanitize_text(text)
        return text in {"菜单", "/menu", "menu", "面板", "控制面板"}

    def _parse_aliases(self) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for line in self._command_aliases.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key and value.startswith("/"):
                result[key] = value
        return result

    def _build_help_text(self) -> str:
        aliases = self._parse_aliases()
        alias_lines = [f"{k} -> {v}" for k, v in aliases.items()]
        alias_text = "\n".join(alias_lines) if alias_lines else "未配置别名"
        return (
            "可用命令：\n"
            f"{', '.join(self._command_whitelist)}\n\n"
            "别名：\n"
            f"{alias_text}\n\n"
            "快捷入口：发送“菜单”可查看可复制的快捷命令。"
        )

    def _build_menu_text(self) -> str:
        return (
            "快捷菜单\n"
            "1. 刮削\n\n"
            "2. 生成STRM\n\n"
            "3. 全量STRM\n\n"
            "4. 刷新极空间\n\n"
            "5. 版本"
        )

    def _extract_text(self, content: Any) -> str:
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
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _split_lines(value: Any) -> List[str]:
        return [line.strip() for line in str(value or "").splitlines() if line.strip()]

    @staticmethod
    def _split_commands(value: Any) -> List[str]:
        raw = str(value or "").replace("\n", ",")
        return [item.strip() for item in raw.split(",") if item.strip()]

    @staticmethod
    def _mask_secret(value: str) -> str:
        value = str(value or "").strip()
        if not value:
            return ""
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}...{value[-4:]}"

    def _reply_if_needed(
        self,
        receive_chat_id: str,
        receive_open_id: str,
        text: str,
    ) -> None:
        if not self._reply_enabled:
            return
        if not self._app_id or not self._app_secret:
            return

        receive_id_type = self._reply_receive_id_type
        receive_id = receive_chat_id if receive_id_type == "chat_id" else receive_open_id
        if not receive_id:
            return

        access_token = self._get_tenant_access_token()
        if not access_token:
            return

        url = (
            "https://open.feishu.cn/open-apis/im/v1/messages"
            f"?receive_id_type={receive_id_type}"
        )
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        payload = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        }
        logger.info(f"[FeishuCommandBridge] 准备回复飞书：{text}")
        response = RequestUtils(headers=headers).post(url=url, json=payload)
        if response is None:
            logger.error("[FeishuCommandBridge] failed to send reply to Feishu")
            return
        try:
            data = response.json()
        except Exception:
            data = {}
        if response.status_code != 200 or data.get("code") not in (0, None):
            logger.error(
                f"[FeishuCommandBridge] reply failed: "
                f"status={response.status_code} body={data}"
            )

    def _get_tenant_access_token(self) -> Optional[str]:
        now = time.time()
        with self._token_lock:
            token = self._token_cache.get("token")
            expires_at = float(self._token_cache.get("expires_at") or 0)
            if token and now < expires_at - 60:
                return token

            response = RequestUtils(content_type="application/json").post(
                url="https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/",
                json={"app_id": self._app_id, "app_secret": self._app_secret},
            )
            if response is None:
                logger.error("[FeishuCommandBridge] failed to fetch tenant access token")
                return None
            try:
                data = response.json()
            except Exception as exc:
                logger.error(
                    f"[FeishuCommandBridge] invalid token response from Feishu: {exc}"
                )
                return None

            token = data.get("tenant_access_token")
            expire = int(data.get("expire") or 0)
            if not token:
                logger.error(
                    f"[FeishuCommandBridge] token missing in response: {data}"
                )
                return None
            self._token_cache = {"token": token, "expires_at": now + expire}
            return token
