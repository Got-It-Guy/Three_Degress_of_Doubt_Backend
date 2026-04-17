# Evidence prompt mapping

- 라운드 시작 시 `app/services/scenario_selector.py`가 장르와 증거 1개를 고른 뒤 `app/services/prompt_mapping.py`로 상세 프롬프트를 조합합니다.
- 이어하기 시에는 기존 `round.scenario_id`를 재사용하므로, 처음 생성된 `scenario.system_prompt`와 `scenario.situation_prompt`가 그대로 유지됩니다.
- 개발 모드에서 Gemini를 끈 경우에도 `StubAIProvider`가 선택된 증거명을 기준으로 응답/사유를 만들어 프롬프트 매핑이 눈에 보이도록 했습니다.
