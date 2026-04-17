from typing import Any

from pydantic import Field

from app.schemas.base import ApiBaseModel


class ErrorResponse(ApiBaseModel):
    status: str = "error"
    message: str
    data: Any = None


class SuccessEnvelope(ApiBaseModel):
    status: str = "success"
    message: str = Field(default="요청이 성공적으로 처리되었습니다.")
