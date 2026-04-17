from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.time_utils import utc_now
from app.db.models import User
from app.repositories.users import add_user, get_next_user_numeric_id, get_user_by_uid
from app.schemas.users import UserMeUpdateRequest, UserSyncRequest
from app.services.firebase_auth import get_firebase_user, verify_firebase_id_token


@dataclass
class SyncUserResult:
    user: User
    is_new_user: bool


@dataclass
class UserProfileResult:
    user: User
    email_verified: bool
    profile_image_url: str | None
    is_new_user: bool


def _is_new_user(user: User) -> bool:
    return not bool((user.nickname or "").strip())


def _safe_get_firebase_user(uid: str, settings: Settings):
    try:
        return get_firebase_user(uid=uid, settings=settings)
    except Exception:
        return None


def build_user_profile_result(*, user: User, settings: Settings) -> UserProfileResult:
    firebase_user = _safe_get_firebase_user(user.uid, settings)
    email_verified = bool(getattr(firebase_user, "email_verified", False)) if firebase_user is not None else False
    profile_image_url = user.profile_image or getattr(firebase_user, "photo_url", None)
    return UserProfileResult(
        user=user,
        email_verified=email_verified,
        profile_image_url=profile_image_url,
        is_new_user=_is_new_user(user),
    )


def sync_user(*, db: Session, payload: UserSyncRequest) -> SyncUserResult:
    user = get_user_by_uid(db, payload.uid)
    is_new_user = user is None

    if user is None:
        user = User(
            id=get_next_user_numeric_id(db),
            uid=payload.uid,
            email=payload.email,
            nickname=payload.nickname,
            provider=payload.provider,
            profile_image=payload.profile_image,
            last_login_at=utc_now(),
        )
        add_user(db, user)
    else:
        user.email = payload.email
        user.nickname = payload.nickname
        user.provider = payload.provider
        user.profile_image = payload.profile_image
        user.last_login_at = utc_now()
        db.flush()

    db.commit()
    db.refresh(user)
    return SyncUserResult(user=user, is_new_user=is_new_user)



def sync_user_from_firebase_token(*, db: Session, id_token: str, settings: Settings, nickname: str | None = None) -> SyncUserResult:
    decoded = verify_firebase_id_token(id_token=id_token, settings=settings)

    uid = str(decoded["uid"])
    email = decoded.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 서버는 email이 포함된 Firebase 계정만 지원합니다.",
        )

    firebase_info = decoded.get("firebase") or {}
    provider = firebase_info.get("sign_in_provider") or "firebase"
    resolved_nickname = nickname or decoded.get("name") or email.split("@")[0]
    profile_image = decoded.get("picture")

    payload = UserSyncRequest(
        uid=uid,
        email=email,
        nickname=resolved_nickname,
        provider=provider,
        profile_image=profile_image,
    )
    return sync_user(db=db, payload=payload)



def get_me(*, db: Session, uid: str, settings: Settings) -> UserProfileResult:
    user = get_user_by_uid(db, uid)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")
    return build_user_profile_result(user=user, settings=settings)



def update_me(*, db: Session, uid: str, payload: UserMeUpdateRequest, settings: Settings) -> UserProfileResult:
    user = get_user_by_uid(db, uid)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")

    if payload.nickname is not None:
        user.nickname = payload.nickname

    if payload.profileImageUrl is not None:
        user.profile_image = payload.profileImageUrl
    elif payload.profileImageDataUrl is not None:
        user.profile_image = payload.profileImageDataUrl
    elif payload.profileImageBase64 is not None:
        user.profile_image = payload.profileImageBase64

    db.flush()
    db.commit()
    db.refresh(user)
    return build_user_profile_result(user=user, settings=settings)
