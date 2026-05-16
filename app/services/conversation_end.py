from __future__ import annotations

COMMON_USER_CLOSE = [
    "감사합니다",
    "고맙습니다",
    "좋은 하루",
    "수고하세요",
    "확인했습니다",
    "결제 완료",
    "입금 완료",
    "송금 완료",
    "거래 완료",
    "예약 완료",
]
COMMON_AI_CLOSE = [
    "감사합니다",
    "고맙습니다",
    "좋은 하루",
    "확인",
    "안내드렸",
    "예약 확정",
    "일정 확정",
]

MARKET_USER_CLOSE = [
    "결제했습니다",
    "결제 완료",
    "송금했습니다",
    "입금했습니다",
    "보내드렸",
    "기다리고 있을게요",
    "받겠습니다",
]
MARKET_AI_CLOSE = [
    "결제 확인",
    "입금 확인",
    "거래 감사",
    "발송",
    "배송",
]

REAL_USER_CLOSE = [
    "뵙겠습니다",
    "그때 뵙겠습니다",
    "내일 뵙겠습니다",
    "방문하겠습니다",
    "방문 일정",
    "예약 확정",
    "방문 예약",
]
REAL_AI_CLOSE = [
    "방문 일정",
    "예약 확정",
    "방문 예약",
    "일정 확정",
    "예약 완료",
    "기다리겠습니다",
    "뵙겠습니다",
]

CONSULT_USER_CLOSE = [
    "알겠습니다",
    "확인해보겠습니다",
    "방문해보겠습니다",
    "앱에서 확인해보겠습니다",
    "고객센터로 확인해보겠습니다",
    "상담 감사합니다",
    "안내 감사합니다",
]
CONSULT_AI_CLOSE = [
    "공식 앱",
    "고객센터",
    "지점 방문",
    "확인해보시면",
    "안내드린",
    "감사합니다",
    "좋은 하루",
]

EXPLORATORY_USER_ONLY = [
    "가능한가요",
    "가능할까요",
    "될까요",
    "가도 되나요",
    "봐도 되나요",
    "보러 가도 되나요",
    "방문 가능할까요",
    "확인 가능할까요",
    "물어봐도 되나요",
    "어떻게 하면 되나요",
    "무엇이 필요할까요",
    "어떤 조건이 필요할까요",
]


def _contains_any(text: str, patterns: list[str]) -> bool:
    lowered = text.lower()
    return any(p.lower() in lowered for p in patterns)


def decide_end_reason(
    *,
    user_text: str,
    ai_text: str,
    user_turn_count: int,
    min_user_turns_for_natural_end: int,
    max_user_turns: int,
    scenario_type: str | None,
    worker_is_conversation_over: bool,
) -> str | None:
    if user_turn_count >= max_user_turns:
        return "max_turns"

    if worker_is_conversation_over:
        return "worker_done"

    if user_turn_count < min_user_turns_for_natural_end:
        return None

    if _contains_any(user_text, EXPLORATORY_USER_ONLY):
        return None

    scenario = (scenario_type or "").lower()
    if ("중고" in scenario or "market" in scenario) and _contains_any(user_text, MARKET_USER_CLOSE) and _contains_any(ai_text, MARKET_AI_CLOSE):
        return "phrase_marketplace_close"
    if ("부동산" in scenario or "estate" in scenario) and _contains_any(user_text, REAL_USER_CLOSE) and _contains_any(ai_text, REAL_AI_CLOSE):
        return "phrase_real_estate_appointment_close"
    if _contains_any(user_text, CONSULT_USER_CLOSE) and _contains_any(ai_text, CONSULT_AI_CLOSE):
        return "phrase_consultation_close"
    if _contains_any(user_text, COMMON_USER_CLOSE) and _contains_any(ai_text, COMMON_AI_CLOSE):
        return "phrase_common_close"

    return None
