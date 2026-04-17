from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import ApiError
from app.db.models import AICallLog, ChatMessage, Scenario, Stage
from app.repositories.rounds import add_ai_log, add_chat_message, get_user_round, list_round_messages
from app.repositories.stages import get_user_progress
from app.schemas.reports import FraudPoint
from app.services.ai import get_ai_provider
from app.services.conversation_memory import RoundConversationContext, build_round_conversation_context, sync_round_conversation_context
from app.services.judge import JudgeResult, judge_round


@dataclass
class SendMessageResult:
    message_id: str
    role: str
    content: str
    is_evidence: bool
    created_at: object


@dataclass
class RoundMessageItemResult:
    message_id: str
    role: str
    content: str
    is_evidence: bool
    evidence_reason: str | None
    created_at: object


@dataclass
class RoundMessagesResult:
    round_id: str
    messages: list[RoundMessageItemResult]


@dataclass
class RoundReportResult:
    report_id: str
    round_id: str
    report_type: str
    summary: str
    fraud_points: list[FraudPoint]


@dataclass
class JudgeRoundResult:
    result: JudgeResult


@dataclass
class RoundContextResult:
    round_id: str
    conversation_summary: str | None
    last_summarized_message_id: str | None
    summary_updated_at: object | None
    total_message_count: int
    recent_message_count: int
    recent_messages: list[RoundMessageItemResult]


def get_user_round_or_404(*, db: Session, round_id: str, uid: str):
    round_obj = get_user_round(db, round_id, uid)
    if round_obj is None:
        raise ApiError("해당 라운드를 찾을 수 없습니다.", status_code=404)
    return round_obj


def _to_round_message_items(messages: list[ChatMessage]) -> list[RoundMessageItemResult]:
    return [
        RoundMessageItemResult(
            message_id=str(message.message_id),
            role=message.role,
            content=message.content,
            is_evidence=message.is_evidence,
            evidence_reason=message.evidence_reason,
            created_at=message.created_at,
        )
        for message in messages
    ]


def _build_context_for_round(
    *,
    round_obj,
    messages: list[ChatMessage],
    recent_message_limit: int,
) -> RoundConversationContext:
    context = build_round_conversation_context(
        messages=messages,
        recent_message_limit=recent_message_limit,
        summary_updated_at=round_obj.summary_updated_at,
    )

    if round_obj.conversation_summary and context.conversation_summary == round_obj.conversation_summary:
        context.summary_updated_at = round_obj.summary_updated_at

    return context


def list_round_messages_for_user(*, db: Session, uid: str, round_id: str) -> RoundMessagesResult:
    round_obj = get_user_round_or_404(db=db, round_id=round_id, uid=uid)
    messages = list_round_messages(db, str(round_obj.round_id))
    return RoundMessagesResult(round_id=str(round_obj.round_id), messages=_to_round_message_items(messages))


def get_round_context_for_user(*, db: Session, uid: str, round_id: str, settings: Settings) -> RoundContextResult:
    round_obj = get_user_round_or_404(db=db, round_id=round_id, uid=uid)
    messages = list_round_messages(db, str(round_obj.round_id))
    context = _build_context_for_round(
        round_obj=round_obj,
        messages=messages,
        recent_message_limit=settings.conversation_recent_message_limit,
    )

    return RoundContextResult(
        round_id=str(round_obj.round_id),
        conversation_summary=context.conversation_summary,
        last_summarized_message_id=context.last_summarized_message_id,
        summary_updated_at=context.summary_updated_at,
        total_message_count=context.total_message_count,
        recent_message_count=context.recent_message_count,
        recent_messages=_to_round_message_items(context.recent_messages),
    )


