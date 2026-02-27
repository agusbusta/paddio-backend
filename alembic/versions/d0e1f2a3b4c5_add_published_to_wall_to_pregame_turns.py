"""add published_to_wall to pregame_turns

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-02-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pregame_turns",
        sa.Column("published_to_wall", sa.String(5), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("pregame_turns", "published_to_wall")
