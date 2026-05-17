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


def test_round_message_judge_and_report_success(client: TestClient, auth_headers: dict[str, str], monkeypatch):
    from app.services.fraud_placeholder import FRAUD_PLACEHOLDER_MESSAGE

    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: True)

    start_response = client.post("/api/v1/stages/5/rounds", headers=auth_headers)
    assert start_response.status_code == 200
    round_id = start_response.json()["data"]["round_id"]

    message_response = client.post(
        f"/api/v1/rounds/{round_id}/messages",
        headers=auth_headers,
        json={"content": "?먯꽭???덉감瑜??뚮젮二쇱꽭??"},
    )
    assert message_response.status_code == 200
    assert message_response.json()["role"] == "ai"
    assert message_response.json()["content"] == FRAUD_PLACEHOLDER_MESSAGE
    assert message_response.json()["is_evidence"] is True
    assert message_response.json()["is_conversation_over"] is False

    judge_response = client.post(
        f"/api/v1/rounds/{round_id}/judge",
        headers=auth_headers,
        json={"is_fraud_judged": True},
    )
    assert judge_response.status_code == 200
    judge_body = judge_response.json()
    assert judge_body["result"] == "pass"
    assert judge_body["current_score"] == 1

    report_response = client.get(f"/api/v1/rounds/{round_id}/report", headers=auth_headers)
    assert report_response.status_code == 200
    report_body = report_response.json()
    assert report_body["report_type"] == "fraud_found"
    assert len(report_body["fraud_points"]) >= 1



def test_normal_scenario_has_no_evidence_and_false_alarm_report(client: TestClient, auth_headers: dict[str, str], monkeypatch):
    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: False)

    start_response = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    round_id = start_response.json()["data"]["round_id"]

    message_response = client.post(
        f"/api/v1/rounds/{round_id}/messages",
        headers=auth_headers,
        json={"content": "?덉감瑜??ㅻ챸??二쇱꽭??"},
    )
    assert message_response.status_code == 200
    assert message_response.json()["is_evidence"] is False

    judge_response = client.post(
        f"/api/v1/rounds/{round_id}/judge",
        headers=auth_headers,
        json={"is_fraud_judged": True},
    )
    assert judge_response.status_code == 200
    assert judge_response.json()["result"] == "warning"

    report_response = client.get(f"/api/v1/rounds/{round_id}/report", headers=auth_headers)
    assert report_response.status_code == 200
    assert report_response.json()["report_type"] == "false_alarm"



def test_fraud_scenario_wrong_safe_judgement_creates_fraud_missed_report(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
):
    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: True)

    start_response = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    round_id = start_response.json()["data"]["round_id"]

    judge_response = client.post(
        f"/api/v1/rounds/{round_id}/judge",
        headers=auth_headers,
        json={"is_fraud_judged": False},
    )
    assert judge_response.status_code == 200
    assert judge_response.json()["result"] == "warning"

    report_response = client.get(f"/api/v1/rounds/{round_id}/report", headers=auth_headers)
    assert report_response.status_code == 200
    assert report_response.json()["report_type"] == "fraud_missed"



def test_two_wrong_judgements_trigger_reset(client: TestClient, auth_headers: dict[str, str], monkeypatch):
    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: True)

    first_round_id = client.post("/api/v1/stages/5/rounds", headers=auth_headers).json()["data"]["round_id"]
    first_judge = client.post(
        f"/api/v1/rounds/{first_round_id}/judge",
        headers=auth_headers,
        json={"is_fraud_judged": False},
    )
    assert first_judge.status_code == 200
    assert first_judge.json()["result"] == "warning"
    assert first_judge.json()["current_warning"] == 1

    second_round_id = client.post("/api/v1/stages/5/rounds", headers=auth_headers).json()["data"]["round_id"]
    assert second_round_id == first_round_id
    second_judge = client.post(
        f"/api/v1/rounds/{second_round_id}/judge",
        headers=auth_headers,
        json={"is_fraud_judged": False},
    )
    assert second_judge.status_code == 200
    assert second_judge.json()["result"] == "reset"
    assert second_judge.json()["current_warning"] == 0
    assert second_judge.json()["current_score"] == 0


