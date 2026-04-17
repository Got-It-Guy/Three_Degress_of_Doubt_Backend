from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.services.firebase_auth import verify_firebase_id_token

bearer_scheme = HTTPBearer(auto_error=True)


from typing import Optional

class AuthenticatedUser:
    def __init__(self, uid: str, email: Optional[str] = None) -> None:
        self.uid = uid
        self.email = email


def _verify_dev_token(token: str, settings: Settings) -> AuthenticatedUser:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효한 Bearer 토큰이 필요합니다.")
    if token == settings.dev_bearer_uid:
        return AuthenticatedUser(uid=settings.dev_bearer_uid)
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        uid = payload.get("uid") or payload.get("sub") or token
        return AuthenticatedUser(uid=str(uid), email=payload.get("email"))
    except Exception:
        return AuthenticatedUser(uid=token)


def _verify_firebase_token(token: str, settings: Settings) -> AuthenticatedUser:
    decoded = verify_firebase_id_token(id_token=token, settings=settings)
    return AuthenticatedUser(uid=str(decoded["uid"]), email=decoded.get("email"))


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedUser:
    token = credentials.credentials
    if settings.auth_mode.lower() == "firebase":
        return _verify_firebase_token(token, settings)
    return _verify_dev_token(token, settings)
