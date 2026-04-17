# Round Context Memory

이 프로젝트에는 긴 채팅 문맥을 자연스럽게 유지하기 위해 `summary + recent messages` 전략을 추가했습니다.

## 왜 필요한가
- 라운드 메시지 전체를 매번 AI에 보내면 토큰 비용이 커집니다.
- 대화가 길어질수록 최근 흐름과 핵심 결정만 보내는 편이 더 안정적입니다.

## 저장 구조
`rounds` 테이블에 아래 필드를 추가했습니다.
- `conversation_summary`: 최근 window 밖의 이전 대화를 압축한 텍스트
- `last_summarized_message_id`: 요약에 마지막으로 포함된 메시지 id
- `summary_updated_at`: 요약 갱신 시각

## 서버 동작
1. 사용자가 메시지를 보내면 현재 턴 직전까지의 대화로 summary/context를 계산합니다.
2. AI 호출 시에는 `conversation_summary + recent_history + 현재 user message`만 전달합니다.
3. AI 응답 저장 후 다시 전체 라운드를 기준으로 summary를 갱신합니다.

## 복원용 API
- 전체 메시지 표시: `GET /api/v1/rounds/{round_id}/messages`
- AI 문맥 복원용 데이터: `GET /api/v1/rounds/{round_id}/context`

`/context` 응답에는 아래가 포함됩니다.
- `conversation_summary`
- `last_summarized_message_id`
- `summary_updated_at`
- `recent_messages`
- `total_message_count`, `recent_message_count`

## 주의
프론트에서 채팅 UI를 복원할 때는 여전히 `/messages` 원문이 필요합니다.
`/context`는 AI 호출 최적화나 재개 로직 확인용으로 쓰는 것이 좋습니다.
