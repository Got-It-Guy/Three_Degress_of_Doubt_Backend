"""add numeric id column to users

Revision ID: 20260413_0003
Revises: 20260322_0002
Create Date: 2026-04-13 12:10:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260413_0003"
down_revision = "20260322_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("id", sa.Integer(), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT uid FROM users ORDER BY created_at, uid")).fetchall()
    for index, row in enumerate(rows, start=1):
        conn.execute(
            sa.text("UPDATE users SET id = :id WHERE uid = :uid"),
            {"id": index, "uid": row.uid},
        )

    op.alter_column("users", "id", nullable=False)
    op.create_unique_constraint("uq_users_id", "users", ["id"])
    op.create_index("ix_users_id", "users", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_id", table_name="users")
    op.drop_constraint("uq_users_id", "users", type_="unique")
    op.drop_column("users", "id")
