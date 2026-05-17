# PR 변경 요약: LLM Worker 연동 및 라운드 진행 정책

## 1. 비교 기준

이 문서는 팀원이 확인한 메인 브랜치 최신 커밋과 현재 작업 브랜치의 차이를 설명하기 위한 문서입니다.

- 비교 기준 커밋: `70a48b1 Add total round count to stage list API`
- 현재 작업 브랜치: `verify-llm-worker-integration`
- 현재 작업 브랜치 HEAD: `56b2936 Verify LLM worker integration and round progress policy`
- 목적: 메인 브랜치 기준에서 어떤 파일이 추가/수정되었고, 왜 수정했는지, LLM 서버와 어떻게 연결되는지 설명합니다.

## 2. 전체 요약

이번 변경은 백엔드가 정상 시나리오 LLM worker 호출, 대화 종료, 라운드 점수, 경고, 리포트, 프론트 응답 호환성을 담당하도록 정리한 작업입니다.

주요 변경 사항은 다음과 같습니다.

- 정상 시나리오 LLM worker 호출 설정 및 HTTP client 추가
- worker 대화 상태 저장을 위한 DB 필드 및 Alembic migration 추가
- 정상 시나리오용 구조화 프롬프트 카탈로그 추가
- 백엔드 주도 대화 종료 규칙 추가
- 사기 시나리오 LLM 미완성 상태를 위한 임시 placeholder 처리 추가
- 라운드 판정, 점수, 경고, 스테이지 클리어 정책 수정
- 전체 스테이지 조회 응답에 `best_round_count` 추가
- 라운드 재입장 시 메시지 복구 흐름 확인 및 테스트 추가
- LLM worker payload, 대화 종료, 경고, 클리어, 리포트 관련 테스트 추가

## 3. LLM 서버 연결 정보

### 3.1 백엔드 환경변수

백엔드는 `app/core/config.py`의 설정을 통해 LLM worker 연결 정보를 읽습니다.

로컬 테스트 예시:

```powershell
$env:AI_WORKER_ENABLED="true"
$env:AI_WORKER_BASE_URL="http://127.0.0.1:8008"
$env:AI_WORKER_TOKEN="test-secret"
```

외부 worker 테스트 예시:

```powershell
$env:AI_WORKER_ENABLED="true"
$env:AI_WORKER_BASE_URL="https://ai.my-bucket-editor.win"
$env:AI_WORKER_TOKEN="test-secret"
```

운영 환경에서는 `test-secret` 대신 더 긴 랜덤 토큰을 사용해야 합니다.

### 3.2 로컬 LLM 서버 실행 명령

현재 로컬 LLM 서버는 아래 명령으로 실행한 기준으로 테스트했습니다.

```powershell
python -m uvicorn ai_worker_server:app --host 127.0.0.1 --port 8008
```

이 경우 백엔드의 worker base URL은 다음과 같습니다.

```text
http://127.0.0.1:8008
```

### 3.3 백엔드가 호출하는 worker API

백엔드는 정상 시나리오에서 다음 worker API를 호출합니다.

```http
POST {AI_WORKER_BASE_URL}/v1/normal-chat
```

요청 헤더:

```http
Content-Type: application/json
X-AI-Worker-Token: <AI_WORKER_TOKEN>
```

### 3.4 worker 요청 payload 형태

백엔드는 최종 LLM prompt를 직접 조립하지 않습니다. 대신 worker가 prompt를 만들 수 있도록 구조화된 context만 보냅니다.

대표 payload 형태:

```json
{
  "round_id": "...",
  "stage_id": 2,
  "scenario_type": "investment_fraud",
  "scenario_variant": "community",
  "scenario_context": {
    "display_label": "...",
    "user_role": "...",
    "counterpart_role": "...",
    "core_item": "...",
    "current_stage": "...",
    "situation": "...",
    "user_intent": "...",
    "counterpart_help": "...",
    "normal_safe_path": "...",
    "watch_boundary": "..."
  },
  "user_profile": {
    "name": "...",
    "ageGroup": "...",
    "job": "...",
    "mainBank": "...",
    "residence": "..."
  },
  "messages": [
    {
      "role": "user",
      "content": "..."
    },
    {
      "role": "assistant",
      "content": "..."
    }
  ]
}
```

개인정보/보안 기준:

