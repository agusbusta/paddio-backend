from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.crud import court as crud
from app.schemas.court import CourtResponse, CourtCreate, CourtUpdate

router = APIRouter()


@router.post("/", response_model=CourtResponse)
def create_court(court: CourtCreate, db: Session = Depends(get_db)):
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
