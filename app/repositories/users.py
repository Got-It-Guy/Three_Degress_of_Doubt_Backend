from __future__ import annotations

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User


def get_user_by_uid(db: Session, uid: str) -> User | None:
    return db.execute(select(User).where(User.uid == uid)).scalar_one_or_none()


def add_user(db: Session, user: User) -> User:
    db.add(user)
    db.flush()
    return user


def get_next_user_numeric_id(db: Session) -> int:
    current_max = db.execute(select(func.max(User.id))).scalar_one()
    return int(current_max or 0) + 1
