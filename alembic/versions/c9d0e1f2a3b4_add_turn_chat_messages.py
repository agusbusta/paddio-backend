"""add turn_chat_messages table

Revision ID: c9d0e1f2a3b4
Revises: b8e9f0a1c2d3
Create Date: 2026-02-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8e9f0a1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "turn_chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pregame_turn_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["pregame_turn_id"], ["pregame_turns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_turn_chat_messages_id", "turn_chat_messages", ["id"], unique=False)
    op.create_index("ix_turn_chat_messages_pregame_turn_id", "turn_chat_messages", ["pregame_turn_id"], unique=False)
    op.create_index("ix_turn_chat_messages_user_id", "turn_chat_messages", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_turn_chat_messages_user_id", table_name="turn_chat_messages")
    op.drop_index("ix_turn_chat_messages_pregame_turn_id", table_name="turn_chat_messages")
    op.drop_index("ix_turn_chat_messages_id", table_name="turn_chat_messages")
    op.drop_table("turn_chat_messages")
