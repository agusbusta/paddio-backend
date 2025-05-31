from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.crud import stadium as crud
from app.schemas.stadium import StadiumResponse, StadiumCreate, StadiumUpdate

router = APIRouter()


@router.post("/", response_model=StadiumResponse)
def create_stadium(stadium: StadiumCreate, db: Session = Depends(get_db)):
    return crud.create_stadium(db=db, stadium=stadium)


@router.get("/", response_model=List[StadiumResponse])
def read_stadiums(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    stadiums = crud.get_stadiums(db, skip=skip, limit=limit)
    return stadiums


@router.get("/{stadium_id}", response_model=StadiumResponse)
def read_stadium(stadium_id: int, db: Session = Depends(get_db)):
    db_stadium = crud.get_stadium(db, stadium_id=stadium_id)
    if db_stadium is None:
        raise HTTPException(status_code=404, detail="Stadium not found")
    return db_stadium


@router.put("/{stadium_id}", response_model=StadiumResponse)
def update_stadium(
    stadium_id: int, stadium: StadiumUpdate, db: Session = Depends(get_db)
):
    db_stadium = crud.update_stadium(db=db, stadium_id=stadium_id, stadium=stadium)
    if db_stadium is None:
        raise HTTPException(status_code=404, detail="Stadium not found")
    return db_stadium


@router.delete("/{stadium_id}")
def delete_stadium(stadium_id: int, db: Session = Depends(get_db)):
    success = crud.delete_stadium(db=db, stadium_id=stadium_id)
    if not success:
        raise HTTPException(status_code=404, detail="Stadium not found")
    return {"message": "Stadium deleted successfully"}