def send_round_message(
    *,
    db: Session,
    settings: Settings,
    uid: str,
    round_id: str,
    content: str,
) -> SendMessageResult:
    round_obj = get_user_round_or_404(db=db, round_id=round_id, uid=uid)

    if round_obj.status != "in_progress":
        raise ApiError("진행 중인 라운드에만 메시지를 전송할 수 있습니다.", status_code=409)

    scenario = db.get(Scenario, round_obj.scenario_id)
    if scenario is None:
        raise ApiError("라운드에 연결된 시나리오를 찾을 수 없습니다.", status_code=404)

    user_message = ChatMessage(
        round_id=round_obj.round_id,
        role="user",
        content=content,
    )
    add_chat_message(db, user_message)

    messages_before_ai = list_round_messages(db, str(round_obj.round_id))
    previous_messages = messages_before_ai[:-1] if messages_before_ai else []
    context_before_ai = sync_round_conversation_context(
        round_obj=round_obj,
        messages=previous_messages,
        recent_message_limit=settings.conversation_recent_message_limit,
    )

    previous_ai_turn_count = sum(1 for message in previous_messages if message.role == "ai")
    reveal_evidence = bool(
        scenario.is_fraud
        and round_obj.evidence_count == 0
        and previous_ai_turn_count >= 1
    )

    provider = get_ai_provider(settings)
    reply = provider.generate_reply(
        settings=settings,
        scenario=scenario,
        conversation_summary=context_before_ai.conversation_summary,
        recent_history=context_before_ai.recent_messages,
        user_message=content,
        reveal_evidence=reveal_evidence,
    )

    ai_message = ChatMessage(
        round_id=round_obj.round_id,
        role="ai",
        content=reply.content,
        is_evidence=reply.is_evidence,
        evidence_reason=reply.evidence_reason,
    )
    add_chat_message(db, ai_message)

    if reply.is_evidence:
        round_obj.evidence_count += 1

    ai_log = AICallLog(
        round_id=round_obj.round_id,
        call_type="chat_response",
        input_tokens=reply.input_tokens,
        output_tokens=reply.output_tokens,
        latency_ms=reply.latency_ms,
        is_evidence_detected=reply.is_evidence,
    )
    add_ai_log(db, ai_log)

    messages_after_ai = list_round_messages(db, str(round_obj.round_id))
    sync_round_conversation_context(
        round_obj=round_obj,
        messages=messages_after_ai,
        recent_message_limit=settings.conversation_recent_message_limit,
    )

    db.commit()
    db.refresh(ai_message)

    return SendMessageResult(
        message_id=str(ai_message.message_id),
        role=ai_message.role,
        content=ai_message.content,
        is_evidence=ai_message.is_evidence,
        created_at=ai_message.created_at,
    )


def judge_round_for_user(
    *,
    db: Session,
    uid: str,
    round_id: str,
    is_fraud_judged: bool,
) -> JudgeResult:
    round_obj = get_user_round_or_404(db=db, round_id=round_id, uid=uid)

    if round_obj.status != "in_progress":
        raise ApiError("이미 종료된 라운드입니다.", status_code=409)

    stage = db.get(Stage, round_obj.stage_id)
    scenario = db.get(Scenario, round_obj.scenario_id)
    progress = get_user_progress(db, uid, round_obj.stage_id)

    if stage is None or scenario is None or progress is None:
        raise ApiError("라운드 판정에 필요한 데이터가 누락되었습니다.", status_code=500)

    result = judge_round(
        db=db,
        round_obj=round_obj,
        progress=progress,
        stage=stage,
        scenario=scenario,
        is_fraud_judged=is_fraud_judged,
    )
    db.commit()
    return result


def get_round_report_for_user(*, db: Session, uid: str, round_id: str) -> RoundReportResult:
    round_obj = get_user_round_or_404(db=db, round_id=round_id, uid=uid)
    if round_obj.report is None:
        raise ApiError("아직 생성된 리포트가 없습니다.", status_code=404)

    fraud_points = [
        FraudPoint(
            message_id=str(item["message_id"]),
            reason=item["reason"],
            tip=item["tip"],
        )
        for item in (round_obj.report.fraud_points or [])
    ]

    return RoundReportResult(
        report_id=str(round_obj.report.report_id),
        round_id=str(round_obj.round_id),
        report_type=round_obj.report.report_type,
        summary=round_obj.report.summary,
        fraud_points=fraud_points,
    )
