from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass
from typing import Any


WORKER_ALLOWED_RANDOM_GENRES = [
    "보이스피싱",
    "투자사기",
    "부동산사기",
    "대출사기",
    "중고거래사기",
]


MARKETPLACE_CORE_ITEM_CANDIDATES = [
    "에어팟 프로 2세대",
    "아이패드 에어 5세대",
    "애플워치 시리즈 9",
    "플레이스테이션5",
]


PROMPT_PROFILES: dict[str, dict[str, Any]] = {
    "기관사칭형피싱": {
        "benign_objective": "사용자 문의를 정확하고 차분하게 해결",
        "safe_topics": ["서비스 이용 안내", "본인확인 일반 절차", "문제 해결 단계"],
        "forbidden_behaviors": ["단정적 위협 안내", "민감정보 요구", "링크 입력 강요"],
        "tone_examples": ["차분하고 공식적인 안내", "단계별 확인 후 다음 절차 안내"],
    },
    "투자리딩방사기": {
        "benign_objective": "위험 고지 중심의 공개 투자 정보 제공",
        "safe_topics": ["분산투자 원칙", "시장 변동성", "공식 공시 확인", "정기 브리핑 구독 안내"],
        "forbidden_behaviors": ["수익 보장", "입금 유도", "비공개방 가입 강요", "내부정보 암시"],
        "tone_examples": ["과장 없이 사실 기반 안내", "불확실성 명확 고지", "절차 중심 설명"],
    },
    "부동산임대차사기": {
        "benign_objective": "매물 확인 절차를 안전하게 안내",
        "safe_topics": ["매물 조건 설명", "방문 일정 조율", "계약 전 확인 절차"],
        "forbidden_behaviors": ["선입금 강요", "과도한 서류 요구", "허위 매물 확정"],
        "tone_examples": ["정중한 상담체", "질문에 명확하게 응답"],
    },
    "대출지원금사기": {
        "benign_objective": "합법적 대출 절차와 주의사항 안내",
        "safe_topics": ["금리/상환 구조 설명", "공식 심사 절차", "필수 서류 안내"],
        "forbidden_behaviors": ["수수료 선납 요구", "승인 보장", "민감정보 과다 수집"],
        "tone_examples": ["절차 중심 설명", "리스크 먼저 안내"],
    },
    "중고거래사기": {
        "benign_objective": "물품 상태와 거래 절차를 분명하게 안내",
        "safe_topics": ["상품 상태", "직거래/택배 일반 절차", "분쟁 예방"],
        "forbidden_behaviors": ["선입금 강요", "링크 입력 강요", "신분증 원본 강제 요구"],
        "tone_examples": ["짧고 명확한 거래 안내", "질문에 구체적으로 답변"],
    },
}


