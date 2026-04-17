from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.core.config import Settings


def _get_firebase_modules():
    try:
        import firebase_admin
        from firebase_admin import auth, credentials
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"firebase-admin 패키지가 필요합니다: {exc}",
        ) from exc
    return firebase_admin, auth, credentials


def ensure_firebase_initialized(settings: Settings) -> None:
    firebase_admin, _, credentials = _get_firebase_modules()

    if firebase_admin._apps:
        return

    init_kwargs: dict[str, Any] = {}
    if settings.firebase_project_id:
        init_kwargs["options"] = {"projectId": settings.firebase_project_id}

    if settings.google_application_credentials:
        cred = credentials.Certificate(settings.google_application_credentials)
        firebase_admin.initialize_app(cred, **init_kwargs)
    else:
        firebase_admin.initialize_app(**init_kwargs)


def verify_firebase_id_token(*, id_token: str, settings: Settings) -> dict[str, Any]:
    if not id_token or not id_token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase ID 토큰이 필요합니다.",
        )

    _, auth, _ = _get_firebase_modules()
    ensure_firebase_initialized(settings)

    try:
        return auth.verify_id_token(id_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Firebase 토큰 검증에 실패했습니다: {exc}",
        ) from exc


def get_firebase_user(*, uid: str, settings: Settings):
    _, auth, _ = _get_firebase_modules()
    ensure_firebase_initialized(settings)
    return auth.get_user(uid)
