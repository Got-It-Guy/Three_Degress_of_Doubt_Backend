"""add round context memory fields

Revision ID: 20260322_0002
Revises: 20260319_0001
Create Date: 2026-03-22 17:15:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260322_0002"
down_revision = "20260319_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rounds", sa.Column("conversation_summary", sa.Text(), nullable=True))
    op.add_column("rounds", sa.Column("last_summarized_message_id", sa.Uuid(), nullable=True))
    op.add_column("rounds", sa.Column("summary_updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("rounds", "summary_updated_at")
    op.drop_column("rounds", "last_summarized_message_id")
    op.drop_column("rounds", "conversation_summary")
