from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Stage
from app.db.session import SessionLocal
from app.services.scenario_catalog import list_stage_blueprints


def seed_initial_data(db: Session) -> None:
    existing_by_id = {stage.stage_id: stage for stage in db.execute(select(Stage)).scalars().all()}

    for blueprint in list_stage_blueprints():
        stage = existing_by_id.get(blueprint.stage_id)
        if stage is None:
            stage = Stage(stage_id=blueprint.stage_id)
            db.add(stage)

        stage.title = blueprint.title
        stage.description = blueprint.description
        stage.genre = blueprint.genre
        stage.is_random = blueprint.stage_id == 99
        stage.required_score = 3
        stage.order_index = blueprint.order_index
        stage.is_active = True
        stage.thumbnail_url = None

    db.commit()


if __name__ == "__main__":
    with SessionLocal() as db:
        seed_initial_data(db)
        print("seed completed")
