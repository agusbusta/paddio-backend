from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import List, Optional

from app.models.pregame_turn import PregameTurn, PregameTurnStatus
from app.schemas.pregame_turn import PregameTurnCreate, PregameTurnUpdate


def get_pregame_turn(db: Session, pregame_turn_id: int) -> Optional[PregameTurn]:
    return db.query(PregameTurn).filter(PregameTurn.id == pregame_turn_id).first()


def get_pregame_turns(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    turn_id: Optional[int] = None,
    court_id: Optional[int] = None,
    date: Optional[date] = None,
    status: Optional[PregameTurnStatus] = None,
) -> List[PregameTurn]:
    query = db.query(PregameTurn)

    if turn_id:
        query = query.filter(PregameTurn.turn_id == turn_id)
    if court_id:
        query = query.filter(PregameTurn.court_id == court_id)
    if date:
        query = query.filter(PregameTurn.date == date)
    if status:
        query = query.filter(PregameTurn.status == status)

    return query.offset(skip).limit(limit).all()


def create_pregame_turn(db: Session, pregame_turn: PregameTurnCreate) -> PregameTurn:
    db_pregame_turn = PregameTurn(**pregame_turn.model_dump())
    db.add(db_pregame_turn)
    db.commit()
    db.refresh(db_pregame_turn)
    return db_pregame_turn


def update_pregame_turn(
    db: Session, pregame_turn_id: int, pregame_turn: PregameTurnUpdate
) -> Optional[PregameTurn]:
    db_pregame_turn = get_pregame_turn(db, pregame_turn_id)
    if not db_pregame_turn:
        return None

    update_data = pregame_turn.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_pregame_turn, field, value)

    db.commit()
    db.refresh(db_pregame_turn)
    return db_pregame_turn


def delete_pregame_turn(db: Session, pregame_turn_id: int) -> bool:
    db_pregame_turn = get_pregame_turn(db, pregame_turn_id)
    if not db_pregame_turn:
        return False

    db.delete(db_pregame_turn)
    db.commit()
    return True


def assign_player_to_pregame_turn(
    db: Session, pregame_turn_id: int, player_id: int
) -> Optional[PregameTurn]:
    """
    Asigna un jugador a un pregame turn.
    Busca la primera posición disponible (player1, player2, player3, player4).
    """
    db_pregame_turn = get_pregame_turn(db, pregame_turn_id)
    if not db_pregame_turn:
        return None

    # Verificar si el jugador ya está asignado
    if (
        db_pregame_turn.player1_id == player_id
        or db_pregame_turn.player2_id == player_id
        or db_pregame_turn.player3_id == player_id
        or db_pregame_turn.player4_id == player_id
    ):
        return db_pregame_turn  # Ya está asignado

    # Buscar la primera posición disponible
    if db_pregame_turn.player1_id is None:
        db_pregame_turn.player1_id = player_id
    elif db_pregame_turn.player2_id is None:
        db_pregame_turn.player2_id = player_id
    elif db_pregame_turn.player3_id is None:
        db_pregame_turn.player3_id = player_id
    elif db_pregame_turn.player4_id is None:
        db_pregame_turn.player4_id = player_id
    else:
        return None  # No hay posiciones disponibles

    # Verificar si ahora está completo (4 jugadores)
    if all(
        [
            db_pregame_turn.player1_id,
            db_pregame_turn.player2_id,
            db_pregame_turn.player3_id,
            db_pregame_turn.player4_id,
        ]
    ):
        db_pregame_turn.status = PregameTurnStatus.READY_TO_PLAY

    db.commit()
    db.refresh(db_pregame_turn)
    return db_pregame_turn


def remove_player_from_pregame_turn(
    db: Session, pregame_turn_id: int, player_id: int
) -> Optional[PregameTurn]:
    """
    Remueve un jugador de un pregame turn.
    """
    db_pregame_turn = get_pregame_turn(db, pregame_turn_id)
    if not db_pregame_turn:
        return None

    # Remover el jugador de la posición que esté ocupando
    if db_pregame_turn.player1_id == player_id:
        db_pregame_turn.player1_id = None
    elif db_pregame_turn.player2_id == player_id:
        db_pregame_turn.player2_id = None
    elif db_pregame_turn.player3_id == player_id:
        db_pregame_turn.player3_id = None
    elif db_pregame_turn.player4_id == player_id:
        db_pregame_turn.player4_id = None
    else:
        return db_pregame_turn  # El jugador no estaba asignado

    # Cambiar estado a WAITING_PLAYERS si no está completo
    db_pregame_turn.status = PregameTurnStatus.WAITING_PLAYERS

    db.commit()
    db.refresh(db_pregame_turn)
    return db_pregame_turn
