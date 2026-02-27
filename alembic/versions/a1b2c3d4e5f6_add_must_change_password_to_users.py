"""add_must_change_password_to_users

Revision ID: a1b2c3d4e5f6
Revises: 437ae1d3d083
Create Date: 2025-01-01 17:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "437ae1d3d083"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Agregar columna must_change_password a la tabla users
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Eliminar columna must_change_password de la tabla users
    op.drop_column("users", "must_change_password")
