from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser, get_current_user
from app.core.config import Settings, get_settings
from app.core.time_utils import to_iso_z
from app.db.session import get_db
from app.schemas.reports import RoundReportResponse
from app.schemas.rounds import (
    JudgeRequest,
    JudgeResponse,
    RoundContextResponse,
    RoundMessageItem,
    RoundMessagesResponse,
    SendMessageRequest,
    SendMessageResponse,
)
from app.services.round_service import (
    get_round_context_for_user,
    get_round_report_for_user,
    judge_round_for_user,
    list_round_messages_for_user,
    send_round_message,
)

router = APIRouter(prefix="/api/v1/rounds", tags=["rounds"])


@router.get("/{round_id}/messages", response_model=RoundMessagesResponse)
def get_round_messages(
    round_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> RoundMessagesResponse:
    result = list_round_messages_for_user(db=db, uid=current_user.uid, round_id=round_id)
    return RoundMessagesResponse(
        round_id=result.round_id,
        messages=[
            RoundMessageItem(
                message_id=item.message_id,
                role=item.role,
                content=item.content,
                is_evidence=item.is_evidence,
                evidence_reason=item.evidence_reason,
                created_at=to_iso_z(item.created_at) or "",
            )
            for item in result.messages
        ],
    )


@router.get("/{round_id}/context", response_model=RoundContextResponse)
def get_round_context(
    round_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> RoundContextResponse:
    result = get_round_context_for_user(
        db=db,
        uid=current_user.uid,
        round_id=round_id,
        settings=settings,
    )
    return RoundContextResponse(
        round_id=result.round_id,
        conversation_summary=result.conversation_summary,
        last_summarized_message_id=result.last_summarized_message_id,
        summary_updated_at=to_iso_z(result.summary_updated_at),
        total_message_count=result.total_message_count,
        recent_message_count=result.recent_message_count,
        recent_messages=[
            RoundMessageItem(
                message_id=item.message_id,
                role=item.role,
                content=item.content,
                is_evidence=item.is_evidence,
                evidence_reason=item.evidence_reason,
                created_at=to_iso_z(item.created_at) or "",
            )
            for item in result.recent_messages
        ],
    )


@router.post("/{round_id}/messages", response_model=SendMessageResponse)
def send_message(
    round_id: str,
    payload: SendMessageRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> SendMessageResponse:
    result = send_round_message(
        db=db,
        settings=settings,
        uid=current_user.uid,
        round_id=round_id,
        content=payload.content,
    )
    return SendMessageResponse(
        message_id=result.message_id,
        role=result.role,
        content=result.content,
        is_evidence=result.is_evidence,
        created_at=to_iso_z(result.created_at) or "",
    )


@router.post("/{round_id}/judge", response_model=JudgeResponse)
def submit_judgement(
    round_id: str,
    payload: JudgeRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> JudgeResponse:
    result = judge_round_for_user(
        db=db,
        uid=current_user.uid,
        round_id=round_id,
        is_fraud_judged=payload.is_fraud_judged,
    )
    return JudgeResponse(
        result=result.result,
        score_delta=result.score_delta,
        current_score=result.current_score,
        current_warning=result.current_warning,
        is_stage_cleared=result.is_stage_cleared,
    )


@router.get("/{round_id}/report", response_model=RoundReportResponse)
def get_round_report(
    round_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> RoundReportResponse:
    report = get_round_report_for_user(db=db, uid=current_user.uid, round_id=round_id)
    return RoundReportResponse(
        report_id=report.report_id,
        round_id=report.round_id,
        report_type=report.report_type,
        summary=report.summary,
        fraud_points=report.fraud_points,
    )