- Firebase UID를 worker로 보내지 않습니다.
- 내부 numeric user id를 worker로 보내지 않습니다.
- 사용자 email을 worker로 보내지 않습니다.
- Authorization bearer token을 worker로 보내지 않습니다.
- DB 접속 정보나 worker token을 프론트 응답으로 노출하지 않습니다.

### 3.5 worker 응답 형태

백엔드는 worker 응답에서 아래 값을 사용합니다.

```json
{
  "status": "success",
  "content": "...",
  "is_conversation_over": false,
  "metadata": {}
}
```

사용 방식:

- `content`: 프론트로 반환할 AI 답변
- `is_conversation_over`: 정상 시나리오 대화 종료 여부
- `metadata`: worker 내부 정보. 핵심 프론트 계약에는 사용하지 않음

### 3.6 worker 직접 smoke test 명령

```powershell
$headers = @{
  "Content-Type" = "application/json"
  "X-AI-Worker-Token" = "test-secret"
}

$body = @{
  round_id = "smoke-test-round"
  stage_id = 2
  scenario_type = "investment_fraud"
  scenario_variant = "community"
  scenario_context = @{
    display_label = "investment info consultation"
    user_role = "user looking for investment information"
    counterpart_role = "investment information guide"
    core_item = "public investment information community"
    current_stage = "asking how to join an investment information community"
    situation = "checking an investment information channel"
    user_intent = "wants to know safe official information-checking steps"
    counterpart_help = "guides official materials and public information"
    normal_safe_path = "official channel -> public materials -> expert consultation if needed"
    watch_boundary = "reject guaranteed returns, upfront payment, private information pressure"
  }
  user_profile = @{
    name = "Dev User"
    ageGroup = ""
    job = ""
    mainBank = ""
    residence = ""
  }
  messages = @()
}

$utf8Body = [System.Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Depth 10))

Invoke-RestMethod `
  -Method POST `
  -Uri "http://127.0.0.1:8008/v1/normal-chat" `
  -Headers $headers `
  -ContentType "application/json; charset=utf-8" `
  -Body $utf8Body | ConvertTo-Json -Depth 10
```

## 4. 백엔드 실행 예시

```powershell
$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/fraud_sim"
$env:AUTH_MODE="dev"
$env:DEV_BEARER_UID="dev-user-001"
$env:AUTO_SEED_ON_STARTUP="true"
$env:AI_WORKER_ENABLED="true"
$env:AI_WORKER_BASE_URL="http://127.0.0.1:8008"
$env:AI_WORKER_TOKEN="test-secret"

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

DB 준비/확인 예시:

```powershell
docker ps
docker exec fraud-sim-postgres pg_isready -U postgres -d fraud_sim
alembic upgrade head
python -m app.seed_data
```

## 5. API 동작 변경 요약

### 5.1 전체 스테이지 조회

`GET /api/v1/stages` 응답에 `best_round_count`가 추가되었습니다.

```json
{
  "status": "success",
  "stages": [
    {
      "stage_id": 1,
      "title": "...",
      "description": "...",
      "thumbnail_url": null,
      "is_random": false,
      "stage_score": 0,
      "warning_count": 0,
      "total_round_count": 0,
      "best_round_count": null,
      "is_cleared": false
    }
  ]
}
```

의미:

- `stage_score`: 현재 스테이지 진행 점수
- `warning_count`: 해당 스테이지에 누적된 경고 수
- `total_round_count`: 현재 도전에서 사용한 라운드 수
- `best_round_count`: 스테이지 클리어 최고 기록. 기록이 없으면 `null`
- `is_cleared`: 해당 스테이지를 한 번이라도 클리어했는지 여부

### 5.2 라운드 시작

`POST /api/v1/stages/{stage_id}/rounds`

동작:

- 같은 유저와 같은 스테이지에 `in_progress` 라운드가 있으면 새로 만들지 않고 기존 라운드를 재사용합니다.
- worker가 만든 초기 AI 메시지가 있으면 `data.initial_message`로 반환합니다.
- 재입장 시 같은 초기 메시지를 중복 생성하지 않습니다.
- 사기 시나리오는 현재 LLM이 준비되지 않았으므로 placeholder 안내를 사용합니다.

### 5.3 메시지 전송

`POST /api/v1/rounds/{round_id}/messages`

응답의 `is_conversation_over`는 top-level 필드입니다.

