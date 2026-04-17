from typing import Optional

from app.schemas.base import ApiBaseModel


class UserSyncRequest(ApiBaseModel):
    uid: str
    email: str
    nickname: str
    provider: str
    profile_image: Optional[str] = None


class UserSyncBody(ApiBaseModel):
    nickname: Optional[str] = None


class UserSyncItem(ApiBaseModel):
    id: int
    firebaseUid: str
    email: str
    provider: str
    nickname: str
    isNewUser: bool


class UserSyncResponse(ApiBaseModel):
    status: str = "success"
    user: UserSyncItem


class UserMeItem(ApiBaseModel):
    id: int
    firebaseUid: str
    email: str
    provider: str
    nickname: str
    emailVerified: bool
    profileImageUrl: Optional[str] = None
    isNewUser: bool
    createdAt: str
    updatedAt: str


class UserMeResponse(ApiBaseModel):
    status: str = "success"
    user: UserMeItem


class UserMeUpdateRequest(ApiBaseModel):
    nickname: Optional[str] = None
    profileImageDataUrl: Optional[str] = None
    profileImageBase64: Optional[str] = None
    profileImageUrl: Optional[str] = None
