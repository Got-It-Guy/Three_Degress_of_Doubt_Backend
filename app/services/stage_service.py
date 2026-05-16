from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.time_utils import utc_now
from app.db.models import Round, UserStageProgress
from app.repositories.rounds import create_round, get_latest_in_progress_round_for_stage, list_user_stage_rounds
from app.repositories.stages import (
    count_user_stage_rounds,
    create_user_progress,
    get_active_stage,
    get_user_progress,
    list_active_stages,
    list_user_progresses,
)
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


class StageNotFoundError(ValueError):
    pass


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

    total_round_count = count_user_stage_rounds(db, uid, stage_id)
    progress.total_round_count = total_round_count
    progress.updated_at = utc_now()

    incomplete_round = get_latest_in_progress_round_for_stage(db, uid, stage_id)

    db.commit()
    db.refresh(progress)
    return StageEnterResult(
        progress=progress,
        total_round_count=total_round_count,
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
        progress.total_round_count = count_user_stage_rounds(db, uid, stage_id)
        progress.updated_at = utc_now()
        db.commit()
        db.refresh(progress)
        return RoundStartResult(
            round_obj=existing_round,
            scenario_id=str(existing_round.scenario.scenario_id),
            situation_prompt=existing_round.scenario.situation_prompt,
            ai_name=existing_round.scenario.ai_name,
            ai_image_url=existing_round.scenario.ai_image_url,
        )

    scenario = select_scenario_for_stage(db, stage)

    round_obj = Round(
        uid=uid,
        stage_id=stage_id,
        scenario_id=scenario.scenario_id,
        status="in_progress",
    )
    create_round(db, round_obj)

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