```json
{
  "status": "success",
  "message_id": "...",
  "role": "ai",
  "content": "...",
  "is_evidence": false,
  "is_conversation_over": false,
  "ended_reason": null,
  "created_at": "..."
}
```

프론트는 아래처럼 읽어야 합니다.

```text
response.is_conversation_over
```

아래 형태가 아닙니다.

```text
response.data.is_conversation_over
```

### 5.4 채팅 기록 복구 / 재입장

기존 메시지 기록 조회 API는 이미 있습니다.

```http
GET /api/v1/rounds/{round_id}/messages
```

권장 프론트 흐름:

```text
1. POST /api/v1/stages/{stage_id}/enter
2. has_incomplete_round 확인
3. POST /api/v1/stages/{stage_id}/rounds
4. 반환된 round_id 확인
5. GET /api/v1/rounds/{round_id}/messages
6. messages 배열로 채팅 UI 복구
```

### 5.5 판정 API

`POST /api/v1/rounds/{round_id}/judge`

응답 예시:

```json
{
  "status": "success",
  "result": "pass",
  "score_delta": 1,
  "current_score": 1,
  "current_warning": 0,
  "is_stage_cleared": false
}
```

중요:

- HTTP 200만 보고 성공/pass로 처리하면 안 됩니다.
- 반드시 `result` 값을 확인해야 합니다.

## 6. 최종 점수 / 경고 / 클리어 정책

### 6.1 라운드 pass

현재 라운드를 클리어한 경우입니다.

```text
stage_score += 1
warning_count 유지
round.status = judged
round.result = pass
```

예시:

```text
이전: stage_score=1, warning_count=1
pass 후: stage_score=2, warning_count=1
```

### 6.2 경고 1회

사용자가 한 번 오답 판정을 한 경우입니다.

```text
warning_count += 1
stage_score 유지
round.status = in_progress
round.result = warning
```

이 경우 현재 라운드는 종료되지 않습니다. 프론트는 같은 `round_id`를 유지해야 합니다.

예시:

```text
이전: stage_score=2, warning_count=0
오답 1회 후: stage_score=2, warning_count=1
현재 round_id 계속 사용
```

### 6.3 경고 2회 / reset

해당 스테이지의 경고 수가 2가 되는 순간입니다.

```text
stage_score = 0
warning_count = 0
round.status = judged
round.result = reset
is_cleared = false
```

이 경우 현재 라운드는 실패 처리되고, 스테이지 점수도 초기화됩니다.

### 6.4 스테이지 클리어

`stage_score`가 클리어 기준 점수인 3에 도달한 경우입니다.

```text
stage_score = 3
is_cleared = true
best_round_count 갱신
warning_count 유지
round.status = judged
round.result = pass
```

판정 응답은 프론트 호환을 위해 다음 값을 반환합니다.

```json
{
  "current_score": 3,
  "is_stage_cleared": true
}
```

프론트는 기존처럼 `current_score == 3`을 보고 홈 화면으로 이동할 수 있습니다.

### 6.5 클리어 후 같은 스테이지 재입장

스테이지를 클리어한 뒤 같은 스테이지에 다시 들어가고, 진행 중인 라운드가 없는 경우입니다.

```text
stage_score = 0
total_round_count = 0
is_cleared = true 유지
cleared_at 유지
best_round_count 유지
warning_count 유지
```

즉 다음 도전은 0점부터 시작하지만, 이미 한 번 클리어했다는 기록과 최고 기록은 유지됩니다.

## 7. 파일별 변경 상세

### `.gitignore`

역할:

- 로컬 임시 파일, 테스트 산출물, 실행 중 생성되는 파일을 git에서 제외합니다.

변경 이유:

- 테스트/검증 과정에서 생기는 로컬 임시 파일이 git에 잡히지 않도록 정리했습니다.

위험도:

- 낮음. 런타임 동작에는 영향 없습니다.

### `alembic/versions/20260515_0006_round_worker_fields.py`

역할:

- worker 연동과 대화 종료 상태 저장을 위한 DB migration입니다.

추가 이유:

- 라운드와 메시지에 worker 관련 상태를 저장해야 합니다.
- `scenario_context`, worker 종료 여부, 종료 사유 등을 DB에 남길 수 있어야 합니다.

주의:

- 배포 DB에서는 반드시 `alembic upgrade head`가 필요합니다.

### `app/core/config.py`

역할:

