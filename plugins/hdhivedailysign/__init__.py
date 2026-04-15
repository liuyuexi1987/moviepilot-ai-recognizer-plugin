"""
影巢签到插件
版本: 1.0.0
作者: liuyuexi1987
功能:
- 自动完成影巢(HDHive)每日签到
- 支持签到失败重试
- 保存签到历史记录
- 提供详细的签到通知
- 默认使用代理访问
- 自动兼容 Next Server Action 签到接口

修改记录:
- v1.4.6: 增加普通/赌狗签到模式选择，并同步兼容旧接口与 Next Server Action 两种签到链路
- v1.4.5: 优先使用仍可用的 `/api/customer/user/checkin` 旧接口签到，接口不可用时再回退到 Next Server Action 解析
- v1.4.4: 修复 sign_history 原地修改导致的历史记录偶发不落库，并增强页面展示兜底
- v1.4.3: 签到历史与用户信息增加本地 JSON 兜底，避免数据库异常影响结果展示
- v1.4.2: 修复签到响应乱码导致的“已签到”误判
- v1.4.1: 修复新版前端 bundle 的 Action ID 识别逻辑，并增强 chunk 拉取重试
- v1.4.0: 改为动态发现站点当前签到 Action，兼容最新地址与新前端结构
- v1.1.0: 域名改为可配置，统一API拼接(Referer/Origin/接口)，精简日志
- v1.0.0: 初始版本，基于影巢网站结构实现自动签到
"""
import time
import requests
import re
import json
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

