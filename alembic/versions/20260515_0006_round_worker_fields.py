"""add round worker fields and end metadata

Revision ID: 20260515_0006
Revises: 20260511_0005
Create Date: 2026-05-15 22:10:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260515_0006"
down_revision = "20260511_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rounds", sa.Column("scenario_type", sa.String(length=50), nullable=True))
    op.add_column("rounds", sa.Column("scenario_variant", sa.String(length=100), nullable=True))
    op.add_column("rounds", sa.Column("scenario_context", sa.JSON(), nullable=True))
    op.add_column("rounds", sa.Column("situation_prompt", sa.Text(), nullable=True))
    op.add_column("rounds", sa.Column("user_turn_count", sa.SmallInteger(), nullable=False, server_default="0"))
    op.add_column("rounds", sa.Column("max_user_turns", sa.SmallInteger(), nullable=False, server_default="20"))
    op.add_column("rounds", sa.Column("ended_reason", sa.String(length=64), nullable=True))
    op.add_column("chat_messages", sa.Column("worker_is_conversation_over", sa.Boolean(), nullable=True))
    op.add_column("chat_messages", sa.Column("backend_end_rule", sa.String(length=64), nullable=True))
    op.alter_column("rounds", "user_turn_count", server_default=None)
    op.alter_column("rounds", "max_user_turns", server_default=None)


def downgrade() -> None:
    op.drop_column("chat_messages", "backend_end_rule")
    op.drop_column("chat_messages", "worker_is_conversation_over")
    op.drop_column("rounds", "ended_reason")
    op.drop_column("rounds", "max_user_turns")
    op.drop_column("rounds", "user_turn_count")
    op.drop_column("rounds", "situation_prompt")
    op.drop_column("rounds", "scenario_context")
    op.drop_column("rounds", "scenario_variant")
    op.drop_column("rounds", "scenario_type")

