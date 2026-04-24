from typing import Optional

from pydantic import BaseModel, Field


class HDHiveSearchSessionToolInput(BaseModel):
    keyword: str = Field(..., description="要搜索的影片或剧集名称")
    media_type: str = Field(default="movie", description="媒体类型，movie 或 tv")
    year: Optional[str] = Field(default=None, description="可选年份，用于缩小候选范围")
    path: Optional[str] = Field(default=None, description="可选目标目录，不填则使用默认目录")


class HDHiveSessionPickToolInput(BaseModel):
    session_id: str = Field(..., description="上一步搜索返回的会话 ID")
    choice: int = Field(default=0, description="当前阶段要选择的编号，从 1 开始；详情或翻页时可为 0")
    path: Optional[str] = Field(default=None, description="可选目标目录，不填则使用会话中的目录")
    action: Optional[str] = Field(default=None, description="可选动作：detail/details/review/详情/审查 或 next/n/下一页")


class ShareRouteToolInput(BaseModel):
    url: str = Field(..., description="115 或夸克分享链接")
    path: Optional[str] = Field(default=None, description="目标目录")
    access_code: Optional[str] = Field(default=None, description="提取码，可选")


class P115QRCodeStartToolInput(BaseModel):
    client_type: Optional[str] = Field(default="alipaymini", description="115 扫码客户端类型，默认 alipaymini")


class P115QRCodeCheckToolInput(BaseModel):
    uid: str = Field(..., description="上一步二维码返回的 uid")
    time: str = Field(..., description="上一步二维码返回的 time")
    sign: str = Field(..., description="上一步二维码返回的 sign")
    client_type: Optional[str] = Field(default="alipaymini", description="客户端类型，需与生成二维码时保持一致")


class P115StatusToolInput(BaseModel):
    pass


class P115PendingToolInput(BaseModel):
    session: Optional[str] = Field(default="default", description="会话标识；不填则查看 default 会话")


class P115ResumePendingToolInput(BaseModel):
    session: Optional[str] = Field(default="default", description="会话标识；不填则继续 default 会话的待处理 115 任务")


class P115CancelPendingToolInput(BaseModel):
    session: Optional[str] = Field(default="default", description="会话标识；不填则取消 default 会话的待处理 115 任务")