- 환경변수 기반 설정을 관리합니다.

변경 이유:

- LLM worker 설정을 추가했습니다.
  - `AI_WORKER_ENABLED`
  - `AI_WORKER_BASE_URL`
  - `AI_WORKER_TOKEN`
  - `AI_WORKER_TIMEOUT_SECONDS`
- 대화 종료 관련 설정도 추가했습니다.

주의:

- worker mode를 켰는데 token이 없으면 worker 호출이 실패합니다.

### `app/services/ai.py`

역할:

- AI provider 및 worker 호출을 담당합니다.

변경 이유:

- `call_normal_worker`를 추가했습니다.
- 정상 시나리오일 때 외부 `/v1/normal-chat` worker를 호출합니다.
- worker 응답의 `content`, `is_conversation_over`를 파싱합니다.

주의:

- worker 서버가 꺼져 있거나 응답이 늦으면 정상 시나리오 채팅에 영향이 있습니다.

### `app/services/normal_prompt_catalog.py`

역할:

- 정상 시나리오용 세부 scenario context를 구성합니다.

추가 이유:

- 백엔드는 장르와 세부 시나리오를 선택하고 구조화된 `scenario_context`만 worker에 전달합니다.
- 최종 프롬프트 조립은 worker가 담당합니다.

포함 장르:

- 보이스피싱
- 투자사기
- 부동산사기
- 대출사기
- 중고거래사기

주의:

- 문구 품질은 추후 제품 방향에 따라 더 다듬을 수 있습니다.

### `app/services/stage_service.py`

역할:

- 스테이지 목록, 스테이지 입장, 라운드 시작, 스테이지별 라운드 목록을 담당합니다.

변경 이유:

- 라운드 시작 시 정상 worker payload context를 생성합니다.
- 진행 중인 라운드가 있으면 재입장 시 기존 라운드를 재사용합니다.
- worker 초기 메시지를 저장하고 응답에 포함합니다.
- 사기 시나리오는 placeholder 안내로 시작합니다.
- 스테이지 목록에 `best_round_count`를 포함합니다.
- 클리어 후 같은 스테이지 재입장 시 새 도전을 위해 `stage_score`, `total_round_count`만 초기화하고, `is_cleared`, `cleared_at`, `best_round_count`는 유지합니다.

주의:

- 프론트는 클리어 후 같은 스테이지 재입장이 새 도전이라는 점을 이해해야 합니다.

### `app/services/round_service.py`

역할:

- 라운드 메시지 처리, 메시지 기록 조회, worker payload 생성, judge wrapper, report 조회, 명시적 종료를 담당합니다.

변경 이유:

- DB에 저장된 메시지 기록을 worker payload에 포함합니다.
- 메시지 응답에 `is_conversation_over`, `ended_reason`을 추가했습니다.
- 완료/판정된 라운드에는 더 이상 메시지를 보낼 수 없도록 막습니다.
- 정상 시나리오가 종료되면 백엔드가 자동으로 pass 처리합니다.
- 사기 시나리오는 placeholder 흐름을 사용합니다.
- 재입장 시 메시지 복구가 가능하도록 기존 기록 조회 흐름을 유지합니다.

주의:

- `is_conversation_over=true` 이후에는 같은 round_id로 메시지를 더 보내면 안 됩니다.

### `app/services/conversation_end.py`

역할:

- 백엔드 주도 대화 종료 규칙을 담당합니다.

추가 이유:

- worker 종료 신호, 특정 종료 문구, 최대 턴 수, 명시적 종료를 처리해야 합니다.

주요 동작:

- worker가 `is_conversation_over=true`를 주면 `ended_reason="worker_done"`으로 처리합니다.
- 너무 이른 종료를 막기 위해 최소 턴 조건을 둡니다.

주의:

- 문구 기반 종료는 휴리스틱이라 추후 조정될 수 있습니다.

### `app/services/fraud_placeholder.py`

역할:

- 사기 LLM이 준비되기 전 임시 사기 시나리오 응답을 담당합니다.

추가 이유:

- 사기 LLM이 아직 준비되지 않았지만 프론트에서 사기 판정 흐름을 테스트해야 합니다.

동작:

- 사기 라운드에서 사용자 메시지를 보내면 고정 AI 응답을 반환합니다.
- `is_evidence=true`로 반환합니다.
- `evidence_reason="fraud_scenario_placeholder"`를 사용합니다.
- 라운드는 `in_progress` 상태로 유지됩니다.