def test_stage_warning_persists_after_pass_and_next_round(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
):
    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: False)

    start = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    assert start.status_code == 200
    round_id = start.json()["data"]["round_id"]

    wrong = client.post(
        f"/api/v1/rounds/{round_id}/judge",
        headers=auth_headers,
        json={"is_fraud_judged": True},
    )
    assert wrong.status_code == 200
    assert wrong.json()["result"] == "warning"
    assert wrong.json()["current_warning"] == 1

    correct = client.post(
        f"/api/v1/rounds/{round_id}/judge",
        headers=auth_headers,
        json={"is_fraud_judged": False},
    )
    assert correct.status_code == 200
    assert correct.json()["result"] == "pass"
    assert correct.json()["current_score"] == 1
    assert correct.json()["current_warning"] == 1

    next_start = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    assert next_start.status_code == 200
    assert next_start.json()["data"]["round_id"] != round_id

    stages = client.get("/api/v1/stages", headers=auth_headers)
    stage1 = next(stage for stage in stages.json()["stages"] if stage["stage_id"] == 1)
    assert stage1["stage_score"] == 1
    assert stage1["warning_count"] == 1



def test_round_messages_can_be_restored_for_incomplete_round(client: TestClient, auth_headers: dict[str, str], monkeypatch):
    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: True)

    start_response = client.post("/api/v1/stages/5/rounds", headers=auth_headers)
    assert start_response.status_code == 200
    round_id = start_response.json()["data"]["round_id"]

    first_message = client.post(
        f"/api/v1/rounds/{round_id}/messages",
        headers=auth_headers,
        json={"content": "?섏씡 援ъ“瑜??ㅻ챸??二쇱꽭??"},
    )
    assert first_message.status_code == 200

    resumed_start = client.post("/api/v1/stages/5/rounds", headers=auth_headers)
    assert resumed_start.status_code == 200
    assert resumed_start.json()["data"]["round_id"] == round_id

    messages_response = client.get(f"/api/v1/rounds/{round_id}/messages", headers=auth_headers)
    assert messages_response.status_code == 200
    body = messages_response.json()
    assert body["round_id"] == round_id
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][0]["content"] == "?섏씡 援ъ“瑜??ㅻ챸??二쇱꽭??"
    assert body["messages"][1]["role"] == "ai"


def test_round_context_returns_summary_plus_recent_messages(client: TestClient, auth_headers: dict[str, str], monkeypatch):
    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: True)

    start_response = client.post("/api/v1/stages/5/rounds", headers=auth_headers)
    assert start_response.status_code == 200
    round_id = start_response.json()["data"]["round_id"]

    prompts = [
        "泥?踰덉㎏ 吏덈Ц?낅땲??",
        "??踰덉㎏ 吏덈Ц?낅땲??",
        "??踰덉㎏ 吏덈Ц?낅땲??",
        "??踰덉㎏ 吏덈Ц?낅땲??",
        "?ㅼ꽢 踰덉㎏ 吏덈Ц?낅땲??",
    ]
    for prompt in prompts:
        response = client.post(
            f"/api/v1/rounds/{round_id}/messages",
            headers=auth_headers,
            json={"content": prompt},
        )
        assert response.status_code == 200

    context_response = client.get(f"/api/v1/rounds/{round_id}/context", headers=auth_headers)
    assert context_response.status_code == 200
    body = context_response.json()

    assert body["round_id"] == round_id
    assert body["total_message_count"] == 10
    assert body["recent_message_count"] == 8
    assert len(body["recent_messages"]) == 8
    assert body["conversation_summary"] is not None
    assert "泥?踰덉㎏ 吏덈Ц?낅땲??" in body["conversation_summary"]
    assert body["last_summarized_message_id"]
    assert body["recent_messages"][0]["content"] == "??踰덉㎏ 吏덈Ц?낅땲??"


