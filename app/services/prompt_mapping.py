from __future__ import annotations

from textwrap import dedent

from app.services.scenario_catalog import (
    SCENARIO_CLUE_CATALOG,
    STAGE_SITUATION_BASE,
    get_primary_clue,
)


def get_evidence_clues(fraud_type: str, evidence_name: str) -> list[str]:
    return list(SCENARIO_CLUE_CATALOG.get(fraud_type, {}).get(evidence_name, []))


def resolve_evidence_name(fraud_type: str, evidence_key: str | None) -> str | None:
    if not evidence_key:
        return None
    evidences = SCENARIO_CLUE_CATALOG.get(fraud_type, {})
    if evidence_key in evidences:
        return evidence_key
    for evidence_name, clues in evidences.items():
        if evidence_key in clues:
            return evidence_name
    return None


def build_fraud_scenario_prompts(*, fraud_type: str, evidence_name: str, ai_name: str) -> tuple[str, str]:
    base_situation = STAGE_SITUATION_BASE.get(fraud_type, "상대방과 대화를 시작합니다.")
    primary_clue = get_primary_clue(fraud_type, evidence_name)

    situation_prompt = dedent(
        f"""
        {base_situation}

        핵심 위험 신호: {evidence_name}
        대표 신호: {primary_clue}
        """
    ).strip()

    system_prompt = dedent(
        f"""
        [역할]
        너는 시뮬레이션 상대 NPC다.
        유형: {fraud_type}
        이름: '{ai_name}'

        [핵심 단서]
        이번 라운드의 핵심 단서는 '{evidence_name}'이다.
        대표 단서 문장은 '{primary_clue}'이다.

        [응답 규칙]
        - 1~2문장으로 자연스럽게 답한다.
        - 단서는 백엔드 지시가 있을 때만 노출한다.
        - 단서 외 새로운 사기 단서를 만들지 않는다.
        """
    ).strip()

    return situation_prompt, system_prompt


def build_normal_scenario_prompts(*, fraud_type: str, ai_name: str) -> tuple[str, str]:
    situation_prompt = STAGE_SITUATION_BASE.get(fraud_type, "상대방과 대화를 시작합니다.")
    system_prompt = dedent(
        f"""
        [역할]
        너는 {fraud_type} 유형의 정상 상담 상대다.
        이름: '{ai_name}'

        [응답 규칙]
        - 자연스럽고 간결하게 답한다.
        - 허위 위협, 사기 단서, 강압 표현을 만들지 않는다.
        """
    ).strip()
    return situation_prompt, system_prompt


def build_turn_instruction_prompt(*, fraud_type: str, evidence_name: str, reveal_evidence: bool) -> str:
    primary_clue = get_primary_clue(fraud_type, evidence_name)
    if reveal_evidence:
        return dedent(
            f"""
            [이번 턴 지시]
            - 이번 응답에서 핵심 단서 '{evidence_name}'를 노출한다.
            - 대표 단서 문장: '{primary_clue}'
            """
        ).strip()

    return dedent(
        """
        [이번 턴 지시]
        - 핵심 단서를 직접 노출하지 않는다.
        - 사용자의 현재 질문에만 자연스럽게 답한다.
        """
    ).strip()
