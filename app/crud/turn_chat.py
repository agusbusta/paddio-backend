"""CRUD para mensajes del chat interno de un turno.

Solo los jugadores que aceptaron la invitación al turno (es decir, están asignados
en player1_id, player2_id, player3_id o player4_id del PregameTurn) pueden ver,
leer y escribir mensajes en el chat. Quienes tienen invitación pendiente no tienen
acceso.
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from app.models.turn_chat_message import TurnChatMessage
from app.models.pregame_turn import PregameTurn
from app.models.turn_chat_read import TurnChatRead


def get_turn_participant_ids(db: Session, pregame_turn_id: int) -> List[int]:
    """Devuelve los user_id que son parte del turno (aceptaron: están en player1..player4)."""
    turn = db.query(PregameTurn).filter(PregameTurn.id == pregame_turn_id).first()
    if not turn:
        return []
    ids = []
    for i in range(1, 5):
        pid = getattr(turn, f"player{i}_id", None)
        if pid is not None:
            ids.append(pid)
    return ids


def is_user_participant(db: Session, pregame_turn_id: int, user_id: int) -> bool:
    return user_id in get_turn_participant_ids(db, pregame_turn_id)


def can_access_chat(db: Session, pregame_turn_id: int, user_id: int) -> bool:
    """True si el usuario puede ver/escribir en el chat: es participante (player1..4) o es el organizador (configurador = player1)."""
    turn = db.query(PregameTurn).filter(PregameTurn.id == pregame_turn_id).first()
    if not turn:
        return False
    if turn.player1_id == user_id:
        return True
    return user_id in get_turn_participant_ids(db, pregame_turn_id)


def get_messages(
    db: Session,
    pregame_turn_id: int,
    limit: int = 100,
    offset: int = 0,
) -> List[TurnChatMessage]:
    """Lista mensajes del chat del turno, más recientes al final (orden ascendente por created_at)."""
    return (
        db.query(TurnChatMessage)
        .filter(TurnChatMessage.pregame_turn_id == pregame_turn_id)
        .order_by(TurnChatMessage.created_at.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def create_message(
    db: Session,
    pregame_turn_id: int,
    user_id: int,
    message: str,
) -> Optional[TurnChatMessage]:
    """Crea un mensaje en el chat del turno. No valida participante aquí (lo hace el router)."""
    if not message or not message.strip():
        return None
    msg = TurnChatMessage(
        pregame_turn_id=pregame_turn_id,
        user_id=user_id,
        message=message.strip()[:2000],
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def upsert_last_read(db: Session, user_id: int, pregame_turn_id: int) -> None:
    """Marca el chat del turno como leído por el usuario (al abrir el chat)."""
    row = (
        db.query(TurnChatRead)
        .filter(
            and_(
                TurnChatRead.user_id == user_id,
                TurnChatRead.pregame_turn_id == pregame_turn_id,
            )
        )
        .first()
    )
    now = datetime.utcnow()
    if row:
        row.last_read_at = now
    else:
        db.add(TurnChatRead(user_id=user_id, pregame_turn_id=pregame_turn_id, last_read_at=now))
    db.commit()


def has_unread_chat(db: Session, user_id: int, pregame_turn_id: int) -> bool:
    """True si hay mensajes de otros después de la última vez que el usuario leyó."""
    row = (
        db.query(TurnChatRead)
        .filter(
            and_(
                TurnChatRead.user_id == user_id,
                TurnChatRead.pregame_turn_id == pregame_turn_id,
            )
        )
        .first()
    )
    since = row.last_read_at if row else datetime.min
    exists = (
        db.query(TurnChatMessage.id)
        .filter(
            TurnChatMessage.pregame_turn_id == pregame_turn_id,
            TurnChatMessage.user_id != user_id,
            TurnChatMessage.created_at > since,
        )
        .limit(1)
        .first()
    )
    return exists is not None
