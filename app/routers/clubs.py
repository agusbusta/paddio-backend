from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.crud import club as crud
from app.schemas.club import ClubResponse, ClubCreate, ClubUpdate

router = APIRouter()


@router.post("/", response_model=ClubResponse)
def create_club(club: ClubCreate, db: Session = Depends(get_db)):
    return crud.create_club(db=db, club=club)


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
