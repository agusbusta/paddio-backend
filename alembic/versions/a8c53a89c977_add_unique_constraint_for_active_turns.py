"""add_unique_constraint_for_active_turns

Revision ID: a8c53a89c977
Revises: cc3175b959ab
Create Date: 2025-12-19 09:37:18.450226

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8c53a89c977'
down_revision: Union[str, None] = 'cc3175b959ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # PRIMERO: Actualizar invitaciones para que apunten al turno más antiguo de cada grupo duplicado
    # Esto es necesario porque hay foreign keys que impiden eliminar turnos con invitaciones
    op.execute("""
        UPDATE invitations i
        SET turn_id = (
            SELECT MIN(p2.id)
            FROM pregame_turns p2
            WHERE p2.turn_id = (
                SELECT p1.turn_id FROM pregame_turns p1 WHERE p1.id = i.turn_id
            )
            AND p2.date = (
                SELECT p1.date FROM pregame_turns p1 WHERE p1.id = i.turn_id
            )
            AND p2.start_time = (
                SELECT p1.start_time FROM pregame_turns p1 WHERE p1.id = i.turn_id
            )
            AND p2.court_id = (
                SELECT p1.court_id FROM pregame_turns p1 WHERE p1.id = i.turn_id
            )
            AND p2.status NOT IN ('CANCELLED', 'COMPLETED')
        )
        WHERE EXISTS (
            SELECT 1
            FROM pregame_turns p1
            WHERE p1.id = i.turn_id
            AND EXISTS (
                SELECT 1
                FROM pregame_turns p2
                WHERE p2.turn_id = p1.turn_id
                AND p2.date = p1.date
                AND p2.start_time = p1.start_time
                AND p2.court_id = p1.court_id
                AND p2.status NOT IN ('CANCELLED', 'COMPLETED')
                AND p2.id < p1.id
            )
        );
    """)
    
    # SEGUNDO: Limpiar duplicados existentes (mantener solo el más antiguo de cada grupo)
    # Esto es necesario porque ya hay datos duplicados en la BD
    op.execute("""
        DELETE FROM pregame_turns p1
        USING pregame_turns p2
        WHERE p1.id > p2.id
        AND p1.turn_id = p2.turn_id
        AND p1.date = p2.date
        AND p1.start_time = p2.start_time
        AND p1.court_id = p2.court_id
        AND p1.status NOT IN ('CANCELLED', 'COMPLETED')
        AND p2.status NOT IN ('CANCELLED', 'COMPLETED');
    """)
    
    # TERCERO: Crear índice único parcial para prevenir turnos duplicados activos
    # Solo aplica a turnos que NO están cancelados o completados
    # Esto previene que dos usuarios reserven la misma cancha, fecha, hora simultáneamente
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS unique_active_turn_per_court_time 
        ON pregame_turns (turn_id, date, start_time, court_id)
        WHERE status NOT IN ('CANCELLED', 'COMPLETED');
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Eliminar el índice único
    op.execute("DROP INDEX IF EXISTS unique_active_turn_per_court_time;")
