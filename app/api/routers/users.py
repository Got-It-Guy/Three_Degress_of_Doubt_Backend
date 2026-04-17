from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser, get_current_user
from app.core.config import Settings, get_settings
from app.core.time_utils import to_iso_z
from app.db.session import get_db
from app.schemas.users import (
    UserMeItem,
    UserMeResponse,
    UserMeUpdateRequest,
    UserSyncBody,
    UserSyncItem,
    UserSyncRequest,
    UserSyncResponse,
)
from app.services.user_service import get_me, sync_user, sync_user_from_firebase_token, update_me

router = APIRouter(prefix="/api/users", tags=["users"])
bearing_scheme = HTTPBearer(auto_error=False)


@router.post("/sync", response_model=UserSyncResponse)
def sync_user_endpoint(
    payload: UserSyncBody | UserSyncRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearing_scheme)],
) -> UserSyncResponse:
    if credentials is not None:
        result = sync_user_from_firebase_token(
            db=db,
            id_token=credentials.credentials,
            settings=settings,
            nickname=getattr(payload, "nickname", None),
        )
    else:
        if not isinstance(payload, UserSyncRequest):
            raise ValueError("인증 토큰이 없으면 uid, email, provider가 포함된 요청 본문이 필요합니다.")
        result = sync_user(db=db, payload=payload)

    user = result.user
    return UserSyncResponse(
        user=UserSyncItem(
            id=user.id,
            firebaseUid=user.uid,
            email=user.email,
            provider=user.provider,
            nickname=user.nickname,
            isNewUser=result.is_new_user,
        )
    )


@router.get("/me", response_model=UserMeResponse)
def get_me_endpoint(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserMeResponse:
    result = get_me(db=db, uid=current_user.uid, settings=settings)
    user = result.user
    return UserMeResponse(
        user=UserMeItem(
            id=user.id,
            firebaseUid=user.uid,
            email=user.email,
            provider=user.provider,
            nickname=user.nickname,
            emailVerified=result.email_verified,
            profileImageUrl=result.profile_image_url,
            isNewUser=result.is_new_user,
            createdAt=to_iso_z(user.created_at) or "",
            updatedAt=to_iso_z(user.updated_at) or "",
        )
    )


@router.patch("/me", response_model=UserMeResponse)
def patch_me_endpoint(
    payload: UserMeUpdateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserMeResponse:
    result = update_me(db=db, uid=current_user.uid, payload=payload, settings=settings)
    user = result.user
    return UserMeResponse(
        user=UserMeItem(
            id=user.id,
            firebaseUid=user.uid,
            email=user.email,
            provider=user.provider,
            nickname=user.nickname,
            emailVerified=result.email_verified,
            profileImageUrl=result.profile_image_url,
            isNewUser=result.is_new_user,
            createdAt=to_iso_z(user.created_at) or "",
            updatedAt=to_iso_z(user.updated_at) or "",
        )
    )
