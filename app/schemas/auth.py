from app.schemas.base import ApiBaseModel


class FirebaseLoginRequest(ApiBaseModel):
    id_token: str


class FirebaseLoginResponse(ApiBaseModel):
    status: str = "success"
    uid: str
    email: str
    nickname: str
    provider: str
    profile_image: str | None = None
    token_type: str = "Bearer"
