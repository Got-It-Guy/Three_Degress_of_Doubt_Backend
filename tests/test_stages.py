from fastapi.testclient import TestClient


def _sync_default_user(client: TestClient) -> None:
    client.post(
        "/api/users/sync",
        json={
            "uid": "dev-user-001",
            "email": "user@example.com",
            "nickname": "tester",
            "provider": "google",
            "profile_image": None,
        },
    )


def test_stage_list_enter_and_start_round(client: TestClient, auth_headers: dict[str, str], monkeypatch):
    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: True)

    list_response = client.get("/api/v1/stages", headers=auth_headers)
    assert list_response.status_code == 200
    stages = list_response.json()["stages"]
    assert [stage["stage_id"] for stage in stages] == [1, 2, 3, 4, 5, 6]
    assert [stage["title"] for stage in stages] == ["보이스피싱", "투자사기", "부동산사기", "대출사기", "중고사기", "랜덤"]
    assert stages[0]["stage_score"] == 0
    assert stages[0]["best_round_count"] is None

    enter_response = client.post("/api/v1/stages/1/enter", headers=auth_headers)
    assert enter_response.status_code == 200
    enter_body = enter_response.json()
    assert enter_body["stage_id"] == 1
    assert enter_body["warning_count"] == 0
    assert enter_body["has_incomplete_round"] is False

    start_response = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    assert start_response.status_code == 200
    data = start_response.json()["data"]
    assert data["round_id"]
    assert data["scenario_id"]
    assert data["ai_name"]

    enter_again_response = client.post("/api/v1/stages/1/enter", headers=auth_headers)
    assert enter_again_response.status_code == 200
    assert enter_again_response.json()["has_incomplete_round"] is True


def test_start_round_reuses_existing_in_progress_round(client: TestClient, auth_headers: dict[str, str], monkeypatch):
    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: True)

    first_start = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    assert first_start.status_code == 200
    first_data = first_start.json()["data"]

    second_start = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    assert second_start.status_code == 200
    second_data = second_start.json()["data"]

    assert second_data["round_id"] == first_data["round_id"]
    assert second_data["scenario_id"] == first_data["scenario_id"]



def test_list_stage_rounds_returns_all_rounds_for_stage(client: TestClient, auth_headers: dict[str, str], monkeypatch):
    _sync_default_user(client)

    values = iter([True, False, True])
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: next(values))

    start_stage1_first = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    assert start_stage1_first.status_code == 200
    first_round_id = start_stage1_first.json()["data"]["round_id"]

    first_message = client.post(
        f"/api/v1/rounds/{first_round_id}/messages",
        headers=auth_headers,
        json={"content": "첫 번째 라운드 증거 메시지"},
    )
    assert first_message.status_code == 200
    assert first_message.json()["is_evidence"] is True

    judge_first = client.post(
        f"/api/v1/rounds/{first_round_id}/judge",
        headers=auth_headers,
        json={"is_fraud_judged": True},
    )
    assert judge_first.status_code == 200

    start_stage1_second = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    assert start_stage1_second.status_code == 200
    second_round_id = start_stage1_second.json()["data"]["round_id"]

    start_other_stage = client.post("/api/v1/stages/2/rounds", headers=auth_headers)
    assert start_other_stage.status_code == 200
    assert start_other_stage.json()["data"]["round_id"]

    rounds_response = client.get("/api/v1/stages/1/rounds", headers=auth_headers)
    assert rounds_response.status_code == 200
    body = rounds_response.json()

    assert body["stage_id"] == 1
    assert len(body["rounds"]) == 2
    assert body["rounds"][0]["round_id"] == second_round_id
    assert body["rounds"][0]["status"] == "in_progress"
    assert body["rounds"][1]["round_id"] == first_round_id
    assert body["rounds"][1]["status"] == "judged"
    assert body["rounds"][1]["is_fraud_scenario"] is True


def test_list_stage_rounds_404_for_missing_stage(client: TestClient, auth_headers: dict[str, str]):
    _sync_default_user(client)
    response = client.get("/api/v1/stages/999/rounds", headers=auth_headers)
    assert response.status_code == 400


