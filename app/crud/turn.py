from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional

from app.models.turn import Turn, TurnStatus
from app.schemas.turn import TurnCreate, TurnUpdate


def get_turn(db: Session, turn_id: int) -> Optional[Turn]:
    return db.query(Turn).filter(Turn.id == turn_id).first()


def get_turns(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    court_id: Optional[int] = None,
    status: Optional[TurnStatus] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> List[Turn]:
    query = db.query(Turn)

    if court_id:
        query = query.filter(Turn.court_id == court_id)
    if status:
        query = query.filter(Turn.status == status)
    if start_time:
        query = query.filter(Turn.start_time >= start_time)
    if end_time:
        query = query.filter(Turn.end_time <= end_time)

    return query.offset(skip).limit(limit).all()


def create_turn(db: Session, turn: TurnCreate) -> Turn:
    db_turn = Turn(
        court_id=turn.court_id,
        start_time=turn.start_time,
        end_time=turn.end_time,
        price=turn.price,
        status=turn.status,
    )
    db.add(db_turn)
    db.commit()
    db.refresh(db_turn)
    return db_turn


def update_turn(db: Session, turn_id: int, turn: TurnUpdate) -> Optional[Turn]:
    db_turn = get_turn(db, turn_id)
    if not db_turn:
        return None

    update_data = turn.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_turn, field, value)

    db.commit()
    db.refresh(db_turn)
    return db_turn


def delete_turn(db: Session, turn_id: int) -> bool:
    db_turn = get_turn(db, turn_id)
    if not db_turn:
        return False

    db.delete(db_turn)
    db.commit()
    return True
