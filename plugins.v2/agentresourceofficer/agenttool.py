from typing import Optional, Type

from pydantic import BaseModel

from app.agent.tools.base import MoviePilotTool
from app.core.plugin import PluginManager

from .schemas import (
    AssistantCapabilitiesToolInput,
    AssistantExecuteActionToolInput,
    AssistantExecuteActionsToolInput,
    AssistantHelpToolInput,
    AssistantPickToolInput,
    AssistantReadinessToolInput,
    AssistantRouteToolInput,
    AssistantSessionClearToolInput,
    AssistantSessionsClearToolInput,
    AssistantSessionsToolInput,
    AssistantSessionStateToolInput,
    AssistantWorkflowToolInput,
    HDHiveSearchSessionToolInput,
    HDHiveSessionPickToolInput,
    P115CancelPendingToolInput,
    P115PendingToolInput,
    P115QRCodeCheckToolInput,
    P115QRCodeStartToolInput,
    P115ResumePendingToolInput,
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


class AssistantRouteTool(MoviePilotTool):
    name: str = "agent_resource_officer_smart_entry"
    description: str = "Use the unified Agent资源官 smart entry for HDHive search, PanSou search, 115 login, or direct 115/Quark share links."
    args_schema: Type[BaseModel] = AssistantRouteToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        text = kwargs.get("text") or kwargs.get("keyword") or kwargs.get("url") or kwargs.get("action") or ""
        return f"正在通过 Agent资源官 统一入口处理：{text}"

    async def run(
        self,
        text: str = None,
        session: str = "default",
        session_id: str = None,
        path: str = None,
        mode: str = None,
        keyword: str = None,
        url: str = None,
        access_code: str = None,
        media_type: str = None,
        year: str = None,
        client_type: str = None,
        action: str = None,
        **kwargs,
    ) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_assistant_route(
            text=text,
            session=session,
            session_id=session_id,
            target_path=path,
            mode=mode,
            keyword=keyword,
            share_url=url,
            access_code=access_code,
            media_type=media_type,
            year=year,
            client_type=client_type,
            action=action,
        )


class AssistantPickTool(MoviePilotTool):
    name: str = "agent_resource_officer_smart_pick"
    description: str = "Continue the unified Agent资源官 smart-entry session by choosing an item, requesting details, or moving to the next page."
    args_schema: Type[BaseModel] = AssistantPickToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        session = kwargs.get("session", "default")
        choice = kwargs.get("choice", 0)
        action = kwargs.get("action", "")
        tail = f"动作 {action}" if action else f"选择 {choice}"
        return f"正在继续 Agent资源官 统一会话：{session}，{tail}"

    async def run(
        self,
        session: str = "default",
        session_id: str = None,
        choice: int = 0,
        action: str = None,
        path: str = None,
        **kwargs,
    ) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_assistant_pick(
            session=session,
            session_id=session_id,
            index=choice,
            action=action,
            target_path=path,
        )


class AssistantHelpTool(MoviePilotTool):
    name: str = "agent_resource_officer_help"
    description: str = "Show the recommended Agent资源官 workflow for MoviePilot Agent, including smart-entry examples, pick examples, and 115 login guidance."
    args_schema: Type[BaseModel] = AssistantHelpToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        return "正在查看 Agent资源官 使用帮助"

    async def run(self, session: str = "default", session_id: str = None, **kwargs) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_assistant_help(session=session, session_id=session_id)


class AssistantCapabilitiesTool(MoviePilotTool):
    name: str = "agent_resource_officer_capabilities"
    description: str = "Show the current Agent资源官 execution capabilities, supported structured smart-entry fields, defaults, and recommended call patterns for external agents."
    args_schema: Type[BaseModel] = AssistantCapabilitiesToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        return "正在查看 Agent资源官 能力说明"

    async def run(self, **kwargs) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_assistant_capabilities()


class AssistantReadinessTool(MoviePilotTool):
    name: str = "agent_resource_officer_readiness"
    description: str = "Check whether Agent资源官 is ready for external agents, including version, services, suggested entrypoints, and startup warnings."
    args_schema: Type[BaseModel] = AssistantReadinessToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        return "正在检查 Agent资源官 启动就绪状态"

    async def run(self, **kwargs) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_assistant_readiness()


class AssistantExecuteActionTool(MoviePilotTool):
    name: str = "agent_resource_officer_execute_action"
    description: str = "Execute a named Agent资源官 action template directly, so external agents can reuse action_templates without manually mapping each next step."
    args_schema: Type[BaseModel] = AssistantExecuteActionToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        return f"正在执行 Agent资源官 动作模板：{kwargs.get('name', '')}"

    async def run(
        self,
        name: str,
        session: str = "default",
        session_id: str = None,
        choice: int = None,
        path: str = None,
        keyword: str = None,
        media_type: str = None,
        year: str = None,
        url: str = None,
        access_code: str = None,
        client_type: str = None,
        kind: str = None,
        has_pending_p115: bool = None,
        stale_only: bool = False,
        all_sessions: bool = False,
        limit: int = 100,
        **kwargs,
    ) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_assistant_execute_action(
            name=name,
            session=session,
            session_id=session_id,
            choice=choice,
            target_path=path,
            keyword=keyword,
            media_type=media_type,
            year=year,
            share_url=url,
            access_code=access_code,
            client_type=client_type,
            kind=kind,
            has_pending_p115=has_pending_p115,
            stale_only=stale_only,
            all_sessions=all_sessions,
            limit=limit,
        )


class AssistantExecuteActionsTool(MoviePilotTool):
    name: str = "agent_resource_officer_execute_actions"
    description: str = "Execute a sequence of Agent资源官 action templates in one request, so external agents can reduce round trips and reuse action_templates directly."
    args_schema: Type[BaseModel] = AssistantExecuteActionsToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        actions = kwargs.get("actions") or []
        return f"正在批量执行 Agent资源官 动作模板：{len(actions)} 步"

    async def run(
        self,
        actions: list,
        session: str = "default",
        session_id: str = None,
        stop_on_error: bool = True,
        include_raw_results: bool = False,
        **kwargs,
    ) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_assistant_execute_actions(
            actions=actions,
            session=session,
            session_id=session_id,
            stop_on_error=stop_on_error,
            include_raw_results=include_raw_results,
        )


class AssistantWorkflowTool(MoviePilotTool):
    name: str = "agent_resource_officer_run_workflow"
    description: str = "Run a preset Agent资源官 workflow such as pansou_transfer, hdhive_candidates, hdhive_unlock, share_transfer, or p115_status with compact inputs."
    args_schema: Type[BaseModel] = AssistantWorkflowToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        return f"正在运行 Agent资源官 预设工作流：{kwargs.get('name', '')}"

    async def run(
        self,
        name: str,
        session: str = "default",
        session_id: str = None,
        keyword: str = None,
        choice: int = None,
        candidate_choice: int = None,
        resource_choice: int = None,
        path: str = None,
        url: str = None,
        access_code: str = None,
        media_type: str = None,
        year: str = None,
        client_type: str = None,
        stop_on_error: bool = True,
        include_raw_results: bool = False,
        **kwargs,
    ) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_assistant_workflow(
            name=name,
            session=session,
            session_id=session_id,
            keyword=keyword,
            choice=choice,
            candidate_choice=candidate_choice,
            resource_choice=resource_choice,
            target_path=path,
            share_url=url,
            access_code=access_code,
            media_type=media_type,
            year=year,
            client_type=client_type,
            stop_on_error=stop_on_error,
            include_raw_results=include_raw_results,
        )


class AssistantSessionStateTool(MoviePilotTool):
    name: str = "agent_resource_officer_session_state"
    description: str = "Inspect the current Agent资源官 assistant session, including stage, current page, selected candidate, and pending 115 task."
    args_schema: Type[BaseModel] = AssistantSessionStateToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        session = kwargs.get("session", "default")
        return f"正在查看 Agent资源官 会话状态：{session}"

    async def run(self, session: str = "default", session_id: str = None, **kwargs) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_assistant_session_state(session=session, session_id=session_id)


class AssistantSessionClearTool(MoviePilotTool):
    name: str = "agent_resource_officer_session_clear"
    description: str = "Clear the current Agent资源官 assistant session cache."
    args_schema: Type[BaseModel] = AssistantSessionClearToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        session = kwargs.get("session", "default")
        return f"正在清理 Agent资源官 会话：{session}"

    async def run(self, session: str = "default", session_id: str = None, **kwargs) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_assistant_session_clear(session=session, session_id=session_id)


class AssistantSessionsTool(MoviePilotTool):
    name: str = "agent_resource_officer_sessions"
    description: str = "List active Agent资源官 assistant sessions so external agents can recover, inspect, and resume the right workflow."
    args_schema: Type[BaseModel] = AssistantSessionsToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        return "正在查看 Agent资源官 活跃会话列表"

    async def run(self, kind: str = None, has_pending_p115: bool = None, limit: int = 20, **kwargs) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_assistant_sessions(
            kind=kind,
            has_pending_p115=has_pending_p115,
            limit=limit,
        )


class AssistantSessionsClearTool(MoviePilotTool):
    name: str = "agent_resource_officer_sessions_clear"
    description: str = "Clear one or more Agent资源官 assistant sessions by session_id, session name, filters, or full reset."
    args_schema: Type[BaseModel] = AssistantSessionsClearToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        return "正在清理 Agent资源官 活跃会话"

    async def run(
        self,
        session: str = None,
        session_id: str = None,
        kind: str = None,
        has_pending_p115: bool = None,
        stale_only: bool = False,
        all_sessions: bool = False,
        limit: int = 100,
        **kwargs,
    ) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_assistant_sessions_clear(
            session=session,
            session_id=session_id,
            kind=kind,
            has_pending_p115=has_pending_p115,
            stale_only=stale_only,
            all_sessions=all_sessions,
            limit=limit,
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


class P115PendingTool(MoviePilotTool):
    name: str = "agent_resource_officer_p115_pending"
    description: str = "Show the pending 115 transfer task for an assistant session, including target path, retry count, and last error."
    args_schema: Type[BaseModel] = P115PendingToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        return "正在通过 Agent资源官 查看待继续的 115 任务"

    async def run(self, session: str = "default", **kwargs) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_p115_pending(session=session)


class P115ResumePendingTool(MoviePilotTool):
    name: str = "agent_resource_officer_p115_resume_pending"
    description: str = "Retry the pending 115 transfer task for an assistant session."
    args_schema: Type[BaseModel] = P115ResumePendingToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        return "正在通过 Agent资源官 继续待处理的 115 任务"

    async def run(self, session: str = "default", **kwargs) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_p115_resume(session=session)


class P115CancelPendingTool(MoviePilotTool):
    name: str = "agent_resource_officer_p115_cancel_pending"
    description: str = "Cancel and clear the pending 115 transfer task for an assistant session."
    args_schema: Type[BaseModel] = P115CancelPendingToolInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        return "正在通过 Agent资源官 取消待处理的 115 任务"

    async def run(self, session: str = "default", **kwargs) -> str:
        plugin = _get_plugin()
        if not plugin:
            return "Agent资源官 插件未运行"
        return await plugin.tool_p115_cancel(session=session)
