"""
Utilidades para detectar solapamientos de turnos.
Un partido dura 1.5 horas, por lo que un turno que comienza a las 9 PM
ocupa el rango de 9:00 PM a 10:30 PM.
"""

from datetime import datetime, date, timedelta
from typing import List, Tuple
from sqlalchemy.orm import Session

from app.models.pregame_turn import PregameTurn, PregameTurnStatus


def parse_time_to_minutes(time_str: str) -> int:
    """
    Convierte un string de tiempo (HH:MM) a minutos desde medianoche.

    Args:
        time_str: String en formato "HH:MM"

    Returns:
        int: Minutos desde medianoche (0-1439)
    """
    try:
        parts = time_str.split(":")
        if len(parts) != 2:
            return -1
        hours = int(parts[0])
        minutes = int(parts[1])
        return hours * 60 + minutes
    except (ValueError, AttributeError):
        return -1


def minutes_to_time_string(minutes: int) -> str:
    """
    Convierte minutos desde medianoche a string de tiempo (HH:MM).

    Args:
        minutes: Minutos desde medianoche

    Returns:
        str: String en formato "HH:MM"
    """
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def get_user_active_reservations_time_ranges(
    db: Session, user_id: int, target_date: date
) -> List[Tuple[int, int]]:
    """
    Obtiene los rangos de tiempo (en minutos) ocupados por las reservas activas del usuario
    para una fecha específica.

    Un partido dura 1.5 horas (90 minutos), por lo que cada reserva ocupa desde
    start_time hasta start_time + 90 minutos.

    Args:
        db: Sesión de base de datos
        user_id: ID del usuario
        target_date: Fecha objetivo

    Returns:
        List[Tuple[int, int]]: Lista de tuplas (start_minutes, end_minutes) para cada reserva
    """
    # Obtener todas las reservas activas del usuario para la fecha objetivo
    # CRÍTICO: Solo considerar turnos activos (PENDING o READY_TO_PLAY), excluir cancelados
    # El filtro .status.in_([PENDING, READY_TO_PLAY]) ya excluye CANCELLED y COMPLETED
    active_reservations = (
        db.query(PregameTurn)
        .filter(
            (
                (PregameTurn.player1_id == user_id)
                | (PregameTurn.player2_id == user_id)
                | (PregameTurn.player3_id == user_id)
                | (PregameTurn.player4_id == user_id)
            )
        )
        .filter(PregameTurn.date == target_date)
        .filter(
            PregameTurn.status.in_(
                [PregameTurnStatus.PENDING, PregameTurnStatus.READY_TO_PLAY]
            )
        )
        .all()
    )

    time_ranges = []
    MATCH_DURATION_MINUTES = 90  # 1.5 horas

    for reservation in active_reservations:
        start_minutes = parse_time_to_minutes(reservation.start_time)
        if start_minutes == -1:
            continue  # Skip invalid times

        end_minutes = start_minutes + MATCH_DURATION_MINUTES

        # Manejar el caso donde el partido termina después de medianoche
        if end_minutes >= 1440:  # 24 horas = 1440 minutos
            end_minutes = 1439  # 23:59

        time_ranges.append((start_minutes, end_minutes))

    return time_ranges


def does_turn_overlap_with_reservations(
    turn_start_time: str,
    turn_end_time: str,
    user_reservations_ranges: List[Tuple[int, int]],
) -> bool:
    """
    Verifica si un turno se solapa con alguna de las reservas activas del usuario.

    Un turno se solapa si:
    - Comienza durante el rango de una reserva existente
    - Termina durante el rango de una reserva existente
    - Contiene completamente una reserva existente
    - Es contenido completamente por una reserva existente

    Args:
        turn_start_time: Hora de inicio del turno (HH:MM)
        turn_end_time: Hora de fin del turno (HH:MM)
        user_reservations_ranges: Lista de rangos de tiempo ocupados por reservas del usuario

    Returns:
        bool: True si hay solapamiento, False en caso contrario
    """
    turn_start_minutes = parse_time_to_minutes(turn_start_time)
    turn_end_minutes = parse_time_to_minutes(turn_end_time)

    if turn_start_minutes == -1 or turn_end_minutes == -1:
        return False  # Invalid time format, don't filter

    # Si el turno termina antes de comenzar (cruza medianoche), no lo manejamos por ahora
    if turn_end_minutes < turn_start_minutes:
        return False

    # Verificar solapamiento con cada reserva
    for reservation_start, reservation_end in user_reservations_ranges:
        # El turno se solapa si:
        # 1. Comienza durante la reserva: turn_start >= reservation_start AND turn_start < reservation_end
        # 2. Termina durante la reserva: turn_end > reservation_start AND turn_end <= reservation_end
        # 3. Contiene la reserva: turn_start <= reservation_start AND turn_end >= reservation_end
        # 4. Es contenido por la reserva: turn_start >= reservation_start AND turn_end <= reservation_end

        if (
            (
                turn_start_minutes >= reservation_start
                and turn_start_minutes < reservation_end
            )
            or (
                turn_end_minutes > reservation_start
                and turn_end_minutes <= reservation_end
            )
            or (
                turn_start_minutes <= reservation_start
                and turn_end_minutes >= reservation_end
            )
            or (
                turn_start_minutes >= reservation_start
                and turn_end_minutes <= reservation_end
            )
        ):
            return True

    return False
