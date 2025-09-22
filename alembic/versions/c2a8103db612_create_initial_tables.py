"""Create initial tables

Revision ID: c2a8103db612
Revises:
Create Date: 2025-09-22 16:06:32.531797

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c2a8103db612"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Crear tabla clubs PRIMERO
    op.create_table(
        "clubs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("address", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clubs_id"), "clubs", ["id"], unique=False)

    # Crear tabla users DESPUÉS
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("hashed_password", sa.String(), nullable=True),
        sa.Column("overall_rating", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=True),
        sa.Column("is_super_admin", sa.Boolean(), nullable=True),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("club_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_name"), "users", ["name"], unique=False)
    op.create_foreign_key("users_club_id_fkey", "users", "clubs", ["club_id"], ["id"])

    # Crear tabla courts
    op.create_table(
        "courts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("club_id", sa.Integer(), nullable=False),
        sa.Column("surface_type", sa.String(), nullable=True),
        sa.Column("is_indoor", sa.Boolean(), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key("courts_club_id_fkey", "courts", "clubs", ["club_id"], ["id"])

    # Crear tabla matches
    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("court_id", sa.Integer(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key(
        "matches_court_id_fkey", "matches", "courts", ["court_id"], ["id"]
    )
    op.create_foreign_key(
        "matches_creator_id_fkey", "matches", "users", ["creator_id"], ["id"]
    )

    # Crear tabla turns
    op.create_table(
        "turns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("court_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key(
        "turns_court_id_fkey", "turns", "courts", ["court_id"], ["id"]
    )
    op.create_foreign_key("turns_user_id_fkey", "turns", "users", ["user_id"], ["id"])

    # Crear tabla bookings
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("court_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key(
        "bookings_user_id_fkey", "bookings", "users", ["user_id"], ["id"]
    )
    op.create_foreign_key(
        "bookings_court_id_fkey", "bookings", "courts", ["court_id"], ["id"]
    )

    # Crear tabla match_players
    op.create_table(
        "match_players",
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("match_id", "user_id"),
    )
    op.create_foreign_key(
        "match_players_match_id_fkey", "match_players", "matches", ["match_id"], ["id"]
    )
    op.create_foreign_key(
        "match_players_user_id_fkey", "match_players", "users", ["user_id"], ["id"]
    )

    # Crear tabla user_ratings
    op.create_table(
        "user_ratings",
        sa.Column("rater_id", sa.Integer(), nullable=False),
        sa.Column("rated_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("comment", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("rater_id", "rated_id"),
    )
    op.create_foreign_key(
        "user_ratings_rater_id_fkey", "user_ratings", "users", ["rater_id"], ["id"]
    )
    op.create_foreign_key(
        "user_ratings_rated_id_fkey", "user_ratings", "users", ["rated_id"], ["id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("user_ratings")
    op.drop_table("match_players")
    op.drop_table("bookings")
    op.drop_table("turns")
    op.drop_table("matches")
    op.drop_table("courts")
    op.drop_table("clubs")
    op.drop_table("users")