def test_worker_payload_uses_db_history_and_profile_without_private_ids(
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

    captured = {}

    def _fake_worker(*, settings, payload):
        from app.services.ai import AIReply
        captured["payload"] = payload
        return AIReply(
            content="worker answer",
            is_evidence=False,
            evidence_reason=None,
            input_tokens=None,
            output_tokens=None,
            latency_ms=1,
            worker_is_conversation_over=False,
        )

    monkeypatch.setattr("app.services.stage_service.call_normal_worker", _fake_worker)
    monkeypatch.setattr("app.services.round_service.call_normal_worker", _fake_worker)

    start = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    round_id = start.json()["data"]["round_id"]

    msg = client.post(
        f"/api/v1/rounds/{round_id}/messages",
        headers=auth_headers,
        json={"content": "안내 부탁해요"},
    )
    assert msg.status_code == 200
    payload = captured["payload"]
    assert "email" not in payload["user_profile"]
    assert "uid" not in payload["user_profile"]
    assert payload["messages"][-1]["role"] == "user"
    assert payload["messages"][-1]["content"] == "안내 부탁해요"
    assert payload["scenario_context"]["core_item"]

    settings.ai_worker_enabled = original_enabled
    settings.ai_worker_token = original_token


def test_worker_done_ends_round_and_rejects_new_message(client: TestClient, auth_headers: dict[str, str], monkeypatch):
    from app.core.config import get_settings

    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: False)
    settings = get_settings()
    original_enabled = settings.ai_worker_enabled
    original_token = settings.ai_worker_token
    settings.ai_worker_enabled = True
    settings.ai_worker_token = "test-token"

    turn = {"n": 0}

    def _fake_worker(*, settings, payload):
        from app.services.ai import AIReply
        turn["n"] += 1
        return AIReply(
            content=f"worker-{turn['n']}",
            is_evidence=False,
            evidence_reason=None,
            input_tokens=None,
            output_tokens=None,
            latency_ms=1,
            worker_is_conversation_over=turn["n"] >= 2,
        )

    monkeypatch.setattr("app.services.stage_service.call_normal_worker", _fake_worker)
    monkeypatch.setattr("app.services.round_service.call_normal_worker", _fake_worker)

    start = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    round_id = start.json()["data"]["round_id"]
    r1 = client.post(f"/api/v1/rounds/{round_id}/messages", headers=auth_headers, json={"content": "첫 질문"})
    assert r1.status_code == 200
    assert r1.json()["is_conversation_over"] is True
    assert r1.json()["ended_reason"] == "worker_done"

    stages = client.get("/api/v1/stages", headers=auth_headers)
    assert stages.status_code == 200
    stage1 = next(stage for stage in stages.json()["stages"] if stage["stage_id"] == 1)
    assert stage1["stage_score"] == 1

    report = client.get(f"/api/v1/rounds/{round_id}/report", headers=auth_headers)
    assert report.status_code == 200
    assert report.json()["report_type"] == "false_alarm"

    r2 = client.post(f"/api/v1/rounds/{round_id}/messages", headers=auth_headers, json={"content": "둘째 질문"})
    assert r2.status_code == 409

    settings.ai_worker_enabled = original_enabled
    settings.ai_worker_token = original_token


