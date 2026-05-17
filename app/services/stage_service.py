from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time_utils import utc_now
from app.db.models import ChatMessage, Round, User, UserStageProgress
from app.repositories.rounds import (
    add_chat_message,
    create_round,
    get_latest_in_progress_round_for_stage,
    list_round_messages,
    list_user_stage_rounds,
)
from app.repositories.stages import (
    count_user_stage_rounds,
    create_user_progress,
    get_active_stage,
    get_user_progress,
    list_active_stages,
    list_user_progresses,
)
from app.services.ai import call_normal_worker
from app.services.fraud_placeholder import FRAUD_PLACEHOLDER_AI_NAME, FRAUD_PLACEHOLDER_SITUATION_PROMPT
from app.services.normal_prompt_catalog import build_normal_prompt_context
from app.services.scenario_selector import select_scenario_for_stage


@dataclass
class StageListRow:
    stage_id: int
    title: str
    description: str | None
    thumbnail_url: str | None
    is_random: bool
    stage_score: int
    warning_count: int
    total_round_count: int
    best_round_count: int | None
    is_cleared: bool


@dataclass
class StageEnterResult:
    progress: UserStageProgress
    total_round_count: int
    has_incomplete_round: bool


@dataclass
class StageRoundRow:
    round_id: str
    scenario_id: str
    scenario_title: str
    is_fraud_scenario: bool
    status: str
    is_fraud_judged: bool | None
    evidence_count: int
    result: str | None
    score_delta: int | None
    started_at: object
    ended_at: object | None


@dataclass
class RoundStartResult:
    round_obj: Round
    scenario_id: str
    situation_prompt: str
    ai_name: str
    ai_image_url: str | None
    initial_message: ChatMessage | None = None


class StageNotFoundError(ValueError):
    pass


def _build_worker_user_profile(user_row: User | None) -> dict[str, str]:
    return {
        "name": (user_row.nickname if user_row else "") or "",
        "ageGroup": (user_row.age_group if user_row else "") or "",
        "job": (user_row.job if user_row else "") or "",
        "mainBank": (user_row.main_bank if user_row else "") or "",
        "residence": (user_row.residence if user_row else "") or "",
    }


def _build_fraud_round_context(*, stage_title: str, scenario_genre: str, ai_name: str, situation_prompt: str) -> dict:
    return {
        "display_label": stage_title,
        "counterpart_role": ai_name,
        "situation": situation_prompt,
        "scenario_family": scenario_genre,
    }


def _reset_progress_for_new_attempt(progress: UserStageProgress) -> None:
    if not progress.is_cleared:
        return
    progress.stage_score = 0
    progress.total_round_count = 0


def list_stages_for_user(*, db: Session, uid: str) -> list[StageListRow]:
    stages = list_active_stages(db)
    progress_rows = list_user_progresses(db, uid)
    progress_map = {row.stage_id: row for row in progress_rows}

    items: list[StageListRow] = []
    for stage in stages:
        progress = progress_map.get(stage.stage_id)
        items.append(
            StageListRow(
                stage_id=stage.stage_id,
                title=stage.title,
                description=stage.description,
                thumbnail_url=stage.thumbnail_url,
                is_random=stage.is_random,
                stage_score=progress.stage_score if progress else 0,
                warning_count=progress.warning_count if progress else 0,
                total_round_count=progress.total_round_count if progress else 0,
                best_round_count=progress.best_round_count if progress else None,
                is_cleared=progress.is_cleared if progress else False,
            )
        )
    return items


def enter_stage_for_user(*, db: Session, uid: str, stage_id: int) -> StageEnterResult:
    stage = get_active_stage(db, stage_id)
    if stage is None:
        raise StageNotFoundError("존재하지 않는 스테이지입니다.")

    progress = get_user_progress(db, uid, stage_id)
    if progress is None:
        progress = create_user_progress(db, uid, stage_id)

    incomplete_round = get_latest_in_progress_round_for_stage(db, uid, stage_id)
    if incomplete_round is None:
        _reset_progress_for_new_attempt(progress)

    progress.updated_at = utc_now()

    db.commit()
    db.refresh(progress)
    return StageEnterResult(
        progress=progress,
        total_round_count=progress.total_round_count,
        has_incomplete_round=incomplete_round is not None,
    )


