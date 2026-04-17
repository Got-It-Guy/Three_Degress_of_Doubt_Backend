# Fraud Simulator FastAPI (Firebase Auth + PostgreSQL)

프론트엔드 API 설계서를 기준으로 만든 FastAPI 백엔드입니다.
이 버전은 아키텍처를 **Firebase Auth + PostgreSQL** 기준으로 다시 정리했습니다.

## 아키텍처 원칙

- **Firebase Auth**: 로그인 / ID 토큰 검증
- **PostgreSQL**: 사용자 프로필 동기화, 스테이지 진행도, 라운드, 채팅, 리포트, AI 로그 저장
- **Firestore**: 사용하지 않음

즉, Firebase는 **인증 전용**이고 실제 서비스 데이터는 전부 PostgreSQL에 저장합니다.

## 현재 구조

```text
fraud_sim_fastapi_firebase_postgres/
├── alembic/
│   ├── env.py
│   └── versions/
├── app/
│   ├── api/
│   │   ├── deps.py
│   │   └── routers/
│   ├── core/
│   ├── db/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   ├── main.py
│   └── seed_data.py
├── tests/
├── alembic.ini
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## 포함된 엔드포인트

- `POST /api/users/sync`
- `GET /api/v1/stages`
- `POST /api/v1/stages/{stage_id}/enter`
- `POST /api/v1/stages/{stage_id}/rounds`
- `POST /api/v1/rounds/{round_id}/messages`
- `POST /api/v1/rounds/{round_id}/judge`
- `GET /api/v1/rounds/{round_id}/report`

## 어떤 데이터가 어디에 저장되나

### Firebase Auth

- 로그인 처리
- 프론트에서 받은 Firebase ID 토큰 검증

### PostgreSQL

- `users`
- `stages`
- `user_stage_progress`
- `scenarios`
- `rounds`
- `chat_messages`
- `round_reports`
- `ai_call_logs`

즉 **채팅도 PostgreSQL**, **사기 수법(시나리오)도 PostgreSQL**, **stage_progress도 PostgreSQL** 입니다.

## 실행 방법

### 1) PostgreSQL 실행

가장 쉬운 방법은 Docker Compose입니다.

```bash
docker compose up -d postgres
```

### 2) 가상환경 + 패키지 설치

```bash
python -m venv .venv
source .venv/bin/activate   # Windows는 .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

`.env`에서 아래 두 값은 꼭 맞춰주세요.

- `DATABASE_URL`
- `GOOGLE_APPLICATION_CREDENTIALS`

### 3) 마이그레이션 + 시드

```bash
alembic upgrade head
python -m app.seed_data
```

### 4) 서버 실행

```bash
uvicorn app.main:app --reload
```

## docker-compose 예시

이 저장소에는 바로 띄울 수 있는 PostgreSQL용 `docker-compose.yml`이 포함되어 있습니다.
기본 계정은 아래와 같습니다.

- DB: `fraud_sim`
- User: `postgres`
- Password: `postgres`
- Port: `5432`

## 인증

기본값은 아래처럼 **Firebase 토큰 검증**입니다.

```env
AUTH_MODE=firebase
```

프론트는 Firebase 로그인 후 받은 **ID 토큰**을 그대로 Bearer로 보내면 됩니다.

```http
Authorization: Bearer <firebase-id-token>
```

개발 편의를 위해 `AUTH_MODE=dev`도 남겨두었지만, 운영 기준 권장값은 `firebase`입니다.

## 테스트 실행

```bash
pytest
```

테스트는 **SQLite 임시 DB + 인증 dependency override**로 동작합니다.
즉 테스트 편의상 SQLite를 쓰지만, 실제 앱 기본 구성은 PostgreSQL입니다.

현재 테스트는 아래 흐름을 검증합니다.

- 유저 sync 생성/갱신
- 스테이지 목록 조회 / 입장 / 라운드 시작
- 메시지 전송 → 판정 → 리포트 생성
- 두 번 오답 시 `reset` 처리

## 왜 Firestore를 쓰지 않았나

이 프로젝트는 단순 실시간 채팅앱보다 **게임형 규칙 처리** 비중이 큽니다.

- 점수 증가
- 경고 누적
- 2회 경고 시 reset
- 라운드 종료
- 리포트 생성
- 메시지와 리포트 연결

이런 로직은 관계형 모델과 트랜잭션이 많은 편이라 PostgreSQL이 더 잘 맞습니다.
그래서 Firestore 대신 PostgreSQL로 통일했습니다.

## 이전 버전 대비 보강점

1. **테스트 추가**: `tests/`에서 핵심 흐름 자동 검증
2. **Alembic 추가**: 스키마를 마이그레이션으로 관리
3. **라우터 → 서비스/리포지토리 분리**: 라우터가 직접 DB를 만지지 않도록 정리
4. **기본 아키텍처 재정렬**: Firebase Auth + PostgreSQL이 기본값이 되도록 설정 정리

## 남아 있는 명세 공백

설계서 원문만으로는 아래 내용은 여전히 최종 확정이 아닙니다.

- 메시지 목록 조회 API를 추가할지
- Firebase 토큰을 그대로 쓸지, 서버 JWT를 따로 발급할지
- 스테이지 클리어 조건을 점수 몇 점으로 볼지

현재 구현에서는 `fraud_missed`를 **실제 사기 시나리오에서 유저가 `is_fraud_judged=false`로 판정한 경우** 생성하도록 정리했습니다.

그래서 현재 구현은 **설계서에서 비어 있지 않은 부분을 우선 안정적으로 실행 가능한 구조로 만든 버전**입니다.
