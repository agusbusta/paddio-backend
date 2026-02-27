"""add_cancellation_message_to_pregame_turns

Revision ID: c617c0ccf152
Revises: a8c53a89c977
Create Date: 2025-12-30 11:40:23.492194

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c617c0ccf152"
down_revision: Union[str, None] = "a8c53a89c977"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Agregar columna cancellation_message a la tabla pregame_turns
    op.add_column(
        "pregame_turns",
        sa.Column("cancellation_message", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Eliminar columna cancellation_message de la tabla pregame_turns
    op.drop_column("pregame_turns", "cancellation_message")
