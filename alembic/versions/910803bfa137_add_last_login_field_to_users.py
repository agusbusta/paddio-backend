"""Add last_login field to users

Revision ID: 910803bfa137
Revises: d55460d49aa4
Create Date: 2025-09-22 15:41:19.576351

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "910803bfa137"
down_revision: Union[str, None] = "d55460d49aa4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Agregar campo last_login a la tabla users
    op.add_column("users", sa.Column("last_login", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remover campo last_login de la tabla users
    op.drop_column("users", "last_login")
