from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.club import Club
from app.schemas.club import ClubCreate, ClubUpdate


def get_club(db: Session, club_id: int) -> Optional[Club]:
    return db.query(Club).filter(Club.id == club_id).first()


def get_clubs(db: Session, skip: int = 0, limit: int = 100) -> List[Club]:
    return db.query(Club).offset(skip).limit(limit).all()


def create_club(db: Session, club: ClubCreate) -> Club:
    db_club = Club(**club.model_dump())
    db.add(db_club)
    db.commit()
    db.refresh(db_club)
    return db_club


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
