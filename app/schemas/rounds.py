from typing import Optional

from app.schemas.base import ApiBaseModel


class SendMessageRequest(ApiBaseModel):
    content: str


class RoundMessageItem(ApiBaseModel):
    message_id: str
    role: str
    content: str
    is_evidence: bool
    evidence_reason: Optional[str] = None
    created_at: str


class RoundMessagesResponse(ApiBaseModel):
    status: str = "success"
    round_id: str
    messages: list[RoundMessageItem]


class RoundContextResponse(ApiBaseModel):
    status: str = "success"
    round_id: str
    conversation_summary: Optional[str] = None
    last_summarized_message_id: Optional[str] = None
    summary_updated_at: Optional[str] = None
    total_message_count: int
    recent_message_count: int
    recent_messages: list[RoundMessageItem]


class SendMessageResponse(ApiBaseModel):
    status: str = "success"
    message_id: str
    role: str
    content: str
    is_evidence: bool
    is_conversation_over: bool = False
    ended_reason: Optional[str] = None
    created_at: str


class JudgeRequest(ApiBaseModel):
    is_fraud_judged: bool


class JudgeResponse(ApiBaseModel):
    status: str = "success"
    result: str
    score_delta: int
    current_score: int
    current_warning: int
    is_stage_cleared: bool
