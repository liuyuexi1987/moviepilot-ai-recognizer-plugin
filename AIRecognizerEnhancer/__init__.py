from typing import Any, Dict, List, Optional, Tuple

from app.plugins import _PluginBase


class AIRecognizerEnhancer(_PluginBase):
    plugin_name = "AI识别增强"
    plugin_desc = "重构中的本地 AI 识别增强插件，后续替代旧版 Gateway 转发链路。"
    plugin_icon = "https://raw.githubusercontent.com/liuyuexi1987/MoviePilot-Plugins/main/icons/airecoginzerforwarder.png"
    plugin_version = "0.0.1-alpha.1"
    plugin_author = "liuyuexi1987"
    author_url = "https://github.com/liuyuexi1987"
    plugin_config_prefix = "arrecognizerenhancer_"
    plugin_order = 41
    auth_level = 1

    _enabled = False
    _debug = False

    def init_plugin(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._debug = bool(config.get("debug", False))

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def stop_service(self):
        return

    def get_api(self) -> List[Dict[str, Any]]:
        return []

    def get_page(self) -> List[dict]:
        return [
            {
                "component": "VAlert",
                "props": {
                    "type": "info",
                    "variant": "tonal",
                    "text": "AI识别增强正在重构中，当前目录仅作为后续本地 LLM 识别增强实现的固定落点。",
                },
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
                                            "text": "当前版本是重构骨架，后续会直接复用 MoviePilot 当前启用的 LLM 配置，实现识别失败后的本地结构化 AI 兜底。",
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
                                            "model": "debug",
                                            "label": "调试模式",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                ],
            }
        ]
        return form, {"enabled": False, "debug": False}