NORMAL_SCENARIO_CATALOG: dict[str, dict[str, Any]] = {
    "보이스피싱": {
        "canonical_label": "기관사칭형피싱",
        "display_label": "고객지원 문의",
        "base": {
            "user_role": "고객지원 문의 사용자",
            "counterpart_role": "고객센터 상담원",
            "current_stage": "서비스 문의를 시작한 단계",
            "core_item": "본인확인 절차 안내",
        },
        "variants": {
            "bank_unusual_activity": {
                "title": "주거래은행 이상거래 확인",
                "core_item": "이상거래 감지 안내",
                "counterpart_role": "은행 보안센터 상담원",
                "current_stage": "이상거래 알림을 받고 본인 확인 절차를 문의하는 단계",
                "situation": "은행에서 로그인/이체 이상 징후 알림을 받은 상황",
                "user_intent": "내 계좌가 안전한지 확인하고 공식 보호 절차를 진행하고 싶음",
                "counterpart_help": "공식 앱/고객센터/지점 기준으로 확인 절차를 안내",
                "normal_safe_path": "공식 앱 알림 확인 -> 대표 고객센터 재확인 -> 필요 시 지점 방문",
                "watch_boundary": "상담원이 비밀번호/OTP/인증번호를 요구하면 비정상",
            },
            "bank_branch_visit": {
                "title": "주거래은행 지점 방문/사고 접수 예약",
                "core_item": "지점 방문 및 사고 접수 예약",
                "counterpart_role": "은행 지점예약 상담원",
                "current_stage": "지점 방문 예약과 사고 접수 절차를 문의하는 단계",
                "situation": "민감한 계좌 보호 작업이 필요해 지점 방문을 고려하는 상황",
                "user_intent": "방문 가능 시간과 사고 접수 절차를 미리 확인하고 싶음",
                "counterpart_help": "준비물과 예약 방법, 현장 처리 절차를 안내",
                "normal_safe_path": "대표 고객센터/공식 앱 예약 -> 지점 방문 -> 창구 처리",
                "watch_boundary": "전화/채팅으로 즉시 송금이나 선입금을 요구하면 비정상",
            },
            "bank_security_settings": {
                "title": "주거래은행 보안 설정 안내",
                "core_item": "보안 설정 점검 안내",
                "counterpart_role": "은행 보안설정 안내 상담원",
                "current_stage": "이체 한도/보안 알림 설정 방법을 문의하는 단계",
                "situation": "최근 보안 이슈를 보고 계좌 보안 설정을 강화하려는 상황",
                "user_intent": "이체 한도/지연이체/로그인 알림 같은 안전 설정을 적용하고 싶음",
                "counterpart_help": "공식 앱 메뉴 기준으로 설정 경로와 확인 포인트를 안내",
                "normal_safe_path": "공식 앱 보안 메뉴 진입 -> 항목별 설정 -> 변경 내역 재확인",
                "watch_boundary": "원격제어 앱 설치나 인증수단 공유 요구는 비정상",
            },
            "health_check_guidance": {
                "title": "연령대 기반 건강검진/보험 안내",
                "core_item": "건강검진 및 보험 자격 안내",
                "counterpart_role": "건강검진/보험 안내 상담원",
                "current_stage": "연령대 기준 건강검진 대상/안내를 문의하는 단계",
                "situation": "연령대 기준 건강검진 또는 보험 자격을 확인하려는 상황",
                "user_intent": "내가 대상자인지, 어디서 어떻게 예약하는지 확인하고 싶음",
                "counterpart_help": "공식 기관/보험사 기준의 조회·예약 절차를 안내",
                "normal_safe_path": "공식 홈페이지/앱 조회 -> 대표 고객센터 확인 -> 병원/기관 예약",
                "watch_boundary": "CVC/인증번호/보안카드 등 민감값 요구는 비정상",
            },
        },
    },
    "투자사기": {
        "canonical_label": "투자리딩방사기",
        "display_label": "투자 정보 상담",
        "base": {
            "user_role": "투자 정보 탐색 사용자",
            "counterpart_role": "투자 정보 안내자",
            "current_stage": "투자 정보 수신 방법을 문의하는 단계",
            "core_item": "시장 정보 브리핑",
        },
        "variants": {
            "community": {
                "scenario_title": "정상 시나리오 템플릿(투자-커뮤니티)",
                "core_item": "공개/투명 투자 정보 커뮤니티 안내",
                "current_stage": "투자 정보 커뮤니티 참여 방법을 문의하는 단계",
                "situation": "투자 정보 채널을 확인하는 상황",
                "user_intent": "공식적이고 안전한 정보 확인 방법을 알고 싶음",
                "counterpart_help": "공식 자료와 공개 정보를 안내",
                "normal_safe_path": "공식 채널 확인 -> 공개 자료 확인 -> 필요 시 전문가 상담",
                "watch_boundary": "수익 보장, 선입금, 비공개 정보 강요는 거절",
            },
            "newsletter": {
                "scenario_title": "정상 시나리오 템플릿(투자-구독)",
                "core_item": "정기 시장 정보/뉴스레터/리포트 구독",
                "current_stage": "정기 투자 브리핑 구독을 검토하는 단계",
                "situation": "정기 투자 정보 구독 여부를 검토하는 상황",
                "user_intent": "공개 자료 기반의 정기 브리핑을 안전하게 받아보고 싶음",
                "counterpart_help": "구독 방식, 자료 출처, 투자 유의사항을 안내",
                "normal_safe_path": "공식 구독 채널 확인 -> 공개 리포트 확인 -> 투자 판단은 본인 책임으로 진행",
                "watch_boundary": "확정 수익, 비공개 종목, 입금 요구는 거절",
            },
        },
    },
    "부동산사기": {
        "canonical_label": "부동산임대차사기",
        "display_label": "부동산 매물 상담",
        "base": {
            "user_role": "임차인",
            "counterpart_role": "중개 상담원",
            "current_stage": "매물 상담을 시작한 단계",
            "core_item": "오피스텔 매물 문의",
            "situation": "부동산 매물 조건과 방문 가능 여부를 확인하는 상황",
            "user_intent": "매물 조건, 방문 일정, 계약 전 확인 절차를 알고 싶음",
            "counterpart_help": "매물 조건과 방문 일정, 계약 전 확인 절차를 안내",
            "normal_safe_path": "매물 조건 확인 -> 방문 일정 조율 -> 등기/계약 전 확인",
            "watch_boundary": "방문 전 선입금, 과도한 서류 요구, 허위 매물 확정은 거절",
        },
        "variants": {"default": {}},
    },
    "대출사기": {
        "canonical_label": "대출지원금사기",
        "display_label": "대출 상담",
        "base": {
            "user_role": "대출 상담 요청자",
            "counterpart_role": "대출 상담원",
            "current_stage": "대출 상담을 시작한 단계",
            "core_item": "대출 조건 안내",
            "situation": "대출 조건과 심사 절차를 확인하는 상황",
            "user_intent": "금리, 상환 방식, 필요 서류와 공식 심사 절차를 알고 싶음",
            "counterpart_help": "합법적인 대출 절차와 주의사항을 안내",
            "normal_safe_path": "공식 상담 접수 -> 금리/상환 조건 확인 -> 심사 및 서류 제출",
            "watch_boundary": "수수료 선납, 승인 보장, 민감정보 과다 요구는 거절",
        },
        "variants": {"default": {}},
    },
    "중고거래사기": {
        "canonical_label": "중고거래사기",
        "display_label": "중고거래",
        "base": {
            "user_role": "중고거래 구매자",
            "counterpart_role": "중고거래 판매자",
            "current_stage": "판매글을 보고 1:1 문의를 시작한 단계",
            "core_item": "중고 전자기기",
            "situation": "중고 물품 거래를 위해 판매자와 연락을 시작한 상황",
            "user_intent": "상품 상태와 거래 절차를 확인하고 안전하게 구매하고 싶음",
            "counterpart_help": "물품 상태, 거래 방식, 배송 또는 직거래 절차를 안내",
            "normal_safe_path": "상품 상태 확인 -> 거래 방식 합의 -> 안전한 결제/수령 절차 진행",
            "watch_boundary": "선입금 강요, 외부 링크 입력, 신분증 원본 요구는 거절",
        },
        "variants": {"default": {}},
    },
}


