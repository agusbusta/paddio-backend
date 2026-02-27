"""add_category_restrictions_to_pregame_turns

Revision ID: f6005aff47e6
Revises: a004c1a3a508
Create Date: 2025-09-27 22:45:08.892725

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6005aff47e6"
down_revision: Union[str, None] = "a004c1a3a508"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add category restriction columns to pregame_turns table
    op.add_column(
        "pregame_turns",
        sa.Column(
            "category_restricted", sa.String(5), nullable=False, server_default="false"
        ),
    )
    op.add_column(
        "pregame_turns",
        sa.Column(
            "category_restriction_type",
            sa.String(20),
            nullable=False,
            server_default="NONE",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove category restriction columns from pregame_turns table
    op.drop_column("pregame_turns", "category_restriction_type")
    op.drop_column("pregame_turns", "category_restricted")
