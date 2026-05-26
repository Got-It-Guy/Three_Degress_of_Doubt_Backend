from __future__ import annotations

import json
import random
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import ApiError
from app.db.models import Scenario, Stage, User
from app.services.normal_prompt_catalog import WORKER_ALLOWED_RANDOM_GENRES
from app.services.prompt_mapping import build_fraud_scenario_prompts, build_normal_scenario_prompts
from app.services.scenario_catalog import (
    get_ai_name,
    get_stage_methods,
)
from app.services.llm_engine.attacker import AttackerEngine


def choose_is_fraud() -> bool:
    return random.random() < 0.5


def _choose_stage_genre(stage: Stage) -> str:
    if stage.is_random:
        # verify 기준 유지: 정상 시나리오 worker가 지원하는 장르 안에서 랜덤 선택한다.
        return random.choice(WORKER_ALLOWED_RANDOM_GENRES)
    return stage.genre


def _build_user_meta(user: User | None) -> dict[str, Any]:
    if user is None:
        return {"이름": "사용자", "연령대": "미상", "직업": "미상", "은행": "미상", "거주지": "미상"}
    return {
        "이름": user.nickname,
        "연령대": user.age_group or "미상",
        "직업": user.job or "미상",
        "은행": user.main_bank or "미상",
        "거주지": user.residence or "미상",
    }


def _build_dynamic_fraud_scenario(
    *,
    stage: Stage,
    stage_genre: str,
    settings: Settings,
    user: User | None,
) -> Scenario:
    engine = AttackerEngine(settings)
    dynamic_data = engine.generate_scenario(stage_genre, _build_user_meta(user))
    if not isinstance(dynamic_data, dict):
        dynamic_data = {}

    ai_name = str(dynamic_data.get("official_name") or get_ai_name(stage_genre))
    pretext = str(dynamic_data.get("pretext") or "동적 사기 시나리오")
    attack_method = str(dynamic_data.get("attack_method") or "동적 사기 단서")

    return Scenario(
        stage_id=stage.stage_id,
        title=f"{stage.title} - {pretext}",
        genre=stage_genre,
        is_fraud=True,
        situation_prompt=pretext,
        system_prompt=json.dumps(dynamic_data, ensure_ascii=False),
        ai_name=ai_name,
        ai_image_url=None,
        fraud_evidence_keys=[attack_method],
        min_evidence_count=1,
        difficulty=1,
        is_active=True,
    )


def _build_fraud_scenario(
    *,
    stage: Stage,
    stage_genre: str,
    settings: Settings | None = None,
    user: User | None = None,
) -> Scenario:
    if settings is not None and settings.llm_studio_enabled:
        return _build_dynamic_fraud_scenario(
            stage=stage,
            stage_genre=stage_genre,
            settings=settings,
            user=user,
        )

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


def select_scenario_for_stage(
    db: Session,
    stage: Stage,
    settings: Settings | None = None,
    user: User | None = None,
) -> Scenario:
    try:
        stage_genre = _choose_stage_genre(stage)
        is_fraud = choose_is_fraud()
    except KeyError as exc:
        raise ApiError(str(exc), status_code=404) from exc

    scenario = (
        _build_fraud_scenario(stage=stage, stage_genre=stage_genre, settings=settings, user=user)
        if is_fraud
        else _build_normal_scenario(stage=stage, stage_genre=stage_genre)
    )

    db.add(scenario)
    db.flush()
    return scenario
