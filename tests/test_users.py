from fastapi.testclient import TestClient


def test_sync_user_creates_and_updates_user(client: TestClient):
    payload = {
        "uid": "dev-user-001",
        "email": "user@example.com",
        "nickname": "first-name",
        "provider": "google",
        "profile_image": None,
    }
    response = client.post("/api/users/sync", json=payload)
    assert response.status_code == 200
    first_body = response.json()
    assert first_body["status"] == "success"
    assert first_body["user"]["id"] == 1
    assert first_body["user"]["firebaseUid"] == "dev-user-001"
    assert first_body["user"]["email"] == "user@example.com"
    assert first_body["user"]["provider"] == "google"
    assert first_body["user"]["nickname"] == "first-name"
    assert first_body["user"]["isNewUser"] is True

    payload["nickname"] = "updated-name"
    response = client.post("/api/users/sync", json=payload)
    assert response.status_code == 200
    second_body = response.json()
    assert second_body["user"]["id"] == 1
    assert second_body["user"]["nickname"] == "updated-name"
    assert second_body["user"]["isNewUser"] is False


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



def test_get_me_returns_profile(client: TestClient, auth_headers: dict[str, str]):
    _sync_default_user(client)
    response = client.get("/api/users/me", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()["user"]
    assert body["firebaseUid"] == "dev-user-001"
    assert body["email"] == "user@example.com"
    assert body["nickname"] == "tester"
    assert body["provider"] == "google"
    assert body["emailVerified"] is False
    assert body["profileImageUrl"] is None
    assert body["isNewUser"] is False
    assert body["createdAt"]
    assert body["updatedAt"]



def test_patch_me_updates_nickname_and_profile_image(client: TestClient, auth_headers: dict[str, str]):
    _sync_default_user(client)
    response = client.patch(
        "/api/users/me",
        headers=auth_headers,
        json={
            "nickname": "patched-name",
            "profileImageUrl": "https://cdn.example.com/profile.jpg",
        },
    )
    assert response.status_code == 200
    body = response.json()["user"]
    assert body["nickname"] == "patched-name"
    assert body["profileImageUrl"] == "https://cdn.example.com/profile.jpg"

    me_response = client.get("/api/users/me", headers=auth_headers)
    assert me_response.status_code == 200
    me_body = me_response.json()["user"]
    assert me_body["nickname"] == "patched-name"
    assert me_body["profileImageUrl"] == "https://cdn.example.com/profile.jpg"
