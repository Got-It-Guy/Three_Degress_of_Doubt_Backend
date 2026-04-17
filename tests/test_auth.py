from fastapi.testclient import TestClient


def test_firebase_login_creates_and_updates_user(client: TestClient, monkeypatch):
    from app.api.routers import auth as auth_router_module

    def fake_sync_user_from_firebase_token(*, db, id_token, settings):
        from app.services.user_service import sync_user
        from app.schemas.users import UserSyncRequest

        if id_token == "token-1":
            payload = UserSyncRequest(
                uid="firebase-user-001",
                email="firebase@example.com",
                nickname="firebase-user",
                provider="google.com",
                profile_image="https://example.com/profile-1.png",
            )
        else:
            payload = UserSyncRequest(
                uid="firebase-user-001",
                email="firebase@example.com",
                nickname="firebase-user-updated",
                provider="google.com",
                profile_image="https://example.com/profile-2.png",
            )

        return sync_user(db=db, payload=payload)

    monkeypatch.setattr(auth_router_module, "sync_user_from_firebase_token", fake_sync_user_from_firebase_token)

    response = client.post("/api/auth/firebase-login", json={"id_token": "token-1"})
    assert response.status_code == 200
    body = response.json()
    assert body["uid"] == "firebase-user-001"
    assert body["nickname"] == "firebase-user"
    assert body["provider"] == "google.com"
    assert body["token_type"] == "Bearer"

    response = client.post("/api/auth/firebase-login", json={"id_token": "token-2"})
    assert response.status_code == 200
    body = response.json()
    assert body["uid"] == "firebase-user-001"
    assert body["nickname"] == "firebase-user-updated"
    assert body["profile_image"] == "https://example.com/profile-2.png"
