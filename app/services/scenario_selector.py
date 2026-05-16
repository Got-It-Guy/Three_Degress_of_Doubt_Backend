from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.db.models import Scenario, Stage
from app.services.normal_prompt_catalog import WORKER_ALLOWED_RANDOM_GENRES
from app.services.prompt_mapping import build_fraud_scenario_prompts, build_normal_scenario_prompts
from app.services.scenario_catalog import (
    get_ai_name,
    get_stage_methods,
)


def choose_is_fraud() -> bool:
    return random.random() < 0.5


def _choose_stage_genre(stage: Stage) -> str:
    if stage.is_random:
        return random.choice(WORKER_ALLOWED_RANDOM_GENRES)
    return stage.genre


def _build_fraud_scenario(*, stage: Stage, stage_genre: str) -> Scenario:
    methods = get_stage_methods(stage_genre)
    evidence_name = random.choice(list(methods.keys()))
    ai_name = get_ai_name(stage_genre)
    situation_prompt, system_prompt = build_fraud_scenario_prompts(
        fraud_type=stage_genre,
        evidence_name=evidence_name,
        ai_name=ai_name,
    )

    return Scenario(
        stage_id=stage.stage_id,
        title=f"{stage.title} - {evidence_name}",
        genre=stage_genre,
        is_fraud=True,
        situation_prompt=situation_prompt,
        system_prompt=system_prompt,
        ai_name=ai_name,
        ai_image_url=None,
        fraud_evidence_keys=[evidence_name],
        min_evidence_count=1,
        difficulty=1,
        is_active=True,
    )


def _build_normal_scenario(*, stage: Stage, stage_genre: str) -> Scenario:
    ai_name = get_ai_name(stage_genre)
    situation_prompt, system_prompt = build_normal_scenario_prompts(
        fraud_type=stage_genre,
        ai_name=ai_name,
    )
    return Scenario(
        stage_id=stage.stage_id,
        title=f"{stage.title} - 정상 시나리오",
        genre=stage_genre,
        is_fraud=False,
        situation_prompt=situation_prompt,
        system_prompt=system_prompt,
        ai_name=ai_name,
        ai_image_url=None,
        fraud_evidence_keys=[],
        min_evidence_count=1,
        difficulty=1,
        is_active=True,
    )


def select_scenario_for_stage(db: Session, stage: Stage) -> Scenario:
    try:
        stage_genre = _choose_stage_genre(stage)
        is_fraud = choose_is_fraud()
    except KeyError as exc:
        raise ApiError(str(exc), status_code=404) from exc

    scenario = (
        _build_fraud_scenario(stage=stage, stage_genre=stage_genre)
        if is_fraud
        else _build_normal_scenario(stage=stage, stage_genre=stage_genre)
    )

    db.add(scenario)
    db.flush()
    return scenario
