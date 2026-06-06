from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import ApiError
from app.core.time_utils import utc_now
from app.db.models import AICallLog, ChatMessage, Scenario, Stage, User
from app.repositories.rounds import add_ai_log, add_chat_message, get_user_round, list_round_messages
from app.repositories.stages import get_user_progress
from app.schemas.reports import FraudPoint
from app.services.ai import AIReply, call_normal_worker, get_ai_provider, should_use_normal_worker
from app.services.conversation_memory import RoundConversationContext, build_round_conversation_context, sync_round_conversation_context
from app.services.conversation_end import decide_end_reason
from app.services.fraud_placeholder import FRAUD_PLACEHOLDER_EVIDENCE_REASON, FRAUD_PLACEHOLDER_MESSAGE
from app.services.judge import JudgeResult, judge_round


@dataclass
class SendMessageResult:
    message_id: str
    role: str
    content: str
    is_evidence: bool
    is_conversation_over: bool
    ended_reason: str | None
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


def _build_attacker_user_meta(user_row: User | None) -> dict[str, str]:
    return {
        "이름": (user_row.nickname if user_row else "") or "사용자",
        "연령대": (user_row.age_group if user_row else "") or "미상",
        "직업": (user_row.job if user_row else "") or "미상",
        "은행": (user_row.main_bank if user_row else "") or "미상",
        "거주지": (user_row.residence if user_row else "") or "미상",
    }


def _auto_pass_completed_normal_round(*, db: Session, uid: str, round_obj, scenario: Scenario) -> None:
    if scenario.is_fraud:
        return
    if round_obj.status != "completed":
        return
    if round_obj.is_fraud_judged is not None:
        return

    stage = db.get(Stage, round_obj.stage_id)
    progress = get_user_progress(db, uid, round_obj.stage_id)
    if stage is None or progress is None:
        raise ApiError("?쇱슫???먯젙???꾩슂???곗씠?곌? ?꾨씫?섏뿀?듬땲??", status_code=500)

    judge_round(
        db=db,
        round_obj=round_obj,
        progress=progress,
        stage=stage,
        scenario=scenario,
        is_fraud_judged=False,
    )


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

    user_row = db.get(User, uid)
    attacker_user_meta = _build_attacker_user_meta(user_row)

    user_message = ChatMessage(
        round_id=round_obj.round_id,
        role="user",
        content=content,
    )
    add_chat_message(db, user_message)
    round_obj.user_turn_count += 1

    messages_before_ai = list_round_messages(db, str(round_obj.round_id))
    previous_messages = messages_before_ai[:-1] if messages_before_ai else []

    previous_ai_turn_count = sum(1 for message in previous_messages if message.role == "ai")
    min_ai_turns_before_evidence = 1 if settings.llm_studio_enabled else 0
    reveal_evidence = bool(
        scenario.is_fraud
        and round_obj.evidence_count == 0
        and previous_ai_turn_count >= min_ai_turns_before_evidence
    )

    if scenario.is_fraud and not settings.llm_studio_enabled:
        reply = AIReply(
            content=FRAUD_PLACEHOLDER_MESSAGE,
            is_evidence=True,
            evidence_reason=FRAUD_PLACEHOLDER_EVIDENCE_REASON,
            input_tokens=None,
            output_tokens=None,
            latency_ms=0,
        )
    elif should_use_normal_worker(settings) and not scenario.is_fraud:
        user_profile = {
            "name": (user_row.nickname if user_row else "") or "",
            "ageGroup": (user_row.age_group if user_row else "") or "",
            "job": (user_row.job if user_row else "") or "",
            "mainBank": (user_row.main_bank if user_row else "") or "",
            "residence": (user_row.residence if user_row else "") or "",
        }
        worker_messages = []
        for message in messages_before_ai:
            if message.role == "user":
                worker_messages.append({"role": "user", "content": message.content})
            elif message.role in ("ai", "assistant"):
                worker_messages.append({"role": "assistant", "content": message.content})
        reply = call_normal_worker(
            settings=settings,
            payload={
                "round_id": str(round_obj.round_id),
                "stage_id": round_obj.stage_id,
                "scenario_type": round_obj.scenario_type or scenario.genre,
                "scenario_variant": round_obj.scenario_variant or "default",
                "scenario_context": round_obj.scenario_context or {},
                "user_profile": user_profile,
                "messages": worker_messages,
            },
        )
    else:
        context_before_ai = sync_round_conversation_context(
            round_obj=round_obj,
            messages=previous_messages,
            recent_message_limit=settings.conversation_recent_message_limit,
        )
        provider = get_ai_provider(settings, scenario=scenario)
        reply = provider.generate_reply(
            settings=settings,
            scenario=scenario,
            conversation_summary=context_before_ai.conversation_summary,
            recent_history=context_before_ai.recent_messages,
            user_message=content,
            reveal_evidence=reveal_evidence,
            user_meta=attacker_user_meta,
        )

    ai_message = ChatMessage(
        round_id=round_obj.round_id,
        role="ai",
        content=reply.content,
        is_evidence=reply.is_evidence,
        evidence_reason=reply.evidence_reason,
        worker_is_conversation_over=reply.worker_is_conversation_over,
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

    ended_reason = decide_end_reason(
        user_text=content,
        ai_text=ai_message.content,
        user_turn_count=round_obj.user_turn_count,
        min_user_turns_for_natural_end=settings.min_user_turns_for_natural_end,
        max_user_turns=round_obj.max_user_turns or settings.normal_max_user_turns,
        scenario_type=round_obj.scenario_type,
        worker_is_conversation_over=reply.worker_is_conversation_over,
    )
    if ended_reason is not None:
        round_obj.status = "completed"
        round_obj.ended_at = utc_now()
        round_obj.ended_reason = ended_reason
        ai_message.backend_end_rule = ended_reason
        _auto_pass_completed_normal_round(db=db, uid=uid, round_obj=round_obj, scenario=scenario)

    db.commit()
    db.refresh(ai_message)

    return SendMessageResult(
        message_id=str(ai_message.message_id),
        role=ai_message.role,
        content=ai_message.content,
        is_evidence=ai_message.is_evidence,
        is_conversation_over=round_obj.status != "in_progress",
        ended_reason=round_obj.ended_reason,
        created_at=ai_message.created_at,
    )


def end_round_for_user(*, db: Session, uid: str, round_id: str) -> None:
    round_obj = get_user_round_or_404(db=db, round_id=round_id, uid=uid)
    if round_obj.status in ("completed", "judged"):
        return
    if round_obj.status != "in_progress":
        raise ApiError("이미 종료된 라운드입니다.", status_code=409)
    round_obj.status = "completed"
    round_obj.ended_at = utc_now()
    round_obj.ended_reason = "user_stop"
    db.commit()


def judge_round_for_user(
    *,
    db: Session,
    uid: str,
    round_id: str,
    is_fraud_judged: bool,
) -> JudgeResult:
    round_obj = get_user_round_or_404(db=db, round_id=round_id, uid=uid)

    if round_obj.status not in ("in_progress", "completed"):
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


