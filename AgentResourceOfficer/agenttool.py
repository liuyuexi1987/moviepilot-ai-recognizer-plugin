from typing import Optional, Type

from pydantic import BaseModel

from app.agent.tools.base import MoviePilotTool
from app.core.plugin import PluginManager

from .schemas import (
    HDHiveSearchSessionToolInput,
    HDHiveSessionPickToolInput,
    P115QRCodeCheckToolInput,
    P115QRCodeStartToolInput,
    P115StatusToolInput,
    ShareRouteToolInput,
)


def _get_plugin():
    return PluginManager().running_plugins.get("AgentResourceOfficer")


class HDHiveSearchSessionTool(MoviePilotTool):
    name: str = "agent_resource_officer_hdhive_search"
    description: str = "Search HDHive by title, return candidate titles and a reusable session_id for the next selection step."
    args_schema: Type[BaseModel] = HDHiveSearchSessionToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        keyword = kwargs.get("keyword", "")
        return f"正在通过 Agent资源官搜索影巢候选：{keyword}"

    async def run(self, keyword: str, media_type: str = "movie", year: str = None, path: str = None, **kwargs) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_hdhive_search_session(
            keyword=keyword,
            media_type=media_type,
            year=year,
            target_path=path,
        )


class HDHiveSessionPickTool(MoviePilotTool):
    name: str = "agent_resource_officer_hdhive_pick"
    description: str = "Continue a previous HDHive session by selecting either a candidate title or a resource item."
    args_schema: Type[BaseModel] = HDHiveSessionPickToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        session_id = kwargs.get("session_id", "")
        choice = kwargs.get("choice", "")
        return f"正在继续 Agent资源官 会话：{session_id}，选择 {choice}"

    async def run(self, session_id: str, choice: int = 0, path: str = None, action: str = None, **kwargs) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_hdhive_pick_session(
            session_id=session_id,
            index=choice,
            target_path=path,
            action=action,
        )


class ShareRouteTool(MoviePilotTool):
    name: str = "agent_resource_officer_route_share"
    description: str = "Route a 115 or Quark share link into the configured transfer pipeline and save it into the target path."
    args_schema: Type[BaseModel] = ShareRouteToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        return "正在通过 Agent资源官 路由分享链接"

    async def run(self, url: str, path: str = None, access_code: str = None, **kwargs) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_route_share(
            share_url=url,
            access_code=access_code,
            target_path=path,
        )


class P115QRCodeStartTool(MoviePilotTool):
    name: str = "agent_resource_officer_p115_qrcode_start"
    description: str = "Generate a 115 login QR code using the p115client-compatible client session flow."
    args_schema: Type[BaseModel] = P115QRCodeStartToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        client_type = kwargs.get("client_type", "alipaymini")
        return f"正在通过 Agent资源官 生成 115 扫码二维码：{client_type}"

    async def run(self, client_type: str = "alipaymini", **kwargs) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_p115_qrcode_start(client_type=client_type)


class P115QRCodeCheckTool(MoviePilotTool):
    name: str = "agent_resource_officer_p115_qrcode_check"
    description: str = "Check the status of a previous 115 QR-code login and save the client session when login succeeds."
    args_schema: Type[BaseModel] = P115QRCodeCheckToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        return "正在通过 Agent资源官 检查 115 扫码状态"

    async def run(self, uid: str, time: str, sign: str, client_type: str = "alipaymini", **kwargs) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_p115_qrcode_check(
            uid=uid,
            time_value=time,
            sign=sign,
            client_type=client_type,
        )


class P115StatusTool(MoviePilotTool):
    name: str = "agent_resource_officer_p115_status"
    description: str = "Show the current 115 transfer readiness, default target path, and current session source."
    args_schema: Type[BaseModel] = P115StatusToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        return "正在通过 Agent资源官 查看 115 当前状态"

    async def run(self, **kwargs) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_p115_status()