def test_start_round_builds_mapped_prompt_and_resume_keeps_same_scenario(
    client: TestClient,
    db_session,
    auth_headers: dict[str, str],
    monkeypatch,
):
    from uuid import UUID

    from app.db.models import Round, Scenario
    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: True)
    monkeypatch.setattr("app.services.scenario_selector.random.choice", lambda seq: list(seq)[0])

    first_start = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    assert first_start.status_code == 200
    first_data = first_start.json()["data"]
    assert first_data["situation_prompt"] == "테스트 동적 사기 명분"
    assert first_data["ai_name"] == "테스트 공격자"

    round_obj = db_session.get(Round, UUID(first_data["round_id"]))
    assert round_obj is not None
    scenario = db_session.get(Scenario, round_obj.scenario_id)
    assert scenario is not None
    assert scenario.fraud_evidence_keys == ["테스트 공격 수단"]
    assert "테스트 동적 사기 명분" in scenario.system_prompt

    resumed = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    assert resumed.status_code == 200
    resumed_data = resumed.json()["data"]
    assert resumed_data["round_id"] == first_data["round_id"]
    assert resumed_data["scenario_id"] == first_data["scenario_id"]
    assert resumed_data["situation_prompt"] == first_data["situation_prompt"]


def test_start_round_worker_initial_message_and_resume_no_duplicate(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
):
    from app.core.config import get_settings

    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: False)
    settings = get_settings()
    original_enabled = settings.ai_worker_enabled
    original_token = settings.ai_worker_token
    settings.ai_worker_enabled = True
    settings.ai_worker_token = "test-token"

    calls = {"count": 0}

    def _fake_worker(*, settings, payload):
        from app.services.ai import AIReply
        calls["count"] += 1
        assert payload["messages"] == []
        return AIReply(
            content="initial ai",
            is_evidence=False,
            evidence_reason=None,
            input_tokens=None,
            output_tokens=None,
            latency_ms=1,
            worker_is_conversation_over=False,
        )

    monkeypatch.setattr("app.services.stage_service.call_normal_worker", _fake_worker)

    start = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    assert start.status_code == 200
    data = start.json()["data"]
    assert data["initial_message"]["content"] == "initial ai"
    assert calls["count"] == 1

    resumed = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    assert resumed.status_code == 200
    resumed_data = resumed.json()["data"]
    assert resumed_data["round_id"] == data["round_id"]
    assert resumed_data["initial_message"]["content"] == "initial ai"
    assert calls["count"] == 1

    settings.ai_worker_enabled = original_enabled
    settings.ai_worker_token = original_token


def test_start_round_worker_uses_token_without_explicit_enabled(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
):
    from app.core.config import get_settings

    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: False)
    settings = get_settings()
    original_enabled = settings.ai_worker_enabled
    original_token = settings.ai_worker_token
    settings.ai_worker_enabled = False
    settings.ai_worker_token = "test-token"

    calls = {"count": 0}

    def _fake_worker(*, settings, payload):
        from app.services.ai import AIReply

        calls["count"] += 1
        return AIReply(
            content="token enabled initial ai",
            is_evidence=False,
            evidence_reason=None,
            input_tokens=None,
            output_tokens=None,
            latency_ms=1,
            worker_is_conversation_over=False,
        )

    monkeypatch.setattr("app.services.stage_service.call_normal_worker", _fake_worker)

    try:
        start = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
        assert start.status_code == 200
        data = start.json()["data"]
        assert data["initial_message"]["content"] == "token enabled initial ai"
        assert calls["count"] == 1
    finally:
        settings.ai_worker_enabled = original_enabled
        settings.ai_worker_token = original_token


def test_round_stores_stable_scenario_context(client: TestClient, db_session, auth_headers: dict[str, str], monkeypatch):
    from uuid import UUID
    from app.db.models import Round

    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: False)

    start = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    assert start.status_code == 200
    round_id = start.json()["data"]["round_id"]

    r1 = db_session.get(Round, UUID(round_id))
    assert r1 is not None
    first_variant = r1.scenario_variant
    first_core = (r1.scenario_context or {}).get("core_item")

    send = client.post(f"/api/v1/rounds/{round_id}/messages", headers=auth_headers, json={"content": "첫 질문"})
    assert send.status_code == 200

    r2 = db_session.get(Round, UUID(round_id))
    assert r2 is not None
    assert r2.scenario_variant == first_variant
    assert (r2.scenario_context or {}).get("core_item") == first_core


