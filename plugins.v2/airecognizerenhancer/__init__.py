import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Request
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.chain.media import MediaChain
from app.core.config import settings
from app.core.event import eventmanager
from app.core.metainfo import MetaInfo
from app.helper.llm import LLMHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import ChainEventType, MediaType


class AIRecognitionGuess(BaseModel):
    name: str = Field(default="", description="标准化后的影视标题；无法判断时返回空字符串")
    year: str = Field(default="", description="四位年份；无法判断时返回空字符串")
    media_type: str = Field(default="unknown", description="movie、tv 或 unknown")
    season: int = Field(default=0, description="剧集季号，电影填 0")
    episode: int = Field(default=0, description="剧集集号，电影或未知填 0")
    confidence: float = Field(default=0.0, description="0 到 1 之间的置信度")
    reason: str = Field(default="", description="简短说明为什么这样判断")


class AIRecognizerEnhancer(_PluginBase):
    plugin_name = "AI识别增强"
    plugin_desc = "原生识别失败后直接复用 MoviePilot 当前 LLM 做本地结构化识别兜底。"
    plugin_icon = "https://raw.githubusercontent.com/liuyuexi1987/MoviePilot-Plugins/main/icons/airecoginzerforwarder.png"
    plugin_version = "0.1.0"
    plugin_author = "liuyuexi1987"
    author_url = "https://github.com/liuyuexi1987"
    plugin_config_prefix = "arrecognizerenhancer_"
    plugin_order = 41
    auth_level = 1

    _enabled = False
    _debug = False
    _confidence_threshold = 0.65
    _request_timeout = 25
    _max_retries = 2
    _save_failed_samples = True

    def init_plugin(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._debug = bool(config.get("debug", False))
        self._confidence_threshold = self._safe_float(config.get("confidence_threshold"), 0.65)
        self._request_timeout = self._safe_int(config.get("request_timeout"), 25)
        self._max_retries = max(1, min(5, self._safe_int(config.get("max_retries"), 2)))
        self._save_failed_samples = bool(config.get("save_failed_samples", True))
        self._register_events()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def stop_service(self):
        try:
            eventmanager.disable_event_handler(self.on_chain_name_recognize)
        except Exception:
            pass

    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _safe_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _extract_apikey(request: Request, body: Optional[Dict[str, Any]] = None) -> str:
        header = str(request.headers.get("Authorization") or "").strip()
        if header.lower().startswith("bearer "):
            return header.split(" ", 1)[1].strip()
        if body:
            for key in ("apikey", "api_key"):
                token = str(body.get(key) or "").strip()
                if token:
                    return token
        return str(request.query_params.get("apikey") or "").strip()

    def _check_api_access(self, request: Request, body: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        expected = str(getattr(settings, "API_TOKEN", "") or "").strip()
        if not expected:
            return False, "服务端未配置 API Token"
        actual = self._extract_apikey(request, body)
        if actual != expected:
            return False, "API Token 无效"
        return True, ""

    def _register_events(self) -> None:
        try:
            eventmanager.register(ChainEventType.NameRecognize)(self.on_chain_name_recognize)
            if self._enabled:
                eventmanager.enable_event_handler(self.on_chain_name_recognize)
            else:
                eventmanager.disable_event_handler(self.on_chain_name_recognize)
        except Exception as exc:
            logger.warning(f"[AI识别增强] 注册链式识别事件失败: {exc}")

    @staticmethod
    def _extract_title_path(event_data: Any) -> Tuple[str, str]:
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
        return str(title or "").strip(), str(path or "").strip()

    def _build_meta_hint(self, raw_text: str) -> Dict[str, Any]:
        try:
            meta = MetaInfo(raw_text)
        except Exception:
            return {}
        return {
            "name": getattr(meta, "name", "") or "",
            "year": getattr(meta, "year", "") or "",
            "type": getattr(getattr(meta, "type", None), "to_agent", lambda: None)() or "",
            "season": getattr(meta, "begin_season", None) or 0,
            "episode": getattr(meta, "begin_episode", None) or 0,
            "org_string": getattr(meta, "org_string", "") or "",
        }

    @staticmethod
    def _clean_guess_name(name: str) -> str:
        text = str(name or "").strip()
        if not text:
            return ""
        text = text.split("/")[0].strip().replace(".", " ")
        return " ".join(text.split())

    def _normalize_guess(self, guess: AIRecognitionGuess) -> AIRecognitionGuess:
        name = self._clean_guess_name(guess.name)
        year = str(guess.year or "").strip()
        if not (len(year) == 4 and year.isdigit()):
            year = ""
        media_type = str(guess.media_type or "unknown").strip().lower()
        if media_type not in {"movie", "tv"}:
            media_type = "unknown"
        season = max(0, self._safe_int(guess.season, 0))
        episode = max(0, self._safe_int(guess.episode, 0))
        confidence = min(1.0, max(0.0, self._safe_float(guess.confidence, 0.0)))
        reason = str(guess.reason or "").strip()
        return AIRecognitionGuess(
            name=name,
            year=year,
            media_type=media_type,
            season=season,
            episode=episode,
            confidence=confidence,
            reason=reason,
        )

    def _record_failed_sample(self, payload: Dict[str, Any]) -> None:
        if not self._save_failed_samples:
            return
        try:
            sample_path = self.get_data_path() / "failed_samples.jsonl"
            sample_path.parent.mkdir(parents=True, exist_ok=True)
            with sample_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning(f"[AI识别增强] 写入失败样本失败: {exc}")

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是 MoviePilot 的影视文件名识别增强助手。

你的任务不是搜索 TMDB，也不是编造结果，而是根据文件名、路径和已有解析提示，尽量提炼出更适合 MoviePilot 二次识别的结构化信息。

规则：
1. 只依据输入内容推断，不要臆造不存在的信息。
2. 如果不确定，请返回空标题，并把 media_type 设为 unknown，confidence 降低。
3. title/name 只保留作品名，不要包含分辨率、制作组、音频编码、网盘标记等噪音。
4. year 只有在比较确定时才给四位年份。
5. 电影 season/episode 必须为 0。
6. 剧集如果能确定季集就填写，否则保持 0。
7. media_type 只能是 movie、tv、unknown。
8. confidence 范围为 0 到 1。
""",
                ),
                (
                    "human",
                    """原始标题：
{title}

原始路径：
{path}

MoviePilot 当前基础解析提示：
{meta_hint}
""",
                ),
            ]
        )

    def _invoke_llm(self, title: str, path: str) -> AIRecognitionGuess:
        raw_text = path or title
        meta_hint = self._build_meta_hint(raw_text)
        llm = LLMHelper.get_llm(streaming=False)
        prompt = self._build_prompt()
        chain = (
            prompt
            | llm.with_structured_output(AIRecognitionGuess).with_retry(stop_after_attempt=self._max_retries)
        )
        result: AIRecognitionGuess = chain.invoke(
            {
                "title": title,
                "path": path,
                "meta_hint": meta_hint,
            },
            config={"configurable": {"timeout": self._request_timeout}},
        )
        return self._normalize_guess(result)

    def _verify_guess(self, title: str, path: str, guess: AIRecognitionGuess) -> Optional[Dict[str, Any]]:
        if not guess.name:
            return None
        try:
            raw_text = path or title or guess.name
            meta = MetaInfo(raw_text)
            meta.name = guess.name
            meta.year = guess.year or None
            meta.begin_season = guess.season or None
            meta.begin_episode = guess.episode or None
            if guess.media_type == "tv" or meta.begin_season or meta.begin_episode:
                meta.type = MediaType.TV
            elif guess.media_type == "movie":
                meta.type = MediaType.MOVIE
            mediainfo = MediaChain().recognize_media(meta=meta, cache=False)
            if not mediainfo:
                return None
            return mediainfo.to_dict()
        except Exception as exc:
            if self._debug:
                logger.warning(f"[AI识别增强] 二次校验失败: {exc}")
            return None

    def _recognize(self, title: str, path: str = "") -> Dict[str, Any]:
        title = str(title or "").strip()
        path = str(path or "").strip()
        if not title and path:
            title = Path(path).name
        if not title:
            return {"success": False, "message": "标题为空"}
        try:
            guess = self._invoke_llm(title, path)
        except Exception as exc:
            self._record_failed_sample(
                {
                    "title": title,
                    "path": path,
                    "reason": f"llm_error:{exc}",
                }
            )
            return {"success": False, "message": f"LLM 调用失败: {exc}"}

        verified = self._verify_guess(title, path, guess)
        passed = bool(guess.name and guess.confidence >= self._confidence_threshold)
        if not passed:
            self._record_failed_sample(
                {
                    "title": title,
                    "path": path,
                    "guess": guess.model_dump(),
                    "reason": "low_confidence_or_empty_name",
                }
            )
        return {
            "success": passed,
            "message": "success" if passed else "识别结果置信度不足，已放弃注入",
            "guess": guess.model_dump(),
            "verified_media_info": verified,
        }

    def on_chain_name_recognize(self, event) -> None:
        if not self._enabled:
            return
        event_data = getattr(event, "event_data", None) or {}
        title, path = self._extract_title_path(event_data)
        if not title and not path:
            return
        result = self._recognize(title=title, path=path)
        if not result.get("success"):
            if self._debug:
                logger.info(f"[AI识别增强] 跳过注入: {title or path} - {result.get('message')}")
            return
        guess = result.get("guess") or {}
        if isinstance(event_data, dict):
            event_data["name"] = guess.get("name", "")
            event_data["year"] = guess.get("year", "")
            event_data["season"] = guess.get("season", 0)
            event_data["episode"] = guess.get("episode", 0)
            event_data["source_plugin"] = "AIRecognizerEnhancer"
            event_data["confidence"] = guess.get("confidence", 0)
            event_data["reason"] = guess.get("reason", "")

    async def api_health(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        llm_ready = bool(getattr(settings, "LLM_API_KEY", None))
        return {
            "success": True,
            "data": {
                "plugin_version": self.plugin_version,
                "enabled": self._enabled,
                "llm_ready": llm_ready,
                "llm_provider": getattr(settings, "LLM_PROVIDER", ""),
                "llm_model": getattr(settings, "LLM_MODEL", ""),
                "confidence_threshold": self._confidence_threshold,
                "request_timeout": self._request_timeout,
            },
        }

    async def api_recognize(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        title = str(body.get("title") or "").strip()
        path = str(body.get("path") or "").strip()
        result = self._recognize(title=title, path=path)
        return {
            "success": result.get("success", False),
            "message": result.get("message", ""),
            "data": {
                "guess": result.get("guess"),
                "verified_media_info": result.get("verified_media_info"),
            },
        }

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/health",
                "endpoint": self.api_health,
                "methods": ["GET"],
                "summary": "检查 AI识别增强 的运行状态",
            },
            {
                "path": "/recognize",
                "endpoint": self.api_recognize,
                "methods": ["POST"],
                "summary": "用当前 LLM 对失败标题做一次本地结构化识别测试",
            },
        ]

    def get_page(self) -> List[dict]:
        llm_ready = bool(getattr(settings, "LLM_API_KEY", None))
        return [
            {
                "component": "VCard",
                "content": [
                    {
                        "component": "VCardText",
                        "text": (
                            "AI识别增强第一版已经切到本地 LLM 方案，不再把外部 Gateway 当作必经链路。"
                            f"\n当前状态：{'已启用' if self._enabled else '未启用'}"
                            f"\nLLM：{getattr(settings, 'LLM_PROVIDER', '—')} / {getattr(settings, 'LLM_MODEL', '—')}"
                            f"\nLLM 可用：{'是' if llm_ready else '否'}"
                            f"\n置信度阈值：{self._confidence_threshold}"
                            f"\n请求超时：{self._request_timeout} 秒"
                            "\n\n当前会在 Chain NameRecognize 阶段回写 name/year/season/episode，供 MoviePilot 继续原生二次识别。"
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
                                            "text": "当前版本已改为直接复用 MoviePilot 当前启用的 LLM 配置，在原生识别失败后做本地结构化兜底。",
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
                                        "props": {"model": "enabled", "label": "启用 AI识别增强"},
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {"model": "debug", "label": "调试模式"},
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {"model": "save_failed_samples", "label": "保存低置信度样本"},
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
                                        "component": "VTextField",
                                        "props": {
                                            "model": "confidence_threshold",
                                            "label": "置信度阈值",
                                            "type": "number",
                                            "hint": "低于该值的结果不注入 MoviePilot，默认 0.65",
                                            "persistent-hint": True,
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
                                            "model": "request_timeout",
                                            "label": "LLM 请求超时（秒）",
                                            "type": "number",
                                            "hint": "默认 25 秒",
                                            "persistent-hint": True,
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
                                            "model": "max_retries",
                                            "label": "结构化输出重试次数",
                                            "type": "number",
                                            "hint": "默认 2 次",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ]
        return form, {
            "enabled": False,
            "debug": False,
            "confidence_threshold": 0.65,
            "request_timeout": 25,
            "max_retries": 2,
            "save_failed_samples": True,
        }
