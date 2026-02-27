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


def create_pregame_turn(
    db: Session, pregame_turn: PregameTurnCreate, commit: bool = True
) -> PregameTurn:
    """
    Crear un pregame turn.

    Args:
        db: Sesión de base de datos
        pregame_turn: Datos del turno a crear
        commit: Si True, hace commit automático. Si False, solo agrega a la sesión (útil para mantener locks)

    Returns:
        PregameTurn creado
    """
    db_pregame_turn = PregameTurn(**pregame_turn.model_dump())
    db.add(db_pregame_turn)
    if commit:
        db.commit()
        db.refresh(db_pregame_turn)
    else:
        # Flush para obtener el ID sin hacer commit (mantiene el lock)
        db.flush()
        db.refresh(db_pregame_turn)
    return db_pregame_turn


def update_pregame_turn(
    db: Session,
    pregame_turn_id: int,
    pregame_turn: PregameTurnUpdate,
    commit: bool = True,
) -> Optional[PregameTurn]:
    """
    Actualizar un pregame turn.

    Args:
        db: Sesión de base de datos
        pregame_turn_id: ID del turno a actualizar
        pregame_turn: Datos a actualizar
        commit: Si True, hace commit automático. Si False, solo actualiza en memoria (útil para mantener locks)

    Returns:
        PregameTurn actualizado o None si no existe
    """
    db_pregame_turn = get_pregame_turn(db, pregame_turn_id)
    if not db_pregame_turn:
        return None

    update_data = pregame_turn.model_dump(exclude_unset=True)

    # CRÍTICO: Proteger player1_id (organizador) - nunca puede ser None
    # Si se intenta establecer player1_id a None, mantener el valor actual
    if "player1_id" in update_data and update_data["player1_id"] is None:
        # El organizador nunca puede ser removido
        # Si se intenta cancelar player1, mantener su ID
        if db_pregame_turn.player1_id is not None:
            # Solo permitir cancelar si se está cancelando explícitamente TODO el turno
            # Pero en este caso, no deberíamos llegar aquí si es solo una actualización de posición
            # Mantener el player1_id original
            update_data["player1_id"] = db_pregame_turn.player1_id

    # CRÍTICO: Si se está actualizando solo side/court_position de un player,
    # asegurar que el player_id correspondiente NO se elimine
    # Si no se envía el player_id en el update, mantener el valor actual
    for player_num in [1, 2, 3, 4]:
        player_id_field = f"player{player_num}_id"
        side_field = f"player{player_num}_side"
        position_field = f"player{player_num}_court_position"

        # Si se está actualizando side o position pero NO se envía el player_id,
        # asegurar que el player_id se mantenga
        if (
            side_field in update_data or position_field in update_data
        ) and player_id_field not in update_data:
            # Mantener el player_id actual si existe
            current_player_id = getattr(db_pregame_turn, player_id_field, None)
            if current_player_id is not None:
                update_data[player_id_field] = current_player_id

    for field, value in update_data.items():
        setattr(db_pregame_turn, field, value)

    if commit:
        db.commit()
        db.refresh(db_pregame_turn)
    else:
        # Flush para aplicar cambios sin hacer commit (mantiene el lock)
        db.flush()
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