주의:

- 사기 LLM이 준비되면 이 placeholder는 교체해야 합니다.

### `app/services/judge.py`

역할:

- 라운드 판정, 점수 증가, 경고 누적, reset, 스테이지 클리어, report 생성을 담당합니다.

변경 이유:

- 현재 제품 정책에 맞게 점수/경고 흐름을 수정했습니다.

핵심 정책:

- pass 시 `stage_score +1`
- warning 1회는 현재 라운드 유지
- warning은 스테이지에 귀속되고 pass/다음 라운드에서도 유지
- warning 2회는 reset 처리
- stage_score가 3이면 스테이지 클리어
- 클리어 순간 프론트에 `current_score=3` 반환

주의:

- 프론트는 반드시 `result`를 확인해야 합니다.
- `warning`은 라운드 종료가 아니라 같은 라운드 계속 진행입니다.

### `app/services/reports.py`

역할:

- 라운드 리포트를 생성하거나 갱신합니다.

변경 이유:

- 같은 라운드에서 여러 번 judge가 발생할 수 있으므로 report upsert를 안전하게 처리했습니다.
- 기존 report가 있으면 새로 insert하지 않고 update합니다.

주의:

- 낮음. round별 report unique 제약을 안전하게 유지하기 위한 변경입니다.

### `app/services/prompt_mapping.py`

역할:

- 기존 사기 시나리오 prompt mapping을 담당합니다.

변경 이유:

- 프론트에 필요한 사기 시나리오 briefing/risk marker가 유지되도록 수정했습니다.

주의:

- 일부 한글이 PowerShell에서 깨져 보일 수 있습니다. 기능 문제가 아니라 콘솔 인코딩 문제일 가능성이 큽니다.

### `app/services/scenario_selector.py`

역할:

- 사기/정상 시나리오 선택 및 랜덤 스테이지 장르 선택을 담당합니다.

변경 이유:

- 랜덤 스테이지가 프론트와 handoff에서 합의한 장르 안에서만 선택되도록 제한했습니다.

주의:

- 장르별 랜덤 비율은 추후 제품 정책에 따라 조정할 수 있습니다.

### `app/seed_data.py`

역할:

- 초기 스테이지와 시나리오 데이터를 seed합니다.

변경 이유:

- 프론트 스테이지 ID 계약과 맞췄습니다.

현재 계약:

```text
1: 보이스피싱
2: 투자사기
3: 부동산사기
4: 대출사기
5: 중고사기
6: 랜덤
```

주의:

- 이미 오래된 stage 데이터가 들어간 DB는 별도 정리나 reseed가 필요할 수 있습니다.

### `app/db/models.py`

역할:

- SQLAlchemy DB model 정의입니다.

변경 이유:

- worker 연동과 대화 종료 상태 저장을 위한 필드를 추가했습니다.
- 라운드에 `scenario_context` 등 worker payload 관련 정보를 저장할 수 있게 했습니다.

주의:

- Alembic migration 적용이 필요합니다.

### `app/api/routers/stages.py`

역할:

- 스테이지 관련 API router입니다.

변경 이유:

- stage list 응답에 `best_round_count`를 노출합니다.
- 라운드 시작 응답에 `initial_message`를 포함합니다.

주의:

- 기존 응답 형태를 깨지 않고 필드를 추가하는 additive 변경입니다.

### `app/api/routers/rounds.py`

역할:

- 라운드 메시지, 판정, 리포트, 종료 API router입니다.

변경 이유:

- 메시지 응답에 `is_conversation_over`, `ended_reason`을 포함합니다.
- 명시적 종료 endpoint를 지원합니다.
- judge 응답 구조는 유지하되 의미를 현재 정책에 맞게 정리했습니다.

주의:

- 프론트는 judge HTTP 200을 pass로 간주하면 안 됩니다.

### `app/api/routers/auth.py`

역할:

- 인증 API router입니다.

변경 이유:

- Firebase login에서 `SyncUserResult.user`를 제대로 꺼내도록 수정했습니다.

주의:

- 실제 Firebase 인증은 올바른 service account 경로가 필요합니다.

### `app/schemas/stages.py`

역할:

- 스테이지 API 응답 schema입니다.

변경 이유:

- `best_round_count`를 추가했습니다.
- 라운드 시작 응답의 `initial_message` schema를 추가했습니다.