def test_stage_clear_keeps_score_until_next_attempt_and_keeps_best_round_count(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
    db_session,
):
    from app.db.models import Stage

    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: True)

    stage = db_session.get(Stage, 5)
    stage.required_score = 1
    db_session.commit()

    start = client.post("/api/v1/stages/5/rounds", headers=auth_headers)
    assert start.status_code == 200
    round_id = start.json()["data"]["round_id"]

    message = client.post(
        f"/api/v1/rounds/{round_id}/messages",
        headers=auth_headers,
        json={"content": "사기 단서 확인"},
    )
    assert message.status_code == 200
    assert message.json()["is_evidence"] is True

    judge = client.post(
        f"/api/v1/rounds/{round_id}/judge",
        headers=auth_headers,
        json={"is_fraud_judged": True},
    )
    assert judge.status_code == 200
    judge_body = judge.json()
    assert judge_body["result"] == "pass"
    assert judge_body["current_score"] == 1
    assert judge_body["is_stage_cleared"] is True

    stages = client.get("/api/v1/stages", headers=auth_headers)
    stage5 = next(stage for stage in stages.json()["stages"] if stage["stage_id"] == 5)
    assert stage5["stage_score"] == 1
    assert stage5["total_round_count"] == 1
    assert stage5["best_round_count"] == 1
    assert stage5["is_cleared"] is True

    enter_again = client.post("/api/v1/stages/5/enter", headers=auth_headers)
    assert enter_again.status_code == 200
    enter_body = enter_again.json()
    assert enter_body["stage_score"] == 0
    assert enter_body["total_round_count"] == 0
    assert enter_body["is_cleared"] is False

    stages_after_enter = client.get("/api/v1/stages", headers=auth_headers)
    stage5_after_enter = next(stage for stage in stages_after_enter.json()["stages"] if stage["stage_id"] == 5)
    assert stage5_after_enter["stage_score"] == 0
    assert stage5_after_enter["total_round_count"] == 0
    assert stage5_after_enter["best_round_count"] == 1
    assert stage5_after_enter["is_cleared"] is False


def test_explicit_end_endpoint_marks_user_stop(client: TestClient, auth_headers: dict[str, str], monkeypatch):
    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: True)
    start = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    round_id = start.json()["data"]["round_id"]

    end = client.post(f"/api/v1/rounds/{round_id}/end", headers=auth_headers)
    assert end.status_code == 200
    blocked = client.post(f"/api/v1/rounds/{round_id}/messages", headers=auth_headers, json={"content": "test"})
    assert blocked.status_code == 409



def test_phrase_rule_common_close_after_min_turns():
    from app.services.conversation_end import decide_end_reason

    reason = decide_end_reason(
        user_text="감사합니다 안내 잘 받았습니다",
        ai_text="확인되었습니다. 좋은 하루 보내세요",
        user_turn_count=3,
        min_user_turns_for_natural_end=3,
        max_user_turns=20,
        scenario_type="일반",
        worker_is_conversation_over=False,
    )
    assert reason == "phrase_common_close"


def test_phrase_rule_early_thanks_does_not_close():
    from app.services.conversation_end import decide_end_reason

    reason = decide_end_reason(
        user_text="감사합니다",
        ai_text="감사합니다",
        user_turn_count=1,
        min_user_turns_for_natural_end=3,
        max_user_turns=20,
        scenario_type="일반",
        worker_is_conversation_over=False,
    )
    assert reason is None


def test_phrase_rule_marketplace_close():
    from app.services.conversation_end import decide_end_reason

    reason = decide_end_reason(
        user_text="송금했습니다 기다리고 있을게요",
        ai_text="입금 확인되었습니다. 오늘 발송하겠습니다",
        user_turn_count=3,
        min_user_turns_for_natural_end=3,
        max_user_turns=20,
        scenario_type="중고거래",
        worker_is_conversation_over=False,
    )
    assert reason == "phrase_marketplace_close"


def test_phrase_rule_real_estate_appointment_close():
    from app.services.conversation_end import decide_end_reason

    reason = decide_end_reason(
        user_text="내일 10시에 방문하겠습니다 그때 뵙겠습니다",
        ai_text="방문 일정 예약 확정되었습니다",
        user_turn_count=3,
        min_user_turns_for_natural_end=3,
        max_user_turns=20,
        scenario_type="부동산",
        worker_is_conversation_over=False,
    )
    assert reason == "phrase_real_estate_appointment_close"


def test_phrase_rule_real_estate_exploratory_stays_open():
    from app.services.conversation_end import decide_end_reason

    reason = decide_end_reason(
        user_text="내일 보러 가도 되나요",
        ai_text="가능한 시간 확인해보겠습니다",
        user_turn_count=3,
        min_user_turns_for_natural_end=3,
        max_user_turns=20,
        scenario_type="부동산",
        worker_is_conversation_over=False,
    )
    assert reason is None


