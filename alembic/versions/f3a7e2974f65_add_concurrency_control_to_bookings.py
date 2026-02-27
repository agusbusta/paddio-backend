"""add_concurrency_control_to_bookings

Revision ID: f3a7e2974f65
Revises: a1b2c3d4e5f6
Create Date: 2026-01-12 19:09:46.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a7e2974f65'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema.
    
    NOTA: Esta migración documenta cambios críticos en la lógica de aplicación
    para prevenir condiciones de carrera en la creación de reservas.
    
    Cambios implementados en app/crud/booking.py:
    - Implementación de SELECT FOR UPDATE para bloqueo de filas
    - Validación de disponibilidad del turno antes de crear reserva
    - Validación de duplicados (usuario ya tiene reserva activa)
    - Validación de capacidad (máximo 4 participantes)
    - Validación de estado del turno (no cancelado/completado)
    
    Estos cambios previenen:
    - Reservas duplicadas para el mismo turno
    - Acceso no autorizado a turnos ajenos
    - Reservas en turnos completos
    - Condiciones de carrera en reservas simultáneas
    """
    # No se requieren cambios en el esquema de base de datos
    # Los cambios son a nivel de lógica de aplicación
    pass


def downgrade() -> None:
    """
    Downgrade schema.
    
    NOTA: Esta migración no modifica el esquema de base de datos,
    por lo que no hay cambios que revertir.
    """
    # No se requieren cambios en el esquema de base de datos
    pass