def start_round_for_user(*, db: Session, uid: str, stage_id: int) -> RoundStartResult:
    stage = get_active_stage(db, stage_id)
    if stage is None:
        raise StageNotFoundError("존재하지 않는 스테이지입니다.")

    progress = get_user_progress(db, uid, stage_id)
    if progress is None:
        progress = create_user_progress(db, uid, stage_id)

    existing_round = get_latest_in_progress_round_for_stage(db, uid, stage_id)
    if existing_round is not None and existing_round.scenario is not None:
        existing_initial_message = next(
            (msg for msg in list_round_messages(db, str(existing_round.round_id)) if msg.role in ("ai", "assistant")),
            None,
        )
        progress.updated_at = utc_now()
        db.commit()
        db.refresh(progress)
        return RoundStartResult(
            round_obj=existing_round,
            scenario_id=str(existing_round.scenario.scenario_id),
            situation_prompt=existing_round.scenario.situation_prompt,
            ai_name=existing_round.scenario.ai_name,
            ai_image_url=existing_round.scenario.ai_image_url,
            initial_message=existing_initial_message,
        )

    _reset_progress_for_new_attempt(progress)

    scenario = select_scenario_for_stage(db, stage)
    user_row = db.get(User, uid)
    user_profile = _build_worker_user_profile(user_row)
    if scenario.is_fraud:
        scenario.situation_prompt = FRAUD_PLACEHOLDER_SITUATION_PROMPT
        scenario.ai_name = FRAUD_PLACEHOLDER_AI_NAME
        scenario_type = scenario.genre
        scenario_variant = "fraud"
        scenario_context = _build_fraud_round_context(
            stage_title=stage.title,
            scenario_genre=scenario.genre,
            ai_name=scenario.ai_name,
            situation_prompt=scenario.situation_prompt,
        )
    else:
        normal_prompt = build_normal_prompt_context(genre=scenario.genre, user_profile=user_profile)
        scenario_type = normal_prompt.scenario_type
        scenario_variant = normal_prompt.scenario_variant
        scenario_context = normal_prompt.scenario_context
        scenario.title = f"{stage.title} - {normal_prompt.scenario_title}"
        scenario.situation_prompt = normal_prompt.situation_prompt
        scenario.ai_name = str(scenario_context["counterpart_role"])

    round_obj = Round(
        uid=uid,
        stage_id=stage_id,
        scenario_id=scenario.scenario_id,
        status="in_progress",
        scenario_type=scenario_type,
        scenario_variant=scenario_variant,
        scenario_context=scenario_context,
        situation_prompt=scenario.situation_prompt,
        max_user_turns=get_settings().normal_max_user_turns,
    )
    create_round(db, round_obj)

    initial_message: ChatMessage | None = None
    settings = get_settings()
    if settings.ai_worker_enabled and not scenario.is_fraud:
        reply = call_normal_worker(
            settings=settings,
            payload={
                "round_id": str(round_obj.round_id),
                "stage_id": round_obj.stage_id,
                "scenario_type": round_obj.scenario_type,
                "scenario_variant": round_obj.scenario_variant,
                "scenario_context": round_obj.scenario_context,
                "user_profile": user_profile,
                "messages": [],
            },
        )
        initial_message = ChatMessage(
            round_id=round_obj.round_id,
            role="ai",
            content=reply.content,
            worker_is_conversation_over=reply.worker_is_conversation_over,
        )
        add_chat_message(db, initial_message)
        if reply.worker_is_conversation_over:
            round_obj.status = "completed"
            round_obj.ended_at = utc_now()
            round_obj.ended_reason = "worker_done"
    # Fraud scenarios keep existing provider flow and should not fail round start.

    progress.total_round_count += 1
    progress.updated_at = utc_now()

    db.commit()
    db.refresh(round_obj)
    return RoundStartResult(
        round_obj=round_obj,
        scenario_id=str(scenario.scenario_id),
        situation_prompt=scenario.situation_prompt,
        ai_name=scenario.ai_name,
        ai_image_url=scenario.ai_image_url,
        initial_message=initial_message,
    )



def list_stage_rounds_for_user(*, db: Session, uid: str, stage_id: int) -> list[StageRoundRow]:
    stage = get_active_stage(db, stage_id)
    if stage is None:
        raise StageNotFoundError("존재하지 않는 스테이지입니다.")

    rounds = list_user_stage_rounds(db, uid, stage_id)
    items: list[StageRoundRow] = []
    for round_obj in rounds:
        scenario = round_obj.scenario
        if scenario is None:
            continue
        items.append(
            StageRoundRow(
                round_id=str(round_obj.round_id),
                scenario_id=str(scenario.scenario_id),
                scenario_title=scenario.title,
                is_fraud_scenario=scenario.is_fraud,
                status=round_obj.status,
                is_fraud_judged=round_obj.is_fraud_judged,
                evidence_count=round_obj.evidence_count,
                result=round_obj.result,
                score_delta=round_obj.score_delta,
                started_at=round_obj.started_at,
                ended_at=round_obj.ended_at,
            )
        )
    return items
