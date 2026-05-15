from __future__ import annotations

import random
import json
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import ApiError
from app.db.models import Scenario, Stage, User
from app.services.prompt_mapping import build_fraud_scenario_prompts, build_normal_scenario_prompts
from app.services.scenario_catalog import (
    get_ai_name,
    get_all_stage_genres,
    get_stage_methods,
)
from app.services.llm_engine.attacker import AttackerEngine


def choose_is_fraud() -> bool:
    return random.random() < 0.5


def _choose_stage_genre(stage: Stage) -> str:
    if stage.is_random:
        return random.choice(get_all_stage_genres())
    return stage.genre


def _build_fraud_scenario(
    *, 
    db: Session,
    stage: Stage, 
    stage_genre: str, 
    settings: Settings,
    user_meta: Optional[Dict[str, Any]] = None
) -> Scenario:
    # AttackerEngine을 사용하여 동적 시나리오 생성
    if settings.llm_studio_base_url and "hiclouddev.com" in settings.llm_studio_base_url:
        engine = AttackerEngine(settings)
        dynamic_data = engine.generate_scenario(stage_genre, user_meta or {})
        
        # Scenario 모델에 저장
        # system_prompt에 JSON으로 저장하여 나중에 AttackerAIProvider가 읽을 수 있게 함
        return Scenario(
            stage_id=stage.stage_id,
            title=f"{stage.title} - {dynamic_data.get('pretext', stage_genre)}",
            genre=stage_genre,
            is_fraud=True,
            situation_prompt=dynamic_data.get('pretext', "동적 사기 시나리오"),
            system_prompt=json.dumps(dynamic_data, ensure_ascii=False),
            ai_name=dynamic_data.get('official_name', get_ai_name(stage_genre)),
            ai_image_url=None,
            fraud_evidence_keys=[dynamic_data.get('attack_method', 'unknown')],
            min_evidence_count=1,
            difficulty=1,
            is_active=True,
        )

    # Fallback to existing logic
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


def select_scenario_for_stage(db: Session, stage: Stage, settings: Settings, user: Optional[User] = None) -> Scenario:
    try:
        stage_genre = _choose_stage_genre(stage)
        is_fraud = choose_is_fraud()
    except KeyError as exc:
        raise ApiError(str(exc), status_code=404) from exc

    user_meta = {}
    if user:
        user_meta = {
            "이름": user.nickname,
            "연령대": user.age_group or "미상",
            "직업": user.job or "미상",
            "은행": user.main_bank or "미상",
            "거주지": user.residence or "미상"
        }

    scenario = (
        _build_fraud_scenario(db=db, stage=stage, stage_genre=stage_genre, settings=settings, user_meta=user_meta)
        if is_fraud
        else _build_normal_scenario(stage=stage, stage_genre=stage_genre)
    )

    db.add(scenario)
    db.flush()
    return scenario
