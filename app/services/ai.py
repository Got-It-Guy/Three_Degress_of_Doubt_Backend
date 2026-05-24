from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.core.config import Settings
from app.db.models import ChatMessage, Scenario
from app.services.prompt_mapping import build_turn_instruction_prompt, resolve_evidence_name
from app.services.scenario_catalog import get_hide_fallback, get_reveal_fallback
from app.services.llm_engine.attacker import AttackerEngine


@dataclass
class AIReply:
    content: str
    is_evidence: bool
    evidence_reason: str | None
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _resolve_primary_evidence_name(scenario: Scenario) -> str | None:
    stored_key = scenario.fraud_evidence_keys[0] if scenario.fraud_evidence_keys else None
    return resolve_evidence_name(scenario.genre, stored_key) or stored_key


def _build_runtime_prompt(
    *,
    scenario: Scenario,
    conversation_summary: str | None,
    recent_history: list[ChatMessage],
    user_message: str,
    reveal_evidence: bool,
) -> str:
    recent_history_lines = [
        {"role": message.role, "content": message.content}
        for message in recent_history
    ]

    evidence_name = _resolve_primary_evidence_name(scenario)
    turn_instruction = (
        build_turn_instruction_prompt(
            fraud_type=scenario.genre,
            evidence_name=evidence_name,
            reveal_evidence=reveal_evidence,
        )
        if scenario.is_fraud and evidence_name
        else "[이번 턴 지시]\n- 사용자의 질문에 자연스럽고 짧게 답하라."
    )

    return f"""
너는 사기 판별 시뮬레이터의 NPC다.
아래 지시와 대화 이력을 따라 한국어로 답하라.
반드시 답변 내용만 평문으로 출력하고, JSON이나 설명문은 쓰지 마라.

[scenario_system_prompt]
{scenario.system_prompt}

[turn_instruction]
{turn_instruction}

[conversation_summary]
{conversation_summary or ""}

[recent_history]
{json.dumps(recent_history_lines, ensure_ascii=False)}

[user_message]
{user_message}
""".strip()


class BaseAIProvider:
    def generate_reply(
        self,
        *,
        settings: Settings,
        scenario: Scenario,
        conversation_summary: str | None,
        recent_history: list[ChatMessage],
        user_message: str,
        reveal_evidence: bool,
        user_meta: Optional[Dict[str, Any]] = None,
    ) -> AIReply:
        raise NotImplementedError


class StubAIProvider(BaseAIProvider):
    def generate_reply(
        self,
        *,
        settings: Settings,
        scenario: Scenario,
        conversation_summary: str | None,
        recent_history: list[ChatMessage],
        user_message: str,
        reveal_evidence: bool,
        user_meta: Optional[Dict[str, Any]] = None,
    ) -> AIReply:
        start = time.perf_counter()
        evidence_name = _resolve_primary_evidence_name(scenario)

        if scenario.is_fraud and reveal_evidence and evidence_name:
            content = get_reveal_fallback(scenario.genre, evidence_name, scenario.ai_name)
            is_evidence = True
            evidence_reason = f"핵심 단서 '{evidence_name}'가 이번 턴에 서버 지시에 따라 노출되었습니다."
        elif scenario.is_fraud:
            content = get_hide_fallback(scenario.genre)
            is_evidence = False
            evidence_reason = None
        else:
            content = f"{scenario.ai_name}입니다. 확인 요청하신 내용은 정상 절차에 맞춰 안내드릴게요."
            is_evidence = False
            evidence_reason = None

        latency_ms = int((time.perf_counter() - start) * 1000)
        prompt_text = _build_runtime_prompt(
            scenario=scenario,
            conversation_summary=conversation_summary,
            recent_history=recent_history,
            user_message=user_message,
            reveal_evidence=reveal_evidence,
        )
        return AIReply(
            content=content,
            is_evidence=is_evidence,
            evidence_reason=evidence_reason,
            input_tokens=estimate_tokens(prompt_text),
            output_tokens=estimate_tokens(content),
            latency_ms=latency_ms,
        )


