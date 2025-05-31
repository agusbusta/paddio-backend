from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.crud import turn as crud
from app.schemas.turn import Turn, TurnCreate, TurnUpdate
from app.models.turn import TurnStatus

router = APIRouter()


@router.post("/", response_model=Turn)
def create_turn(turn: TurnCreate, db: Session = Depends(get_db)):
    return crud.create_turn(db=db, turn=turn)


@router.get("/", response_model=List[Turn])
def read_turns(
    skip: int = 0,
    limit: int = 100,
    court_id: Optional[int] = None,
    status: Optional[TurnStatus] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    turns = crud.get_turns(
        db=db,
        skip=skip,
        limit=limit,
        court_id=court_id,
        status=status,
        start_time=start_time,
        end_time=end_time,
    )
    return turns


@router.get("/{turn_id}", response_model=Turn)
def read_turn(turn_id: int, db: Session = Depends(get_db)):
    db_turn = crud.get_turn(db=db, turn_id=turn_id)
    if db_turn is None:
        raise HTTPException(status_code=404, detail="Turn not found")
    return db_turn


@router.put("/{turn_id}", response_model=Turn)
def update_turn(turn_id: int, turn: TurnUpdate, db: Session = Depends(get_db)):
    db_turn = crud.update_turn(db=db, turn_id=turn_id, turn=turn)
    if db_turn is None:
        raise HTTPException(status_code=404, detail="Turn not found")
    return db_turn


@router.delete("/{turn_id}")
def delete_turn(turn_id: int, db: Session = Depends(get_db)):
    success = crud.delete_turn(db=db, turn_id=turn_id)
    if not success:
        raise HTTPException(status_code=404, detail="Turn not found")
    return {"message": "Turn deleted successfully"}