import jwt
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.plugins import _PluginBase
from typing import Any, List, Dict, Tuple, Optional
from app.log import logger
from app.schemas import NotificationType
from app.utils.http import RequestUtils

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class HDHiveDailySign(_PluginBase):
    # 插件名称
    plugin_name = "HDHive Daily Sign"
    # 插件描述
    plugin_desc = "自动完成影巢(HDHive)每日签到，支持失败重试和历史记录"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/liuyuexi1987/MoviePilot-Plugins/main/icons/hdhive.ico"
    # 插件版本
    plugin_version = "1.0.0"
    # 插件作者
    plugin_author = "liuyuexi1987"
    # 作者主页
    author_url = "https://github.com/liuyuexi1987"
    # 插件配置项ID前缀
    plugin_config_prefix = "hdhivedailysign_"
    # 加载顺序
    plugin_order = 1
    # 可使用的用户级别
    auth_level = 2

    # 私有属性
    _enabled = False
    _cookie = None
    _notify = False
    _gambler_mode = False
    _onlyonce = False
    _cron = None
    _max_retries = 3  # 最大重试次数
    _retry_interval = 30  # 重试间隔(秒)
    _history_days = 30  # 历史保留天数
    _manual_trigger = False
    # 定时器
    _scheduler: Optional[BackgroundScheduler] = None
    _current_trigger_type = None  # 保存当前执行的触发类型

    # 影巢站点配置（域名可配置）
    _base_url = "https://hdhive.com"
    _site_url = f"{_base_url}/"
    _user_info_api = f"{_base_url}/api/customer/user/info"
    _signin_action_name = "checkIn"
    _signin_action_id = None
    _signin_router_tree = ["", {"children": ["(app)", {"children": ["__PAGE__", {}, None, None]}, None, None]}, None, None, True]
    _history_fallback_file = "/config/logs/plugins/hdhivedailysign_history.json"
    _user_info_fallback_file = "/config/logs/plugins/hdhivedailysign_user_info.json"
    _login_api_candidates = [
        "/api/customer/user/login",
        "/api/customer/auth/login",
    ]
    _login_page = "/login"

    def init_plugin(self, config: dict = None):
        # 停止现有任务
        self.stop_service()

        logger.info("============= hdhivedailysign 初始化 =============")
        try:
            if config:
                self._enabled = config.get("enabled")
                self._cookie = config.get("cookie")
                self._notify = config.get("notify")
                self._gambler_mode = bool(config.get("gambler_mode"))
                self._cron = config.get("cron")
                self._onlyonce = config.get("onlyonce")
                # 新增：站点地址配置
                self._base_url = (config.get("base_url") or self._base_url or "").rstrip("/") or "https://hdhive.com"
                # 基于 base_url 统一构建接口地址
                self._site_url = f"{self._base_url}/"
                self._user_info_api = f"{self._base_url}/api/customer/user/info"
                self._signin_action_id = None
                self._max_retries = int(config.get("max_retries", 3))
                self._retry_interval = int(config.get("retry_interval", 30))
                self._history_days = int(config.get("history_days", 30))
                self._username = (config.get("username") or "").strip()
                self._password = (config.get("password") or "").strip()
                logger.info(f"影巢签到插件已加载，配置：enabled={self._enabled}, notify={self._notify}, cron={self._cron}")
            
            # 清理所有可能的延长重试任务
            self._clear_extended_retry_tasks()
            
            if self._onlyonce:
                logger.info("执行一次性签到")
                self._scheduler = BackgroundScheduler(timezone=settings.TZ)
                self._manual_trigger = True
                self._scheduler.add_job(func=self.sign, trigger='date',
                                    run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                                    name="影巢签到")
                self._onlyonce = False
                self.update_config({
                    "onlyonce": False,
                    "enabled": self._enabled,
                    "cookie": self._cookie,
                    "notify": self._notify,
                    "gambler_mode": self._gambler_mode,
                    "cron": self._cron,
                    "base_url": self._base_url,
                    "max_retries": self._max_retries,
                    "retry_interval": self._retry_interval,
                    "history_days": self._history_days
                })

                # 启动任务
                if self._scheduler.get_jobs():
                    self._scheduler.print_jobs()
                    self._scheduler.start()

        except Exception as e:
            logger.error(f"hdhivedailysign初始化错误: {str(e)}", exc_info=True)

    def sign(self, retry_count=0, extended_retry=0):
        """
        执行签到，支持失败重试。
        参数：
            retry_count: 常规重试计数
            extended_retry: 延长重试计数（0=首次尝试, 1=第一次延长重试, 2=第二次延长重试）
        """
        # 设置执行超时保护
        start_time = datetime.now()
        sign_timeout = 300  # 限制签到执行最长时间为5分钟
        
        # 保存当前执行的触发类型
        self._current_trigger_type = "手动触发" if self._is_manual_trigger() else "定时触发"
        
        # 如果是定时任务且不是重试，检查是否有正在运行的延长重试任务
        if retry_count == 0 and extended_retry == 0 and not self._is_manual_trigger():
            if self._has_running_extended_retry():
                logger.warning("检测到有正在运行的延长重试任务，跳过本次执行")
                return {
                    "date": datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
                    "status": "跳过: 有正在进行的重试任务"
                }
        
        logger.info("开始影巢签到")
        logger.debug(f"参数: retry={retry_count}, ext_retry={extended_retry}, trigger={self._current_trigger_type}")

        notification_sent = False  # 标记是否已发送通知
        sign_dict = None
        sign_status = None  # 记录签到状态

        # 根据重试情况记录日志
        if retry_count > 0:
            logger.debug(f"常规重试: 第{retry_count}次")
        if extended_retry > 0:
            logger.debug(f"延长重试: 第{extended_retry}次")
        
        try:
            if not self._is_manual_trigger() and self._is_already_signed_today():
                logger.info("根据历史记录，今日已成功签到，跳过本次执行")
                
                # 创建跳过记录
                sign_dict = {
                    "date": datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
                    "status": "跳过: 今日已签到",
                }
                
                # 获取最后一次成功签到的记录信息
                history = self._load_sign_history()
                today = datetime.now().strftime('%Y-%m-%d')
                today_success = [
                    record for record in history 
                    if record.get("date", "").startswith(today) 
                    and record.get("status") in ["签到成功", "已签到"]
                ]
                
                # 添加最后成功签到记录的详细信息
                if today_success:
                    last_success = max(today_success, key=lambda x: x.get("date", ""))
                    # 复制积分信息到跳过记录
                    sign_dict.update({
                        "message": last_success.get("message"),
                        "points": last_success.get("points"),
                        "days": last_success.get("days"),
                        "mode": last_success.get("mode", self._get_sign_mode_label())
                    })
                
                # 发送通知 - 通知用户已经签到过了
                if self._notify:
                    last_sign_time = self._get_last_sign_time()
                    
                    title = "【ℹ️ 影巢重复签到】"
                    text = (
                        f"📢 执行结果\n"
                        f"━━━━━━━━━━\n"
                        f"🕐 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"📍 方式：{self._current_trigger_type}\n"
                        f"🎯 模式：{sign_dict.get('mode', self._get_sign_mode_label())}\n"
                        f"ℹ️ 状态：今日已完成签到 ({last_sign_time})\n"
                    )
                    
                    # 如果有积分信息，添加到通知中
                    if "message" in sign_dict and sign_dict["message"]:
                        text += (
                            f"━━━━━━━━━━\n"
                            f"📊 签到信息\n"
                            f"💬 消息：{sign_dict.get('message', '—')}\n"
                            f"🎁 奖励：{sign_dict.get('points', '—')}\n"
                            f"📆 天数：{sign_dict.get('days', '—')}\n"
                        )
                    
                    text += f"━━━━━━━━━━"
                    
                    self.post_message(
                        mtype=NotificationType.SiteMessage,
                        title=title,
                        text=text
                    )
                try:
                    cookies = {}
                    if self._cookie:
                        for cookie_item in self._cookie.split(';'):
                            if '=' in cookie_item:
                                name, value = cookie_item.strip().split('=', 1)
                                cookies[name] = value
                    token = cookies.get('token')
                    if token:
                        self._fetch_user_info(cookies, token)
                except Exception:
                    pass
                
                return sign_dict
            
            if not self._cookie:
                # 尝试自动登录获取 Cookie
                new_cookie = self._auto_login()
                if new_cookie:
                    self._cookie = new_cookie
                    self.update_config({
                        "enabled": self._enabled,
                        "notify": self._notify,
                        "gambler_mode": self._gambler_mode,
                        "cron": self._cron,
                        "cookie": self._cookie,
                        "base_url": self._base_url,
                        "max_retries": self._max_retries,
                        "retry_interval": self._retry_interval,
                        "history_days": self._history_days,
                        "username": getattr(self, "_username", ""),
                        "password": getattr(self, "_password", ""),
                    })
                    logger.info("已通过自动登录获取新Cookie")
                else:
                    logger.error("未配置Cookie且自动登录失败")
                    sign_dict = {
                        "date": datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
                        "status": "签到失败: 未配置Cookie",
                        "mode": self._get_sign_mode_label(),
                    }
                    self._save_sign_history(sign_dict)
                    
                    if self._notify:
                        self.post_message(
                            mtype=NotificationType.SiteMessage,
                            title="【影巢签到失败】",
                            text="❌ 未配置Cookie，且自动登录失败，请在设置中添加Cookie或用户名密码"
                        )
                        notification_sent = True
                    return sign_dict
            
            logger.info("执行签到...")

            try:
                ensured = self._ensure_valid_cookie()
                if ensured:
                    self._cookie = ensured
                    self.update_config({
                        "enabled": self._enabled,
                        "notify": self._notify,
                        "gambler_mode": self._gambler_mode,
                        "cron": self._cron,
                        "cookie": self._cookie,
                        "base_url": self._base_url,
                        "max_retries": self._max_retries,
                        "retry_interval": self._retry_interval,
                        "history_days": self._history_days,
                        "username": getattr(self, "_username", ""),
                        "password": getattr(self, "_password", ""),
                    })
            except Exception:
                pass

            try:
                cookies = {}
                if self._cookie:
                    for cookie_item in self._cookie.split(';'):
                        if '=' in cookie_item:
                            name, value = cookie_item.strip().split('=', 1)
                            cookies[name] = value
                token = cookies.get('token')
                if token:
                    logger.info("尝试预拉取用户信息用于页面展示")
                    self._fetch_user_info(cookies, token)
            except Exception:
                pass
            
            state, message = self._signin_base()
            
            if state:
                logger.debug(f"签到API消息: {message}")
                
                if "已经签到" in message or "签到过" in message:
                    sign_status = "已签到"
                else:
                    sign_status = "签到成功"
                
                logger.debug(f"签到状态: {sign_status}")

                # --- 核心修复：插件自身逻辑计算连续签到天数 ---
                today_str = datetime.now().strftime('%Y-%m-%d')
                last_date_str = self._safe_get_data('last_success_date')
                consecutive_days = self._safe_get_data('consecutive_days', 0)

                if last_date_str == today_str:
                    # 当天重复运行，天数不变
                    pass
                elif last_date_str == (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'):
                    # 连续签到，天数+1
                    consecutive_days += 1
                else:
                    # 签到中断或首次签到，重置为1
                    consecutive_days = 1
                
                # 更新连续签到数据
                self._safe_save_data('consecutive_days', consecutive_days)
                self._safe_save_data('last_success_date', today_str)

                # 创建签到记录
                sign_dict = {
                    "date": datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
                    "status": sign_status,
                    "message": message,
                    "mode": self._get_sign_mode_label(),
                    "days": consecutive_days  # 使用计算出的天数
                }
                logger.info(f"影巢签到结果: {sign_status} - {message}")
                
                # 解析奖励积分
                points_match = re.search(r'获得 (\d+) 积分', message)
                sign_dict['points'] = int(points_match.group(1)) if points_match else "—"

                self._save_sign_history(sign_dict)
                self._send_sign_notification(sign_dict)
                return sign_dict
            else:
                # 签到失败, a real failure that needs retry
                logger.error(f"影巢签到失败: {message}")

                # 检测鉴权失败，尝试自动登录刷新 Cookie 后重试一次
                if any(k in (message or "") for k in ["未配置Cookie", "缺少'token'", "未授权", "Unauthorized", "token", "csrf", "登录已过期", "过期", "expired"]):
                    logger.info("检测到Cookie或鉴权问题，尝试自动登录刷新Cookie后重试一次")
                    new_cookie = self._auto_login()
                    if new_cookie:
                        self._cookie = new_cookie
                        self.update_config({
                            "enabled": self._enabled,
                            "notify": self._notify,
                            "gambler_mode": self._gambler_mode,
                            "cron": self._cron,
                            "cookie": self._cookie,
                            "base_url": self._base_url,
                            "max_retries": self._max_retries,
                            "retry_interval": self._retry_interval,
                            "history_days": self._history_days,
                            "username": getattr(self, "_username", ""),
                            "password": getattr(self, "_password", ""),
                        })
                        logger.info("自动登录成功，使用新Cookie重试签到")
                        state2, message2 = self._signin_base()
                        if state2:
                            sign_status = "签到成功" if "签到" in (message2 or "") and "已" not in message2 else "已签到"
                            sign_dict = {
                                "date": datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
                                "status": sign_status,
                                "message": message2,
                                "mode": self._get_sign_mode_label(),
                            }
                            # 解析奖励积分
                            points_match = re.search(r'获得 (\d+) 积分', message2 or "")
                            sign_dict['points'] = int(points_match.group(1)) if points_match else "—"
                            self._save_sign_history(sign_dict)
                            self._send_sign_notification(sign_dict)
                            return sign_dict
                
                # 暂不保存失败记录，视重试策略决定是否写入
                
                # 常规重试逻辑
                if retry_count < self._max_retries:
                    logger.info(f"将在{self._retry_interval}秒后进行第{retry_count+1}次常规重试...")
                    if self._notify:
                        self.post_message(
                            mtype=NotificationType.SiteMessage,
                            title="【影巢签到重试】",
                            text=f"❗ 签到失败: {message}，{self._retry_interval}秒后将进行第{retry_count+1}次常规重试"
                        )
                    time.sleep(self._retry_interval)
                    return self.sign(retry_count + 1, extended_retry)
                
                # 所有重试都失败
                sign_dict = {
                    "date": datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
                    "status": f"签到失败: {message}",
                    "message": message,
                    "mode": self._get_sign_mode_label()
                }
                self._save_sign_history(sign_dict)
                
                if self._notify:
                    self.post_message(
                        mtype=NotificationType.SiteMessage,
                        title="【❌ 影巢签到失败】",
                        text=f"❌ 签到失败: {message}，所有重试均已失败"
                    )
                    notification_sent = True
                return sign_dict
        
        except requests.RequestException as req_exc:
            # 网络请求异常处理
            logger.error(f"网络请求异常: {str(req_exc)}")
            # 添加执行超时检查
            if (datetime.now() - start_time).total_seconds() > sign_timeout:
                logger.error("签到执行时间超过5分钟，执行超时")
                sign_dict = {
                    "date": datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
                    "status": "签到失败: 执行超时",
                    "mode": self._get_sign_mode_label(),
                }
                self._save_sign_history(sign_dict)
                
                if self._notify and not notification_sent:
                    self.post_message(
                        mtype=NotificationType.SiteMessage,
                        title="【❌ 影巢签到失败】",
                        text="❌ 签到执行超时，已强制终止，请检查网络或站点状态"
                    )
                    notification_sent = True
                
                return sign_dict
        except Exception as e:
            logger.error(f"影巢 签到异常: {str(e)}", exc_info=True)
            sign_dict = {
                "date": datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
                "status": f"签到失败: {str(e)}",
                "mode": self._get_sign_mode_label(),
            }
            self._save_sign_history(sign_dict)
            
            if self._notify and not notification_sent:
                self.post_message(
                    mtype=NotificationType.SiteMessage,
                    title="【❌ 影巢签到失败】",
                    text=f"❌ 签到异常: {str(e)}"
                )
                notification_sent = True
            
            return sign_dict

    def _parse_cookie_string(self, cookie_str: Optional[str]) -> Dict[str, str]:
        cookies: Dict[str, str] = {}
        if not cookie_str:
            return cookies
        for cookie_item in cookie_str.split(';'):
            if '=' in cookie_item:
                name, value = cookie_item.strip().split('=', 1)
                cookies[name] = value
        return cookies

    def _get_user_id_from_token(self, token: Optional[str]) -> Optional[str]:
        if not token:
            return None
        try:
            decoded_token = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
            user_id = decoded_token.get('user_id') or decoded_token.get('sub') or decoded_token.get('id')
            return str(user_id) if user_id else None
        except Exception as e:
            logger.warning(f"从Token中解析用户ID失败，将使用默认Referer: {e}")
            return None

    def _build_signin_tree_header(self) -> str:
        return urllib.parse.quote(json.dumps(self._signin_router_tree, separators=(',', ':')))

    def _get_sign_mode_label(self, is_gambler: Optional[bool] = None) -> str:
        gambler_mode = self._gambler_mode if is_gambler is None else bool(is_gambler)
        return "赌狗签到" if gambler_mode else "普通签到"

    def _build_legacy_signin_payload(self) -> Dict[str, Any]:
        return {"is_gambler": True} if self._gambler_mode else {}

    def _build_signin_action_body(self) -> str:
        return json.dumps([bool(self._gambler_mode)], separators=(',', ':'))

    def _extract_signin_action_id_from_chunk(self, chunk_text: str) -> Optional[str]:
        if not chunk_text:
            return None

        patterns = [
            rf'createServerReference[\s\S]{{0,120}}?\("([a-f0-9]{{32,}})"[\s\S]{{0,1200}}?"{re.escape(self._signin_action_name)}"',
            rf'([a-f0-9]{{32,}}).{{0,240}}?"{re.escape(self._signin_action_name)}"',
        ]

        for pattern in patterns:
            match = re.search(pattern, chunk_text, re.S)
            if match:
                return match.group(1)
        return None

    def _normalize_response_text(self, text: str) -> str:
        if not text:
            return ""

        # 站点响应实际为 UTF-8，requests 在部分 text/x-component 场景下可能误解码成乱码
        if "ä½" in text or "å·²" in text or "ç­¾å°" in text:
            try:
                return text.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
            except Exception:
                return text
        return text

    def _read_json_fallback(self, file_path: str, default: Any = None) -> Any:
        try:
            path = Path(file_path)
            if not path.exists():
                return default
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"读取兜底文件失败: {file_path} - {e}")
            return default

    def _write_json_fallback(self, file_path: str, value: Any) -> None:
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"写入兜底文件失败: {file_path} - {e}")

    def _clone_json_value(self, value: Any) -> Any:
        if isinstance(value, (dict, list)):
            try:
                return json.loads(json.dumps(value, ensure_ascii=False))
            except Exception:
                if isinstance(value, dict):
                    return dict(value)
                return list(value)
        return value

    def _safe_get_data(self, key: str, default: Any = None, fallback_path: Optional[str] = None) -> Any:
        try:
            value = self.get_data(key)
            if value is not None:
                return self._clone_json_value(value)
        except Exception as e:
            logger.warning(f"读取插件数据失败: {key} - {e}")

        if fallback_path:
            return self._read_json_fallback(fallback_path, default)
        return default

    def _safe_save_data(self, key: str, value: Any, fallback_path: Optional[str] = None) -> None:
        normalized_value = self._clone_json_value(value)
        try:
            self.save_data(key=key, value=normalized_value)
        except Exception as e:
            logger.warning(f"写入插件数据失败: {key} - {e}")
        if fallback_path:
            self._write_json_fallback(fallback_path, normalized_value)

    def _get_history_signature(self, history: Any) -> Tuple[str, int]:
        if not isinstance(history, list):
            return "", 0

        latest_date = ""
        for record in history:
            if not isinstance(record, dict):
                continue
            record_date = str(record.get("date") or "")
            if record_date > latest_date:
                latest_date = record_date
        return latest_date, len(history)

    def _load_sign_history(self) -> List[dict]:
        history = self._safe_get_data("sign_history", default=[])
        fallback_history = self._read_json_fallback(self._history_fallback_file, [])

        if isinstance(history, list) and isinstance(fallback_history, list):
            db_signature = self._get_history_signature(history)
            fallback_signature = self._get_history_signature(fallback_history)
            if fallback_signature > db_signature:
                logger.info("检测到本地兜底历史更新，优先使用兜底签到历史")
                return fallback_history

        return history if isinstance(history, list) else fallback_history if isinstance(fallback_history, list) else []

    def _load_user_info(self) -> dict:
        user = self._safe_get_data("hdhive_user_info", default={}, fallback_path=self._user_info_fallback_file)
        return user if isinstance(user, dict) else {}

    def _discover_signin_action_id(self, cookies: Dict[str, str], token: str) -> Optional[str]:
        if self._signin_action_id:
            return self._signin_action_id

        referer = self._site_url
        user_id = self._get_user_id_from_token(token)
        if user_id:
            referer = f"{self._base_url}/user/{user_id}"

        headers = {
            'User-Agent': settings.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Origin': self._base_url,
            'Referer': referer,
            'Authorization': f'Bearer {token}',
        }

        logger.info("开始动态发现签到 Action ID")
        home_resp = requests.get(
            url=self._site_url,
            headers=headers,
            cookies=cookies,
            proxies=settings.PROXY,
            timeout=30,
            verify=False
        )
        if home_resp.status_code != 200:
            logger.error(f"拉取首页失败，状态码: {home_resp.status_code}")
            return None

        html = home_resp.text or ""
        chunk_paths = list(dict.fromkeys(re.findall(r'/_next/static/chunks/[A-Za-z0-9._-]+\.js', html)))
        if not chunk_paths:
            logger.error("首页未发现可用的前端 chunk，无法解析签到 Action")
            return None

        for chunk_path in chunk_paths:
            chunk_url = f"{self._base_url}{chunk_path}"
            for attempt in range(1, 4):
                try:
                    chunk_resp = requests.get(
                        url=chunk_url,
                        headers={
                            'User-Agent': settings.USER_AGENT,
                            'Accept': 'application/javascript,text/javascript,*/*;q=0.1',
                            'Connection': 'close',
                        },
                        proxies=settings.PROXY,
                        timeout=20,
                        verify=False
                    )
                    if chunk_resp.status_code != 200:
                        break

                    action_id = self._extract_signin_action_id_from_chunk(chunk_resp.text or "")
                    if action_id:
                        self._signin_action_id = action_id
                        logger.info(f"已发现签到 Action ID: {self._signin_action_id}")
                        return self._signin_action_id
                    break
                except Exception as e:
                    if attempt >= 3:
                        logger.warning(f"解析 chunk 失败: {chunk_url} - {e}")
                    else:
                        time.sleep(1)

        logger.error("未找到签到 Action ID，站点前端结构可能已变更")
        return None

    def _parse_signin_action_response(self, text: str) -> Tuple[bool, str]:
        text = self._normalize_response_text(text)
        if not text:
            return False, "签到响应为空"

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or ':' not in line:
                continue
            _, payload = line.split(':', 1)
            try:
                data = json.loads(payload)
            except Exception:
                continue

            if not isinstance(data, dict):
                continue

            # Next Server Action responses may wrap the actual payload under "response".
            if isinstance(data.get("response"), dict):
                data = data["response"]

            error = data.get("error")
            if isinstance(error, dict):
                message = self._normalize_response_text(error.get("description") or error.get("message") or "签到失败")
                if "已经签到" in message or "签到过" in message or "明天再来" in message:
                    return True, message
                return False, message

            message = self._normalize_response_text(data.get("message") or data.get("description"))
            success = data.get("success")
            if message:
                if success is False:
                    return False, message
                if "已经签到" in message or "签到过" in message or "明天再来" in message:
                    return True, message
                return True, message

        logger.error(f"无法解析签到响应: {text[:500]}")
        return False, "签到响应格式异常"

    def _signin_via_legacy_api(
        self,
        cookies: Dict[str, str],
        token: str,
        csrf_token: Optional[str],
        referer: str,
    ) -> Tuple[Optional[bool], str]:
        """
        优先尝试旧版 REST 接口签到。

        返回:
            - (True, message): 已成功处理，包含“签到成功”或“今日已签到”
            - (False, message): 已命中接口，但接口明确返回失败
            - (None, message): 当前站点未暴露旧接口，调用方应继续回退到 Next Server Action
        """
        signin_api = f"{self._base_url}/api/customer/user/checkin"
        payload = self._build_legacy_signin_payload()
        headers = {
            'User-Agent': settings.USER_AGENT,
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'Origin': self._base_url,
            'Referer': referer,
            'Authorization': f'Bearer {token}',
        }
        if csrf_token:
            headers['X-CSRF-TOKEN'] = csrf_token

        try:
            resp = requests.post(
                url=signin_api,
                headers=headers,
                cookies=cookies,
                json=payload,
                proxies=settings.PROXY,
                timeout=30,
                verify=False
            )
        except Exception as e:
            logger.warning(f"旧版签到接口请求异常，准备回退 Next Action: {e}")
            return None, f"旧版签到接口请求异常: {e}"

        if resp is None:
            return None, "旧版签到接口响应为空"

        if resp.status_code in (404, 405):
            logger.info(f"旧版签到接口不可用(HTTP {resp.status_code})，回退 Next Action")
            return None, f"旧版签到接口不可用: HTTP {resp.status_code}"

        payload = None
        try:
            payload = resp.json()
        except Exception:
            payload = None

        if isinstance(payload, dict):
            message = self._normalize_response_text(
                payload.get("description")
                or payload.get("message")
                or payload.get("code")
                or f"HTTP {resp.status_code}"
            )
            success = payload.get("success")
            if success is not False and resp.status_code < 400:
                logger.info("旧版签到接口调用成功")
                return True, message or "签到成功"
            if "已经签到" in message or "签到过" in message or "明天再来" in message:
                logger.info("旧版签到接口返回今日已签到")
                return True, message
            logger.warning(f"旧版签到接口返回失败: HTTP {resp.status_code}, message={message}")
            return False, message or f"HTTP {resp.status_code}"

        body = self._normalize_response_text(resp.text or "")
        if resp.status_code >= 400 and ("404 page not found" in body.lower() or "<html" in body.lower()):
            logger.info(f"旧版签到接口返回非 JSON 页面响应(HTTP {resp.status_code})，回退 Next Action")
            return None, f"旧版签到接口不可用: HTTP {resp.status_code}"

        logger.warning(f"旧版签到接口返回非 JSON 响应: HTTP {resp.status_code}, body={body[:200]}")
        return False, body[:200] if body else f"HTTP {resp.status_code}"

    def _signin_base(self) -> Tuple[bool, str]:
        """
        优先走旧版 REST 接口，失败后回退站点当前 Next Server Action
        """
        try:
            cookies = self._parse_cookie_string(self._cookie)
            if not cookies:
                return False, "未配置Cookie"

            token = cookies.get('token')
            csrf_token = cookies.get('csrf_access_token')
            if not token:
                return False, "Cookie中缺少'token'"

            user_id = self._get_user_id_from_token(token)
            referer = f"{self._base_url}/user/{user_id}" if user_id else self._site_url
            legacy_state, legacy_message = self._signin_via_legacy_api(cookies, token, csrf_token, referer)
            if legacy_state is not None:
                if legacy_state:
                    try:
                        self._fetch_user_info(cookies, token)
                    except Exception:
                        pass
                return legacy_state, legacy_message

            self._signin_action_id = None
            action_id = self._discover_signin_action_id(cookies, token)
            if not action_id:
                return False, "未能解析当前站点签到 Action，请更新插件或稍后重试"

            headers = {
                'User-Agent': settings.USER_AGENT,
                'Accept': 'text/x-component',
                'Content-Type': 'text/plain;charset=UTF-8',
                'Origin': self._base_url,
                'Referer': self._site_url,
                'Authorization': f'Bearer {token}',
                'next-action': action_id,
                'next-router-state-tree': self._build_signin_tree_header(),
            }
            if csrf_token:
                headers['x-csrf-token'] = csrf_token

            signin_res = requests.post(
                url=self._site_url,
                headers=headers,
                cookies=cookies,
                data=self._build_signin_action_body(),
                proxies=settings.PROXY,
                timeout=30,
                verify=False
            )

            if signin_res is None:
                return False, '签到请求失败，响应为空，请检查代理或网络环境'

            if signin_res.headers.get('x-nextjs-action-not-found') == '1':
                logger.error("站点返回 Action 不存在，可能刚刚重新部署")
                return False, "站点签到接口已刷新，请稍后重试"

            response_text = ""
            try:
                response_text = signin_res.content.decode("utf-8", errors="ignore")
            except Exception:
                response_text = signin_res.text or ""

            state, message = self._parse_signin_action_response(response_text)
            if state:
                try:
                    self._fetch_user_info(cookies, token)
                except Exception:
                    pass
                return True, message

            logger.error(f"签到失败, HTTP状态码: {signin_res.status_code}, 消息: {message}")
            return False, message

        except Exception as e:
            logger.error("签到流程发生未知异常", exc_info=True)
            return False, f'签到异常: {str(e)}'

    def _save_sign_history(self, sign_data):
        """
        保存签到历史记录
        """
        try:
            # 读取现有历史
            history = self._load_sign_history()

            # 确保日期格式正确
            if "date" not in sign_data:
                sign_data["date"] = datetime.today().strftime('%Y-%m-%d %H:%M:%S')

            history.append(sign_data)

            # 清理旧记录
            retention_days = int(self._history_days)
            now = datetime.now()
            valid_history = []

            for record in history:
                try:
                    # 尝试将记录日期转换为datetime对象
                    record_date = datetime.strptime(record["date"], '%Y-%m-%d %H:%M:%S')
                    # 检查是否在保留期内
                    if (now - record_date).days < retention_days:
                        valid_history.append(record)
                except (ValueError, KeyError):
                    # 如果记录日期格式不正确，尝试修复
                    logger.warning(f"历史记录日期格式无效: {record.get('date', '无日期')}")
                    # 添加新的日期并保留记录
                    record["date"] = datetime.today().strftime('%Y-%m-%d %H:%M:%S')
                    valid_history.append(record)

            # 保存历史
            self._safe_save_data(key="sign_history", value=valid_history, fallback_path=self._history_fallback_file)
            logger.info(f"保存签到历史记录，当前共有 {len(valid_history)} 条记录")

        except Exception as e:
            logger.error(f"保存签到历史记录失败: {str(e)}", exc_info=True)

    def _fetch_user_info(self, cookies: Dict[str, str], token: str) -> Optional[dict]:
        try:
            referer = self._site_url
            user_id = self._get_user_id_from_token(token)
            if user_id:
                referer = f"{self._base_url}/user/{user_id}"
            headers = {
                'User-Agent': settings.USER_AGENT,
                'Accept': 'application/json, text/plain, */*',
                'Origin': self._base_url,
                'Referer': referer,
                'Authorization': f'Bearer {token}',
            }
            resp = requests.get(self._user_info_api, headers=headers, cookies=cookies, proxies=settings.PROXY, timeout=30, verify=False)
            logger.info(f"拉取用户信息 API 状态码: {getattr(resp,'status_code','unknown')} CT: {getattr(resp.headers,'get',lambda k:'' )('Content-Type')}")
            data = {}
            try:
                data = resp.json()
            except Exception:
                data = {}
            # 统一解析 response.data / detail / data 结构
            detail = (data.get('response') or {}).get('data') or data.get('detail') or data.get('data') or {}
            if not isinstance(detail, dict):
                detail = {}
            info = {
                'id': detail.get('id') or detail.get('member_id'),
                'nickname': detail.get('nickname') or detail.get('member_name'),
                'avatar_url': detail.get('avatar_url') or detail.get('gravatar_url'),
                'created_at': detail.get('created_at'),
                'points': ((detail.get('user_meta') or {}).get('points')),
                'signin_days_total': ((detail.get('user_meta') or {}).get('signin_days_total')),
                'warnings_nums': detail.get('warnings_nums'),
            }
            # 若 API 未返回完整信息，尝试 RSC 页面解析
            if not info.get('nickname') or info.get('points') is None or info.get('signin_days_total') is None:
                try:
                    rsc_headers = {
                        'User-Agent': settings.USER_AGENT,
                        'Accept': 'text/x-component',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Origin': self._base_url,
                        'Referer': referer,
                        'rsc': '1',
                    }
                    rsc_url = referer
                    rsc_resp = requests.get(rsc_url, headers=rsc_headers, cookies=cookies, proxies=settings.PROXY, timeout=30, verify=False)
                    logger.info(f"RSC 用户页状态码: {getattr(rsc_resp,'status_code','unknown')} CT: {getattr(rsc_resp.headers,'get',lambda k:'' )('Content-Type')}")
                    rsc_text = rsc_resp.text or ''
                    import re as _re
                    m_nick = _re.search(r'"nickname":"([^"]+)"', rsc_text)
                    m_points = _re.search(r'"points":(\d+)', rsc_text)
                    m_days = _re.search(r'"signin_days_total":(\d+)', rsc_text)
                    m_avatar = _re.search(r'"avatar_url":"([^"]+)"', rsc_text)
                    m_created = _re.search(r'"created_at":"([^"]+)"', rsc_text)
                    if m_nick:
                        info['nickname'] = m_nick.group(1)
                    if m_points:
                        info['points'] = int(m_points.group(1))
                    if m_days:
                        info['signin_days_total'] = int(m_days.group(1))
                    if m_avatar:
                        info['avatar_url'] = m_avatar.group(1)
                    if m_created:
                        info['created_at'] = m_created.group(1)
                    if (not info.get('nickname') or info.get('points') is None or info.get('signin_days_total') is None) and '"user":' in rsc_text:
                        user_json = self._extract_rsc_object(rsc_text, 'user')
                        if user_json:
                            try:
                                obj = json.loads(user_json)
                                info['id'] = obj.get('id') or info.get('id')
                                info['nickname'] = obj.get('nickname') or info.get('nickname')
                                info['avatar_url'] = obj.get('avatar_url') or info.get('avatar_url')
                                info['created_at'] = obj.get('created_at') or info.get('created_at')
                                meta = obj.get('user_meta') or {}
                                if isinstance(meta, dict):
                                    if meta.get('points') is not None:
                                        info['points'] = meta.get('points')
                                    if meta.get('signin_days_total') is not None:
                                        info['signin_days_total'] = meta.get('signin_days_total')
                            except Exception:
                                pass
                except Exception:
                    pass
            self._safe_save_data('hdhive_user_info', info, fallback_path=self._user_info_fallback_file)
            return info
        except Exception as e:
            logger.warning(f"获取用户信息失败: {e}")
            return None

    def _extract_rsc_object(self, text: str, key: str) -> Optional[str]:
        try:
            marker = f'"{key}":'
            idx = text.find(marker)
            if idx == -1:
                return None
            brace_idx = text.find('{', idx + len(marker))
            if brace_idx == -1:
                return None
            depth = 0
            i = brace_idx
            in_str = False
            prev = ''
            while i < len(text):
                ch = text[i]
                if ch == '"' and prev != '\\':
                    in_str = not in_str
                if not in_str:
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            segment = text[brace_idx:i+1]
                            return segment
                prev = ch
                i += 1
            return None
        except Exception:
            return None

    def _send_sign_notification(self, sign_dict):
        """
        发送签到通知
        """
        if not self._notify:
            return

        status = sign_dict.get("status", "未知")
        message = sign_dict.get("message", "—")
        mode = sign_dict.get("mode", self._get_sign_mode_label())
        points = sign_dict.get("points", "—")
        days = sign_dict.get("days", "—")
        sign_time = sign_dict.get("date", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        user = self._load_user_info()
        nickname = user.get('nickname') or '—'
        user_points = user.get('points') if user.get('points') is not None else '—'
        signin_days_total = user.get('signin_days_total') if user.get('signin_days_total') is not None else '—'
        created_at = user.get('created_at') or '—'

        # 检查奖励信息是否为空
        info_missing = message == "—" and points == "—" and days == "—"

        # 获取触发方式
        trigger_type = self._current_trigger_type

        # 构建通知文本
        if "签到成功" in status:
            title = "【✅ 影巢签到成功】"

            if info_missing:
                text = (
                    f"📢 执行结果\n"
                    f"━━━━━━━━━━\n"
                    f"🕐 时间：{sign_time}\n"
                    f"📍 方式：{trigger_type}\n"
                    f"🎯 模式：{mode}\n"
                    f"✨ 状态：{status}\n"
                    f"⚠️ 详细信息获取失败，请手动查看\n"
                    f"━━━━━━━━━━\n"
                    f"👤 用户信息\n"
                    f"昵称：{nickname}\n"
                    f"积分：{user_points}\n"
                    f"累计签到天数（站点）：{signin_days_total}\n"
                    f"加入时间：{created_at}\n"
                    f"━━━━━━━━━━"
                )
            else:
                text = (
                    f"📢 执行结果\n"
                    f"━━━━━━━━━━\n"
                    f"🕐 时间：{sign_time}\n"
                    f"📍 方式：{trigger_type}\n"
                    f"🎯 模式：{mode}\n"
                    f"✨ 状态：{status}\n"
                    f"━━━━━━━━━━\n"
                    f"📊 签到信息\n"
                    f"💬 消息：{message}\n"
                    f"🎁 奖励：{points}\n"
                    f"📆 天数：{days}\n"
                    f"━━━━━━━━━━\n"
                    f"👤 用户信息\n"
                    f"昵称：{nickname}\n"
                    f"积分：{user_points}\n"
                    f"累计签到天数（站点）：{signin_days_total}\n"
                    f"加入时间：{created_at}\n"
                    f"━━━━━━━━━━"
                )
        elif "已签到" in status:
            title = "【ℹ️ 影巢重复签到】"

            if info_missing:
                text = (
                    f"📢 执行结果\n"
                    f"━━━━━━━━━━\n"
                    f"🕐 时间：{sign_time}\n"
                    f"📍 方式：{trigger_type}\n"
                    f"🎯 模式：{mode}\n"
                    f"✨ 状态：{status}\n"
                    f"ℹ️ 说明：今日已完成签到\n"
                    f"⚠️ 详细信息获取失败，请手动查看\n"
                    f"━━━━━━━━━━\n"
                    f"👤 用户信息\n"
                    f"昵称：{nickname}\n"
                    f"积分：{user_points}\n"
                    f"累计签到天数（站点）：{signin_days_total}\n"
                    f"加入时间：{created_at}\n"
                    f"━━━━━━━━━━"
                )
            else:
                text = (
                    f"📢 执行结果\n"
                    f"━━━━━━━━━━\n"
                    f"🕐 时间：{sign_time}\n"
                    f"📍 方式：{trigger_type}\n"
                    f"🎯 模式：{mode}\n"
                    f"✨ 状态：{status}\n"
                    f"ℹ️ 说明：今日已完成签到\n"
                    f"━━━━━━━━━━\n"
                    f"📊 签到信息\n"
                    f"💬 消息：{message}\n"
                    f"🎁 奖励：{points}\n"
                    f"📆 天数：{days}\n"
                    f"━━━━━━━━━━\n"
                    f"👤 用户信息\n"
                    f"昵称：{nickname}\n"
                    f"积分：{user_points}\n"
                    f"累计签到天数（站点）：{signin_days_total}\n"
                    f"加入时间：{created_at}\n"
                    f"━━━━━━━━━━"
                )
        else:
            title = "【❌ 影巢签到失败】"
            text = (
                f"📢 执行结果\n"
                f"━━━━━━━━━━\n"
                f"🕐 时间：{sign_time}\n"
                f"📍 方式：{trigger_type}\n"
                f"🎯 模式：{mode}\n"
                f"❌ 状态：{status}\n"
                f"━━━━━━━━━━\n"
                f"💡 可能的解决方法\n"
                f"• 检查Cookie是否有效\n"
                f"• 确认代理连接正常\n"
                f"• 查看站点是否正常访问\n"
                f"━━━━━━━━━━"
            )

        # 发送通知
        self.post_message(
            mtype=NotificationType.SiteMessage,
            title=title,
            text=text
        )

    def get_state(self) -> bool:
        logger.info(f"hdhivedailysign状态: {self._enabled}")
        return self._enabled

    def get_service(self) -> List[Dict[str, Any]]:
        if self._enabled and self._cron:
            logger.info(f"注册定时服务: {self._cron}")
            return [{
                "id": "hdhivedailysign",
                "name": "HDHive Daily Sign",
                "trigger": CronTrigger.from_crontab(self._cron),
                "func": self.sign,
                "kwargs": {}
            }]
        return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        返回插件配置的表单
        """
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'notify',
                                            'label': '开启通知',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'gambler_mode',
                                            'label': '默认赌狗签到',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': '立即运行一次',
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
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'cookie',
                                            'label': '站点Cookie',
                                            'placeholder': '请输入影巢站点Cookie值'
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
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'username',
                                            'label': '用户名/邮箱（用于自动登录）',
                                            'placeholder': '例如：email@example.com'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'password',
                                            'label': '密码（用于自动登录）',
                                            'placeholder': '请输入密码',
                                            'type': 'password'
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
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'base_url',
                                            'label': '站点地址',
                                            'placeholder': '例如：https://hdhive.online 或新域名',
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
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VCronField',
                                        'props': {
                                            'model': 'cron',
                                            'label': '签到周期'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'max_retries',
                                            'label': '最大重试次数',
                                            'type': 'number',
                                            'placeholder': '3'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'retry_interval',
                                            'label': '重试间隔(秒)',
                                            'type': 'number',
                                            'placeholder': '30'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'history_days',
                                            'label': '历史保留天数',
                                            'type': 'number',
                                            'placeholder': '30'
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
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'text': '【使用教程】\n1. 登录影巢站点（具体域名请在上方“站点地址”中填写），按F12打开开发者工具。\n2. 切换到"应用(Application)" -> "Cookie"，复制当前站点完整 Cookie。\n3. 确保至少包含 `token` 字段；`csrf_access_token` 为可选项。\n4. 如需赌狗签到，请打开上方“默认赌狗签到”开关。\n5. 粘贴 Cookie 后启用插件并保存。\n6. 若 Cookie 过期，可填写用户名/密码让插件自动重新登录。\n\n⚠️ 插件已改为自动兼容站点当前前端签到接口。若签到异常，请优先确认“站点地址”和登录态是否有效。'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "notify": True,
            "gambler_mode": False,
            "onlyonce": False,
            "cookie": "",
            "base_url": "https://hdhive.com",
            "cron": "0 8 * * *",
            "max_retries": 3,
            "retry_interval": 30,
            "history_days": 30,
            "username": "",
            "password": ""
        }

    def get_page(self) -> List[dict]:
        """
        构建插件详情页面，展示签到历史 (完全参照 qmjsign)
        """
        historys = self._load_sign_history()
        user = self._load_user_info()
        consecutive_days = self._safe_get_data('consecutive_days', 0) or 0

        info_card = []
        if user:
            avatar = user.get('avatar_url') or ''
            nickname = user.get('nickname') or '—'
            points = user.get('points') if user.get('points') is not None else '—'
            signin_days_total = user.get('signin_days_total') if user.get('signin_days_total') is not None else '—'
            created_at = user.get('created_at') or '—'
            info_card = [{
                'component': 'VCard',
                'props': {'variant': 'outlined', 'class': 'mb-4'},
                'content': [
                    {
                        'component': 'VCardTitle',
                        'props': {'class': 'd-flex align-center justify-space-between'},
                        'content': [
                            {
                                'component': 'div',
                                'content': [
                                    {'component': 'span', 'props': {'class': 'text-h6'}, 'text': '👤 影巢用户信息'},
                                    {'component': 'div', 'props': {'class': 'text-caption'}, 'text': f'加入时间：{created_at}'}
                                ]
                            },
                            {'component': 'VAvatar', 'props': {'size': 64}, 'content': [{'component': 'img', 'props': {'src': avatar, 'alt': nickname}}]}
                        ]
                    },
                    {'component': 'VDivider'},
                    {
                        'component': 'VCardText',
                        'content': [
                            {
                                'component': 'VRow',
                                'content': [
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VChip', 'props': {'variant': 'elevated', 'color': 'primary', 'class': 'mb-2'}, 'text': f'用户：{nickname}'}]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VChip', 'props': {'variant': 'elevated', 'color': 'amber-darken-2', 'class': 'mb-2'}, 'text': f'积分：{points}'}]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VChip', 'props': {'variant': 'elevated', 'color': 'success', 'class': 'mb-2'}, 'text': f'累计签到天数（站点）：{signin_days_total}'}]},
                                    {'component': 'VCol', 'props': {'cols': 12, 'md': 3}, 'content': [{'component': 'VChip', 'props': {'variant': 'elevated', 'color': 'cyan-darken-2', 'class': 'mb-2'}, 'text': f'连续签到天数（插件）：{consecutive_days}'}]},
                                ]
                            },
                            {'component': 'VAlert', 'props': {'type': 'info', 'variant': 'tonal', 'class': 'mt-2', 'text': '注：累计签到天数来自站点数据；插件统计的是连续天数，两者可能不同'}},
                        ]
                    }
                ]
            }]

        if not historys:
            return info_card + [{
                'component': 'VAlert',
                'props': {
                    'type': 'info', 'variant': 'tonal',
                    'text': '暂无签到记录，请等待下一次自动签到或手动触发一次。',
                    'class': 'mb-2'
                }
            }]

        historys = sorted(historys, key=lambda x: x.get("date", ""), reverse=True)

        history_rows = []
        for history in historys:
            status = history.get("status", "未知")
            if "成功" in status or "已签到" in status:
                status_color = "success"
            elif "失败" in status:
                status_color = "error"
            else:
                status_color = "info"

            history_rows.append({
                'component': 'tr',
                'content': [
                    {'component': 'td', 'props': {'class': 'text-caption'}, 'text': history.get("date", "")},
                    {
                        'component': 'td',
                        'content': [{
                            'component': 'VChip',
                            'props': {'color': status_color, 'size': 'small', 'variant': 'outlined'},
                            'text': status
                        }]
                    },
                    {'component': 'td', 'text': history.get('mode', '普通签到')},
                    {'component': 'td', 'text': history.get('message', '—')},
                    {'component': 'td', 'text': str(history.get('points', '—'))},
                    {'component': 'td', 'text': str(history.get('days', '—'))},
                ]
            })

        return info_card + [{
            'component': 'VCard',
            'props': {'variant': 'outlined', 'class': 'mb-4'},
            'content': [
                {'component': 'VCardTitle', 'props': {'class': 'text-h6'}, 'text': '📊 影巢签到历史'},
                {
                    'component': 'VCardText',
                    'content': [{
                        'component': 'VTable',
                        'props': {'hover': True, 'density': 'compact'},
                        'content': [
                            {
                                'component': 'thead',
                                'content': [{
                                    'component': 'tr',
                                    'content': [
                                        {'component': 'th', 'text': '时间'},
                                        {'component': 'th', 'text': '状态'},
                                        {'component': 'th', 'text': '模式'},
                                        {'component': 'th', 'text': '详情'},
                                        {'component': 'th', 'text': '奖励积分'},
                                        {'component': 'th', 'text': '连续天数'}
                                    ]
                                }]
                            },
                            {'component': 'tbody', 'content': history_rows}
                        ]
                    }]
                }
            ]
        }]

    def get_api(self) -> List[Dict[str, Any]]:
        return []

    def stop_service(self):
        """
        停止服务
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            logger.error(f"停止影巢签到服务失败: {str(e)}")

    def _is_manual_trigger(self) -> bool:
        """
        判断是否为手动触发
        """
        return getattr(self, '_manual_trigger', False)

    def _clear_extended_retry_tasks(self):
        """
        清理所有延长重试任务
        """
        try:
            if self._scheduler:
                jobs = self._scheduler.get_jobs()
                for job in jobs:
                    if "延长重试" in job.name:
                        self._scheduler.remove_job(job.id)
                        logger.info(f"清理延长重试任务: {job.name}")
        except Exception as e:
            logger.warning(f"清理延长重试任务失败: {str(e)}")

    def _has_running_extended_retry(self) -> bool:
        """
        检查是否有正在运行的延长重试任务
        """
        try:
            if self._scheduler:
                jobs = self._scheduler.get_jobs()
                for job in jobs:
                    if "延长重试" in job.name:
                        return True
            return False
        except Exception:
            return False

    def _is_already_signed_today(self) -> bool:
        """
        检查今天是否已经签到成功
        """
        history = self._load_sign_history()
        if not history:
            return False
        today = datetime.now().strftime('%Y-%m-%d')
        # 查找今日是否有成功签到记录
        return any(
            record.get("date", "").startswith(today)
            and record.get("status") in ["签到成功", "已签到"]
            for record in history
        )

    def _ensure_valid_cookie(self) -> Optional[str]:
        try:
            if not self._cookie:
                return None
            token = None
            for part in self._cookie.split(';'):
                p = part.strip()
                if p.startswith('token='):
                    token = p.split('=', 1)[1]
                    break
            if not token:
                return None
            try:
                decoded = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
                exp_ts = decoded.get('exp')
            except Exception:
                exp_ts = None
            if exp_ts and isinstance(exp_ts, (int, float)):
                import time as _t
                now_ts = int(_t.time())
                if exp_ts <= now_ts:
                    return self._auto_login()
            return None
        except Exception:
            return None

    def _auto_login(self) -> Optional[str]:
        try:
            if not getattr(self, "_username", None) or not getattr(self, "_password", None):
                logger.warning("未配置用户名或密码，无法自动登录")
                return None
            try:
                import cloudscraper
                scraper = cloudscraper.create_scraper()
                logger.info("自动登录: 使用 cloudscraper")
            except Exception as e:
                logger.warning(f"cloudscraper 不可用，将尝试 requests：{e}")
                scraper = requests
                logger.info("自动登录: 回退到 requests")
            # 预热登录页，拿到初始 Cookie
            login_url = f"{self._base_url}{self._login_page}"
            try:
                logger.info(f"自动登录: 预热 {login_url}")
                resp_warm = scraper.get(login_url, timeout=30, proxies=settings.PROXY)
                logger.info(f"自动登录: 预热状态码 {getattr(resp_warm, 'status_code', 'unknown')} Content-Type {getattr(resp_warm.headers, 'get', lambda k: '')('Content-Type')}")
            except Exception:
                pass
            # 尝试 API 登录候选
            for path in self._login_api_candidates:
                url = f"{self._base_url}{path}"
                headers = {
                    'User-Agent': settings.USER_AGENT,
                    'Accept': 'application/json, text/plain, */*',
                    'Origin': self._base_url,
                    'Referer': login_url,
                    'Content-Type': 'application/json'
                }
                payload = {
                    'username': getattr(self, "_username", ""),
                    'password': getattr(self, "_password", "")
                }
                try:
                    logger.info(f"自动登录: 尝试 API 登录 {url}")
                    resp = scraper.post(url, headers=headers, json=payload, timeout=30, proxies=settings.PROXY)
                    logger.info(f"自动登录: API 登录状态码 {getattr(resp, 'status_code', 'unknown')} Content-Type {getattr(resp.headers, 'get', lambda k: '')('Content-Type')}")
                    # 成功条件：响应包含 set-cookie 或 JSON 内含 meta.access_token
                    cookies_dict = None
                    try:
                        cookies_dict = getattr(resp, 'cookies', None).get_dict() if getattr(resp, 'cookies', None) else {}
                    except Exception:
                        cookies_dict = {}
                    token_cookie = cookies_dict.get('token')
                    csrf_cookie = cookies_dict.get('csrf_access_token')
                    if not token_cookie:
                        try:
                            data = resp.json()
                            logger.info(f"自动登录: API 登录返回JSON keys {list(data.keys()) if isinstance(data, dict) else 'non-dict'}")
                            meta = (data.get('meta') or {})
                            acc = meta.get('access_token')
                            ref = meta.get('refresh_token')
                            if acc:
                                # 将 access_token 写入 token Cookie
                                if hasattr(scraper, 'cookies'):
                                    try:
                                        scraper.cookies.set('token', acc, domain=self._base_url.replace('https://','').replace('http://',''))
                                        token_cookie = acc
                                    except Exception:
                                        token_cookie = acc
                                else:
                                    token_cookie = acc
                        except Exception:
                            pass
                    if token_cookie:
                        cookie_items = [f"token={token_cookie}"]
                        if csrf_cookie:
                            cookie_items.append(f"csrf_access_token={csrf_cookie}")
                        cookie_str = "; ".join(cookie_items)
                        logger.info("API登录成功，已生成Cookie")
                        return cookie_str
                except Exception as e:
                    logger.debug(f"API登录候选失败: {path} -> {e}")
            # 尝试 Next.js Server Action 登录
            url = f"{self._base_url}{self._login_page}"
            headers = {
                'User-Agent': settings.USER_AGENT,
                'Accept': 'text/x-component',
                'Origin': self._base_url,
                'Referer': login_url,
                'Content-Type': 'text/plain;charset=UTF-8'
            }
            # 从预热页面尝试提取 next-action token
            next_action_token = None
            try:
                warm_text = getattr(resp_warm, 'text', '') or ''
                # 常见形式：next-action":"<token>" 或 name="next-action" value="<token>"
                import re as _re
                m = _re.search(r'next-action"\s*:\s*"([a-fA-F0-9]{16,64})"', warm_text)
                if not m:
                    m = _re.search(r'name="next-action"\s+value="([a-fA-F0-9]{16,64})"', warm_text)
                if m:
                    next_action_token = m.group(1)
                    headers['next-action'] = next_action_token
                    # 参考样例的最小 router state（静态值）
                    headers['next-router-state-tree'] = '%5B%22%22%2C%7B%22children%22%3A%5B%22(auth)%22%2C%7B%22children%22%3A%5B%22login%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2C%22%2Flogin%22%2C%22refresh%22%5D%7D%5D%7D%2Cnull%2Cnull%2Ctrue%5D%7D%2Cnull%2Cnull%2Ctrue%5D'
                    logger.info(f"自动登录: 提取 next-action={next_action_token}")
                else:
                    logger.info("自动登录: 未在页面提取到 next-action token")
            except Exception as e:
                logger.debug(f"自动登录: 提取 next-action 失败: {e}")
            body = json.dumps([{'username': getattr(self, "_username", ""), 'password': getattr(self, "_password", "")}])
            try:
                logger.info(f"自动登录: 尝试 Server Action 登录 {url}")
                resp = scraper.post(url, headers=headers, data=body, timeout=30, proxies=settings.PROXY)
                logger.info(f"自动登录: SA 登录状态码 {getattr(resp, 'status_code', 'unknown')} Content-Type {getattr(resp.headers, 'get', lambda k: '')('Content-Type')}")
                cookies_dict = None
                try:
                    cookies_dict = getattr(resp, 'cookies', None).get_dict() if getattr(resp, 'cookies', None) else {}
                except Exception:
                    cookies_dict = {}
                token_cookie = cookies_dict.get('token')
                csrf_cookie = cookies_dict.get('csrf_access_token')
                if token_cookie:
                    cookie_items = [f"token={token_cookie}"]
                    if csrf_cookie:
                        cookie_items.append(f"csrf_access_token={csrf_cookie}")
                    cookie_str = "; ".join(cookie_items)
                    logger.info("Server Action 登录成功，已生成Cookie")
                    return cookie_str
            except Exception as e:
                logger.warning(f"Server Action 登录失败: {e}")
            # 浏览器自动化兜底：使用 Playwright 直接执行页面登录并读取 Cookie
            try:
                from playwright.sync_api import sync_playwright
                logger.info("自动登录: 尝试使用 Playwright 浏览器自动化")
                proxy = None
                try:
                    pxy = settings.PROXY or {}
                    server = pxy.get('http') or pxy.get('https')
                    if server:
                        proxy = {"server": server}
                except Exception:
                    proxy = None
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True, proxy=proxy) if proxy else pw.chromium.launch(headless=True)
                    context = browser.new_context()
                    page = context.new_page()
                    page.goto(login_url, wait_until="domcontentloaded")
                    # 选择器启发式
                    selectors = [
                        "input[name='username']",
                        "input[name='email']",
                        "input[type='email']",
                        "input[placeholder*='邮箱']",
                        "input[placeholder*='email']",
                        "input[placeholder*='用户名']",
                    ]
                    pwd_selectors = [
                        "input[name='password']",
                        "input[type='password']",
                        "input[placeholder*='密码']",
                    ]
                    for sel in selectors:
                        try:
                            if page.query_selector(sel):
                                page.fill(sel, getattr(self, "_username", ""))
                                break
                        except Exception:
                            continue
                    for sel in pwd_selectors:
                        try:
                            if page.query_selector(sel):
                                page.fill(sel, getattr(self, "_password", ""))
                                break
                        except Exception:
                            continue
                    # 点击提交按钮
                    try:
                        btn = page.query_selector("button[type='submit']") or page.query_selector("button:has-text('登录')") or page.query_selector("button:has-text('Login')")
                        if btn:
                            btn.click()
                        else:
                            page.keyboard.press("Enter")
                    except Exception:
                        page.keyboard.press("Enter")
                    # 等待可能的跳转或网络静止
                    try:
                        page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        pass
                    # 读取 Cookie
                    cookies = context.cookies()
                    token_cookie = None
                    csrf_cookie = None
                    for c in cookies:
                        if c.get('name') == 'token':
                            token_cookie = c.get('value')
                        elif c.get('name') == 'csrf_access_token':
                            csrf_cookie = c.get('value')
                    context.close()
                    browser.close()
                    if token_cookie:
                        cookie_items = [f"token={token_cookie}"]
                        if csrf_cookie:
                            cookie_items.append(f"csrf_access_token={csrf_cookie}")
                        cookie_str = "; ".join(cookie_items)
                        logger.info("Playwright 登录成功，已生成Cookie")
                        return cookie_str
                logger.error("自动登录失败，未获取到有效Cookie")
                return None
            except Exception as e:
                logger.error(f"Playwright 自动登录异常: {e}")
                logger.error("自动登录失败，未获取到有效Cookie")
                return None
        except Exception as e:
            logger.error(f"自动登录异常: {str(e)}")
            return None

    def _get_last_sign_time(self) -> str:
        """
        获取最后一次签到成功的时间
        """
        history = self._load_sign_history()
        if history:
            try:
                last_success = max([
                    record for record in history if record.get("status") in ["签到成功", "已签到"]
                ], key=lambda x: x.get("date", ""))
                return last_success.get("date")
            except ValueError:
                return "从未"
        return "从未"