def test_phrase_rule_consultation_close():
    from app.services.conversation_end import decide_end_reason

    reason = decide_end_reason(
        user_text="알겠습니다 공식 앱에서 확인해보겠습니다 안내 감사합니다",
        ai_text="공식 앱과 고객센터 기준으로 확인해보시면 됩니다 감사합니다",
        user_turn_count=3,
        min_user_turns_for_natural_end=3,
        max_user_turns=20,
        scenario_type="투자",
        worker_is_conversation_over=False,
    )
    assert reason == "phrase_consultation_close"


def test_phrase_rule_max_turns_close():
    from app.services.conversation_end import decide_end_reason

    reason = decide_end_reason(
        user_text="계속 진행",
        ai_text="안내 계속",
        user_turn_count=20,
        min_user_turns_for_natural_end=3,
        max_user_turns=20,
        scenario_type="일반",
        worker_is_conversation_over=False,
    )
    assert reason == "max_turns"


def test_worker_error_does_not_persist_ai_message(client: TestClient, auth_headers: dict[str, str], monkeypatch):
    from app.core.config import get_settings
    from app.core.exceptions import ApiError
    from app.services.ai import AIReply

    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: False)
    settings = get_settings()
    original_enabled = settings.ai_worker_enabled
    original_token = settings.ai_worker_token
    settings.ai_worker_enabled = True
    settings.ai_worker_token = "test-token"

    def _ok_worker(*, settings, payload):
        return AIReply(
            content="initial",
            is_evidence=False,
            evidence_reason=None,
            input_tokens=None,
            output_tokens=None,
            latency_ms=1,
            worker_is_conversation_over=False,
        )

    monkeypatch.setattr("app.services.stage_service.call_normal_worker", _ok_worker)
    start = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    round_id = start.json()["data"]["round_id"]

    def _fail_worker(*, settings, payload):
        raise ApiError("AI 응답 생성에 실패했습니다. 잠시 후 다시 시도해주세요.", status_code=504)

    monkeypatch.setattr("app.services.round_service.call_normal_worker", _fail_worker)

    before = client.get(f"/api/v1/rounds/{round_id}/messages", headers=auth_headers).json()["messages"]
    send = client.post(f"/api/v1/rounds/{round_id}/messages", headers=auth_headers, json={"content": "질문"})
    assert send.status_code == 504
    after = client.get(f"/api/v1/rounds/{round_id}/messages", headers=auth_headers).json()["messages"]
    assert len(after) == len(before) + 1
    assert after[-1]["role"] == "user"

    settings.ai_worker_enabled = original_enabled
    settings.ai_worker_token = original_token


def test_call_normal_worker_401_maps_error(monkeypatch):
    from app.core.config import get_settings
    from app.core.exceptions import ApiError
    from app.services.ai import call_normal_worker

    class _Resp:
        status_code = 401

        def json(self):
            return {"status": "error"}

    class _Client:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            return _Resp()

    monkeypatch.setattr("app.services.ai.httpx.Client", _Client)

    settings = get_settings()
    settings.ai_worker_token = "token"
    try:
        call_normal_worker(settings=settings, payload={})
        assert False, "expected ApiError"
    except ApiError as exc:
        assert exc.status_code == 502


def test_call_normal_worker_5xx_maps_error(monkeypatch):
    from app.core.config import get_settings
    from app.core.exceptions import ApiError
    from app.services.ai import call_normal_worker

    class _Resp:
        status_code = 503

        def json(self):
            return {"status": "error"}

    class _Client:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            return _Resp()

    monkeypatch.setattr("app.services.ai.httpx.Client", _Client)

    settings = get_settings()
    settings.ai_worker_token = "token"
    try:
        call_normal_worker(settings=settings, payload={})
        assert False, "expected ApiError"
    except ApiError as exc:
        assert exc.status_code == 503