class GeminiAIProvider(BaseAIProvider):
    def generate_reply(
        self,
        *,
        settings: Settings,
        scenario: Scenario,
        conversation_summary: str | None,
        recent_history: list[ChatMessage],
        user_message: str,
        reveal_evidence: bool,
        user_meta: Optional[Dict[str, Any]] = None,
    ) -> AIReply:
        from google import genai

        start = time.perf_counter()
        client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else genai.Client()

        prompt = _build_runtime_prompt(
            scenario=scenario,
            conversation_summary=conversation_summary,
            recent_history=recent_history,
            user_message=user_message,
            reveal_evidence=reveal_evidence,
        )

        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        raw_text = (response.text or "").strip()
        content = raw_text

        if not content:
            evidence_name = _resolve_primary_evidence_name(scenario)
            if scenario.is_fraud and reveal_evidence and evidence_name:
                content = get_reveal_fallback(scenario.genre, evidence_name, scenario.ai_name)
            elif scenario.is_fraud:
                content = get_hide_fallback(scenario.genre)
            else:
                content = f"{scenario.ai_name}입니다. 다시 한번 말씀해 주세요."

        evidence_name = _resolve_primary_evidence_name(scenario)
        is_evidence = bool(scenario.is_fraud and reveal_evidence and evidence_name)
        evidence_reason = (
            f"핵심 단서 '{evidence_name}'가 이번 턴에 서버 지시에 따라 노출되었습니다."
            if is_evidence and evidence_name
            else None
        )

        usage = getattr(response, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", None) if usage else None
        output_tokens = getattr(usage, "candidates_token_count", None) if usage else None

        return AIReply(
            content=content,
            is_evidence=is_evidence,
            evidence_reason=evidence_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )


class AttackerAIProvider(BaseAIProvider):
    def __init__(self, settings: Settings):
        self.engine = AttackerEngine(settings)

    def generate_reply(
        self,
        *,
        settings: Settings,
        scenario: Scenario,
        conversation_summary: str | None,
        recent_history: list[ChatMessage],
        user_message: str,
        reveal_evidence: bool,
        user_meta: Optional[Dict[str, Any]] = None,
    ) -> AIReply:
        start = time.perf_counter()
        
        history = [
            {"role": "assistant" if m.role == "ai" else m.role, "content": m.content}
            for m in recent_history
        ]
        history.append({"role": "user", "content": user_message})
        
        try:
            scenario_data = json.loads(scenario.system_prompt)
        except:
            scenario_data = {
                "official_name": scenario.ai_name,
                "scammer_role": scenario.genre,
                "pretext": scenario.title,
                "logic": "긴급 확인 필요"
            }

        if user_meta is None:
            user_meta = {"이름": "사용자", "연령대": "미상", "직업": "미상"}

        # 엔진 응답 (Dict 형태)
        result = self.engine.generate_reply(
            category=scenario.genre,
            history=history,
            user_meta=user_meta,
            scenario_data=scenario_data
        )
        
        content = result["content"]
        latency_ms = int((time.perf_counter() - start) * 1000)
        
        # 엔진의 판단 결과 반영
        is_evidence = result["is_evidence"] or reveal_evidence
        evidence_reason = None
        if is_evidence:
            evidence_name = _resolve_primary_evidence_name(scenario)
            evidence_reason = f"사기 혐의점('{result.get('stage', '상태')}')이 감지되었습니다."

        return AIReply(
            content=content,
            is_evidence=is_evidence,
            evidence_reason=evidence_reason,
            input_tokens=estimate_tokens(str(history)),
            output_tokens=estimate_tokens(content),
            latency_ms=latency_ms,
        )


def get_ai_provider(settings: Settings) -> BaseAIProvider:
    if settings.llm_studio_base_url and "hiclouddev.com" in settings.llm_studio_base_url:
        return AttackerAIProvider(settings)
    if settings.gemini_enabled:
        return GeminiAIProvider()
    return StubAIProvider()
