from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.auth import FirebaseLoginRequest, FirebaseLoginResponse
from app.services.user_service import sync_user_from_firebase_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/firebase-login", response_model=FirebaseLoginResponse)
def firebase_login_endpoint(
    payload: FirebaseLoginRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FirebaseLoginResponse:
    user = sync_user_from_firebase_token(db=db, id_token=payload.id_token, settings=settings)
    return FirebaseLoginResponse(
        uid=user.uid,
        email=user.email,
        nickname=user.nickname,
        provider=user.provider,
        profile_image=user.profile_image,
    )
