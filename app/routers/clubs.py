from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.crud import club as crud
from app.schemas.club import ClubResponse, ClubCreate, ClubUpdate
from app.services.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=ClubResponse)
def create_club(
    club: ClubCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Solo admins pueden crear clubs
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can create clubs")

    # Verificar que el admin no tenga ya un club
    if current_user.club_id is not None:
        raise HTTPException(status_code=400, detail="Admin already has a club")

    return crud.create_club(db=db, club=club, admin_user_id=current_user.id)


@router.get("/", response_model=List[ClubResponse])
def read_clubs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    clubs = crud.get_clubs(db, skip=skip, limit=limit)
    return clubs


@router.get("/{club_id}", response_model=ClubResponse)
def read_club(club_id: int, db: Session = Depends(get_db)):
    db_club = crud.get_club(db, club_id=club_id)
    if db_club is None:
        raise HTTPException(status_code=404, detail="Club not found")
    return db_club


@router.put("/{club_id}", response_model=ClubResponse)
def update_club(club_id: int, club: ClubUpdate, db: Session = Depends(get_db)):
    db_club = crud.update_club(db=db, club_id=club_id, club=club)
    if db_club is None:
        raise HTTPException(status_code=404, detail="Club not found")
    return db_club


@router.delete("/{club_id}")
def delete_club(club_id: int, db: Session = Depends(get_db)):
    success = crud.delete_club(db=db, club_id=club_id)
    if not success:
        raise HTTPException(status_code=404, detail="Club not found")
    return {"message": "Club deleted successfully"}
