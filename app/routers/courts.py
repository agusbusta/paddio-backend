from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.crud import court as crud
from app.schemas.court import CourtResponse, CourtCreate, CourtUpdate
from app.services.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=CourtResponse)
def create_court(
    court: CourtCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Solo admins pueden crear canchas
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can create courts")

    # Verificar que el admin tenga un club
    if not current_user.club_id:
        raise HTTPException(
            status_code=400, detail="Admin must have a club to create courts"
        )

    # Verificar que la cancha pertenezca al club del admin
    if court.club_id != current_user.club_id:
        raise HTTPException(
            status_code=403, detail="Can only create courts for your own club"
        )

    return crud.create_court(db=db, court=court)


@router.get("/", response_model=List[CourtResponse])
def read_courts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    courts = crud.get_courts(db, skip=skip, limit=limit)
    return courts


@router.get("/{court_id}", response_model=CourtResponse)
def read_court(court_id: int, db: Session = Depends(get_db)):
    db_court = crud.get_court(db, court_id=court_id)
    if db_court is None:
        raise HTTPException(status_code=404, detail="Court not found")
    return db_court


@router.put("/{court_id}", response_model=CourtResponse)
def update_court(court_id: int, court: CourtUpdate, db: Session = Depends(get_db)):
    db_court = crud.update_court(db=db, court_id=court_id, court=court)
    if db_court is None:
        raise HTTPException(status_code=404, detail="Court not found")
    return db_court


@router.delete("/{court_id}")
def delete_court(court_id: int, db: Session = Depends(get_db)):
    success = crud.delete_court(db=db, court_id=court_id)
    if not success:
        raise HTTPException(status_code=404, detail="Court not found")
    return {"message": "Court deleted successfully"}
