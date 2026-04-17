"""initial schema

Revision ID: 20260319_0001
Revises: 
Create Date: 2026-03-19 17:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260319_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("uid", sa.String(length=128), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("nickname", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False, server_default="email"),
        sa.Column("profile_image", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "stages",
        sa.Column("stage_id", sa.SmallInteger(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("genre", sa.String(length=50), nullable=False),
        sa.Column("is_random", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("required_score", sa.SmallInteger(), nullable=False, server_default="3"),
        sa.Column("order_index", sa.SmallInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
    )

    op.create_table(
        "user_stage_progress",
        sa.Column("progress_id", sa.Uuid(), primary_key=True),
        sa.Column("uid", sa.String(length=128), sa.ForeignKey("users.uid", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_id", sa.SmallInteger(), sa.ForeignKey("stages.stage_id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_score", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("warning_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("is_cleared", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("best_round_count", sa.Integer(), nullable=True),
        sa.Column("total_round_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("uid", "stage_id", name="uq_user_stage_progress_uid_stage_id"),
    )

    op.create_table(
        "scenarios",
        sa.Column("scenario_id", sa.Uuid(), primary_key=True),
        sa.Column("case_source_id", sa.Uuid(), nullable=True),
        sa.Column("source_scenario_id", sa.Uuid(), sa.ForeignKey("scenarios.scenario_id"), nullable=True),
        sa.Column("stage_id", sa.SmallInteger(), sa.ForeignKey("stages.stage_id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("genre", sa.String(length=50), nullable=False),
        sa.Column("is_fraud", sa.Boolean(), nullable=False),
        sa.Column("situation_prompt", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("ai_name", sa.String(length=50), nullable=False),
        sa.Column("ai_image_url", sa.Text(), nullable=True),
        sa.Column("fraud_evidence_keys", sa.JSON(), nullable=False),
        sa.Column("min_evidence_count", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("difficulty", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "rounds",
        sa.Column("round_id", sa.Uuid(), primary_key=True),
        sa.Column("uid", sa.String(length=128), sa.ForeignKey("users.uid", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_id", sa.SmallInteger(), sa.ForeignKey("stages.stage_id", ondelete="CASCADE"), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), sa.ForeignKey("scenarios.scenario_id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="in_progress"),
        sa.Column("is_fraud_judged", sa.Boolean(), nullable=True),
        sa.Column("judged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("result", sa.String(length=20), nullable=True),
        sa.Column("score_delta", sa.SmallInteger(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "chat_messages",
        sa.Column("message_id", sa.Uuid(), primary_key=True),
        sa.Column("round_id", sa.Uuid(), sa.ForeignKey("rounds.round_id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_evidence", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("evidence_reason", sa.Text(), nullable=True),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "round_reports",
        sa.Column("report_id", sa.Uuid(), primary_key=True),
        sa.Column("round_id", sa.Uuid(), sa.ForeignKey("rounds.round_id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("report_type", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("evidence_messages", sa.JSON(), nullable=False),
        sa.Column("fraud_points", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "ai_call_logs",
        sa.Column("log_id", sa.Uuid(), primary_key=True),
        sa.Column("round_id", sa.Uuid(), sa.ForeignKey("rounds.round_id", ondelete="CASCADE"), nullable=False),
        sa.Column("call_type", sa.String(length=30), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("is_evidence_detected", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ai_call_logs")
    op.drop_table("round_reports")
    op.drop_table("chat_messages")
    op.drop_table("rounds")
    op.drop_table("scenarios")
    op.drop_table("user_stage_progress")
    op.drop_table("stages")
    op.drop_table("users")