def test_normal_prompt_catalog_contains_handoff_required_context_fields():
    from app.services.normal_prompt_catalog import NORMAL_SCENARIO_CATALOG, build_normal_prompt_context

    required_keys = {
        "display_label",
        "user_role",
        "counterpart_role",
        "core_item",
        "current_stage",
        "situation",
        "user_intent",
        "counterpart_help",
        "normal_safe_path",
        "watch_boundary",
        "benign_objective",
        "safe_topics",
        "forbidden_behaviors",
        "tone_examples",
    }

    for genre, catalog in NORMAL_SCENARIO_CATALOG.items():
        for variant in catalog["variants"]:
            prompt = build_normal_prompt_context(genre=genre, variant=variant)
            assert prompt.scenario_type == genre
            assert prompt.scenario_variant == variant
            assert required_keys <= set(prompt.scenario_context)
            assert prompt.situation_prompt.startswith("상황: ")
            assert "\n현재 단계: " in prompt.situation_prompt
            assert "\n내가 하려는 것: " in prompt.situation_prompt


def test_start_round_worker_payload_uses_prompt_source_handoff_context(
    client: TestClient,
    db_session,
    auth_headers: dict[str, str],
    monkeypatch,
):
    from app.core.config import get_settings
    from app.db.models import User

    _sync_default_user(client)
    user = db_session.get(User, "dev-user-001")
    user.main_bank = "국민은행"
    db_session.commit()

    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: False)
    monkeypatch.setattr("app.services.normal_prompt_catalog.random.choice", lambda seq: list(seq)[0])

    settings = get_settings()
    original_enabled = settings.ai_worker_enabled
    original_token = settings.ai_worker_token
    settings.ai_worker_enabled = True
    settings.ai_worker_token = "test-token"

    captured = {}

    def _fake_worker(*, settings, payload):
        from app.services.ai import AIReply

        captured["payload"] = payload
        return AIReply(
            content="initial ai",
            is_evidence=False,
            evidence_reason=None,
            input_tokens=None,
            output_tokens=None,
            latency_ms=1,
            worker_is_conversation_over=False,
        )

    monkeypatch.setattr("app.services.stage_service.call_normal_worker", _fake_worker)

    try:
        start = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
        assert start.status_code == 200
        data = start.json()["data"]
        assert data["situation_prompt"].startswith("상황: 은행에서 로그인/이체 이상 징후 알림을 받은 상황")
        assert "현재 단계: 이상거래 알림을 받고 본인 확인 절차를 문의하는 단계" in data["situation_prompt"]
        assert "내가 하려는 것: 내 계좌가 안전한지 확인하고 공식 보호 절차를 진행하고 싶음" in data["situation_prompt"]
        assert data["ai_name"] == "국민은행 보안센터 상담원"

        payload = captured["payload"]
        assert payload["scenario_type"] == "보이스피싱"
        assert payload["scenario_variant"] == "bank_unusual_activity"
        assert payload["user_profile"]["mainBank"] == "국민은행"
        context = payload["scenario_context"]
        assert context["canonical_label"] == "기관사칭형피싱"
        assert context["display_label"] == "고객지원 문의"
        assert context["counterpart_role"] == "국민은행 보안센터 상담원"
        assert context["core_item"] == "이상거래 감지 안내"
        assert context["normal_safe_path"] == "공식 앱 알림 확인 -> 대표 고객센터 재확인 -> 필요 시 지점 방문"
        assert context["forbidden_behaviors"] == ["단정적 위협 안내", "민감정보 요구", "링크 입력 강요"]
    finally:
        settings.ai_worker_enabled = original_enabled
        settings.ai_worker_token = original_token


def test_random_stage_normal_context_uses_selected_genre_not_random_stage_title(
    client: TestClient,
    db_session,
    auth_headers: dict[str, str],
    monkeypatch,
):
    from uuid import UUID

    from app.db.models import Round

    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: False)
    monkeypatch.setattr("app.services.scenario_selector.random.choice", lambda seq: list(seq)[0])
    monkeypatch.setattr("app.services.normal_prompt_catalog.random.choice", lambda seq: list(seq)[0])

    start = client.post("/api/v1/stages/6/rounds", headers=auth_headers)
    assert start.status_code == 200
    round_id = start.json()["data"]["round_id"]

    round_obj = db_session.get(Round, UUID(round_id))
    assert round_obj is not None
    assert round_obj.scenario_type == "보이스피싱"
    assert round_obj.scenario_variant == "bank_unusual_activity"
    assert round_obj.scenario_context["display_label"] == "고객지원 문의"
    assert round_obj.scenario_context["core_item"] == "이상거래 감지 안내"