프론트 영향:

- 스테이지 카드에서 최고 기록을 표시할 수 있습니다.
- 라운드 화면에서 초기 AI 메시지를 바로 렌더링할 수 있습니다.

### `app/schemas/rounds.py`

역할:

- 라운드 API 요청/응답 schema입니다.

변경 이유:

- 메시지 전송 응답에 `is_conversation_over`, `ended_reason`을 추가했습니다.

프론트 영향:

- `is_conversation_over`는 top-level에서 읽어야 합니다.

### `tests/test_rounds.py`

역할:

- 라운드 메시지, 판정, 경고, report, 대화 종료, worker payload 등을 검증합니다.

변경 이유:

- fraud placeholder evidence 검증
- 정상 worker payload 검증
- worker 대화 종료 검증
- 정상 시나리오 auto-pass 검증
- 완료된 라운드 메시지 차단 검증
- warning 유지 정책 검증
- warning 2회 reset 검증
- stage clear와 best record 유지 검증

### `tests/test_stages.py`

역할:

- 스테이지 목록, 입장, 라운드 시작, 재입장, stage round listing을 검증합니다.

변경 이유:

- 프론트 스테이지 ID 계약에 맞춰 테스트 수정
- `best_round_count` 응답 검증
- 사기 라운드는 evidence 생성 후 judge하도록 테스트 수정
- worker 초기 메시지 재입장 시 중복 생성 방지 검증

## 8. 프론트 연동 주의사항

### 8.1 정상 시나리오

```text
POST /api/v1/stages/{stage_id}/rounds
POST /api/v1/rounds/{round_id}/messages
if is_conversation_over=false:
  계속 채팅
if is_conversation_over=true:
  백엔드가 이미 정상 pass 처리함
  judge API 호출하지 않음
  GET /api/v1/stages 재조회
```

### 8.2 사기 placeholder 시나리오

```text
POST /api/v1/stages/{stage_id}/rounds
POST /api/v1/rounds/{round_id}/messages
is_evidence=true 확인
POST /api/v1/rounds/{round_id}/judge with is_fraud_judged=true
if result=pass:
  report 조회 가능
```

### 8.3 judge result 처리

```text
result=pass:
  라운드 종료
  stage_score 증가
  current_score == 3 또는 is_stage_cleared == true이면 홈 화면 이동

result=warning:
  라운드 종료 아님
  같은 round_id 유지
  경고 UI 표시
  report 최종 화면으로 이동하지 않음
  다음 라운드 시작하지 않음

result=reset:
  라운드 종료
  stage_score=0
  warning_count=0
  새 라운드 시작 또는 스테이지 흐름으로 복귀
```

## 9. 검증 명령어

```powershell
python -m py_compile app\services\judge.py app\services\reports.py app\services\stage_service.py app\services\round_service.py app\services\ai.py app\services\conversation_end.py app\services\normal_prompt_catalog.py app\services\fraud_placeholder.py app\schemas\stages.py app\schemas\rounds.py tests\test_rounds.py tests\test_stages.py

pytest tests\test_rounds.py tests\test_stages.py -q -s --tb=short --basetemp C:\tmp\pytest-pr-rounds-stages-basetemp -o cache_dir=C:\tmp\pytest-pr-rounds-stages-cache

pytest tests\test_users.py tests\test_auth.py -q -s --tb=short --basetemp C:\tmp\pytest-pr-auth-users-basetemp -o cache_dir=C:\tmp\pytest-pr-auth-users-cache
```

## 10. 남은 주의사항

- 사기 LLM은 아직 placeholder입니다.
- 실제 Firebase login은 올바른 Firebase service account 설정이 필요합니다.
- PowerShell에서 한글이 깨져 보일 수 있으나, UTF-8 body를 사용하면 LLM/HTTP 응답은 정상적으로 보이는 것을 확인했습니다.
- 프론트는 반드시 judge 응답의 `result`를 기준으로 분기해야 합니다.
- 기존 운영/개발 DB에 오래된 stage seed가 있으면 migration/seed 이후 stage ID를 확인해야 합니다.
- PR에 이 문서를 포함하려면 `.gitignore`의 `*.md` 때문에 강제 add가 필요합니다.

```powershell
git add -f PR_CHANGE_SUMMARY_LLM_WORKER_INTEGRATION.md
```
