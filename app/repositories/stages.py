from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Round, Stage, UserStageProgress


def list_active_stages(db: Session) -> list[Stage]:
    return db.execute(
        select(Stage).where(Stage.is_active.is_(True)).order_by(Stage.order_index.asc())
    ).scalars().all()


def get_active_stage(db: Session, stage_id: int) -> Stage | None:
    stage = db.get(Stage, stage_id)
    if stage is None or not stage.is_active:
        return None
    return stage


def list_user_progresses(db: Session, uid: str) -> list[UserStageProgress]:
    return db.execute(
        select(UserStageProgress).where(UserStageProgress.uid == uid)
    ).scalars().all()


def get_user_progress(db: Session, uid: str, stage_id: int) -> UserStageProgress | None:
    return db.execute(
        select(UserStageProgress).where(
            UserStageProgress.uid == uid,
            UserStageProgress.stage_id == stage_id,
        )
    ).scalar_one_or_none()


def create_user_progress(db: Session, uid: str, stage_id: int) -> UserStageProgress:
    progress = UserStageProgress(uid=uid, stage_id=stage_id)
    db.add(progress)
    db.flush()
    return progress


def count_user_stage_rounds(db: Session, uid: str, stage_id: int) -> int:
    value = db.execute(
        select(func.count(Round.round_id)).where(Round.uid == uid, Round.stage_id == stage_id)
    ).scalar_one()
    return int(value or 0)
