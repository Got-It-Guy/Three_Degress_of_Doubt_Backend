from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import AICallLog, ChatMessage, Round


def _as_uuid(value: str) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def get_user_round(db: Session, round_id: str, uid: str) -> Round | None:
    return db.execute(
        select(Round)
        .options(
            selectinload(Round.messages),
            selectinload(Round.report),
            selectinload(Round.scenario),
        )
        .where(Round.round_id == _as_uuid(round_id), Round.uid == uid)
    ).scalar_one_or_none()


def create_round(db: Session, round_obj: Round) -> Round:
    db.add(round_obj)
    db.flush()
    return round_obj


def add_chat_message(db: Session, message: ChatMessage) -> ChatMessage:
    db.add(message)
    db.flush()
    return message


def list_round_messages(db: Session, round_id: str) -> list[ChatMessage]:
    return db.execute(
        select(ChatMessage)
        .where(ChatMessage.round_id == _as_uuid(round_id))
        .order_by(ChatMessage.created_at.asc())
    ).scalars().all()


def add_ai_log(db: Session, log: AICallLog) -> AICallLog:
    db.add(log)
    db.flush()
    return log


def get_latest_in_progress_round_for_stage(db: Session, uid: str, stage_id: int) -> Round | None:
    return db.execute(
        select(Round)
        .options(
            selectinload(Round.messages),
            selectinload(Round.report),
            selectinload(Round.scenario),
        )
        .where(
            Round.uid == uid,
            Round.stage_id == stage_id,
            Round.status == "in_progress",
        )
        .order_by(Round.started_at.desc())
    ).scalars().first()



def list_user_stage_rounds(db: Session, uid: str, stage_id: int) -> list[Round]:
    return db.execute(
        select(Round)
        .options(
            selectinload(Round.messages),
            selectinload(Round.report),
            selectinload(Round.scenario),
        )
        .where(
            Round.uid == uid,
            Round.stage_id == stage_id,
        )
        .order_by(Round.started_at.desc())
    ).scalars().all()
