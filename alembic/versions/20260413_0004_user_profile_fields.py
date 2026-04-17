"""add user updated_at field for profile endpoints

Revision ID: 20260413_0004
Revises: 20260413_0003
Create Date: 2026-04-13 15:10:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260413_0004"
down_revision = "20260413_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE users SET updated_at = created_at WHERE updated_at IS NULL"))
    op.alter_column("users", "updated_at", nullable=False)


def downgrade() -> None:
    op.drop_column("users", "updated_at")
