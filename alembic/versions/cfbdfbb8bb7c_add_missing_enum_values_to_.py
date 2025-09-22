"""Add missing enum values to pregameturnstatus

Revision ID: cfbdfbb8bb7c
Revises: 732fe9639c43
Create Date: 2025-09-22 17:56:39.176127

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cfbdfbb8bb7c"
down_revision: Union[str, None] = "732fe9639c43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add missing enum values to pregameturnstatus
    op.execute("ALTER TYPE pregameturnstatus ADD VALUE 'AVAILABLE'")
    op.execute("ALTER TYPE pregameturnstatus ADD VALUE 'PENDING'")
    op.execute("ALTER TYPE pregameturnstatus ADD VALUE 'COMPLETED'")


def downgrade() -> None:
    """Downgrade schema."""
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum type and updating all references
    # For now, we'll leave the enum values as they are
    pass
