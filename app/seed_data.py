from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Stage
from app.db.session import SessionLocal


FRONTEND_STAGE_BLUEPRINTS = [
    {
        "stage_id": 1,
        "title": "보이스피싱",
        "description": "보이스피싱 상황에서 자주 보이는 단서를 구분하는 훈련입니다.",
        "genre": "보이스피싱",
        "is_random": False,
        "order_index": 1,
    },
    {
        "stage_id": 2,
        "title": "투자사기",
        "description": "투자사기 상황에서 자주 보이는 단서를 구분하는 훈련입니다.",
        "genre": "투자사기",
        "is_random": False,
        "order_index": 2,
    },
    {
        "stage_id": 3,
        "title": "부동산사기",
        "description": "부동산사기 상황에서 자주 보이는 단서를 구분하는 훈련입니다.",
        "genre": "부동산사기",
        "is_random": False,
        "order_index": 3,
    },
    {
        "stage_id": 4,
        "title": "대출사기",
        "description": "대출사기 상황에서 자주 보이는 단서를 구분하는 훈련입니다.",
        "genre": "대출사기",
        "is_random": False,
        "order_index": 4,
    },
    {
        "stage_id": 5,
        "title": "중고사기",
        "description": "중고거래사기 상황에서 자주 보이는 단서를 구분하는 훈련입니다.",
        "genre": "중고거래사기",
        "is_random": False,
        "order_index": 5,
    },
    {
        "stage_id": 6,
        "title": "랜덤",
        "description": "허용된 사기 유형 중 하나를 랜덤으로 선택하는 훈련입니다.",
        "genre": "random",
        "is_random": True,
        "order_index": 6,
    },
]


def seed_initial_data(db: Session) -> None:
    existing_by_id = {stage.stage_id: stage for stage in db.execute(select(Stage)).scalars().all()}

    for blueprint in FRONTEND_STAGE_BLUEPRINTS:
        stage = existing_by_id.get(blueprint["stage_id"])
        if stage is None:
            stage = Stage(stage_id=blueprint["stage_id"])
            db.add(stage)

        stage.title = blueprint["title"]
        stage.description = blueprint["description"]
        stage.genre = blueprint["genre"]
        stage.is_random = blueprint["is_random"]
        stage.required_score = 3
        stage.order_index = blueprint["order_index"]
        stage.is_active = True
        stage.thumbnail_url = None

    db.commit()


if __name__ == "__main__":
    with SessionLocal() as db:
        seed_initial_data(db)
        print("seed completed")
