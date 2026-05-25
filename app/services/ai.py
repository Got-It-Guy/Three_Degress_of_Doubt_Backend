from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings
from app.core.exceptions import ApiError
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
    worker_is_conversation_over: bool = False


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
        user_meta: dict[str, Any] | None = None,
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
        user_meta: dict[str, Any] | None = None,
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
        user_meta: dict[str, Any] | None = None,
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
        user_meta: dict[str, Any] | None = None,
    ) -> AIReply:
        start = time.perf_counter()
        history = [
            {"role": "assistant" if message.role == "ai" else message.role, "content": message.content}
            for message in recent_history
        ]
        if user_message:
            history.append({"role": "user", "content": user_message})

        try:
            scenario_data = json.loads(scenario.system_prompt)
            if not isinstance(scenario_data, dict):
                scenario_data = {}
        except (TypeError, ValueError):
            scenario_data = {}

        if not scenario_data:
            scenario_data = {
                "official_name": scenario.ai_name,
                "scammer_role": scenario.genre,
                "pretext": scenario.title,
                "logic": "상황 확인이 필요합니다.",
            }

        safe_user_meta = user_meta or {"이름": "사용자", "연령대": "미상", "직업": "미상"}
        result = self.engine.generate_reply(
            category=scenario.genre,
            history=history,
            user_meta=safe_user_meta,
            scenario_data=scenario_data,
        )

        content = str(result.get("content") or "").strip() or get_hide_fallback(scenario.genre)
        latency_ms = int((time.perf_counter() - start) * 1000)

        is_evidence = bool(result.get("is_evidence") or reveal_evidence)
        evidence_reason = None
        if is_evidence:
            evidence_name = _resolve_primary_evidence_name(scenario)
            stage = result.get("stage") or "진행 단계"
            evidence_reason = (
                f"핵심 단서 '{evidence_name}'가 감지되었습니다."
                if evidence_name
                else f"사기 의심 단계('{stage}')가 감지되었습니다."
            )

        return AIReply(
            content=content,
            is_evidence=is_evidence,
            evidence_reason=evidence_reason,
            input_tokens=estimate_tokens(str(history)),
            output_tokens=estimate_tokens(content),
            latency_ms=latency_ms,
        )


def get_ai_provider(settings: Settings, scenario: Scenario | None = None) -> BaseAIProvider:
    if scenario is not None and scenario.is_fraud and settings.llm_studio_enabled:
        return AttackerAIProvider(settings)
    if settings.gemini_enabled:
        return GeminiAIProvider()
    return StubAIProvider()


def call_normal_worker(*, settings: Settings, payload: dict) -> AIReply:
    if not settings.ai_worker_token:
        raise ApiError("AI 응답 생성에 실패했습니다. 잠시 후 다시 시도해주세요.", status_code=500)

    url = f"{settings.ai_worker_base_url.rstrip('/')}/v1/normal-chat"
    headers = {
        "X-AI-Worker-Token": settings.ai_worker_token,
        "Content-Type": "application/json; charset=utf-8",
    }
    start = time.perf_counter()
    try:
        with httpx.Client(timeout=settings.ai_worker_timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise ApiError("AI 응답 생성에 실패했습니다. 잠시 후 다시 시도해주세요.", status_code=504) from exc
    except httpx.HTTPError as exc:
        raise ApiError("AI 응답 생성에 실패했습니다. 잠시 후 다시 시도해주세요.", status_code=503) from exc

    if response.status_code == 401:
        raise ApiError("AI 응답 생성에 실패했습니다. 잠시 후 다시 시도해주세요.", status_code=502)
    if response.status_code >= 500:
        raise ApiError("AI 응답 생성에 실패했습니다. 잠시 후 다시 시도해주세요.", status_code=503)

    try:
        body = response.json()
    except ValueError as exc:
        raise ApiError("AI 응답 생성에 실패했습니다. 잠시 후 다시 시도해주세요.", status_code=502) from exc

    content = (body.get("content") or "").strip()
    if body.get("status") != "success" or not content:
        raise ApiError("AI 응답 생성에 실패했습니다. 잠시 후 다시 시도해주세요.", status_code=502)

    return AIReply(
        content=content,
        is_evidence=False,
        evidence_reason=None,
        input_tokens=None,
        output_tokens=None,
        latency_ms=int((time.perf_counter() - start) * 1000),
        worker_is_conversation_over=bool(body.get("is_conversation_over")),
    )
