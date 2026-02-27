"""add_organizer_category_to_pregame_turns

Revision ID: 7f09d6430329
Revises: f6005aff47e6
Create Date: 2025-09-27 22:53:44.518784

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f09d6430329"
down_revision: Union[str, None] = "f6005aff47e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add organizer_category column to pregame_turns table
    op.add_column(
        "pregame_turns",
        sa.Column("organizer_category", sa.String(10), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove organizer_category column from pregame_turns table
    op.drop_column("pregame_turns", "organizer_category")
