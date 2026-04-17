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
    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: True)

    start_response = client.post("/api/v1/stages/5/rounds", headers=auth_headers)
    assert start_response.status_code == 200
    round_id = start_response.json()["data"]["round_id"]

    message_response = client.post(
        f"/api/v1/rounds/{round_id}/messages",
        headers=auth_headers,
        json={"content": "자세한 절차를 알려주세요."},
    )
    assert message_response.status_code == 200
    assert message_response.json()["role"] == "ai"
    assert message_response.json()["is_evidence"] is True

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
        json={"content": "절차를 설명해 주세요."},
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
    second_judge = client.post(
        f"/api/v1/rounds/{second_round_id}/judge",
        headers=auth_headers,
        json={"is_fraud_judged": False},
    )
    assert second_judge.status_code == 200
    assert second_judge.json()["result"] == "reset"
    assert second_judge.json()["current_warning"] == 0
    assert second_judge.json()["current_score"] == 0



def test_round_messages_can_be_restored_for_incomplete_round(client: TestClient, auth_headers: dict[str, str], monkeypatch):
    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: True)

    start_response = client.post("/api/v1/stages/5/rounds", headers=auth_headers)
    assert start_response.status_code == 200
    round_id = start_response.json()["data"]["round_id"]

    first_message = client.post(
        f"/api/v1/rounds/{round_id}/messages",
        headers=auth_headers,
        json={"content": "수익 구조를 설명해 주세요."},
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
    assert body["messages"][0]["content"] == "수익 구조를 설명해 주세요."
    assert body["messages"][1]["role"] == "ai"


def test_round_context_returns_summary_plus_recent_messages(client: TestClient, auth_headers: dict[str, str], monkeypatch):
    _sync_default_user(client)
    monkeypatch.setattr("app.services.scenario_selector.choose_is_fraud", lambda: True)

    start_response = client.post("/api/v1/stages/5/rounds", headers=auth_headers)
    assert start_response.status_code == 200
    round_id = start_response.json()["data"]["round_id"]

    prompts = [
        "첫 번째 질문입니다.",
        "두 번째 질문입니다.",
        "세 번째 질문입니다.",
        "네 번째 질문입니다.",
        "다섯 번째 질문입니다.",
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
    assert "첫 번째 질문입니다." in body["conversation_summary"]
    assert body["last_summarized_message_id"]
    assert body["recent_messages"][0]["content"] == "두 번째 질문입니다."
