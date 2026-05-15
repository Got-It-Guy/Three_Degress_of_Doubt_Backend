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


## 4. 추후 필요
1. 판례 데이터, 