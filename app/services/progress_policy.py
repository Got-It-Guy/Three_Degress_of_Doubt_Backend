from __future__ import annotations

from app.db.models import UserStageProgress


def has_stage_clear_record(progress: UserStageProgress) -> bool:
    return progress.is_cleared or (
        progress.best_round_count is not None and progress.best_round_count > 0
    )