def test_call_normal_worker_invalid_response_maps_error(monkeypatch):
    from app.core.config import get_settings
    from app.core.exceptions import ApiError
    from app.services.ai import call_normal_worker

    class _Resp:
        status_code = 200

        def json(self):
            return {"status": "success", "content": ""}

    class _Client:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            return _Resp()

    monkeypatch.setattr("app.services.ai.httpx.Client", _Client)

    settings = get_settings()
    settings.ai_worker_token = "token"
    try:
        call_normal_worker(settings=settings, payload={})
        assert False, "expected ApiError"
    except ApiError as exc:
        assert exc.status_code == 502


def test_call_normal_worker_timeout_maps_error(monkeypatch):
    import httpx
    from app.core.config import get_settings
    from app.core.exceptions import ApiError
    from app.services.ai import call_normal_worker

    class _Client:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            raise httpx.TimeoutException("timeout")

    monkeypatch.setattr("app.services.ai.httpx.Client", _Client)

    settings = get_settings()
    settings.ai_worker_token = "token"
    try:
        call_normal_worker(settings=settings, payload={})
        assert False, "expected ApiError"
    except ApiError as exc:
        assert exc.status_code == 504


def test_call_normal_worker_connection_error_maps_error(monkeypatch):
    import httpx
    from app.core.config import get_settings
    from app.core.exceptions import ApiError
    from app.services.ai import call_normal_worker

    class _Client:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            raise httpx.ConnectError("down")

    monkeypatch.setattr("app.services.ai.httpx.Client", _Client)

    settings = get_settings()
    settings.ai_worker_token = "token"
    try:
        call_normal_worker(settings=settings, payload={})
        assert False, "expected ApiError"
    except ApiError as exc:
        assert exc.status_code == 503


def test_send_message_rejects_completed_round(client: TestClient, auth_headers: dict[str, str], monkeypatch):
    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: True)

    start = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    round_id = start.json()["data"]["round_id"]

    end = client.post(f"/api/v1/rounds/{round_id}/end", headers=auth_headers)
    assert end.status_code == 200

    blocked = client.post(
        f"/api/v1/rounds/{round_id}/messages",
        headers=auth_headers,
        json={"content": "추가 메시지"},
    )
    assert blocked.status_code == 409


def test_explicit_end_does_not_overwrite_existing_ended_reason(client: TestClient, auth_headers: dict[str, str], monkeypatch):
    from app.core.config import get_settings
    from app.services.ai import AIReply

    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: False)

    settings = get_settings()
    prev_enabled = settings.ai_worker_enabled
    prev_token = settings.ai_worker_token
    settings.ai_worker_enabled = True
    settings.ai_worker_token = "test-token"

    turn = {"n": 0}

    def _fake_worker(*, settings, payload):
        turn["n"] += 1
        return AIReply(
            content=f"worker-{turn['n']}",
            is_evidence=False,
            evidence_reason=None,
            input_tokens=None,
            output_tokens=None,
            latency_ms=1,
            worker_is_conversation_over=turn["n"] >= 2,
        )

    monkeypatch.setattr("app.services.stage_service.call_normal_worker", _fake_worker)
    monkeypatch.setattr("app.services.round_service.call_normal_worker", _fake_worker)

    start = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    round_id = start.json()["data"]["round_id"]

    send = client.post(
        f"/api/v1/rounds/{round_id}/messages",
        headers=auth_headers,
        json={"content": "첫 질문"},
    )
    assert send.status_code == 200
    assert send.json()["ended_reason"] == "worker_done"

    end_again = client.post(f"/api/v1/rounds/{round_id}/end", headers=auth_headers)
    assert end_again.status_code == 200

    send_after = client.post(
        f"/api/v1/rounds/{round_id}/messages",
        headers=auth_headers,
        json={"content": "둘째 질문"},
    )
    assert send_after.status_code == 409

    settings.ai_worker_enabled = prev_enabled
    settings.ai_worker_token = prev_token
