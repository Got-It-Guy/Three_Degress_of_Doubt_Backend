from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser, get_current_user
from app.core.time_utils import to_iso_z
from app.db.session import get_db
from app.schemas.stages import (
    RoundStartData,
    RoundStartResponse,
    StageEnterResponse,
    StageListItem,
    StageListResponse,
    StageRoundItem,
    StageRoundsResponse,
)
from app.services.stage_service import enter_stage_for_user, list_stage_rounds_for_user, list_stages_for_user, start_round_for_user

router = APIRouter(prefix="/api/v1/stages", tags=["stages"])


@router.get("", response_model=StageListResponse)
def list_stages(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> StageListResponse:
    items = [StageListItem(**row.__dict__) for row in list_stages_for_user(db=db, uid=current_user.uid)]
    return StageListResponse(stages=items)


@router.post("/{stage_id}/enter", response_model=StageEnterResponse)
def enter_stage(
    stage_id: int,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> StageEnterResponse:
    result = enter_stage_for_user(db=db, uid=current_user.uid, stage_id=stage_id)
    progress = result.progress
    return StageEnterResponse(
        progress_id=str(progress.progress_id),
        stage_id=progress.stage_id,
        stage_score=progress.stage_score,
        warning_count=progress.warning_count,
        is_cleared=progress.is_cleared,
        total_round_count=result.total_round_count,
        has_incomplete_round=result.has_incomplete_round,
    )


@router.get("/{stage_id}/rounds", response_model=StageRoundsResponse)
def list_stage_rounds(
    stage_id: int,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> StageRoundsResponse:
    rows = list_stage_rounds_for_user(db=db, uid=current_user.uid, stage_id=stage_id)
    return StageRoundsResponse(
        stage_id=stage_id,
        rounds=[
            StageRoundItem(
                round_id=row.round_id,
                scenario_id=row.scenario_id,
                scenario_title=row.scenario_title,
                is_fraud_scenario=row.is_fraud_scenario,
                status=row.status,
                is_fraud_judged=row.is_fraud_judged,
                evidence_count=row.evidence_count,
                result=row.result,
                score_delta=row.score_delta,
                started_at=to_iso_z(row.started_at) or "",
                ended_at=to_iso_z(row.ended_at),
            )
            for row in rows
        ],
    )


@router.post("/{stage_id}/rounds", response_model=RoundStartResponse)
def start_round(
    stage_id: int,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> RoundStartResponse:
    result = start_round_for_user(db=db, uid=current_user.uid, stage_id=stage_id)
    return RoundStartResponse(
        data=RoundStartData(
            round_id=str(result.round_obj.round_id),
            scenario_id=result.scenario_id,
            situation_prompt=result.situation_prompt,
            ai_name=result.ai_name,
            ai_image_url=result.ai_image_url,
            started_at=to_iso_z(result.round_obj.started_at) or "",
        )
    )
