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
    assert len(stages) >= 10
    assert stages[0]["stage_score"] == 0

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

    judge_first = client.post(
        f"/api/v1/rounds/{first_round_id}/judge",
        headers=auth_headers,
        json={"is_fraud_judged": True},
    )
    assert judge_first.status_code == 200

    start_stage1_second = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    assert start_stage1_second.status_code == 200
    second_round_id = start_stage1_second.json()["data"]["round_id"]

    start_stage2 = client.post("/api/v1/stages/2/rounds", headers=auth_headers)
    assert start_stage2.status_code == 200
    assert start_stage2.json()["data"]["round_id"]

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
    assert "핵심 위험 신호" in first_data["situation_prompt"]

    round_obj = db_session.get(Round, UUID(first_data["round_id"]))
    assert round_obj is not None
    scenario = db_session.get(Scenario, round_obj.scenario_id)
    assert scenario is not None
    assert scenario.fraud_evidence_keys == ["기관 사칭"]
    assert "이번 라운드의 핵심 단서는 '기관 사칭'이다." in scenario.system_prompt

    resumed = client.post("/api/v1/stages/1/rounds", headers=auth_headers)
    assert resumed.status_code == 200
    resumed_data = resumed.json()["data"]
    assert resumed_data["round_id"] == first_data["round_id"]
    assert resumed_data["scenario_id"] == first_data["scenario_id"]
    assert resumed_data["situation_prompt"] == first_data["situation_prompt"]