@dataclass(frozen=True)
class NormalPromptContext:
    scenario_type: str
    scenario_variant: str
    scenario_title: str
    scenario_context: dict[str, Any]
    situation_prompt: str


def _choose_variant(genre: str) -> str:
    variants = list(NORMAL_SCENARIO_CATALOG[genre]["variants"].keys())
    return random.choice(variants)


def _naturalize_user_intent(intent: str) -> str:
    intent = intent.strip()
    if intent.endswith("싶음"):
        return f"{intent[:-2].rstrip()} 싶어 한다"
    if intent.endswith("."):
        return intent[:-1]
    return intent


def build_frontend_situation_prompt(context: dict[str, Any]) -> str:
    situation = str(context["situation"]).strip()
    current_stage = str(context["current_stage"]).strip()
    user_intent = _naturalize_user_intent(str(context["user_intent"]))
    counterpart = str(context["counterpart_role"]).strip()
    return (
        f"상황: 사용자는 {situation}이며, 현재 {current_stage}이다. "
        f"상대방은 {counterpart}이고, 사용자는 {user_intent}."
    )


def build_normal_prompt_context(
    *,
    genre: str,
    variant: str | None = None,
    user_profile: dict[str, str] | None = None,
) -> NormalPromptContext:
    catalog = NORMAL_SCENARIO_CATALOG[genre]
    canonical_label = catalog["canonical_label"]
    selected_variant = variant or _choose_variant(genre)
    variant_data = catalog["variants"][selected_variant]

    context = {
        "canonical_label": canonical_label,
        "display_label": catalog["display_label"],
        **deepcopy(catalog["base"]),
        **deepcopy(variant_data),
        **deepcopy(PROMPT_PROFILES[canonical_label]),
    }

    if genre == "중고거래사기":
        context["core_item"] = random.choice(MARKETPLACE_CORE_ITEM_CANDIDATES)

    primary_bank = (user_profile or {}).get("mainBank") or ""
    if genre == "보이스피싱" and primary_bank and selected_variant.startswith("bank_"):
        role = context["counterpart_role"]
        bank_role = role.removeprefix("은행 ")
        context["counterpart_role"] = f"{primary_bank} {bank_role}" if not role.startswith(primary_bank) else role
        context["primary_bank"] = primary_bank

    scenario_title = context.get("title") or context.get("scenario_title") or f"{context['display_label']} 정상 시나리오"
    context["scenario_title"] = scenario_title

    return NormalPromptContext(
        scenario_type=genre,
        scenario_variant=selected_variant,
        scenario_title=scenario_title,
        scenario_context=context,
        situation_prompt=build_frontend_situation_prompt(context),
    )
