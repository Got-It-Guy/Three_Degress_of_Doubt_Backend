from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import AuthenticatedUser, get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.seed_data import seed_initial_data


@pytest.fixture()
def db_session(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )

    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        seed_initial_data(session)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user() -> AuthenticatedUser:
        return AuthenticatedUser(uid="dev-user-001", email="user@example.com")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token-not-used"}

@pytest.fixture(autouse=True)
def fake_attacker_engine(monkeypatch):
    class FakeAttackerEngine:
        def __init__(self, settings):
            self.settings = settings

        def generate_scenario(self, category, user_meta):
            return {
                "official_name": "테스트 공격자",
                "scammer_role": category,
                "main_goal": "테스트 목적",
                "attack_method": "테스트 공격 수단",
                "pretext": "테스트 동적 사기 명분",
                "logic": "테스트 압박 논리",
                "target_amount": 10000,
                "account_no": "테스트은행 123-456",
                "fake_link": "",
            }

        def generate_reply(self, category, history, user_meta, scenario_data):
            has_user_message = bool(history and history[-1].get("role") == "user" and history[-1].get("content"))
            if not has_user_message:
                return {
                    "content": "테스트 공격자입니다. 확인이 필요합니다.",
                    "stage": "접근",
                    "is_evidence": False,
                }
            return {
                "content": "테스트 사기 응답입니다.",
                "stage": "행동유도",
                "is_evidence": True,
            }

    monkeypatch.setattr("app.services.scenario_selector.AttackerEngine", FakeAttackerEngine)
    monkeypatch.setattr("app.services.ai.AttackerEngine", FakeAttackerEngine)
