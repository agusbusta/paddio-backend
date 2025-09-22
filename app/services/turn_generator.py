from sqlalchemy.orm import Session
from datetime import datetime, time, timedelta
from typing import List
import logging

from app.models.turn import Turn, TurnStatus
from app.models.court import Court

logger = logging.getLogger(__name__)


def generate_turns_for_club(
    db: Session, club_id: int, days_ahead: int = 30
) -> List[Turn]:
    """
    Genera turnos automáticamente para todas las canchas de un club.

    Args:
        db: Sesión de base de datos
        club_id: ID del club
        days_ahead: Días hacia adelante para generar turnos (default: 30)

    Returns:
        Lista de turnos creados
    """
    # Obtener el club
    from app.crud import club as club_crud

    club = club_crud.get_club(db, club_id)
    if not club:
        logger.error(f"Club {club_id} not found")
        return []

    # Obtener todas las canchas del club
    courts = db.query(Court).filter(Court.club_id == club_id).all()
    if not courts:
        logger.warning(f"No courts found for club {club_id}")
        return []

    created_turns = []
    start_date = datetime.now().date()

    # Generar turnos para cada día
    for day_offset in range(days_ahead):
        current_date = start_date + timedelta(days=day_offset)
        day_of_week = current_date.weekday()  # 0 = lunes, 6 = domingo

        # Verificar si el club está abierto ese día
        if not is_club_open_on_day(club, day_of_week):
            continue

        # Generar turnos para cada cancha
        for court in courts:
            turns = generate_turns_for_court_and_date(db, court, club, current_date)
            created_turns.extend(turns)

    logger.info(f"Generated {len(created_turns)} turns for club {club_id}")
    return created_turns


def is_club_open_on_day(club, day_of_week: int) -> bool:
    """
    Verifica si el club está abierto en un día específico de la semana.

    Args:
        club: Objeto Club
        day_of_week: Día de la semana (0 = lunes, 6 = domingo)

    Returns:
        True si el club está abierto, False en caso contrario
    """
    day_fields = [
        club.monday_open,
        club.tuesday_open,
        club.wednesday_open,
        club.thursday_open,
        club.friday_open,
        club.saturday_open,
        club.sunday_open,
    ]

    return day_fields[day_of_week]


def generate_turns_for_court_and_date(
    db: Session, court: Court, club, date
) -> List[Turn]:
    """
    Genera turnos para una cancha específica en una fecha específica.

    Args:
        db: Sesión de base de datos
        court: Cancha
        club: Club
        date: Fecha

    Returns:
        Lista de turnos creados
    """
    turns = []

    # Convertir horarios a datetime
    opening_datetime = datetime.combine(date, club.opening_time)
    closing_datetime = datetime.combine(date, club.closing_time)

    # Calcular duración del turno en minutos
    turn_duration = timedelta(minutes=club.turn_duration_minutes)

    # Generar turnos desde la hora de apertura hasta la de cierre
    current_time = opening_datetime

    while current_time + turn_duration <= closing_datetime:
        end_time = current_time + turn_duration

        # Verificar si ya existe un turno en ese horario
        existing_turn = (
            db.query(Turn)
            .filter(
                Turn.court_id == court.id,
                Turn.start_time == current_time,
                Turn.end_time == end_time,
            )
            .first()
        )

        if not existing_turn:
            # Crear nuevo turno
            turn = Turn(
                court_id=court.id,
                user_id=None,  # Sin usuario asignado inicialmente
                start_time=current_time,
                end_time=end_time,
                status=TurnStatus.AVAILABLE,
            )

            db.add(turn)
            turns.append(turn)
            logger.debug(
                f"Created turn for court {court.id} from {current_time} to {end_time}"
            )

        # Avanzar al siguiente turno
        current_time += turn_duration

    return turns


def generate_turns_for_new_court(
    db: Session, court_id: int, days_ahead: int = 30
) -> List[Turn]:
    """
    Genera turnos para una cancha recién creada.

    Args:
        db: Sesión de base de datos
        court_id: ID de la cancha
        days_ahead: Días hacia adelante para generar turnos

    Returns:
        Lista de turnos creados
    """
    court = db.query(Court).filter(Court.id == court_id).first()
    if not court:
        logger.error(f"Court {court_id} not found")
        return []

    return generate_turns_for_club(db, court.club_id, days_ahead)
