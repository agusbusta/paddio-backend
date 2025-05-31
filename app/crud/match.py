from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.match import Match
from app.schemas.match import MatchCreate, MatchUpdate


def get_match(db: Session, match_id: int) -> Optional[Match]:
    return db.query(Match).filter(Match.id == match_id).first()


def get_matches(db: Session, skip: int = 0, limit: int = 100) -> List[Match]:
    return db.query(Match).offset(skip).limit(limit).all()


def create_match(db: Session, match: MatchCreate) -> Match:
    db_match = Match(**match.model_dump())
    db.add(db_match)
    db.commit()
    db.refresh(db_match)
    return db_match


def update_match(db: Session, match_id: int, match: MatchUpdate) -> Optional[Match]:
    db_match = get_match(db, match_id)
    if not db_match:
        return None

    update_data = match.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_match, field, value)

    db.commit()
    db.refresh(db_match)
    return db_match


def delete_match(db: Session, match_id: int) -> bool:
    db_match = get_match(db, match_id)
    if not db_match:
        return False

    db.delete(db_match)
    db.commit()
    return True
