"""add_incomplete_reminder_sent_at_to_pregame_turns

Revision ID: b8e9f0a1c2d3
Revises: f3a7e2974f65
Create Date: 2026-02-09

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8e9f0a1c2d3"
down_revision: Union[str, None] = "f3a7e2974f65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pregame_turns",
        sa.Column("incomplete_reminder_sent_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pregame_turns", "incomplete_reminder_sent_at")
