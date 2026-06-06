# LLM 공격 엔진 백엔드 이식 및 통합 가이드

이 문서는 사기꾼 LLM(Attacker Engine)을 FastAPI 백엔드에 이식한 상세 내역을 정리한 문서입니다. 다른 팀원이 정상 시나리오 LLM을 통합하거나 메인 브랜치와 합칠 때 참고할 수 있도록 작성되었습니다.

## 1. 개요
기존 프로토타입의 복합적인 LLM 로직(심리 분석, 단계별 공격, 동적 시나리오 생성)을 백엔드의 아키텍처에 맞춰 모듈화하여 이식.

## 2. 주요 변경 사항 상세

### A. 설정 및 환경 구성
- **파일**: `app/core/config.py`
- **내역**: LM 스튜디오 연결을 위한 설정값 추가
  - `llm_studio_base_url`: 기본값 `http://llm.hiclouddev.com/v1`
  - `llm_studio_api_key`: `lm-studio`
  - `llm_studio_model`: `local-model`
- **파일**: `requirements.txt`
  - **내역**: `pandas`, `openai` 라이브러리 추가

### B. LLM 전용 엔진 모듈 신설 (`app/services/llm_engine/`)
유지보수를 위해 LLM 관련 로직을 별도 패키지로 분리했습니다.

- **파일**: `app/services/llm_engine/prompts.py`
  - **내역**: 모든 프롬프트 템플릿(시나리오 추출, 심리 분석, 단계별 지침, 카테고리별 페르소나)을 중앙 관리하도록 정리.
- **파일**: `app/services/llm_engine/attacker.py`
  - **내역**: `AttackerEngine` 클래스 구현
    - `generate_scenario()`: 판례/금감원 CSV를 읽어 동적 사기 시나리오(JSON) 생성.
    - `analyze_user_state()`: 대화 이력을 바탕으로 사용자의 순응도, 의심도, 공포심 분석.
    - `generate_reply()`: 현재 단계(접근~마무리)와 심리 상태를 고려한 개인화된 공격 메시지 생성.

### C. AI Provider 통합
- **파일**: `app/services/ai.py`
  - **내역**: `AttackerAIProvider` 클래스 추가
    - `BaseAIProvider` 인터페이스를 구현하여 기존 백엔드 흐름과 완벽히 호환.
    - `get_ai_provider()`에서 `llm_studio_base_url`이 설정되어 있고 특정 도메인을 포함할 경우 우선적으로 `AttackerAIProvider`를 반환하도록 로직 수정.

### D. 비즈니스 로직 수정 (Service Layer)
- **파일**: `app/services/scenario_selector.py`
  - **내역**: 사기 시나리오 생성 시 `AttackerEngine`을 호출하도록 수정. 생성된 상세 시나리오 데이터(JSON)는 `Scenario.system_prompt` 필드에 직렬화하여 저장.
- **파일**: `app/services/stage_service.py`
  - **내역**: `start_round_for_user()` 호출 시 유저 메타데이터(닉네임, 직업 등)를 가져와 시나리오 생성기에 전달하도록 수정.
- **파일**: `app/services/round_service.py`
  - **내역**: `send_round_message()` 호출 시 DB에서 유저 정보를 추출하여 `user_meta` 딕셔너리를 구성하고, AI Provider에 전달하도록 수정.

## 3. 데이터 흐름 (Data Flow)
1. **라운드 시작**: `stage_service` -> `scenario_selector` -> `AttackerEngine.generate_scenario()` (판례 기반 시나리오 생성 및 DB 저장)
2. **메시지 전송**: `round_service` -> `AttackerAIProvider` -> `AttackerEngine.generate_reply()`
3. **심리 분석**: `AttackerEngine` 내부에서 매 턴마다 사용자의 상태를 분석하여 사기 단계(Stage)를 동적으로 결정.

## 4. 중고거래 사기 카테고리 추가 및 엔진 고도화 내역
기존 구조를 바탕으로 '중고거래사기'를 이식하고, 모델의 환각(Hallucination) 및 카테고리 오염을 방지하기 위해 엔진과 프롬프트를 대폭 강화했습니다.

### A. 카테고리 및 프롬프트 고도화 (`prompts.py`)
- **중고거래사기 페르소나 추가**: `CATEGORY_PROMPTS`에 친근한 개인 판매자 역할 추가 (딱딱한 상담사 말투 금지, 일상적인 채팅체 강제).
- **단일 목표 지향 시나리오**: `SCENARIO_STAGES`에서 결제유도, 계약유도 등 중복되는 클라이맥스 단계를 `행동유도` 하나로 통합하여 모델이 한 가지 목표(송금 OR 링크)에만 집중하도록 구조화.
- **카테고리 오염 방지 (Negative Constraints)**: 대출사기에서 중고 물품을 파는 등 도메인을 이탈하는 현상을 막기 위해 각 카테고리별로 강력한 금지 키워드 명시.
- **계좌번호 구체화**: `SCENARIO_EXTRACTION_PROMPT`에 `account_no` 필드를 추가하여 모델이 입금 유도 시 구체적인 은행명과 계좌번호를 제시하도록 수정.

### B. 엔진 로직 및 가드레일 강화 (`attacker.py`)
- **데이터 소스 연결**: `file_map`에 `중고거래사기.csv` 연결.
- **도메인 락(Domain Lock) 및 디폴트 설정**: `category_goals`와 `default_configs`를 카테고리별로 철저히 분리하여, 모델이 실패하거나 오염된 데이터를 내뱉더라도 해당 카테고리에 맞는 고품질의 기본 시나리오(이름, 금액, 계좌번호 등)로 즉시 덮어쓰는 가드레일 구현.
- **능동적 증거(is_evidence) 판정**: `generate_reply`의 반환형을 딕셔너리(`Dict`)로 변경. 엔진 내부에서 현재 단계(행동유도, 위협_압박 등)와 발화 내용(링크 포함 여부)을 자체 분석하여 `is_evidence` 판정값을 함께 반환하도록 수정.
- **치환자 강제 소거**: 최종 응답 전, `{fake_link}`나 `{item_name}` 같은 시스템 변수명이 텍스트에 그대로 노출될 경우 실제 값으로 강제 치환하는 최종 방어선 구축.

### C. AI Provider 연동 (`ai.py`)
- **엔진 응답 규격 변경 대응**: `AttackerAIProvider`가 `attacker.py`로부터 딕셔너리 형태의 응답을 받아 `content`와 `is_evidence`를 파싱.
- **단서 노출 사유 기록**: 사기 혐의점이 포착될 경우, `evidence_reason`에 구체적인 단계명(예: 사기 혐의점('행동유도')이 감지되었습니다)을 기록하여 프론트엔드로 전달.

## 5. 추후 필요
1. 판례 데이터 확충 및 정제 작업, DB 저장.
2. 프론트엔드 연동 및 인게임 밸런싱(단서 노출 빈도, 난이도 등) 테스트.