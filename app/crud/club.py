from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.models.club import Club
from app.schemas.club import ClubCreate, ClubUpdate

logger = logging.getLogger(__name__)


def get_club(db: Session, club_id: int) -> Optional[Club]:
    return db.query(Club).filter(Club.id == club_id).first()


def get_clubs(db: Session, skip: int = 0, limit: int = 100) -> List[Club]:
    return db.query(Club).offset(skip).limit(limit).all()


def create_club(db: Session, club: ClubCreate, admin_user_id: int) -> Club:
    db_club = Club(**club.model_dump())
    db.add(db_club)
    db.commit()
    db.refresh(db_club)

    # Asignar el club al admin
    from app.models.user import User

    admin_user = db.query(User).filter(User.id == admin_user_id).first()
    if admin_user:
        admin_user.club_id = db_club.id
        db.commit()

    return db_club


def generate_turns_data_for_club(db: Session, club_id: int) -> dict:
    """
    Genera la estructura de datos de turnos para un club.
    Crea un objeto JSON con todos los turnos posibles del club, sin importar las canchas.

    Args:
        db: Sesión de base de datos
        club_id: ID del club

    Returns:
        Diccionario con la estructura de turnos del club
    """
    from datetime import datetime, timedelta

    # Obtener el club
    club = get_club(db, club_id)
    if not club:
        logger.error(f"Club {club_id} not found")
        return {}

    # Generar turnos basándose solo en los horarios del club
    turns_data = []

    # Convertir horarios a datetime
    opening_datetime = datetime.combine(datetime.now().date(), club.opening_time)
    closing_datetime = datetime.combine(datetime.now().date(), club.closing_time)

    # Calcular duración del turno en minutos
    turn_duration = timedelta(minutes=club.turn_duration_minutes)

    # Generar turnos desde la hora de apertura hasta la de cierre
    current_time = opening_datetime

    while current_time + turn_duration <= closing_datetime:
        end_time = current_time + turn_duration

        # Crear objeto de turno (sin court_id ni court_name)
        turn_item = {
            "start_time": current_time.strftime("%H:%M"),
            "end_time": end_time.strftime("%H:%M"),
            "price": club.price_per_turn,
        }

        turns_data.append(turn_item)

        # Avanzar al siguiente turno
        current_time += turn_duration

    # Crear la estructura final
    club_turns_data = {"club_id": club.id, "club_name": club.name, "turns": turns_data}

    logger.info(
        f"Generated turns data for club {club_id} with {len(turns_data)} turn slots"
    )
    return club_turns_data


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


def generate_turns_for_court_and_date(db: Session, court, club, date) -> List[dict]:
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
    from app.models.turn import Turn, TurnStatus
    from datetime import datetime, timedelta

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


def update_club(db: Session, club_id: int, club: ClubUpdate) -> Optional[Club]:
    db_club = get_club(db, club_id)
    if not db_club:
        return None

    update_data = club.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_club, field, value)

    db.commit()
    db.refresh(db_club)
    return db_club


def delete_club(db: Session, club_id: int) -> bool:
    db_club = get_club(db, club_id)
    if not db_club:
        return False

    db.delete(db_club)
    db.commit()
    return True
