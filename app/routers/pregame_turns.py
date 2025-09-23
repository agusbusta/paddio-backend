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
from app.models.pregame_turn import PregameTurn, PregameTurnStatus
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


@router.get("/available-turns")
def get_all_available_turns(
    target_date: date = Query(
        ..., description="Date to check for available turns (YYYY-MM-DD)"
    ),
    start_time: Optional[str] = Query(
        None, description="Filter by start time (HH:MM format)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene todos los turnos disponibles de todos los clubs para una fecha específica.
    Endpoint para el frontend que necesita mostrar turnos de múltiples clubs.
    """
    # Obtener todos los clubs
    clubs = club_crud.get_clubs(db)

    result = {
        "date": target_date.isoformat(),
        "clubs": [],
        "total_clubs": 0,
        "total_available_turns": 0,
    }

    for club in clubs:
        # Obtener el template de turnos del club
        club_turns = turn_crud.get_turns(db, club_id=club.id)
        if not club_turns:
            continue  # Skip clubs without turn templates

        # Obtener turnos ya reservados para esa fecha
        existing_pregame_turns = crud.get_pregame_turns(
            db,
            turn_id=club_turns[0].id,
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
            # Filtrar por horario si se especifica
            if start_time and turn["start_time"] != start_time:
                continue

            if turn["start_time"] not in reserved_times:
                available_turns.append(
                    {
                        "start_time": turn["start_time"],
                        "end_time": turn["end_time"],
                        "price": turn["price"],
                        "status": "AVAILABLE",
                    }
                )

        # Solo incluir clubs que tengan turnos disponibles
        if available_turns:
            club_data = {
                "club_id": club.id,
                "club_name": club.name,
                "club_address": club.address,
                "club_phone": club.phone,
                "available_turns": available_turns,
                "total_available": len(available_turns),
            }
            result["clubs"].append(club_data)
            result["total_available_turns"] += len(available_turns)

    result["total_clubs"] = len(result["clubs"])
    return result


@router.get("/my-reservations")
def get_my_reservations(
    target_date: Optional[date] = Query(
        None, description="Filter by date (YYYY-MM-DD)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene las reservas activas del jugador actual:
    - Turnos PENDIENTES (1-3 jugadores, esperando más)
    - Turnos READY_TO_PLAY (4 jugadores, listos para jugar)
    """
    # Verificar que el usuario sea un jugador (no admin ni super admin)
    if current_user.is_admin or current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="Only players can view their reservations"
        )

    # Buscar todos los pregame_turns donde el jugador esté asignado
    # Solo incluir turnos activos (PENDING y READY_TO_PLAY)
    query = (
        db.query(PregameTurn)
        .filter(
            (PregameTurn.player1_id == current_user.id)
            | (PregameTurn.player2_id == current_user.id)
            | (PregameTurn.player3_id == current_user.id)
            | (PregameTurn.player4_id == current_user.id)
        )
        .filter(
            PregameTurn.status.in_(
                [PregameTurnStatus.PENDING, PregameTurnStatus.READY_TO_PLAY]
            )
        )
    )

    # Aplicar filtro de fecha si se especifica
    if target_date:
        query = query.filter(
            PregameTurn.date == datetime.combine(target_date, datetime.min.time())
        )

    # Ordenar por fecha y hora
    reservations = query.order_by(PregameTurn.date, PregameTurn.start_time).all()

    # Separar turnos por estado
    pending_turns = []
    ready_turns = []

    for reservation in reservations:
        # Obtener información del club
        club = club_crud.get_club(db, reservation.turn.club_id)

        # Determinar posición del jugador
        player_position = None
        if reservation.player1_id == current_user.id:
            player_position = "player1"
        elif reservation.player2_id == current_user.id:
            player_position = "player2"
        elif reservation.player3_id == current_user.id:
            player_position = "player3"
        elif reservation.player4_id == current_user.id:
            player_position = "player4"

        # Contar jugadores actuales
        players_count = sum(
            [
                1
                for player_id in [
                    reservation.player1_id,
                    reservation.player2_id,
                    reservation.player3_id,
                    reservation.player4_id,
                ]
                if player_id is not None
            ]
        )

        formatted_reservation = {
            "id": reservation.id,
            "club_id": club.id if club else None,
            "club_name": club.name if club else "Unknown Club",
            "club_address": club.address if club else None,
            "club_phone": club.phone if club else None,
            "date": reservation.date.strftime("%Y-%m-%d"),
            "start_time": reservation.start_time,
            "end_time": reservation.end_time,
            "price": reservation.price,
            "status": reservation.status.value,
            "player_position": player_position,
            "player_side": reservation.player_side,
            "player_court_position": reservation.player_court_position,
            "players_count": players_count,
            "players_needed": 4 - players_count,
            "created_at": reservation.created_at,
            "updated_at": reservation.updated_at,
        }

        # Separar por estado
        if reservation.status == PregameTurnStatus.PENDING:
            pending_turns.append(formatted_reservation)
        elif reservation.status == PregameTurnStatus.READY_TO_PLAY:
            ready_turns.append(formatted_reservation)

    return {
        "user_id": current_user.id,
        "user_name": current_user.name,
        "pending_turns": {
            "turns": pending_turns,
            "count": len(pending_turns),
            "description": "Turnos esperando más jugadores (1-3 jugadores)",
        },
        "ready_turns": {
            "turns": ready_turns,
            "count": len(ready_turns),
            "description": "Turnos listos para jugar (4 jugadores)",
        },
        "total_active_reservations": len(pending_turns) + len(ready_turns),
        "filters": {
            "date": target_date.isoformat() if target_date else None,
        },
    }


@router.post("/join-turn")
def join_turn(
    club_id: int = Query(..., description="Club ID"),
    start_time: str = Query(..., description="Start time in HH:MM format"),
    target_date: date = Query(..., description="Date to join (YYYY-MM-DD)"),
    player_side: Optional[str] = Query(
        None, description="Player side: 'reves' or 'drive'"
    ),
    player_court_position: Optional[str] = Query(
        None, description="Player court position: 'izquierda' or 'derecha'"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Un jugador se une a un turno existente o crea uno nuevo si no existe.
    """
    # Verificar que el usuario sea un jugador (no admin ni super admin)
    if current_user.is_admin or current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Only players can join turns")

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

    # Buscar si ya existe un pregame_turn para este horario
    existing_pregame_turns = crud.get_pregame_turns(
        db,
        turn_id=club_turns[0].id,
        date=datetime.combine(target_date, datetime.min.time()),
    )

    existing_turn = None
    for pregame_turn in existing_pregame_turns:
        if pregame_turn.start_time == start_time:
            existing_turn = pregame_turn
            break

    # Si no existe el turno, crearlo
    if not existing_turn:
        # Crear el pregame_turn (necesitamos un court_id, usaremos el primero disponible)
        courts = club.courts
        if not courts:
            raise HTTPException(status_code=400, detail="Club has no courts available")

        pregame_turn_data = PregameTurnCreate(
            turn_id=club_turns[0].id,
            court_id=courts[0].id,  # Asignar a la primera cancha disponible
            date=datetime.combine(target_date, datetime.min.time()),
            start_time=turn_info["start_time"],
            end_time=turn_info["end_time"],
            price=turn_info["price"],
            status="PENDING",
            player1_id=current_user.id,
            player_side=player_side,
            player_court_position=player_court_position,
        )

        created_turn = crud.create_pregame_turn(db, pregame_turn_data)

        return {
            "message": "Turn created and joined successfully",
            "pregame_turn": created_turn,
            "players_count": 1,
            "players_needed": 3,
        }

    # Si existe el turno, verificar que no esté completo
    if existing_turn.status == "READY_TO_PLAY":
        raise HTTPException(status_code=400, detail="Turn is already full")

    # Verificar que el jugador no esté ya en el turno
    if (
        existing_turn.player1_id == current_user.id
        or existing_turn.player2_id == current_user.id
        or existing_turn.player3_id == current_user.id
        or existing_turn.player4_id == current_user.id
    ):
        raise HTTPException(status_code=400, detail="Player already in this turn")

    # Asignar al jugador a la primera posición disponible
    update_data = PregameTurnUpdate()

    if not existing_turn.player1_id:
        update_data.player1_id = current_user.id
        update_data.player_side = player_side
        update_data.player_court_position = player_court_position
    elif not existing_turn.player2_id:
        update_data.player2_id = current_user.id
        update_data.player_side = player_side
        update_data.player_court_position = player_court_position
    elif not existing_turn.player3_id:
        update_data.player3_id = current_user.id
        update_data.player_side = player_side
        update_data.player_court_position = player_court_position
    elif not existing_turn.player4_id:
        update_data.player4_id = current_user.id
        update_data.player_side = player_side
        update_data.player_court_position = player_court_position
    else:
        raise HTTPException(status_code=400, detail="Turn is already full")

    # Contar jugadores actuales (incluyendo el nuevo)
    players_count = sum(
        [
            1
            for player_id in [
                existing_turn.player1_id,
                existing_turn.player2_id,
                existing_turn.player3_id,
                existing_turn.player4_id,
                current_user.id,  # Incluir al jugador actual para la cuenta
            ]
            if player_id is not None
        ]
    )

    # Si es el cuarto jugador, cambiar estado a READY_TO_PLAY
    if players_count == 4:
        update_data.status = "READY_TO_PLAY"

    updated_turn = crud.update_pregame_turn(db, existing_turn.id, update_data)

    # Recalcular players_count después de la actualización
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
        "message": "Successfully joined existing turn",
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
