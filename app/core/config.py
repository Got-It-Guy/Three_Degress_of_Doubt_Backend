from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fraud Simulator API"
    app_version: str = "1.2.0"
    debug: bool = True

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/fraud_sim"

    auth_mode: str = "firebase"  # firebase | dev
    dev_bearer_uid: str = "dev-user-001"

    firebase_project_id: Optional[str] = None
    google_application_credentials: Optional[str] = None

    gemini_enabled: bool = False
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.0-flash"

    llm_studio_base_url: str = "http://llm.hiclouddev.com/v1"
    llm_studio_api_key: str = "lm-studio"
    llm_studio_model: str = "local-model"

    conversation_recent_message_limit: int = 8

    default_required_score: int = 3
    default_max_scriptless_turns: int = 3
    auto_seed_on_startup: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()