"""
MoviePilot AI 识别转发插件
功能：原生识别失败时转发给 AI Gateway，等待异步回调后二次整理
版本：2.0.1
作者：liuyuexi1987
"""

from typing import List, Tuple, Dict, Any, Optional
from app.plugins import _PluginBase
from app.log import logger
import importlib


def _load_event_system():
    eventmanager_local = None
    event_type_local = None
    chain_event_type_local = None
    loaded_from = []

    candidates = [
        "app.event",
        "app.core.event",
        "app.core.event_manager",
        "app.eventmanager",
        "app.event_manager",
    ]

    for mod_name in candidates:
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue

        if not eventmanager_local:
            eventmanager_local = getattr(mod, "eventmanager", None)
            if eventmanager_local:
                loaded_from.append(f"eventmanager@{mod_name}")

        if not event_type_local:
            event_type_local = getattr(mod, "EventType", None)
            if event_type_local:
                loaded_from.append(f"EventType@{mod_name}")

        if not chain_event_type_local:
            chain_event_type_local = getattr(mod, "ChainEventType", None)
            if chain_event_type_local:
                loaded_from.append(f"ChainEventType@{mod_name}")

    if not event_type_local or not chain_event_type_local:
        try:
            schema_mod = importlib.import_module("app.schemas.event")
            if not event_type_local:
                event_type_local = getattr(schema_mod, "EventType", None)
                if event_type_local:
                    loaded_from.append("EventType@app.schemas.event")
            if not chain_event_type_local:
                chain_event_type_local = getattr(schema_mod, "ChainEventType", None)
                if chain_event_type_local:
                    loaded_from.append("ChainEventType@app.schemas.event")
        except Exception:
            pass

    return eventmanager_local, event_type_local, chain_event_type_local, loaded_from


eventmanager, EventType, ChainEventType, _event_loaded_from = _load_event_system()
if not eventmanager:
    logger.warning("事件系统加载失败，名称识别事件将不可用：eventmanager 未找到")
elif not EventType or not ChainEventType:
    logger.warning("事件系统加载部分成功，但 EventType/ChainEventType 未找到")
else:
    logger.info(f"事件系统加载成功：{', '.join(_event_loaded_from)}")

from fastapi import Request
import json
import time
import urllib.request

# 配置
CALLBACK_TIMEOUT = 300  # 回调超时时间（秒）
REQUEST_DEDUP_WINDOW = 60  # 请求去重窗口（秒）
NAME_RECOGNIZE_TIMEOUT = 15  # 名称识别事件允许的最大等待时间（秒）
FORWARD_WEBHOOK_TIMEOUT = 10  # 转发到 AI Gateway 的超时时间（秒）


