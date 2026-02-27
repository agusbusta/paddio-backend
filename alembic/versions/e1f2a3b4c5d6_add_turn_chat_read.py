"""add turn_chat_read table

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-02-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "turn_chat_read",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("pregame_turn_id", sa.Integer(), nullable=False),
        sa.Column("last_read_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["pregame_turn_id"], ["pregame_turns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "pregame_turn_id", name="uq_turn_chat_read_user_turn"),
    )
    op.create_index("ix_turn_chat_read_id", "turn_chat_read", ["id"], unique=False)
    op.create_index("ix_turn_chat_read_user_id", "turn_chat_read", ["user_id"], unique=False)
    op.create_index("ix_turn_chat_read_pregame_turn_id", "turn_chat_read", ["pregame_turn_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_turn_chat_read_pregame_turn_id", table_name="turn_chat_read")
    op.drop_index("ix_turn_chat_read_user_id", table_name="turn_chat_read")
    op.drop_index("ix_turn_chat_read_id", table_name="turn_chat_read")
    op.drop_table("turn_chat_read")
