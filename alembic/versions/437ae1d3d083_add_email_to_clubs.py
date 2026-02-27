"""add_email_to_clubs

Revision ID: 437ae1d3d083
Revises: c617c0ccf152
Create Date: 2026-01-01 16:44:52.078327

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '437ae1d3d083'
down_revision: Union[str, None] = 'c617c0ccf152'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Agregar columna email a la tabla clubs
    op.add_column(
        "clubs",
        sa.Column("email", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Eliminar columna email de la tabla clubs
    op.drop_column("clubs", "email")