class AIRecoginzerForwarder(_PluginBase):
    """AI 识别转发插件"""

    plugin_name = "AI 识别转发"
    plugin_desc = "原生识别失败后异步调用 AI Gateway，并在回调后自动二次整理"
    plugin_version = "2.0.1"
    plugin_order = 100
    plugin_author = "liuyuexi1987"

    def __init__(self):
        super().__init__()
        self.enabled = False
        self.callback_timeout = CALLBACK_TIMEOUT
        # Some MoviePilot internals expect plugin.name
        self.name = self.plugin_name
        # Gateway settings
        self.forward_webhook_url = ""
        self.forward_webhook_headers = {}
        self.forward_webhook_timeout = FORWARD_WEBHOOK_TIMEOUT
        self.recognize_mode = "standard"

        # 历史兼容配置：前端已不再暴露，统一按推荐模式运行
        self.enable_for_downloads = True
        self.enable_for_transfer = True
        self.enable_for_manual = True
        self.allow_manual_without_path = True
        self.download_path_keywords = ["downloads", "torrents", "下载"]

        # 存储等待回调的识别请求
        self.pending_requests = {}
        # 超时但仍可接受回调的请求
        self.expired_requests = {}
        # 已发送的请求记录（用于去重）
        self.sent_requests = {}
        # 最近一次标题->路径映射（用于无路径事件回补）
        self.recent_title_paths = {}

    def init_plugin(self, config: dict = None):
        """生效配置信息"""
        if config:
            self.enabled = config.get("enabled", False)
            self.callback_timeout = self._safe_int(
                config.get("callback_timeout", CALLBACK_TIMEOUT),
                CALLBACK_TIMEOUT,
            )
            self.forward_webhook_url = config.get("forward_webhook_url", "")
            self.forward_webhook_timeout = self._safe_int(
                config.get("forward_webhook_timeout", FORWARD_WEBHOOK_TIMEOUT),
                FORWARD_WEBHOOK_TIMEOUT,
            )
            self.forward_webhook_headers = self._safe_json_dict(
                config.get("forward_webhook_headers", {}),
                {},
            )
            self.recognize_mode = self._normalize_recognize_mode(
                config.get("recognize_mode", "standard")
            )

            legacy_scene_filter_keys = (
                "enable_for_downloads",
                "enable_for_transfer",
                "enable_for_manual",
                "allow_manual_without_path",
                "download_path_keywords",
            )
            if any(key in config for key in legacy_scene_filter_keys):
                logger.info("场景过滤开关已收敛为统一模式，旧配置项将自动忽略")

        if self.enabled:
            logger.info("AI 识别转发插件已启用 (已挂载官方 recognize_media 钩子)")
            logger.info("  - 运行模式：统一自动接管（原生识别失败后兜底）")
            logger.info(f"  - 识别增强模式：{'标准模式' if self.recognize_mode == 'standard' else '增强模式'}")
            self._register_events()
        else:
            logger.info("AI 识别转发插件已禁用")

    def _safe_int(self, value: Any, default: int) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def _safe_json_dict(self, value: Any, default: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return default
        return default

    def _normalize_recognize_mode(self, value: Any) -> str:
        mode = str(value or "standard").strip().lower()
        if mode not in {"standard", "enhanced"}:
            return "standard"
        return mode

    def get_state(self) -> bool:
        return self.enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    @staticmethod
    def get_render_mode() -> Tuple[str, Optional[str]]:
        return "vuetify", None

    def get_api(self) -> List[Dict[str, Any]]:
        """注册插件 API"""
        return [
            {
                "path": "/ai_recognize_callback",
                "endpoint": self.ai_recognize_callback,
                "methods": ["POST"],
                "summary": "AI 识别回调",
                "description": "接收 AI 助手的识别结果"
            }
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """拼装插件配置页面"""
        form_data = [
            {
                'component': 'VForm',
                                                        'content': [
                                                            {
                                                                'component': 'VRow',
                                                                'content': [
                            {
                                'component': 'VCol',
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                            'color': 'primary',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'forward_webhook_url',
                                            'label': 'AI Gateway Webhook 地址',
                                            'placeholder': 'http://moviepilot-ai-recognizer-gateway:9000/webhook',
                                            'hint': '填写 MoviePilot 当前环境可直接访问的 Webhook 地址',
                                            'persistent-hint': True
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'forward_webhook_headers',
                                            'label': 'AI Gateway Webhook Headers（JSON）',
                                            'placeholder': '{"X-API-KEY":"xxx"}',
                                            'hint': '可选，JSON 格式的请求头',
                                            'persistent-hint': True
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'forward_webhook_timeout',
                                            'label': 'AI Gateway Webhook 超时（秒）',
                                            'type': 'number',
                                            'placeholder': '10',
                                            'hint': '建议 10 秒；Webhook 应立即 accepted，后台异步识别',
                                            'persistent-hint': True
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'callback_timeout',
                                            'label': '回调超时时间（秒）',
                                            'type': 'number',
                                            'placeholder': '300',
                                            'hint': '建议 300 秒（5 分钟）',
                                            'persistent-hint': True
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {'cols': '12', 'md': '6'},
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'recognize_mode',
                                            'label': '识别增强模式',
                                            'items': [
                                                {'title': '标准模式（推荐）', 'value': 'standard'},
                                                {'title': '增强模式（适合网盘规避命名）', 'value': 'enhanced'},
                                            ],
                                            'hint': '标准模式更稳；增强模式更适合拼音、漏词、规避命名，但查询会更宽松',
                                            'persistent-hint': True,
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {'cols': '12', 'md': '6'},
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'warning',
                                            'icon': 'mdi-tune-variant',
                                            'variant': 'tonal',
                                            'dense': True,
                                        },
                                        'content': [
                                            {'component': 'div', 'text': '标准模式：适合 PT 规范命名，优先保证准确率。'},
                                            {'component': 'div', 'text': '增强模式：适合网盘拼音、漏词、规避版权命名，但耗时略高。'},
                                            {'component': 'div', 'text': '增强模式会增加额外 AI 猜测和更宽松的标题查询，误命中风险也会略升。'}
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'icon': 'mdi-information',
                                            'dense': True,
                                            'border': 'left',
                                        },
                                        'content': [
                                            {'component': 'div', 'text': '💡 配置说明：'},
                                            {'component': 'div', 'text': '1. 推荐保持 MoviePilot【插件优先模式】关闭，本插件只在原生 TMDB 失败后兜底。'},
                                            {'component': 'div', 'text': '2. 同机 Docker 场景：Webhook 地址直接填网关容器名，例如 http://moviepilot-ai-recognizer-gateway:9000/webhook。'},
                                            {'component': 'div', 'text': '3. 跨主机场景：Webhook 地址可填写对端机器地址，例如 http://<对端IP>:9000/webhook，但不建议作为默认方案。'},
                                            {'component': 'div', 'text': '4. Webhook 服务需要立即返回 accepted，在后台调用 AI 后端识别，再异步回调 MoviePilot。'},
                                            {'component': 'div', 'text': '5. Webhook 回调端点固定为 POST /api/v1/plugin/AIRecoginzerForwarder/ai_recognize_callback，无需在插件里额外填写。'},
                                            {'component': 'div', 'text': '6. 识别增强模式建议默认使用【标准模式】；只有在网盘规避命名、拼音标题较多时再切换到【增强模式】。'},
                                            {'component': 'div', 'text': '7. 当前稳定支持本地文件整理、手动整理，以及 115/u115 云盘挂载文件的二次整理。'}
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

        default_config = {
            "enabled": True,
            "callback_timeout": 300,
            "forward_webhook_url": "",
            "forward_webhook_headers": {},
            "forward_webhook_timeout": FORWARD_WEBHOOK_TIMEOUT,
            "recognize_mode": "standard",
        }

        return form_data, default_config

    def get_page(self) -> List[dict]:
        """拼装插件详情页面"""
        return [
            {
                'component': 'VContainer',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'content': [
                                    {
                                        'component': 'VCard',
                                        'props': {'flat': True, 'border': True},
                                        'content': [
                                            {
                                                'component': 'VCardTitle',
                                                'content': [
                                                    {'component': 'VIcon', 'props': {'left': True, 'color': 'primary'}, 'text': 'mdi-robot'},
                                                    {'component': 'span', 'text': 'AI 识别转发插件 - 项目说明'}
                                                ]
                                            },
                                            {
                                                'component': 'VCardText',
                                                'content': [
                                                    {'component': 'h3', 'text': '⚠️ 重要设置'},
                                                    {'component': 'p', 'text': '推荐在 MoviePilot 设置 -> 媒体 中保持【插件优先模式】关闭。本插件设计为原生 TMDB 识别失败后的兜底链路，这样更省 AI 资源，也更容易排查问题。'},
                                                    {'component': 'br'},

                                                    {'component': 'h3', 'text': '🎯 插件功能'},
                                                    {'component': 'p', 'text': '当 MoviePilot 原生识别失败时，插件会把标题和可用文件信息转发给 AI Gateway，等待异步回调识别结果，并自动触发二次整理。'},
                                                    {'component': 'br'},

                                                    {'component': 'h3', 'text': '✅ 推荐搭建方式'},
                                                    {'component': 'p', 'text': '场景 1：MoviePilot 和 Gateway 在同一台 Docker 主机。插件中直接填写容器可达地址，例如 http://moviepilot-ai-recognizer-gateway:9000/webhook。'},
                                                    {'component': 'p', 'text': '场景 2：MoviePilot 和 Gateway 不在同一台机器。插件地址可以填写对端机器可访问的 Gateway 地址，例如 http://<对端IP>:9000/webhook，但不建议作为默认推荐方案。'},
                                                    {'component': 'p', 'text': '原因：跨主机场景更容易出现容器网络、宿主机地址、双向回调、端口映射和超时排查问题。更推荐 MoviePilot 与 Gateway 同机部署，并在同一 Docker 网络内互通。'},
                                                    {'component': 'p', 'text': '场景 3：如果用户已有 OpenClaw 或其他外部识别端，也可以由 Gateway 转发过去；插件本身不绑定具体 AI 后端。'},
                                                    {'component': 'br'},

                                                    {'component': 'h3', 'text': '📦 适用场景'},
                                                    {'component': 'p', 'text': '支持本地文件整理、手动整理失败补救、下载入库时的兜底识别，以及 115/u115 云盘挂载文件的二次整理。'},
                                                    {'component': 'p', 'text': '赛事和新闻这类非标准影视条目建议直接回退为 tmdb_id=0；演唱会、电影、剧集则继续正常识别。'},
                                                    {'component': 'br'},

                                                    {'component': 'h3', 'text': '🧠 识别增强模式'},
                                                    {'component': 'p', 'text': '标准模式：适合 PT 站规范命名，优先按模型标准标题和清洗后的文件名查询 TMDB，整体更稳。'},
                                                    {'component': 'p', 'text': '增强模式：会增加额外 AI 猜测和更宽松的标题路由，适合网盘拼音、漏词、规避版权审查的标题。'},
                                                    {'component': 'p', 'text': '增强模式的代价是耗时略高，且在同名作品较多的场景下，误命中的风险会略高于标准模式。'},
                                                    {'component': 'br'},

                                                    {'component': 'h3', 'text': '📊 回调 API'},
                                                    {'component': 'p', 'text': 'Webhook 识别完成后，请回调以下端点：'},
                                                    {'component': 'code', 'text': 'POST /api/v1/plugin/AIRecoginzerForwarder/ai_recognize_callback'},
                                                    {'component': 'br'},

                                                    {'component': 'h3', 'text': '🧭 当前版本'},
                                                    {'component': 'p', 'text': '2.0.1：修正版本展示格式，并继续以插件仓库 + Gateway 镜像仓库为主方向。'},
                                                    {'component': 'p', 'text': '设置页已收敛为推荐配置，不再暴露场景过滤开关，避免因上游事件差异导致误判。'}
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

    def get_service(self) -> List[Dict[str, Any]]:
        return []

    def stop_service(self) -> None:
        logger.info("AI 识别转发插件停止")
        self.enabled = False

    def should_process(self, title: str, path: str = "") -> Tuple[bool, str]:
        if not self.enabled:
            return False, "插件未启用"

        if not title:
            return False, "标题为空"

        if path:
            return True, "已获取文件路径"

        remembered_path = self.recent_title_paths.get(title, "")
        if remembered_path:
            return True, "已命中最近路径回补"

        inferred_path = self._infer_path_from_title(title)
        if inferred_path:
            return True, "已根据文件名推断路径"

        return False, "无可用文件路径，已跳过"

    def recognize_media(self, meta: Any = None, mtype: Any = None, **kwargs) -> Optional[Dict[str, Any]]:
        """
        MoviePilot 官方标准的识别 Hook
        当原生识别失败，或者开启了"插件优先模式"时，MoviePilot 会调用此方法
        """
        if not self.enabled:
            return None

        # 提取标题 (兼容不同版本的 MetaBase 对象)
        title = getattr(meta, 'name', '')
        if not title:
            title = getattr(meta, 'title', '')
        if not title:
            title = str(meta)
        
        if not title:
            return None

        # 提取路径
        path = kwargs.get('path', '')
        if not path and hasattr(meta, 'path'):
            path = getattr(meta, 'path', '')
        if not path and hasattr(meta, 'org_string'):
            path = getattr(meta, 'org_string', '')
        if not path:
            path = self._infer_path_from_title(title)
        if path:
            self._remember_title_path(title, path)

        should_process, reason = self.should_process(title, path)
        if not should_process:
            logger.info(f"跳过 AI 识别：{title} - {reason}")
            return None

        if self.is_duplicate_request(title):
            logger.info(f"跳过重复识别请求：{title}")
            return None

        request_id = f"ai_{int(time.time())}_{abs(hash(title)) % 10000}"

        self.pending_requests[request_id] = {
            'title': title,
            'path': path,
            'timestamp': time.time()
        }

        self.sent_requests[title] = {
            'request_id': request_id,
            'timestamp': time.time()
        }

        logger.info(f"原生识别失败，AI 插件接管识别：{title}")

        # 同步发送请求 (因为 recognize_media 是同步执行的)
        self.send_ai_request_sync(request_id, title, path)

        # 同步等待回调
        result = self.wait_for_callback_sync(request_id)

        if result:
            logger.info(f"AI 识别结果已注入：{result.get('name')} ({result.get('year')})")
            return result
        else:
            logger.warning(f"AI 识别超时：{title}")
            return None

    def on_name_recognize(self, event) -> None:
        """
        兼容 V1 的名称识别事件处理
        说明：此事件要求在 15 秒内回复，否则结果会被丢弃
        """
        event_data = getattr(event, "event_data", None) or {}
        title, path = self._extract_title_path(event_data)
        if not path:
            path = self.recent_title_paths.get(title, "")

        if not title:
            return

        logger.info(f"收到 NameRecognize 事件：{title}")

        should_process, reason = self.should_process(title, path)
        if not should_process:
            logger.info(f"跳过 AI 识别：{title} - {reason}")
            self._send_empty_name_recognize_result(title)
            return

        if self.is_duplicate_request(title):
            logger.info(f"跳过重复识别请求：{title}")
            self._send_empty_name_recognize_result(title)
            return

        result = self._request_and_wait(title, max_wait=NAME_RECOGNIZE_TIMEOUT)
        if result:
            self._send_name_recognize_result(title, result)
        else:
            logger.warning(f"AI 识别超时（NameRecognize）：{title}")
            self._send_empty_name_recognize_result(title)

    def on_chain_name_recognize(self, event) -> None:
        """
        兼容 V2 的链式名称识别事件处理
        说明：链式事件也需要在 15 秒内完成
        """
        event_data = getattr(event, "event_data", None) or {}
        title, path = self._extract_title_path(event_data)
        if not path:
            path = self.recent_title_paths.get(title, "")

        try:
            if isinstance(event_data, dict):
                logger.info(f"NameRecognize event_data keys: {list(event_data.keys())}")
            else:
                logger.info(f"NameRecognize event_data type: {type(event_data)}")
        except Exception:
            pass
        try:
            logger.info(f"NameRecognize event type: {getattr(event, 'event_type', '')}")
        except Exception:
            pass
        try:
            logger.info(f"NameRecognize event raw: {vars(event)}")
        except Exception:
            pass

        # 如果这是注入的 AI 结果，直接应用并返回，避免再次触发识别
        if isinstance(event_data, dict):
            ai_result = event_data.get("ai_result")
            if ai_result:
                self._apply_chain_result(event_data, ai_result)
                logger.info(f"AI 结果已注入（无需再次识别）：{title}")
                return

        if not title:
            return

        logger.info(f"收到 Chain NameRecognize 事件：{title}")

        should_process, reason = self.should_process(title, path)
        if not should_process:
            logger.info(f"跳过 AI 识别：{title} - {reason}")
            return

        if self.is_duplicate_request(title):
            logger.info(f"跳过重复识别请求：{title}")
            return

        # 异步模式：发送请求后立即返回，避免阻塞 15 秒链式窗口
        self._request_async(title, path=path)
        return

    def is_duplicate_request(self, title: str) -> bool:
        if title not in self.sent_requests:
            return False

        current_time = time.time()
        expired_titles = [
            t for t, data in self.sent_requests.items()
            if current_time - data['timestamp'] > REQUEST_DEDUP_WINDOW
        ]
        for t in expired_titles:
            del self.sent_requests[t]

        if title in self.sent_requests:
            return current_time - self.sent_requests[title]['timestamp'] < REQUEST_DEDUP_WINDOW

        return False

    def _extract_title_path(self, event_data: Any) -> Tuple[str, str]:
        title = ""
        path = ""
        if isinstance(event_data, dict):
            title = (
                event_data.get("title")
                or event_data.get("name")
                or event_data.get("org_string")
                or ""
            )
            path = (
                event_data.get("path")
                or event_data.get("file_path")
                or event_data.get("org_string")
                or ""
            )
            if not path:
                for key in ("fileitem", "file_item", "file", "torrent", "download", "meta"):
                    nested = event_data.get(key)
                    if isinstance(nested, dict):
                        path = (
                            nested.get("path")
                            or nested.get("file_path")
                            or nested.get("full_path")
                            or nested.get("save_path")
                            or ""
                        )
                        if path:
                            break
                if not path:
                    raw = event_data.get("file") or event_data.get("filepath") or ""
                    if isinstance(raw, str):
                        path = raw
        else:
            title = (
                getattr(event_data, "title", "")
                or getattr(event_data, "name", "")
                or getattr(event_data, "org_string", "")
                or ""
            )
            path = (
                getattr(event_data, "path", "")
                or getattr(event_data, "file_path", "")
                or getattr(event_data, "org_string", "")
                or ""
            )
        if not path:
            path = self._infer_path_from_title(title)
        return title, path

    def _apply_chain_result(self, event_data: Any, result: Dict[str, Any]) -> None:
        if isinstance(event_data, dict):
            event_data["name"] = result.get("name", "")
            event_data["year"] = result.get("year", "")
            event_data["season"] = result.get("season", 0)
            event_data["episode"] = result.get("episode", 0)
        else:
            setattr(event_data, "name", result.get("name", ""))
            setattr(event_data, "year", result.get("year", ""))
            setattr(event_data, "season", result.get("season", 0))
            setattr(event_data, "episode", result.get("episode", 0))

    def _send_name_recognize_result(self, title: str, result: Dict[str, Any]) -> None:
        if not eventmanager or not EventType:
            return
        eventmanager.send_event(
            EventType.NameRecognizeResult,
            {
                "title": title,
                "name": result.get("name", ""),
                "year": result.get("year", ""),
                "season": result.get("season", 0),
                "episode": result.get("episode", 0),
            },
        )

    def _send_empty_name_recognize_result(self, title: str) -> None:
        if not eventmanager or not EventType:
            return
        eventmanager.send_event(EventType.NameRecognizeResult, {"title": title})

    def _request_and_wait(self, title: str, max_wait: int) -> Optional[Dict[str, Any]]:
        request_id = f"ai_{int(time.time())}_{abs(hash(title)) % 10000}"

        path = self.recent_title_paths.get(title, "") or self._infer_path_from_title(title)
        self.pending_requests[request_id] = {
            "title": title,
            "path": path,
            "timestamp": time.time(),
            "mode": "sync",
        }

        self.sent_requests[title] = {
            "request_id": request_id,
            "timestamp": time.time(),
        }

        logger.info(f"原生识别失败，AI 插件接管识别：{title}")
        self.send_ai_request_sync(request_id, title, path)

        wait_time = min(self.callback_timeout, max_wait)
        result = self.wait_for_callback_sync_with_timeout(request_id, wait_time)
        return result

    def _request_async(self, title: str, path: str = "") -> None:
        request_id = f"ai_{int(time.time())}_{abs(hash(title)) % 10000}"

        if not path:
            path = self.recent_title_paths.get(title, "") or self._infer_path_from_title(title)
        self.pending_requests[request_id] = {
            "title": title,
            "path": path,
            "timestamp": time.time(),
            "mode": "async",
        }

        self.sent_requests[title] = {
            "request_id": request_id,
            "timestamp": time.time(),
        }

        logger.info(f"原生识别失败，AI 插件接管识别（异步）：{title}")
        self.send_ai_request_sync(request_id, title, path)

    def wait_for_callback_sync_with_timeout(self, request_id: str, timeout: int) -> Optional[Dict]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            if request_id in self.pending_requests:
                request = self.pending_requests[request_id]
                if "result" in request:
                    result = request["result"]
                    del self.pending_requests[request_id]
                    return result
            time.sleep(1)

        if request_id in self.pending_requests:
            self.expired_requests[request_id] = self.pending_requests[request_id]
            del self.pending_requests[request_id]
        return None

    def _register_events(self) -> None:
        if not eventmanager:
            logger.warning("事件系统不可用，无法注册名称识别事件")
            return
        if EventType:
            try:
                eventmanager.register(EventType.NameRecognize)(self.on_name_recognize)
                logger.info("已注册 NameRecognize 事件处理器")
            except Exception as e:
                logger.warning(f"注册 NameRecognize 事件失败：{e}")
        if ChainEventType:
            try:
                eventmanager.register(ChainEventType.NameRecognize)(self.on_chain_name_recognize)
                logger.info("已注册 Chain NameRecognize 事件处理器")
            except Exception as e:
                logger.warning(f"注册 Chain NameRecognize 事件失败：{e}")

    def send_ai_request_sync(self, request_id: str, title: str, path: str = "") -> None:
        """发送 AI 识别请求 (同步方式)"""
        if not self.forward_webhook_url:
            logger.warning("已启用 AI Gateway Webhook 转发，但未配置 URL")
            return
        if self.send_forward_webhook_sync(request_id, title, path):
            return
        logger.warning("AI Gateway Webhook 转发失败")

    def send_forward_webhook_sync(self, request_id: str, title: str, path: str = "") -> bool:
        """转发到 AI Gateway Webhook (同步方式)"""
        payload = {
            "request_id": request_id,
            "title": title,
            "path": path,
            "timestamp": int(time.time()),
            "recognize_mode": self.recognize_mode,
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            headers.update(self.forward_webhook_headers or {})
            req = urllib.request.Request(
                url=self.forward_webhook_url,
                data=data,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.forward_webhook_timeout) as resp:
                logger.info(f"AI Gateway Webhook 已转发：{request_id}")
                return True
        except Exception as e:
            logger.error(f"AI Gateway Webhook 转发失败：{self._format_http_error(e)}")
            return False

    def _format_http_error(self, err: Exception) -> str:
        if hasattr(err, "code") and hasattr(err, "read"):
            try:
                body = err.read().decode("utf-8", errors="ignore")
            except Exception:
                body = ""
            return f"HTTP {getattr(err, 'code', '')} {body}".strip()
        return str(err)

    def wait_for_callback_sync(self, request_id: str) -> Optional[Dict]:
        """等待回调结果 (同步阻塞等待)"""
        start_time = time.time()

        while time.time() - start_time < self.callback_timeout:
            if request_id in self.pending_requests:
                request = self.pending_requests[request_id]
                if 'result' in request:
                    result = request['result']
                    del self.pending_requests[request_id]  # 成功时清理
                    return result

            time.sleep(1)  # 阻塞等待回调写入

        # 超时时清理，防止内存泄漏
        if request_id in self.pending_requests:
            del self.pending_requests[request_id]
        
        return None

    async def ai_recognize_callback(self, request: Request) -> Dict:
        """AI 识别回调 API (异步，供外部调用)"""
        start_time = time.time()
        try:
            data = await request.json()
        except Exception:
            return {"success": False, "message": "无效的 JSON 数据"}

        request_id = data.get('request_id')
        result = data.get('result')
        title_hint = data.get('title', '') or data.get('source_title', '') or ''
        path_hint = data.get('path', '') or ''
        if not path_hint and title_hint:
            path_hint = self.recent_title_paths.get(title_hint, "") or self._infer_path_from_title(title_hint)

        if not request_id or not result:
            return {"success": False, "message": "缺少参数"}

        name = result.get('name', '')
        year = result.get('year', '')
        tmdb_id = result.get('tmdb_id', 0)
        media_type = result.get('type', 'movie')
        season = result.get('season', 0)
        episode = result.get('episode', 0)

        result_payload = {
            'name': name,
            'year': year,
            'tmdb_id': tmdb_id,
            'type': media_type,
            'season': season,
            'episode': episode
        }

        if request_id not in self.pending_requests and request_id not in self.expired_requests:
            if title_hint:
                logger.warning(f"回调未命中请求ID，使用 title 兜底触发二次整理：{request_id} - {title_hint}")
                self._trigger_second_pass(title_hint, path_hint, result_payload)
                return {"success": True, "message": "回调成功（ID未命中，已兜底处理）"}
            return {"success": False, "message": "请求不存在或已超时"}

        # 正常回调（仍在等待）
        if request_id in self.pending_requests:
            created_time = self.pending_requests[request_id].get("timestamp", 0)
            total_wait = time.time() - created_time
            elapsed = time.time() - start_time
            mode = self.pending_requests[request_id].get("mode", "sync")
            if mode == "sync":
                self.pending_requests[request_id]['result'] = result_payload
                logger.info(f"AI 识别回调成功：{request_id} - {name} ({year}) TMDB:{tmdb_id}")
                logger.info(f"回调耗时：{elapsed:.2f}s，总等待：{total_wait:.2f}s")
                return {"success": True, "message": "回调成功"}

            # async mode: no waiter, trigger second pass directly
            pending = self.pending_requests.pop(request_id, {})
            title = pending.get("title", "")
            path = pending.get("path", "") or self.recent_title_paths.get(title, "") or self._infer_path_from_title(title)
            logger.info(f"AI 识别回调成功（异步）：{request_id} - {name} ({year}) TMDB:{tmdb_id}")
            logger.info(f"回调耗时：{elapsed:.2f}s，总等待：{total_wait:.2f}s")
            self._trigger_second_pass(title, path, result_payload)
            return {"success": True, "message": "回调成功（异步已处理）"}

        # 超时后回调（异步二次整理）
        if request_id in self.expired_requests:
            expired = self.expired_requests.pop(request_id, {})
            title = expired.get("title", "")
            path = expired.get("path", "") or self.recent_title_paths.get(title, "") or self._infer_path_from_title(title)
            created_time = expired.get("timestamp", 0)
            total_wait = time.time() - created_time
            elapsed = time.time() - start_time
            logger.info(f"AI 识别回调迟到：{request_id} - {name} ({year}) TMDB:{tmdb_id}")
            logger.info(f"回调耗时：{elapsed:.2f}s，总等待：{total_wait:.2f}s")
            self._trigger_second_pass(title, path, result_payload)
            return {"success": True, "message": "回调成功（迟到已接收）"}

        return {"success": False, "message": "请求不存在或已超时"}

    def _trigger_second_pass(self, title: str, path: str, result: Dict[str, Any]) -> None:
        """
        二次整理触发：尽可能将迟到的识别结果注入系统
        """
        if not path and title:
            path = self.recent_title_paths.get(title, "") or self._infer_path_from_title(title)
        if self._trigger_manual_transfer(title, path, result):
            logger.info(f"二次整理触发完成（官方 manual_transfer）：{title}")
            return
        if not eventmanager:
            logger.warning("二次整理触发失败：事件系统不可用")
            return

        # 如果存在链式识别结果事件，则发送
        if ChainEventType and hasattr(ChainEventType, "NameRecognizeResult"):
            try:
                eventmanager.send_event(
                    ChainEventType.NameRecognizeResult,
                    {
                        "title": title,
                        "path": path,
                        "name": result.get("name", ""),
                        "year": result.get("year", ""),
                        "season": result.get("season", 0),
                        "episode": result.get("episode", 0),
                    },
                )
                logger.info(f"二次整理触发完成（Chain NameRecognizeResult）：{title}")
                return
            except Exception as e:
                logger.warning(f"二次整理触发失败（Chain NameRecognizeResult）：{e}")

        # 兜底：如果存在普通识别结果事件，也尝试发送
        if EventType and hasattr(EventType, "NameRecognizeResult"):
            try:
                eventmanager.send_event(
                    EventType.NameRecognizeResult,
                    {
                        "title": title,
                        "name": result.get("name", ""),
                        "year": result.get("year", ""),
                        "season": result.get("season", 0),
                        "episode": result.get("episode", 0),
                    },
                )
                logger.info(f"二次整理触发完成（NameRecognizeResult）：{title}")
                return
            except Exception as e:
                logger.warning(f"二次整理触发失败（NameRecognizeResult）：{e}")

        # 再兜底：回放 Chain NameRecognize，并注入 AI 结果，避免超时丢失
        if ChainEventType and hasattr(ChainEventType, "NameRecognize"):
            try:
                eventmanager.send_event(
                    ChainEventType.NameRecognize,
                    {
                        "title": title,
                        "path": path,
                        "ai_result": result,
                    },
                )
                logger.info(f"二次整理触发完成（Chain NameRecognize 回放）：{title}")
                return
            except Exception as e:
                logger.warning(f"二次整理触发失败（Chain NameRecognize 回放）：{e}")

        logger.warning("二次整理触发未执行：未找到可用事件类型")

    def _remember_title_path(self, title: str, path: str) -> None:
        if not title or not path:
            return
        self.recent_title_paths[title] = path
        # 清理过期项，防止内存增长
        current_time = time.time()
        expired = [
            t for t, p in self.recent_title_paths.items()
            if t != title and current_time - self.sent_requests.get(t, {}).get("timestamp", 0) > REQUEST_DEDUP_WINDOW
        ]
        for t in expired:
            self.recent_title_paths.pop(t, None)

    def _infer_path_from_title(self, title: str) -> str:
        if not title or "/" in title or "\\" in title:
            return ""
        lowered = title.lower()
        if any(lowered.endswith(ext) for ext in (".mkv", ".mp4", ".avi", ".ts", ".m2ts", ".iso", ".strm")):
            return f"/{title}"
        return ""

    def _trigger_manual_transfer(self, title: str, path: str, result: Dict[str, Any]) -> bool:
        if not result.get("tmdb_id"):
            return False

        try:
            from app.chain.transfer import TransferChain
            from app.db.transferhistory_oper import TransferHistoryOper
            from app.chain.media import MediaChain
            from app.chain.storage import StorageChain
            from app.schemas import FileItem, MediaType
        except Exception as e:
            logger.warning(f"加载官方整理链路失败：{e}")
            return False

        media_type = str(result.get("type") or "movie").lower()
        try:
            if media_type == "tv":
                mtype = MediaType.TV if hasattr(MediaType, "TV") else MediaType("电视剧")
            else:
                mtype = MediaType.MOVIE if hasattr(MediaType, "MOVIE") else MediaType("电影")
        except Exception:
            mtype = None

        try:
            fileitem = None

            histories = TransferHistoryOper().get_by_title(title)
            if histories:
                for history in histories:
                    src_fileitem = getattr(history, "src_fileitem", None) or {}
                    if isinstance(src_fileitem, dict) and src_fileitem.get("path"):
                        fileitem = FileItem(**src_fileitem)
                        logger.info(f"官方 manual_transfer 使用历史源文件：{fileitem.path}")
                        break

            if not fileitem:
                if not path:
                    return False
                fileitem = FileItem(storage="local", path=path, type="file")
                logger.info(f"官方 manual_transfer 使用兜底路径：{path}")

            mediainfo = MediaChain().recognize_media(
                tmdbid=int(result.get("tmdb_id") or 0),
                mtype=mtype,
            )
            if not mediainfo:
                logger.warning(f"官方 manual_transfer 识别媒体失败：{title}")
                return False

            transfer_chain = TransferChain()

            # 115 等云盘场景常只有 fileid/pickcode，path 可能是根路径占位。
            # 这里临时绕过按 path 的存在性校验，直接把历史里的 FileItem 交给官方 do_transfer。
            original_get_item = StorageChain.get_item

            def patched_get_item(storage_chain_self, request_fileitem):
                if (
                    request_fileitem
                    and fileitem
                    and request_fileitem.storage == fileitem.storage
                    and request_fileitem.path == fileitem.path
                    and getattr(request_fileitem, "fileid", None)
                ):
                    logger.info(f"官方 do_transfer 使用 fileid 直通源文件：{request_fileitem.storage}:{request_fileitem.path}")
                    return request_fileitem
                return original_get_item(storage_chain_self, request_fileitem)

            if fileitem.storage == "u115" and fileitem.fileid:
                StorageChain.get_item = patched_get_item
            try:
                state, errmsg = transfer_chain.do_transfer(
                    fileitem=fileitem,
                    mediainfo=mediainfo,
                    season=int(result.get("season") or 0) or None,
                    force=True,
                    background=False,
                    manual=True,
                )
            finally:
                StorageChain.get_item = original_get_item
            if not state:
                logger.warning(f"官方 manual_transfer 触发失败：{title} - {errmsg}")
                return False
            return True
        except Exception as e:
            logger.warning(f"官方 manual_transfer 执行异常：{title} - {e}")
            return False
