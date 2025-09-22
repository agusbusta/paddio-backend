"""Create initial tables

Revision ID: d55460d49aa4
Revises:
Create Date: 2025-09-22 15:37:38.212390

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d55460d49aa4"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=True),
        sa.Column("is_super_admin", sa.Boolean(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_name"), "users", ["name"], unique=False)

    # Create clubs table
    op.create_table(
        "clubs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=False),
        sa.Column("contact", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clubs_id"), "clubs", ["id"], unique=False)

    # Create courts table
    op.create_table(
        "courts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("club_id", sa.Integer(), nullable=False),
        sa.Column("surface_type", sa.String(), nullable=True),
        sa.Column("is_covered", sa.Boolean(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create matches table
    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("court_id", sa.Integer(), nullable=True),
        sa.Column("player1_name", sa.String(), nullable=True),
        sa.Column("player2_name", sa.String(), nullable=True),
        sa.Column("player3_name", sa.String(), nullable=True),
        sa.Column("player4_name", sa.String(), nullable=True),
        sa.Column("match_date", sa.DateTime(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("score", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["court_id"],
            ["courts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create turns table
    op.create_table(
        "turns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("court_id", sa.Integer(), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "AVAILABLE", "RESERVED", "IN_PROGRESS", "COMPLETED", name="turnstatus"
            ),
            nullable=True,
        ),
        sa.Column("price", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["court_id"],
            ["courts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_turns_id"), "turns", ["id"], unique=False)

    # Create bookings table
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("turn_id", sa.Integer(), nullable=True),
        sa.Column("court_id", sa.Integer(), nullable=True),
        sa.Column("booking_date", sa.DateTime(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "CONFIRMED", "CANCELLED", "COMPLETED", name="bookingstatus"
            ),
            nullable=True,
        ),
        sa.Column("notes", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["court_id"],
            ["courts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["turn_id"],
            ["turns.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bookings_id"), "bookings", ["id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_bookings_id"), table_name="bookings")
    op.drop_table("bookings")
    op.drop_index(op.f("ix_turns_id"), table_name="turns")
    op.drop_table("turns")
    op.drop_table("matches")
    op.drop_table("courts")
    op.drop_index(op.f("ix_clubs_id"), table_name="clubs")
    op.drop_table("clubs")
    op.drop_index(op.f("ix_users_name"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
