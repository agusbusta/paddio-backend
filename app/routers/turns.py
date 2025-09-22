from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.crud import turn as crud
from app.schemas.turn import TurnResponse, TurnCreate, TurnUpdate
from app.models.turn import TurnStatus
from app.services.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=TurnResponse)
def create_turn(
    turn: TurnCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Solo admins pueden crear turnos
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can create turns")

    # Verificar que el turno pertenezca al club del admin
    if turn.club_id != current_user.club_id:
        raise HTTPException(
            status_code=403, detail="Can only create turns for your own club"
        )

    return crud.create_turn(db=db, turn=turn)


@router.get("/", response_model=List[TurnResponse])
def read_turns(
    skip: int = 0,
    limit: int = 100,
    club_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    turns = crud.get_turns(
        db=db,
        skip=skip,
        limit=limit,
        club_id=club_id,
    )
    return turns


@router.get("/{turn_id}", response_model=TurnResponse)
def read_turn(turn_id: int, db: Session = Depends(get_db)):
    db_turn = crud.get_turn(db=db, turn_id=turn_id)
    if db_turn is None:
        raise HTTPException(status_code=404, detail="Turn not found")
    return db_turn


@router.put("/{turn_id}", response_model=TurnResponse)
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
