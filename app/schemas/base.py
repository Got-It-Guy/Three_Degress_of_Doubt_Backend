from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.time_utils import to_iso_z


class ApiBaseModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        json_encoders={
            datetime: to_iso_z,
            UUID: str,
        },
    )
