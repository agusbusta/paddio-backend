from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.court import Court
from app.schemas.court import CourtCreate, CourtUpdate


def get_court(db: Session, court_id: int) -> Optional[Court]:
    return db.query(Court).filter(Court.id == court_id).first()


def get_courts(db: Session, skip: int = 0, limit: int = 100) -> List[Court]:
    return db.query(Court).offset(skip).limit(limit).all()


def create_court(db: Session, court: CourtCreate) -> Court:
    db_court = Court(**court.model_dump())
    db.add(db_court)
    db.commit()
    db.refresh(db_court)
    return db_court


def update_court(db: Session, court_id: int, court: CourtUpdate) -> Optional[Court]:
    db_court = get_court(db, court_id)
    if not db_court:
        return None

    update_data = court.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_court, field, value)

    db.commit()
    db.refresh(db_court)
    return db_court


def delete_court(db: Session, court_id: int) -> bool:
    db_court = get_court(db, court_id)
    if not db_court:
        return False

    db.delete(db_court)
    db.commit()
    return True
