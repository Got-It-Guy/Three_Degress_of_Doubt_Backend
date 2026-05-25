from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, SmallInteger, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time_utils import utc_now
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    uid: Mapped[str] = mapped_column(String(128), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), default="email", nullable=False)
    profile_image: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    age_group: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    job: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    main_bank: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    residence: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    progresses: Mapped[list["UserStageProgress"]] = relationship(back_populates="user")
    rounds: Mapped[list["Round"]] = relationship(back_populates="user")


class Stage(Base):
    __tablename__ = "stages"

    stage_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    genre: Mapped[str] = mapped_column(String(50), nullable=False)
    is_random: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    required_score: Mapped[int] = mapped_column(SmallInteger, default=3, nullable=False)
    order_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    progresses: Mapped[list["UserStageProgress"]] = relationship(back_populates="stage")
    scenarios: Mapped[list["Scenario"]] = relationship(back_populates="stage")
    rounds: Mapped[list["Round"]] = relationship(back_populates="stage")


class UserStageProgress(Base):
    __tablename__ = "user_stage_progress"
    __table_args__ = (
        UniqueConstraint("uid", "stage_id", name="uq_user_stage_progress_uid_stage_id"),
    )

    progress_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uid: Mapped[str] = mapped_column(ForeignKey("users.uid", ondelete="CASCADE"), nullable=False)
    stage_id: Mapped[int] = mapped_column(ForeignKey("stages.stage_id", ondelete="CASCADE"), nullable=False)
    stage_score: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    warning_count: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    is_cleared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    best_round_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_round_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cleared_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="progresses")
    stage: Mapped[Stage] = relationship(back_populates="progresses")


class Scenario(Base):
    __tablename__ = "scenarios"

    scenario_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_source_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    source_scenario_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("scenarios.scenario_id"), nullable=True
    )
    stage_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("stages.stage_id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    genre: Mapped[str] = mapped_column(String(50), nullable=False)
    is_fraud: Mapped[bool] = mapped_column(Boolean, nullable=False)
    situation_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    ai_name: Mapped[str] = mapped_column(String(50), nullable=False)
    ai_image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fraud_evidence_keys: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    min_evidence_count: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    difficulty: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    stage: Mapped[Optional[Stage]] = relationship(back_populates="scenarios")
    rounds: Mapped[list["Round"]] = relationship(back_populates="scenario")


class Round(Base):
    __tablename__ = "rounds"

    round_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uid: Mapped[str] = mapped_column(ForeignKey("users.uid", ondelete="CASCADE"), nullable=False)
    stage_id: Mapped[int] = mapped_column(ForeignKey("stages.stage_id", ondelete="CASCADE"), nullable=False)
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("scenarios.scenario_id", ondelete="CASCADE"), nullable=False
    )
    scenario_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    scenario_variant: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    scenario_context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    situation_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_turn_count: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    max_user_turns: Mapped[int] = mapped_column(SmallInteger, default=20, nullable=False)
    ended_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    is_fraud_judged: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    judged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_count: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    result: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    score_delta: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    conversation_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_summarized_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    summary_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="rounds")
    stage: Mapped[Stage] = relationship(back_populates="rounds")
    scenario: Mapped[Scenario] = relationship(back_populates="rounds")
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="round", cascade="all, delete-orphan")
    report: Mapped[Optional["RoundReport"]] = relationship(
        back_populates="round", uselist=False, cascade="all, delete-orphan"
    )
    ai_logs: Mapped[list["AICallLog"]] = relationship(back_populates="round", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    message_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    round_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rounds.round_id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_evidence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    evidence_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    worker_is_conversation_over: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    backend_end_rule: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    round: Mapped[Round] = relationship(back_populates="messages")


class RoundReport(Base):
    __tablename__ = "round_reports"

    report_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    round_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rounds.round_id", ondelete="CASCADE"), unique=True, nullable=False
    )
    report_type: Mapped[str] = mapped_column(String(20), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_messages: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    fraud_points: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    round: Mapped[Round] = relationship(back_populates="report")


class AICallLog(Base):
    __tablename__ = "ai_call_logs"

    log_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    round_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rounds.round_id", ondelete="CASCADE"), nullable=False
    )
    call_type: Mapped[str] = mapped_column(String(30), nullable=False)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_evidence_detected: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    round: Mapped[Round] = relationship(back_populates="ai_logs")
