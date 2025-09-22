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

    # Crear el club
    created_club = crud.create_club(db=db, club=club, admin_user_id=current_user.id)

    # Generar estructura de turnos para el club
    try:
        turns_data = crud.generate_turns_data_for_club(db=db, club_id=created_club.id)
        if turns_data:
            # Crear el registro de turnos en la base de datos
            from app.schemas.turn import TurnCreate
            from app.crud import turn as turn_crud

            turn_create = TurnCreate(club_id=created_club.id, turns_data=turns_data)
            turn_crud.create_turn(db=db, turn=turn_create)
    except Exception as e:
        # Log el error pero no fallar la creación del club
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error generating turns data for club {created_club.id}: {e}")

    return created_club


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


@router.post("/{club_id}/generate-turns")
def generate_turns_for_club(
    club_id: int,
    days_ahead: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Genera turnos automáticamente para un club.
    """
    # Solo admins pueden generar turnos
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can generate turns")

    # Verificar que el admin tenga un club
    if not current_user.club_id:
        raise HTTPException(
            status_code=400, detail="Admin must have a club to generate turns"
        )

    # Verificar que el club pertenezca al admin
    if club_id != current_user.club_id:
        raise HTTPException(
            status_code=403, detail="Can only generate turns for your own club"
        )

    # Generar estructura de turnos
    try:
        turns_data = crud.generate_turns_data_for_club(db=db, club_id=club_id)
        if turns_data:
            # Crear o actualizar el registro de turnos en la base de datos
            from app.schemas.turn import TurnCreate
            from app.crud import turn as turn_crud

            # Verificar si ya existe un registro de turnos para este club
            existing_turn = turn_crud.get_turns(db=db, club_id=club_id)
            if existing_turn:
                # Actualizar el registro existente
                turn_crud.update_turn(
                    db=db,
                    turn_id=existing_turn[0].id,
                    turn=TurnCreate(club_id=club_id, turns_data=turns_data),
                )
                return {
                    "message": f"Updated turns data for club {club_id} with {len(turns_data['turns'])} turn slots"
                }
            else:
                # Crear nuevo registro
                turn_create = TurnCreate(club_id=club_id, turns_data=turns_data)
                turn_crud.create_turn(db=db, turn=turn_create)
                return {
                    "message": f"Generated turns data for club {club_id} with {len(turns_data['turns'])} turn slots"
                }
        else:
            return {"message": "No turns data generated"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating turns data: {str(e)}"
        )
