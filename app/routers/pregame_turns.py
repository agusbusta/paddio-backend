from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date

from app.database import get_db
from app.crud import pregame_turn as crud
from app.crud import turn as turn_crud
from app.crud import club as club_crud
from app.schemas.pregame_turn import (
    PregameTurnResponse,
    PregameTurnCreate,
    PregameTurnUpdate,
)
from app.services.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/clubs/{club_id}/available-turns")
def get_available_turns_for_club(
    club_id: int,
    target_date: date = Query(
        ..., description="Date to check for available turns (YYYY-MM-DD)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene los turnos disponibles de un club para una fecha específica.
    Un turno está disponible si:
    1. Existe en la tabla 'turns' (template del club)
    2. NO existe en 'pregame_turns' para esa fecha específica
    """
    # Verificar que el club existe
    club = club_crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    # Obtener el template de turnos del club
    club_turns = turn_crud.get_turns(db, club_id=club_id)
    if not club_turns:
        raise HTTPException(
            status_code=404, detail="No turns template found for this club"
        )

    # Obtener turnos ya reservados para esa fecha
    existing_pregame_turns = crud.get_pregame_turns(
        db,
        turn_id=club_turns[0].id,  # Usar el primer (y único) turn template
        date=datetime.combine(target_date, datetime.min.time()),
    )

    # Crear set de horarios ya reservados
    reserved_times = set()
    for pregame_turn in existing_pregame_turns:
        reserved_times.add(pregame_turn.start_time)

    # Filtrar turnos disponibles
    turns_data = club_turns[0].turns_data
    available_turns = []

    for turn in turns_data["turns"]:
        if turn["start_time"] not in reserved_times:
            available_turns.append(
                {
                    "start_time": turn["start_time"],
                    "end_time": turn["end_time"],
                    "price": turn["price"],
                    "club_id": club_id,
                    "club_name": club.name,
                    "date": target_date.isoformat(),
                    "status": "AVAILABLE",
                }
            )

    return {
        "club_id": club_id,
        "club_name": club.name,
        "date": target_date.isoformat(),
        "available_turns": available_turns,
        "total_available": len(available_turns),
    }


@router.get("/clubs/{club_id}/pregame-turns")
def get_pregame_turns_for_club(
    club_id: int,
    target_date: Optional[date] = Query(
        None, description="Date to filter pregame turns (YYYY-MM-DD)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene los pregame turns de un club (turnos iniciados pero no completos).
    """
    # Verificar que el club existe
    club = club_crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    # Obtener el template de turnos del club
    club_turns = turn_crud.get_turns(db, club_id=club_id)
    if not club_turns:
        raise HTTPException(
            status_code=404, detail="No turns template found for this club"
        )

    # Obtener pregame turns
    pregame_turns = crud.get_pregame_turns(
        db,
        turn_id=club_turns[0].id,
        date=(
            datetime.combine(target_date, datetime.min.time()) if target_date else None
        ),
    )

    return {
        "club_id": club_id,
        "club_name": club.name,
        "pregame_turns": pregame_turns,
        "total_pregame_turns": len(pregame_turns),
    }


@router.post("/reserve-turn")
def reserve_turn(
    club_id: int,
    start_time: str = Query(..., description="Start time in HH:MM format"),
    target_date: date = Query(..., description="Date to reserve (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Reserva un turno (crea un pregame_turn con el primer jugador).
    """
    # Verificar que el club existe
    club = club_crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    # Obtener el template de turnos del club
    club_turns = turn_crud.get_turns(db, club_id=club_id)
    if not club_turns:
        raise HTTPException(
            status_code=404, detail="No turns template found for this club"
        )

    # Verificar que el turno existe en el template
    turns_data = club_turns[0].turns_data
    turn_info = None
    for turn in turns_data["turns"]:
        if turn["start_time"] == start_time:
            turn_info = turn
            break

    if not turn_info:
        raise HTTPException(status_code=404, detail="Turn not found in club template")

    # Verificar que el turno no esté ya reservado
    existing_pregame_turns = crud.get_pregame_turns(
        db,
        turn_id=club_turns[0].id,
        date=datetime.combine(target_date, datetime.min.time()),
    )

    for pregame_turn in existing_pregame_turns:
        if pregame_turn.start_time == start_time:
            raise HTTPException(status_code=400, detail="Turn already reserved")

    # Crear el pregame_turn (necesitamos un court_id, usaremos el primero disponible)
    courts = club.courts
    if not courts:
        raise HTTPException(status_code=400, detail="Club has no courts available")

    # Crear el pregame_turn
    pregame_turn_data = PregameTurnCreate(
        turn_id=club_turns[0].id,
        court_id=courts[0].id,  # Usar la primera cancha disponible
        date=datetime.combine(target_date, datetime.min.time()),
        start_time=start_time,
        end_time=turn_info["end_time"],
        price=turn_info["price"],
        status="PENDING",
        player1_id=current_user.id,
    )

    pregame_turn = crud.create_pregame_turn(db, pregame_turn_data)

    return {
        "message": "Turn reserved successfully",
        "pregame_turn": pregame_turn,
        "players_needed": 3,  # Faltan 3 jugadores más
    }


@router.post("/join-turn/{pregame_turn_id}")
def join_turn(
    pregame_turn_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Un jugador se une a un turno existente.
    """
    pregame_turn = crud.get_pregame_turn(db, pregame_turn_id)
    if not pregame_turn:
        raise HTTPException(status_code=404, detail="Pregame turn not found")

    # Verificar que el turno no esté completo
    if pregame_turn.status == "READY_TO_PLAY":
        raise HTTPException(status_code=400, detail="Turn is already full")

    # Verificar que el jugador no esté ya en el turno
    if (
        pregame_turn.player1_id == current_user.id
        or pregame_turn.player2_id == current_user.id
        or pregame_turn.player3_id == current_user.id
        or pregame_turn.player4_id == current_user.id
    ):
        raise HTTPException(status_code=400, detail="Player already in this turn")

    # Asignar al jugador a la primera posición disponible
    update_data = PregameTurnUpdate()

    if not pregame_turn.player1_id:
        update_data.player1_id = current_user.id
    elif not pregame_turn.player2_id:
        update_data.player2_id = current_user.id
    elif not pregame_turn.player3_id:
        update_data.player3_id = current_user.id
    elif not pregame_turn.player4_id:
        update_data.player4_id = current_user.id
        # Si es el cuarto jugador, cambiar estado a READY_TO_PLAY
        update_data.status = "READY_TO_PLAY"

    updated_turn = crud.update_pregame_turn(db, pregame_turn_id, update_data)

    # Contar jugadores actuales
    players_count = sum(
        [
            1
            for player_id in [
                updated_turn.player1_id,
                updated_turn.player2_id,
                updated_turn.player3_id,
                updated_turn.player4_id,
            ]
            if player_id is not None
        ]
    )

    return {
        "message": "Successfully joined turn",
        "pregame_turn": updated_turn,
        "players_count": players_count,
        "players_needed": 4 - players_count,
    }


@router.get("/{pregame_turn_id}", response_model=PregameTurnResponse)
def get_pregame_turn(
    pregame_turn_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene un pregame turn específico.
    """
    pregame_turn = crud.get_pregame_turn(db, pregame_turn_id)
    if not pregame_turn:
        raise HTTPException(status_code=404, detail="Pregame turn not found")
    return pregame_turn


@router.put("/{pregame_turn_id}", response_model=PregameTurnResponse)
def update_pregame_turn(
    pregame_turn_id: int,
    pregame_turn: PregameTurnUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Actualiza un pregame turn.
    """
    updated_turn = crud.update_pregame_turn(db, pregame_turn_id, pregame_turn)
    if not updated_turn:
        raise HTTPException(status_code=404, detail="Pregame turn not found")
    return updated_turn


@router.delete("/{pregame_turn_id}")
def delete_pregame_turn(
    pregame_turn_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Elimina un pregame turn (cancelar reserva).
    """
    success = crud.delete_pregame_turn(db, pregame_turn_id)
    if not success:
        raise HTTPException(status_code=404, detail="Pregame turn not found")
    return {"message": "Pregame turn deleted successfully"}
