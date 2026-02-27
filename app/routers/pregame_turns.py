from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime, date, timedelta

from app.database import get_db
from app.crud import pregame_turn as crud
from app.crud import turn as turn_crud
from app.crud import turn_chat as turn_chat_crud
from app.crud import club as club_crud
from app.schemas.pregame_turn import (
    PregameTurnResponse,
    PregameTurnCreate,
    PregameTurnUpdate,
)
from app.models.pregame_turn import PregameTurn, PregameTurnStatus
from app.models.booking import Booking, BookingStatus
from app.services.auth import get_current_user
from app.models.user import User
from app.enums.category_restriction import CategoryRestrictionType
from app.utils.category_validator import CategoryRestrictionValidator
from app.utils.turn_utils import (
    count_players_in_turn,
    validate_mixed_match_gender_balance,
    can_invite_player_to_mixed_match,
    validate_mixed_match_side_gender_balance,
)
from app.utils.turn_overlap import (
    get_user_active_reservations_time_ranges,
    does_turn_overlap_with_reservations,
    parse_time_to_minutes,
    minutes_to_time_string,
)
from app.services.notification_service import notification_service

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
    # CRÍTICO: Solo considerar turnos activos (PENDING o READY_TO_PLAY), excluir cancelados
    reserved_times = set()
    for pregame_turn in existing_pregame_turns:
        # Solo considerar turnos que NO están cancelados
        if pregame_turn.status not in [
            PregameTurnStatus.CANCELLED,
            PregameTurnStatus.COMPLETED,
        ]:
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


def _get_available_courts_for_club(club) -> list:
    """
    Obtiene todas las canchas disponibles del club con información completa.
    """
    available_courts = []
    for court in club.courts:
        if court.is_available:  # Solo canchas disponibles
            available_courts.append(
                {
                    "court_id": court.id,
                    "court_name": court.name,
                    "is_indoor": court.is_indoor,
                    "has_lighting": court.has_lighting,
                    "price_per_hour": (
                        court.price_per_hour
                        if hasattr(court, "price_per_hour")
                        else None
                    ),
                    "description": court.description or "",
                }
            )
    return available_courts


@router.get("/available-turns")
def get_all_available_turns(
    target_date: date = Query(
        ..., description="Date to check for available turns (YYYY-MM-DD)"
    ),
    start_time: Optional[str] = Query(
        None, description="Filter by start time (HH:MM format)"
    ),
    favorites_only: Optional[bool] = Query(
        False, description="Show only favorite clubs"
    ),
    show_only_mixed_matches: Optional[bool] = Query(
        False, description="Show only mixed matches (accepts players of both genders)"
    ),
    show_only_available: Optional[bool] = Query(
        False,
        description="Show only completely available turns (0 players, status AVAILABLE). Excludes turns with existing players.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene todos los turnos disponibles de todos los clubs para una fecha específica.
    Endpoint para el frontend que necesita mostrar turnos de múltiples clubs.

    PARÁMETROS:
    - target_date: Fecha objetivo (YYYY-MM-DD)
    - start_time: Filtro por hora de inicio (HH:MM) - opcional
    - favorites_only: Mostrar solo clubs favoritos - opcional
    - show_only_mixed_matches: Filtrar solo partidos mixtos - opcional

    RESPONSE FORMAT:
    {
        "date": "2025-09-23",
        "clubs": [
            {
                "club_id": 3,
                "club_name": "Club Admin Test",
                "club_address": "Av. Admin 456",
                "club_phone": "987654321",
                "available_turns": [
                    {
                        "turn_id": 123,           // ID del turno (null si es AVAILABLE)
                        "court_id": 5,            // ID de la cancha
                        "court_name": "Cancha 1", // Nombre de la cancha
                        "is_indoor": true,        // Cancha cubierta
                        "has_lighting": true,     // Tiene iluminación
                        "start_time": "18:00",
                        "end_time": "19:30",
                        "price": 2500,
                        "status": "PENDING",      // "AVAILABLE" o "PENDING"
                        "players_count": 1,       // Jugadores actuales (1-4)
                        "players_needed": 3,      // Jugadores que faltan
                        "assigned_players": [     // Solo si status = "PENDING"
                            {
                                "position": "player1",        // "player1", "player2", "player3", "player4"
                                "player_id": 7,               // ID del jugador
                                "player_side": "drive",       // "drive" o "reves"
                                "player_court_position": "derecha"  // "izquierda" o "derecha"
                            }
                        ],
                        "category_restricted": false,         // Restricciones de categoría
                        "category_restriction_type": "NONE",  // Tipo de restricción
                        "organizer_category": "5ta",          // Categoría del organizador
                        "is_mixed_match": true,               // Es partido mixto
                        "free_category": "7ma"                // Categoría libre para partidos mixtos
                    }
                ],
                "total_available": 1
            }
        ],
        "total_clubs": 1,
        "total_available_turns": 1
    }

    FRONTEND USAGE:
    - Si status = "AVAILABLE": Turno sin jugadores, mostrar como disponible
    - Si status = "PENDING": Turno con jugadores, mostrar assigned_players en la cancha azul
    - Usar player_side y player_court_position para posicionar jugadores visualmente
    - Si is_mixed_match = true: Mostrar badge "Mixto" y free_category en la UI
    - Si show_only_mixed_matches = true: Filtrar solo turnos con is_mixed_match = true
    """
    # Obtener todos los clubs
    clubs = club_crud.get_clubs(db)

    # Si se solicita solo clubs favoritos, filtrar
    if favorites_only:
        favorite_club_ids = favorite_crud.get_user_favorite_club_ids(
            db, current_user.id
        )
        clubs = [club for club in clubs if club.id in favorite_club_ids]

    result = {
        "date": target_date.isoformat(),
        "clubs": [],
        "total_clubs": 0,
        "total_available_turns": 0,
        "favorites_only": favorites_only,
    }

    # Obtener rangos de tiempo ocupados por las reservas activas del usuario para esta fecha
    # Esto filtra turnos que se solapan con reservas existentes (considerando que los partidos duran 1.5 horas)
    user_reservations_ranges = get_user_active_reservations_time_ranges(
        db, current_user.id, target_date
    )

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

        # Crear diccionario de turnos por cancha y horario
        # CRÍTICO: Solo considerar turnos activos (PENDING o READY_TO_PLAY), excluir cancelados
        existing_turns_by_court_and_time = {}
        for pregame_turn in existing_pregame_turns:
            # Solo considerar turnos que NO están cancelados
            if pregame_turn.status not in [
                PregameTurnStatus.CANCELLED,
                PregameTurnStatus.COMPLETED,
            ]:
                key = f"{pregame_turn.court_id}_{pregame_turn.start_time}"
                existing_turns_by_court_and_time[key] = pregame_turn

        # Filtrar turnos disponibles
        turns_data = club_turns[0].turns_data
        available_turns = []

        for turn in turns_data["turns"]:
            # Filtrar por horario si se especifica
            if start_time and turn["start_time"] != start_time:
                continue

            turn_start_time = turn["start_time"]
            turn_end_time = turn.get("end_time", "")

            # Si no hay end_time en el template, calcularlo (start_time + 1.5 horas)
            if not turn_end_time:
                start_minutes = parse_time_to_minutes(turn_start_time)
                if start_minutes != -1:
                    end_minutes = start_minutes + 90  # 1.5 horas = 90 minutos
                    if end_minutes >= 1440:
                        end_minutes = 1439
                    turn_end_time = minutes_to_time_string(end_minutes)
                else:
                    turn_end_time = ""  # Si no se puede parsear, usar string vacío

            # CRÍTICO: Filtrar turnos que se solapan con reservas activas del usuario
            # Si el usuario ya tiene un turno a las 9 PM, no puede ver turnos entre 9 PM y 10:30 PM
            if user_reservations_ranges and turn_end_time:
                if does_turn_overlap_with_reservations(
                    turn_start_time, turn_end_time, user_reservations_ranges
                ):
                    continue  # Saltar este turno porque se solapa con una reserva existente

            # Para cada cancha del club, crear un turno separado
            for court in club.courts:
                if not court.is_available:
                    continue  # Skip unavailable courts

                key = f"{court.id}_{turn_start_time}"

                # Si ya existe un pregame_turn para esta cancha y horario específico
                if key in existing_turns_by_court_and_time:
                    existing_turn = existing_turns_by_court_and_time[key]

                    # Solo mostrar si NO está completo (no es READY_TO_PLAY)
                    if existing_turn.status != "READY_TO_PLAY":
                        # Contar jugadores actuales
                        players_count = sum(
                            [
                                1
                                for player_id in [
                                    existing_turn.player1_id,
                                    existing_turn.player2_id,
                                    existing_turn.player3_id,
                                    existing_turn.player4_id,
                                ]
                                if player_id is not None
                            ]
                        )

                        # Crear lista de jugadores asignados con sus posiciones y nombres
                        assigned_players = []

                        if existing_turn.player1_id:
                            player1 = existing_turn.player1
                            assigned_players.append(
                                {
                                    "player_id": existing_turn.player1_id,
                                    "player_name": (
                                        player1.name.split()[0]
                                        if player1.name
                                        else "Unknown"
                                    ),
                                    "player_last_name": (
                                        " ".join(player1.name.split()[1:])
                                        if player1.name
                                        and len(player1.name.split()) > 1
                                        else ""
                                    ),
                                    "player_side": existing_turn.player1_side,
                                    "player_court_position": existing_turn.player1_court_position,
                                    "position": "player1",
                                }
                            )

                        if existing_turn.player2_id:
                            player2 = existing_turn.player2
                            assigned_players.append(
                                {
                                    "player_id": existing_turn.player2_id,
                                    "player_name": (
                                        player2.name.split()[0]
                                        if player2.name
                                        else "Unknown"
                                    ),
                                    "player_last_name": (
                                        " ".join(player2.name.split()[1:])
                                        if player2.name
                                        and len(player2.name.split()) > 1
                                        else ""
                                    ),
                                    "player_side": existing_turn.player2_side,
                                    "player_court_position": existing_turn.player2_court_position,
                                    "position": "player2",
                                }
                            )

                        if existing_turn.player3_id:
                            player3 = existing_turn.player3
                            assigned_players.append(
                                {
                                    "player_id": existing_turn.player3_id,
                                    "player_name": (
                                        player3.name.split()[0]
                                        if player3.name
                                        else "Unknown"
                                    ),
                                    "player_last_name": (
                                        " ".join(player3.name.split()[1:])
                                        if player3.name
                                        and len(player3.name.split()) > 1
                                        else ""
                                    ),
                                    "player_side": existing_turn.player3_side,
                                    "player_court_position": existing_turn.player3_court_position,
                                    "position": "player3",
                                }
                            )

                        if existing_turn.player4_id:
                            player4 = existing_turn.player4
                            assigned_players.append(
                                {
                                    "player_id": existing_turn.player4_id,
                                    "player_name": (
                                        player4.name.split()[0]
                                        if player4.name
                                        else "Unknown"
                                    ),
                                    "player_last_name": (
                                        " ".join(player4.name.split()[1:])
                                        if player4.name
                                        and len(player4.name.split()) > 1
                                        else ""
                                    ),
                                    "player_side": existing_turn.player4_side,
                                    "player_court_position": existing_turn.player4_court_position,
                                    "position": "player4",
                                }
                            )

                        available_turns.append(
                            {
                                "turn_id": existing_turn.id,
                                "court_id": court.id,
                                "court_name": court.name,
                                "is_indoor": court.is_indoor,
                                "has_lighting": court.has_lighting,
                                "start_time": turn["start_time"],
                                "end_time": turn["end_time"],
                                "price": turn["price"],
                                "status": "PENDING",  # Ya tiene jugadores
                                "players_count": players_count,
                                "players_needed": 4 - players_count,
                                "assigned_players": assigned_players,
                                "category_restricted": existing_turn.category_restricted
                                == "true",
                                "category_restriction_type": existing_turn.category_restriction_type,
                                "organizer_category": existing_turn.organizer_category,
                                # Campos para partidos mixtos
                                "is_mixed_match": (
                                    existing_turn.is_mixed_match == "true"
                                    if existing_turn.is_mixed_match
                                    else False
                                ),
                                "free_category": existing_turn.free_category,
                            }
                        )
                else:
                    # Turno completamente disponible (sin jugadores) para esta cancha específica
                    available_turns.append(
                        {
                            "turn_id": None,  # No existe aún el pregame_turn
                            "court_id": court.id,
                            "court_name": court.name,
                            "is_indoor": court.is_indoor,
                            "has_lighting": court.has_lighting,
                            "start_time": turn["start_time"],
                            "end_time": turn["end_time"],
                            "price": turn["price"],
                            "status": "AVAILABLE",  # Sin jugadores
                            "players_count": 0,
                            "players_needed": 4,
                            "assigned_players": [],
                            "category_restricted": False,  # Por defecto sin restricciones
                            "category_restriction_type": "NONE",
                            "organizer_category": None,  # No hay organizador aún
                            # Campos para partidos mixtos (por defecto false para turnos nuevos)
                            "is_mixed_match": False,
                            "free_category": None,
                        }
                    )

        # Aplicar filtro de partidos mixtos si se solicita
        if show_only_mixed_matches:
            available_turns = [
                turn for turn in available_turns if turn.get("is_mixed_match", False)
            ]

        # Aplicar filtro de solo turnos completamente disponibles (sin jugadores)
        # Esto es para el flujo de reservas, donde solo se deben mostrar canchas libres
        if show_only_available:
            available_turns = [
                turn
                for turn in available_turns
                if turn.get("status") == "AVAILABLE"
                and turn.get("players_count", 0) == 0
            ]

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


@router.get("/available-times-by-club")
def get_available_times_by_club(
    club_id: int = Query(..., description="Club ID"),
    target_date: date = Query(..., description="Target date (YYYY-MM-DD)"),
    show_only_mixed_matches: Optional[bool] = Query(
        None, description="Filter only mixed matches"
    ),
    show_only_available: Optional[bool] = Query(
        False,
        description="Show only completely available courts (0 players, status AVAILABLE). Excludes courts with existing players.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene horarios disponibles para un club específico en una fecha determinada.
    Incluye información detallada de canchas disponibles para cada horario.

    PARÁMETROS:
    - club_id: ID del club (requerido)
    - target_date: Fecha objetivo (YYYY-MM-DD) (requerido)
    - show_only_mixed_matches: Filtrar solo partidos mixtos (opcional)

    RESPONSE FORMAT:
    {
        "success": true,
        "times": [
            {
                "start_time": "08:00",
                "end_time": "09:30",
                "price": 12000,
                "available_courts": [
                    {
                        "court_id": 5,
                        "court_name": "Cancha 1",
                        "is_indoor": true,
                        "has_lighting": true,
                        "turn_id": null,
                        "players_count": 0,
                        "status": "AVAILABLE"
                    }
                ]
            }
        ],
        "club_id": 2,
        "target_date": "2025-01-27",
        "show_only_mixed_matches": true,
        "total_available_times": 1
    }
    """
    # Verificar que el club existe
    club = club_crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    # Obtener el template de turnos del club
    club_turns = turn_crud.get_turns(db, club_id=club_id)
    if not club_turns:
        raise HTTPException(
            status_code=404, detail="No turns template found for this club"
        )

    # Obtener turnos ya reservados para esa fecha
    existing_pregame_turns = crud.get_pregame_turns(
        db,
        turn_id=club_turns[0].id,
        date=datetime.combine(target_date, datetime.min.time()),
    )

    # Crear diccionario de turnos por cancha y horario
    # CRÍTICO: Solo considerar turnos activos (PENDING o READY_TO_PLAY), excluir cancelados
    existing_turns_by_court_and_time = {}
    for pregame_turn in existing_pregame_turns:
        # Solo considerar turnos que NO están cancelados
        if pregame_turn.status not in [
            PregameTurnStatus.CANCELLED,
            PregameTurnStatus.COMPLETED,
        ]:
            key = f"{pregame_turn.court_id}_{pregame_turn.start_time}"
            existing_turns_by_court_and_time[key] = pregame_turn

    # Obtener rangos de tiempo ocupados por las reservas activas del usuario para esta fecha
    # Esto filtra horarios que se solapan con reservas existentes (considerando que los partidos duran 1.5 horas)
    user_reservations_ranges = get_user_active_reservations_time_ranges(
        db, current_user.id, target_date
    )

    # Obtener horarios del template del club
    turns_data = club_turns[0].turns_data
    time_slots = []

    for turn in turns_data["turns"]:
        turn_start_time = turn["start_time"]
        turn_end_time = turn.get("end_time", "")
        turn_price = turn["price"]

        # Si no hay end_time en el template, calcularlo (start_time + 1.5 horas)
        if not turn_end_time:
            start_minutes = parse_time_to_minutes(turn_start_time)
            if start_minutes != -1:
                end_minutes = start_minutes + 90  # 1.5 horas = 90 minutos
                if end_minutes >= 1440:
                    end_minutes = 1439
                turn_end_time = minutes_to_time_string(end_minutes)

        # CRÍTICO: Filtrar horarios que se solapan con reservas activas del usuario
        # Si el usuario ya tiene un turno a las 9 PM, no puede ver horarios entre 9 PM y 10:30 PM
        if user_reservations_ranges and turn_end_time:
            if does_turn_overlap_with_reservations(
                turn_start_time, turn_end_time, user_reservations_ranges
            ):
                continue  # Saltar este horario porque se solapa con una reserva existente

        available_courts = []

        # Para cada cancha del club, verificar disponibilidad
        for court in club.courts:
            if not court.is_available:
                continue  # Skip unavailable courts

            key = f"{court.id}_{turn_start_time}"

            # Determinar el estado de la cancha
            court_info = {
                "court_id": court.id,
                "court_name": court.name,
                "is_indoor": court.is_indoor,
                "has_lighting": court.has_lighting,
                "turn_id": None,
                "players_count": 0,
                "status": "AVAILABLE",
            }

            # Si ya existe un pregame_turn para esta cancha y horario específico
            if key in existing_turns_by_court_and_time:
                existing_turn = existing_turns_by_court_and_time[key]

                # Aplicar filtro de partidos mixtos si se especifica
                if show_only_mixed_matches is not None:
                    is_mixed = (
                        existing_turn.is_mixed_match == "true"
                        if existing_turn.is_mixed_match
                        else False
                    )
                    if show_only_mixed_matches != is_mixed:
                        continue

                # Actualizar información del turno existente
                court_info["turn_id"] = existing_turn.id
                court_info["players_count"] = count_players_in_turn(existing_turn)

                # Determinar estado basado en número de jugadores
                if existing_turn.status == "READY_TO_PLAY":
                    court_info["status"] = "FULL"
                elif court_info["players_count"] > 0:
                    court_info["status"] = "PENDING"
                else:
                    court_info["status"] = "AVAILABLE"
            else:
                # Turno completamente disponible (sin jugadores)
                # Aplicar filtro de partidos mixtos si se especifica
                if show_only_mixed_matches is not None:
                    # Para turnos nuevos, is_mixed_match es False por defecto
                    if show_only_mixed_matches != False:
                        continue

            # Aplicar filtro de solo turnos completamente disponibles si se solicita
            # Esto es para el flujo de reservas, donde solo se deben mostrar canchas libres
            if show_only_available:
                # Solo incluir canchas completamente disponibles (sin jugadores)
                if (
                    court_info["status"] == "AVAILABLE"
                    and court_info["players_count"] == 0
                ):
                    available_courts.append(court_info)
            else:
                # Incluir canchas disponibles o con espacio (comportamiento normal)
                if court_info["status"] in ["AVAILABLE", "PENDING"]:
                    available_courts.append(court_info)

        # Solo incluir horarios que tengan al menos una cancha disponible
        if available_courts:
            time_slots.append(
                {
                    "start_time": turn_start_time,
                    "end_time": turn_end_time,
                    "price": turn_price,
                    "available_courts": available_courts,
                }
            )

    # Ordenar por hora de inicio
    time_slots.sort(key=lambda x: x["start_time"])

    return {
        "success": True,
        "times": time_slots,
        "club_id": club_id,
        "target_date": target_date.isoformat(),
        "show_only_mixed_matches": show_only_mixed_matches,
        "total_available_times": len(time_slots),
    }


@router.get("/wall")
def get_turn_wall(
    target_date: Optional[date] = Query(
        None,
        description="Fecha desde la cual listar (YYYY-MM-DD). Por defecto hoy.",
    ),
    days_ahead: int = Query(
        14,
        ge=1,
        le=60,
        description="Días hacia adelante desde target_date para incluir turnos.",
    ),
    club_id: Optional[int] = Query(None, description="Filtrar por ID de club."),
    city: Optional[str] = Query(None, description="Filtrar por ciudad (busca en dirección del club)."),
    category: Optional[str] = Query(None, description="Filtrar por categoría (organizador o libre)."),
    is_mixed_match: Optional[bool] = Query(None, description="Filtrar por partido mixto (true/false)."),
    sort_by: str = Query(
        "soonest",
        description="Orden: 'soonest' = más pronto primero, 'furthest' = más lejano primero.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Muro general de turnos incompletos (1, 2 o 3 jugadores) para que cualquier usuario pueda sumarse.
    Filtros: club, ciudad, categoría, mixto. Orden: más pronto o más lejano.
    Excluye turnos donde el usuario actual ya está inscripto.
    """
    from sqlalchemy import or_, not_
    from app.models.court import Court
    from app.models.club import Club

    if current_user.is_admin or current_user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail="Solo jugadores pueden ver el muro de turnos",
        )

    start_date = target_date or date.today()
    end_date = start_date + timedelta(days=days_ahead)

    # Solo turnos que el organizador publicó en el muro (como un post); invitaciones directas no aparecen
    query = (
        db.query(PregameTurn)
        .join(Court, PregameTurn.court_id == Court.id)
        .join(Club, Court.club_id == Club.id)
        .filter(PregameTurn.status == PregameTurnStatus.PENDING)
        .filter(PregameTurn.published_to_wall == "true")
        .filter(not_(PregameTurn.player1_id.is_(None)))
        .filter(
            or_(
                PregameTurn.player2_id.is_(None),
                PregameTurn.player3_id.is_(None),
                PregameTurn.player4_id.is_(None),
            )
        )
        .filter(PregameTurn.date >= datetime.combine(start_date, datetime.min.time()))
        .filter(
            PregameTurn.date
            < datetime.combine(end_date, datetime.min.time()) + timedelta(days=1)
        )
    )
    if club_id is not None:
        query = query.filter(Club.id == club_id)
    if city and city.strip():
        query = query.filter(Club.address.ilike(f"%{city.strip()}%"))
    if category and category.strip():
        cat = category.strip()
        query = query.filter(
            or_(
                PregameTurn.organizer_category == cat,
                PregameTurn.free_category == cat,
            )
        )
    if is_mixed_match is not None:
        query = query.filter(
            PregameTurn.is_mixed_match == ("true" if is_mixed_match else "false")
        )
    if sort_by == "furthest":
        query = query.order_by(PregameTurn.date.desc(), PregameTurn.start_time.desc())
    else:
        query = query.order_by(PregameTurn.date.asc(), PregameTurn.start_time.asc())

    turns = query.all()

    # Excluir turnos donde el usuario ya está
    wall_items = []
    for turn in turns:
        if turn.player1_id == current_user.id or turn.player2_id == current_user.id or turn.player3_id == current_user.id or turn.player4_id == current_user.id:
            continue
        players_count = count_players_in_turn(turn)
        if players_count >= 4:
            continue
        club_name = "Club"
        court_name = "Cancha"
        cid = None
        club_address = ""
        if turn.court:
            court_name = turn.court.name or court_name
            if turn.court.club:
                club_name = turn.court.club.name or club_name
                cid = turn.court.club.id
                club_address = turn.court.club.address or ""
        wall_items.append(
            _wall_item_from_turn(turn, players_count, club_name, court_name, cid, club_address)
        )

    # Turnos del usuario publicados por él en el muro (incompletos) — "Mis turnos en el muro"
    my_turns_query = (
        db.query(PregameTurn)
        .filter(PregameTurn.status == PregameTurnStatus.PENDING)
        .filter(PregameTurn.player1_id == current_user.id)
        .filter(PregameTurn.published_to_wall == "true")
        .filter(
            or_(
                PregameTurn.player2_id.is_(None),
                PregameTurn.player3_id.is_(None),
                PregameTurn.player4_id.is_(None),
            )
        )
        .filter(PregameTurn.date >= datetime.combine(start_date, datetime.min.time()))
        .filter(
            PregameTurn.date
            < datetime.combine(end_date, datetime.min.time()) + timedelta(days=1)
        )
    )
    my_turns = my_turns_query.order_by(PregameTurn.date, PregameTurn.start_time).all()
    my_wall_items = []
    for turn in my_turns:
        players_count = count_players_in_turn(turn)
        if players_count >= 4:
            continue
        club_name = "Club"
        court_name = "Cancha"
        cid = None
        club_address = ""
        if turn.court:
            court_name = turn.court.name or court_name
            if turn.court.club:
                club_name = turn.court.club.name or club_name
                cid = turn.court.club.id
                club_address = turn.court.club.address or ""
        my_wall_items.append(
            _wall_item_from_turn(turn, players_count, club_name, court_name, cid, club_address)
        )

    return {
        "success": True,
        "data": {
            "items": wall_items,
            "my_turns": my_wall_items,
            "total": len(wall_items),
            "from_date": start_date.isoformat(),
            "to_date": end_date.isoformat(),
        },
    }


def _wall_item_from_turn(turn, players_count, club_name, court_name, club_id, club_address=""):
    """Construye un ítem del muro a partir de un PregameTurn. Incluye assigned_players para el visor de posiciones."""
    assigned_players = []
    for i in range(1, 5):
        player_id = getattr(turn, f"player{i}_id", None)
        if not player_id:
            continue
        player = getattr(turn, f"player{i}", None)
        player_side = getattr(turn, f"player{i}_side", None)
        player_court_position = getattr(turn, f"player{i}_court_position", None)
        entry = {
            "player_id": player_id,
            "position": f"player{i}",
            "player_side": player_side,
            "player_court_position": player_court_position,
        }
        if player:
            entry["player_name"] = player.name.split()[0] if player.name else "Jugador"
            entry["player_last_name"] = (
                " ".join(player.name.split()[1:])
                if player.name and len(player.name.split()) > 1
                else ""
            )
        else:
            entry["player_name"] = "Jugador"
            entry["player_last_name"] = ""
        assigned_players.append(entry)

    return {
        "pregame_turn_id": turn.id,
        "club_id": club_id,
        "club_name": club_name,
        "club_address": club_address or "",
        "court_id": turn.court_id,
        "court_name": court_name,
        "date": turn.date.strftime("%Y-%m-%d") if turn.date else None,
        "start_time": turn.start_time,
        "end_time": turn.end_time,
        "price": turn.price,
        "players_count": players_count,
        "players_needed": 4 - players_count,
        "is_mixed_match": turn.is_mixed_match == "true" if turn.is_mixed_match else False,
        "free_category": turn.free_category,
        "category_restricted": turn.category_restricted == "true",
        "category_restriction_type": turn.category_restriction_type or "NONE",
        "organizer_category": turn.organizer_category,
        "is_indoor": turn.court.is_indoor if turn.court else False,
        "has_lighting": turn.court.has_lighting if turn.court else False,
        "assigned_players": assigned_players,
    }


def _process_incomplete_turn_reminders(db: Session, user_id: int) -> None:
    """
    Si el usuario es organizador de turnos vacíos (solo player1) creados hace más de 30 min,
    envía push de recordatorio y marca incomplete_reminder_sent_at.
    """
    import logging
    logger = logging.getLogger(__name__)
    reminder_delay_minutes = 30
    cutoff = datetime.utcnow() - timedelta(minutes=reminder_delay_minutes)
    try:
        incomplete_turns = (
            db.query(PregameTurn)
            .filter(
                PregameTurn.player1_id == user_id,
                PregameTurn.player2_id.is_(None),
                PregameTurn.player3_id.is_(None),
                PregameTurn.player4_id.is_(None),
                PregameTurn.status == PregameTurnStatus.PENDING,
                PregameTurn.created_at < cutoff,
                PregameTurn.incomplete_reminder_sent_at.is_(None),
            )
            .all()
        )
        for turn in incomplete_turns:
            club_name = "Club"
            if turn.court and turn.court.club:
                club_name = turn.court.club.name
            try:
                from app.utils.notification_utils import notify_turn_incomplete_reminder
                notify_turn_incomplete_reminder(db=db, turn=turn, club_name=club_name)
                turn.incomplete_reminder_sent_at = datetime.utcnow()
                db.commit()
            except Exception as e:
                logger.error(
                    "Error enviando recordatorio turno incompleto turn_id=%s: %s",
                    turn.id,
                    e,
                )
                db.rollback()
    except Exception as e:
        logger.error("Error en _process_incomplete_turn_reminders: %s", e)


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

    # Recordatorio: si el organizador tiene turnos vacíos (solo él) desde hace > 30 min, enviar push
    _process_incomplete_turn_reminders(db, current_user.id)

    # Buscar todos los pregame_turns donde el jugador esté asignado
    # CRÍTICO: Solo incluir turnos activos (PENDING y READY_TO_PLAY)
    # Los turnos cancelados NO deben aparecer en "Mis próximos partidos"
    # Deben moverse al historial o sección de cancelados
    query = (
        db.query(PregameTurn)
        .filter(
            (PregameTurn.player1_id == current_user.id)
            | (PregameTurn.player2_id == current_user.id)
            | (PregameTurn.player3_id == current_user.id)
            | (PregameTurn.player4_id == current_user.id)
        )
        .filter(
            # Solo incluir turnos activos, excluir cancelados y completados
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

        # Determinar posición del jugador y obtener sus datos de posición
        player_position = None
        player_side = None
        player_court_position = None

        if reservation.player1_id == current_user.id:
            player_position = "player1"
            player_side = reservation.player1_side
            player_court_position = reservation.player1_court_position
        elif reservation.player2_id == current_user.id:
            player_position = "player2"
            player_side = reservation.player2_side
            player_court_position = reservation.player2_court_position
        elif reservation.player3_id == current_user.id:
            player_position = "player3"
            player_side = reservation.player3_side
            player_court_position = reservation.player3_court_position
        elif reservation.player4_id == current_user.id:
            player_position = "player4"
            player_side = reservation.player4_side
            player_court_position = reservation.player4_court_position

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

        # Contar invitaciones pendientes para este turno
        from app.crud import invitation as invitation_crud

        pending_invitations = invitation_crud.get_pending_invitations_by_turn(
            db, reservation.id
        )
        pending_invitations_count = len(pending_invitations)

        # Crear lista de otros jugadores (excluyendo al usuario actual)
        other_players = []

        if reservation.player1_id and reservation.player1_id != current_user.id:
            player1 = reservation.player1
            other_players.append(
                {
                    "player_id": reservation.player1_id,
                    "player_name": (
                        player1.name.split()[0] if player1.name else "Unknown"
                    ),
                    "player_last_name": (
                        " ".join(player1.name.split()[1:])
                        if player1.name and len(player1.name.split()) > 1
                        else ""
                    ),
                    "player_side": reservation.player1_side,
                    "player_court_position": reservation.player1_court_position,
                    "position": "player1",
                }
            )

        if reservation.player2_id and reservation.player2_id != current_user.id:
            player2 = reservation.player2
            other_players.append(
                {
                    "player_id": reservation.player2_id,
                    "player_name": (
                        player2.name.split()[0] if player2.name else "Unknown"
                    ),
                    "player_last_name": (
                        " ".join(player2.name.split()[1:])
                        if player2.name and len(player2.name.split()) > 1
                        else ""
                    ),
                    "player_side": reservation.player2_side,
                    "player_court_position": reservation.player2_court_position,
                    "position": "player2",
                }
            )

        if reservation.player3_id and reservation.player3_id != current_user.id:
            player3 = reservation.player3
            other_players.append(
                {
                    "player_id": reservation.player3_id,
                    "player_name": (
                        player3.name.split()[0] if player3.name else "Unknown"
                    ),
                    "player_last_name": (
                        " ".join(player3.name.split()[1:])
                        if player3.name and len(player3.name.split()) > 1
                        else ""
                    ),
                    "player_side": reservation.player3_side,
                    "player_court_position": reservation.player3_court_position,
                    "position": "player3",
                }
            )

        if reservation.player4_id and reservation.player4_id != current_user.id:
            player4 = reservation.player4
            other_players.append(
                {
                    "player_id": reservation.player4_id,
                    "player_name": (
                        player4.name.split()[0] if player4.name else "Unknown"
                    ),
                    "player_last_name": (
                        " ".join(player4.name.split()[1:])
                        if player4.name and len(player4.name.split()) > 1
                        else ""
                    ),
                    "player_side": reservation.player4_side,
                    "player_court_position": reservation.player4_court_position,
                    "position": "player4",
                }
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
            "player_side": player_side,
            "player_court_position": player_court_position,
            "players_count": players_count,
            "players_needed": max(0, 4 - players_count - pending_invitations_count),
            "other_players": other_players,  # Nuevo campo
            "created_at": reservation.created_at,
            "updated_at": reservation.updated_at,
            # Campos para partidos mixtos
            "is_mixed_match": (
                reservation.is_mixed_match == "true"
                if reservation.is_mixed_match
                else False
            ),
            "free_category": reservation.free_category,
            "category_restricted": (
                reservation.category_restricted == "true"
                if reservation.category_restricted
                else False
            ),
            "category_restriction_type": reservation.category_restriction_type,
            "organizer_category": reservation.organizer_category,
            "cancellation_message": reservation.cancellation_message,  # Mensaje de justificación si un jugador se retiró
            "has_unread_chat": turn_chat_crud.has_unread_chat(db, current_user.id, reservation.id)
            if (players_count >= 2)
            else False,
        }

        # Separar por estado
        # CRÍTICO: Los turnos cancelados ya no deberían llegar aquí porque fueron filtrados
        # pero por seguridad, solo agregar turnos activos
        if reservation.status == PregameTurnStatus.PENDING:
            pending_turns.append(formatted_reservation)
        elif reservation.status == PregameTurnStatus.READY_TO_PLAY:
            ready_turns.append(formatted_reservation)
        # Los turnos cancelados NO se incluyen en "Mis próximos partidos"

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


@router.get("/user/{user_id}/reservations")
def get_user_reservations(
    user_id: int,
    target_date: Optional[date] = Query(
        None, description="Filter by date (YYYY-MM-DD)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtener reservas de un usuario específico.

    Solo disponible para super admins.
    """
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="Only super admins can view user reservations"
        )

    # Buscar todos los pregame_turns donde el usuario esté asignado
    from datetime import timedelta

    seven_days_ago = datetime.now() - timedelta(days=7)

    query = db.query(PregameTurn).filter(
        (PregameTurn.player1_id == user_id)
        | (PregameTurn.player2_id == user_id)
        | (PregameTurn.player3_id == user_id)
        | (PregameTurn.player4_id == user_id)
    )

    # Aplicar filtro de fecha si se especifica
    if target_date:
        query = query.filter(
            PregameTurn.date == datetime.combine(target_date, datetime.min.time())
        )

    # Ordenar por fecha y hora (más recientes primero)
    reservations = query.order_by(
        PregameTurn.date.desc(), PregameTurn.start_time.desc()
    ).all()

    # Formatear las reservas
    formatted_reservations = []
    for reservation in reservations:
        # Obtener información del club
        club = (
            club_crud.get_club(db, reservation.turn.club_id)
            if reservation.turn
            else None
        )

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
            "date": reservation.date.isoformat() if reservation.date else None,
            "start_time": reservation.start_time,
            "status": reservation.status.value if reservation.status else None,
            "club_id": reservation.turn.club_id if reservation.turn else None,
            "club_name": club.name if club else None,
            "court_id": reservation.court_id,
            "court_name": reservation.court.name if reservation.court else None,
            "players_count": players_count,
            "is_mixed_match": reservation.is_mixed_match,
            "created_at": (
                reservation.created_at.isoformat() if reservation.created_at else None
            ),
            "updated_at": (
                reservation.updated_at.isoformat() if reservation.updated_at else None
            ),
            "cancellation_message": reservation.cancellation_message,
        }

        formatted_reservations.append(formatted_reservation)

    return {
        "user_id": user_id,
        "reservations": formatted_reservations,
        "total": len(formatted_reservations),
    }


@router.get("/all")
def get_all_reservations(
    skip: int = Query(0, description="Number of results to skip"),
    limit: int = Query(100, description="Maximum number of results to return"),
    club_id: Optional[int] = Query(None, description="Filter by club ID"),
    start_date: Optional[date] = Query(
        None, description="Filter by start date (YYYY-MM-DD)"
    ),
    end_date: Optional[date] = Query(
        None, description="Filter by end date (YYYY-MM-DD)"
    ),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtener todas las reservas (pregame_turns).

    Solo disponible para super admins.
    """
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="Only super admins can view all reservations"
        )

    # Construir query
    query = db.query(PregameTurn)

    # Filtrar por club
    if club_id:
        from app.models.court import Court

        query = query.join(Court).filter(Court.club_id == club_id)

    # Filtrar por rango de fechas
    if start_date:
        query = query.filter(PregameTurn.date >= start_date)
    if end_date:
        from datetime import timedelta

        query = query.filter(PregameTurn.date < end_date + timedelta(days=1))

    # Filtrar por status
    if status:
        try:
            turn_status = PregameTurnStatus(status)
            query = query.filter(PregameTurn.status == turn_status)
        except ValueError:
            pass  # Ignorar status inválido

    # Ordenar por fecha y hora (más recientes primero)
    reservations = (
        query.order_by(PregameTurn.date.desc(), PregameTurn.start_time.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    # Formatear las reservas
    formatted_reservations = []
    for reservation in reservations:
        # Obtener información del club
        club = None
        if reservation.court and reservation.court.club:
            club = reservation.court.club
        elif reservation.turn:
            club = club_crud.get_club(db, reservation.turn.club_id)

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
            "date": reservation.date.isoformat() if reservation.date else None,
            "start_time": reservation.start_time,
            "end_time": reservation.end_time,
            "status": reservation.status.value if reservation.status else None,
            "club_id": club.id if club else None,
            "club_name": club.name if club else None,
            "court_id": reservation.court_id,
            "court_name": reservation.court.name if reservation.court else None,
            "players_count": players_count,
            "is_mixed_match": (
                reservation.is_mixed_match == "true"
                if reservation.is_mixed_match
                else False
            ),
            "created_at": (
                reservation.created_at.isoformat() if reservation.created_at else None
            ),
            "updated_at": (
                reservation.updated_at.isoformat() if reservation.updated_at else None
            ),
            "cancellation_message": reservation.cancellation_message,
        }

        formatted_reservations.append(formatted_reservation)

    return {
        "reservations": formatted_reservations,
        "total": len(formatted_reservations),
        "skip": skip,
        "limit": limit,
    }


@router.post("/join-turn")
def join_turn(
    club_id: int = Query(..., description="Club ID"),
    start_time: str = Query(..., description="Start time in HH:MM format"),
    target_date: date = Query(..., description="Date to join (YYYY-MM-DD)"),
    court_id: int = Query(..., description="Court ID to join (required)"),
    player_side: Optional[str] = Query(
        None, description="Player side: 'reves' or 'drive'"
    ),
    player_position: Optional[str] = Query(
        None, description="Player court position: 'izquierda' or 'derecha'"
    ),
    category_restricted: Optional[bool] = Query(
        False, description="Enable category restrictions for this turn"
    ),
    category_restriction_type: Optional[str] = Query(
        "NONE",
        description="Type of category restriction: 'NONE', 'SAME_CATEGORY', 'NEARBY_CATEGORIES'",
    ),
    is_mixed_match: Optional[bool] = Query(
        False, description="Is this a mixed match (accepts players of both genders)"
    ),
    free_category: Optional[str] = Query(
        None,
        description="Free category for mixed matches (required for female organizers)",
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

    # CRÍTICO: Validar que el usuario no tenga ya una reserva activa en el mismo horario y fecha
    # Un jugador no puede estar en dos canchas al mismo tiempo
    existing_user_reservations = (
        db.query(PregameTurn)
        .filter(
            (
                (PregameTurn.player1_id == current_user.id)
                | (PregameTurn.player2_id == current_user.id)
                | (PregameTurn.player3_id == current_user.id)
                | (PregameTurn.player4_id == current_user.id)
            )
        )
        .filter(PregameTurn.date == target_date)
        .filter(PregameTurn.start_time == start_time)
        .filter(
            PregameTurn.status.in_(
                [PregameTurnStatus.PENDING, PregameTurnStatus.READY_TO_PLAY]
            )
        )
        .all()
    )

    if existing_user_reservations:
        # El usuario ya tiene una reserva activa en este horario
        existing_turn = existing_user_reservations[0]
        club_name = (
            existing_turn.court.club.name
            if existing_turn.court and existing_turn.court.club
            else "un club"
        )
        court_name = existing_turn.court.name if existing_turn.court else "una cancha"
        raise HTTPException(
            status_code=400,
            detail=f"Ya tenés una reserva activa en este horario ({start_time}) en {court_name} de {club_name}. No podés estar en dos canchas al mismo tiempo.",
        )

    # CRÍTICO: Validar que la fecha y hora no sean en el pasado
    now = datetime.now()
    today = now.date()

    # Si la fecha es hoy, verificar que la hora no haya pasado
    if target_date == today:
        try:
            # Parsear la hora de inicio (formato HH:MM)
            time_parts = start_time.split(":")
            if len(time_parts) != 2:
                raise HTTPException(
                    status_code=400, detail="Invalid start_time format. Expected HH:MM"
                )

            turn_hour = int(time_parts[0])
            turn_minute = int(time_parts[1])

            # Crear datetime para el turno
            turn_datetime = datetime.combine(
                target_date,
                datetime.min.time().replace(hour=turn_hour, minute=turn_minute),
            )

            # Verificar que el turno no haya comenzado ya
            if turn_datetime <= now:
                raise HTTPException(
                    status_code=400,
                    detail="No se pueden reservar turnos que ya comenzaron. Por favor, selecciona un horario futuro.",
                )
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid start_time format. Expected HH:MM"
            )
    elif target_date < today:
        # La fecha es en el pasado
        raise HTTPException(
            status_code=400,
            detail="No se pueden reservar turnos en fechas pasadas. Por favor, selecciona una fecha futura.",
        )

    # Validar parámetros de partidos mixtos
    if is_mixed_match:
        # Verificar que el usuario tenga género asignado
        if not current_user.gender or current_user.gender not in [
            "Masculino",
            "Femenino",
        ]:
            raise HTTPException(
                status_code=400,
                detail="Completá tu género para crear un partido mixto.",
            )

        # Para mujeres, usar su categoría como free_category si no la envían (no bloquear)
        if current_user.gender == "Femenino" and not free_category:
            free_category = current_user.category
        # Para hombres, usar su categoría como free_category
        elif current_user.gender == "Masculino":
            free_category = current_user.category

        # En partidos mixtos, no se pueden activar restricciones de categoría
        category_restricted = False
        category_restriction_type = "NONE"

    # Validar parámetros de restricción de categoría
    if category_restricted and category_restriction_type == "NONE":
        raise HTTPException(
            status_code=400,
            detail="category_restriction_type cannot be 'NONE' when category_restricted is true",
        )

    if not CategoryRestrictionValidator.validate_restriction_type(
        category_restriction_type
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid category_restriction_type. Must be 'NONE', 'SAME_CATEGORY', or 'NEARBY_CATEGORIES'",
        )

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

    # CRÍTICO: BLOQUEO DE CONCURRENCIA
    # Usar bloqueo pesimista para prevenir condiciones de carrera
    # Esto asegura que solo un usuario pueda crear/actualizar el turno a la vez
    from sqlalchemy import and_, or_
    from sqlalchemy.exc import IntegrityError

    target_date_combined = datetime.combine(target_date, datetime.min.time())

    # CRÍTICO: Buscar turno existente con bloqueo de fila (SELECT FOR UPDATE)
    # Esto bloquea la fila hasta que la transacción se complete
    # Usar with_for_update(nowait=False) para esperar si otro usuario tiene el bloqueo
    existing_turn = (
        db.query(PregameTurn)
        .filter(
            and_(
                PregameTurn.turn_id == club_turns[0].id,
                PregameTurn.date == target_date_combined,
                PregameTurn.start_time == start_time,
                PregameTurn.court_id == court_id,
                PregameTurn.status.notin_(
                    [PregameTurnStatus.CANCELLED, PregameTurnStatus.COMPLETED]
                ),
            )
        )
        .with_for_update(
            nowait=False
        )  # BLOQUEO DE FILA - previene condiciones de carrera
        .first()
    )

    # Si no existe el turno (o está cancelado), intentar crearlo
    if not existing_turn:
        # Validar que la cancha existe y está disponible
        courts = club.courts
        if not courts:
            raise HTTPException(status_code=400, detail="Club has no courts available")

        court_exists = any(court.id == court_id for court in courts)
        if not court_exists:
            raise HTTPException(
                status_code=400, detail="Court not found or not available"
            )

        # CRÍTICO: Crear el turno con manejo de concurrencia
        # El constraint único en la BD previene duplicados a nivel de base de datos
        pregame_turn_data = PregameTurnCreate(
            turn_id=club_turns[0].id,
            court_id=court_id,
            selected_court_id=court_id,
            date=target_date_combined,
            start_time=turn_info["start_time"],
            end_time=turn_info["end_time"],
            price=turn_info["price"],
            status="PENDING",
            player1_id=current_user.id,
            player1_side=player_side,
            player1_court_position=player_position,
            category_restricted=category_restricted,
            category_restriction_type=CategoryRestrictionType(
                category_restriction_type
            ),
            organizer_category=current_user.category,
            is_mixed_match=is_mixed_match,
            free_category=free_category,
        )

        try:
            # Intentar crear el turno
            # Si otro usuario ya lo creó, el constraint único lanzará IntegrityError
            created_turn = crud.create_pregame_turn(db, pregame_turn_data, commit=True)

            # Notificar al administrador del club sobre el nuevo turno creado
            try:
                from app.utils.notification_utils import send_notification_with_fcm
                from app.models.user import User

                # Obtener información del club
                club_name = club.name if club else "Club"
                club_id = club.id if club else None

                if club_id:
                    # Buscar el administrador del club
                    club_admin = (
                        db.query(User)
                        .filter(User.club_id == club_id, User.is_admin == True)
                        .first()
                    )

                    if club_admin:
                        # Enviar notificación al admin del club
                        send_notification_with_fcm(
                            db=db,
                            user_id=club_admin.id,
                            title="Nuevo turno creado",
                            message=f"{current_user.name or 'Un jugador'} creó un turno de las {created_turn.start_time} en {club_name}",
                            notification_type="external_request",
                            data={
                                "turn_id": str(created_turn.id),
                                "club_name": club_name,
                                "club_id": str(club_id),
                                "start_time": created_turn.start_time,
                                "date": (
                                    created_turn.date.isoformat()
                                    if created_turn.date
                                    else None
                                ),
                                "organizer_id": str(current_user.id),
                                "organizer_name": current_user.name or "Un jugador",
                                "court_id": str(court_id),
                                "court_name": (
                                    created_turn.court.name
                                    if created_turn.court
                                    else None
                                ),
                            },
                        )
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.info(
                            f"Notificación de nuevo turno enviada al admin del club {club_id}"
                        )
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Error enviando notificación al admin del club: {e}")

            # Si llegamos aquí, el turno se creó exitosamente
            # Devolver pregame_turn como dict para evitar serializar el ORM (lazy loading puede colgar la respuesta)
            return {
                "success": True,
                "message": "Turn created and joined successfully",
                "turn_id": created_turn.id,
                "data": {
                    "turn_id": created_turn.id,
                    "is_mixed_match": is_mixed_match,
                    "free_category": free_category,
                    "category_restricted": category_restricted,
                    "category_restriction_type": category_restriction_type,
                    "organizer_category": current_user.category,
                },
                "pregame_turn": {"id": created_turn.id},
                "players_count": 1,
                "players_needed": 3,
            }

        except IntegrityError as e:
            # Violación del constraint único: otro usuario ya creó el turno
            db.rollback()

            # Buscar el turno que fue creado por el otro usuario
            conflict_turn = (
                db.query(PregameTurn)
                .filter(
                    and_(
                        PregameTurn.turn_id == club_turns[0].id,
                        PregameTurn.date == target_date_combined,
                        PregameTurn.start_time == start_time,
                        PregameTurn.court_id == court_id,
                        PregameTurn.status.notin_(
                            [
                                PregameTurnStatus.CANCELLED,
                                PregameTurnStatus.COMPLETED,
                            ]
                        ),
                    )
                )
                .with_for_update(nowait=False)
                .first()
            )

            if conflict_turn:
                # Otro usuario creó el turno, continuar con la lógica de unirse
                existing_turn = conflict_turn
            else:
                # No se encontró el turno (caso raro), rechazar la reserva
                raise HTTPException(
                    status_code=400,
                    detail="El turno ya no está disponible. Por favor, intentá con otro horario.",
                )
        except Exception as e:
            # Otro tipo de error
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error al crear el turno: {str(e)}",
            )

    # CRÍTICO: Validar nuevamente el estado del turno justo antes de actualizar
    # Refrescar el turno con bloqueo para obtener el estado más reciente
    # Esto asegura que ningún otro usuario pueda modificar el turno mientras lo estamos procesando
    db.refresh(existing_turn)

    # CRÍTICO: Re-bloquear el turno después del refresh para asegurar consistencia
    # Esto previene que otro usuario modifique el turno entre el refresh y la actualización
    locked_turn = (
        db.query(PregameTurn)
        .filter(PregameTurn.id == existing_turn.id)
        .with_for_update(nowait=False)
        .first()
    )

    if not locked_turn:
        raise HTTPException(
            status_code=404,
            detail="El turno ya no existe o fue cancelado.",
        )

    existing_turn = locked_turn

    # Si existe el turno, verificar que no esté completo
    if existing_turn.status == PregameTurnStatus.READY_TO_PLAY:
        raise HTTPException(
            status_code=400,
            detail="Turno no disponible",
        )
    
    # CRÍTICO: Verificar también las reservas activas para este turno
    # Esto previene que un usuario se una cuando ya hay reservas que ocupan el espacio
    # IMPORTANTE: No se puede usar .count() con .with_for_update() en PostgreSQL
    # Primero obtenemos las reservas con bloqueo, luego contamos en Python
    active_bookings = (
        db.query(Booking)
        .filter(
            and_(
                Booking.pregame_turn_id == existing_turn.id,
                Booking.status.in_([
                    BookingStatus.PENDING,
                    BookingStatus.CONFIRMED
                ])
            )
        )
        .with_for_update(nowait=False)  # Bloquear las reservas activas
        .all()
    )
    active_bookings_count = len(active_bookings)
    
    # Contar jugadores directamente asignados
    players_count = sum([
        1 for player_id in [
            existing_turn.player1_id,
            existing_turn.player2_id,
            existing_turn.player3_id,
            existing_turn.player4_id
        ] if player_id is not None
    ])
    
    total_participants = players_count + active_bookings_count
    
    if total_participants >= 4:
        raise HTTPException(
            status_code=400,
            detail="Turno no disponible",
        )

    # Verificar que el jugador no esté ya en el turno
    if (
        existing_turn.player1_id == current_user.id
        or existing_turn.player2_id == current_user.id
        or existing_turn.player3_id == current_user.id
        or existing_turn.player4_id == current_user.id
    ):
        raise HTTPException(
            status_code=400,
            detail="Ya estás en este turno.",
        )

    # CRÍTICO: Verificar si el jugador es externo (no fue invitado por el configurador)
    # Si es externo, crear una solicitud pendiente en lugar de unirse directamente
    from app.crud import invitation as invitation_crud

    is_organizer = existing_turn.player1_id == current_user.id
    is_validated = invitation_crud.is_player_validated(
        db, existing_turn.id, current_user.id
    )
    has_pending_invitation = invitation_crud.check_existing_invitation(
        db, existing_turn.id, current_user.id
    )

    # Si el jugador es externo (no es organizador, no está validado, no tiene invitación pendiente)
    if not is_organizer and not is_validated and not has_pending_invitation:
        # Crear solicitud externa pendiente de aprobación
        from app.schemas.invitation import InvitationCreate

        # Verificar que no haya ya una solicitud externa pendiente
        existing_external_request = (
            db.query(Invitation)
            .filter(
                and_(
                    Invitation.turn_id == existing_turn.id,
                    Invitation.invited_player_id == current_user.id,
                    Invitation.is_external_request == True,
                    Invitation.status == "PENDING",
                )
            )
            .first()
        )

        if existing_external_request:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="Ya tenés una solicitud pendiente para este turno. El configurador debe aprobarla antes de que puedas unirte.",
            )

        # Crear la solicitud externa
        # En una solicitud externa, el configurador es el "invitador" (quien debe aprobar)
        # y el jugador externo es el "invitado" (quien solicita unirse)
        external_request_data = InvitationCreate(
            turn_id=existing_turn.id,
            inviter_id=existing_turn.player1_id,  # El configurador debe aprobar
            invited_player_id=current_user.id,  # El jugador externo que solicita
            message=f"Solicitud para unirse al turno",
            is_external_request=True,  # Marcar como solicitud externa
        )

        external_invitation = invitation_crud.create_invitation(
            db, external_request_data
        )

        # Notificar al configurador sobre la solicitud
        try:
            from app.utils.notification_utils import send_notification_with_fcm
            from app.models.user import User

            organizer = (
                db.query(User).filter(User.id == existing_turn.player1_id).first()
            )
            if organizer:
                send_notification_with_fcm(
                    db=db,
                    user_id=organizer.id,
                    title="Nueva solicitud para unirse al turno",
                    message=f"{current_user.name or 'Un jugador'} quiere unirse al turno de las {existing_turn.start_time}",
                    notification_type="external_request",
                    data={
                        "turn_id": existing_turn.id,
                        "requesting_player_id": current_user.id,
                        "requesting_player_name": current_user.name or "Un jugador",
                        "invitation_id": external_invitation.id,
                        "club_name": (
                            existing_turn.court.club.name
                            if existing_turn.court and existing_turn.court.club
                            else "Club"
                        ),
                        "start_time": existing_turn.start_time,
                    },
                )
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error enviando notificación de solicitud externa: {e}")

        # Notificar también al administrador del club
        try:
            from app.utils.notification_utils import send_notification_with_fcm
            from app.models.user import User

            # Obtener información del club
            club_name = (
                existing_turn.court.club.name
                if existing_turn.court and existing_turn.court.club
                else "Club"
            )
            club_id = (
                existing_turn.court.club.id
                if existing_turn.court and existing_turn.court.club
                else None
            )

            if club_id:
                # Buscar el administrador del club
                club_admin = (
                    db.query(User)
                    .filter(User.club_id == club_id, User.is_admin == True)
                    .first()
                )

                if club_admin:
                    # Enviar notificación al admin del club
                    send_notification_with_fcm(
                        db=db,
                        user_id=club_admin.id,
                        title="Nueva solicitud para unirse al turno",
                        message=f"{current_user.name or 'Un jugador'} quiere unirse al turno de las {existing_turn.start_time} en {club_name}",
                        notification_type="external_request",
                        data={
                            "turn_id": str(existing_turn.id),
                            "club_name": club_name,
                            "club_id": str(club_id),
                            "start_time": existing_turn.start_time,
                            "date": (
                                existing_turn.date.isoformat()
                                if existing_turn.date
                                else None
                            ),
                            "requesting_player_id": str(current_user.id),
                            "requesting_player_name": current_user.name or "Un jugador",
                            "invitation_id": str(external_invitation.id),
                            "court_id": (
                                str(existing_turn.court_id)
                                if existing_turn.court_id
                                else None
                            ),
                            "court_name": (
                                existing_turn.court.name
                                if existing_turn.court
                                else None
                            ),
                        },
                    )
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.info(
                        f"Notificación de solicitud externa enviada al admin del club {club_id}"
                    )
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error enviando notificación al admin del club: {e}")

        # Hacer commit de la solicitud externa
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error al crear la solicitud: {str(e)}",
            )

        return {
            "success": True,
            "message": "Tu solicitud para unirte al turno ha sido enviada. El configurador debe aprobarla antes de que puedas unirte.",
            "requires_approval": True,
            "invitation_id": external_invitation.id,
        }

    # CRÍTICO: Verificar nuevamente que el turno no esté completo
    # Contar jugadores actuales para asegurar que hay espacio
    # Esta es la validación FINAL antes de asignar al jugador
    current_players_count = count_players_in_turn(existing_turn)
    if current_players_count >= 4:
        db.rollback()  # Liberar el lock y revertir cualquier cambio
        raise HTTPException(
            status_code=400,
            detail="El turno ya está completo. No hay lugares disponibles.",
        )

    # CRÍTICO: Validación final adicional - verificar que la posición específica no esté ocupada
    # si se proporcionó player_side y player_position
    if player_side and player_position:
        # Verificar si otro jugador ya ocupa esa combinación de lado y posición
        for pos_num in [1, 2, 3, 4]:
            pos_str = f"player{pos_num}"
            other_player_id = getattr(existing_turn, f"{pos_str}_id", None)
            if other_player_id is None:
                continue  # Esta posición está vacía

            other_side = getattr(existing_turn, f"{pos_str}_side", None)
            other_court_pos = getattr(existing_turn, f"{pos_str}_court_position", None)

            if other_side == player_side and other_court_pos == player_position:
                db.rollback()  # Liberar el lock y revertir cualquier cambio
                raise HTTPException(
                    status_code=400,
                    detail=f"Esta posición ({player_side}, {player_position}) ya está ocupada por otro jugador. Elegí otra.",
                )

    # CRÍTICO: Validar restricciones de categoría si el turno las tiene habilitadas
    # Verificar que category_restricted sea "true" (string) o True (boolean)
    is_category_restricted = (
        existing_turn.category_restricted == "true"
        or existing_turn.category_restricted is True
    )

    if (
        is_category_restricted
        and existing_turn.category_restriction_type
        and existing_turn.category_restriction_type != "NONE"
    ):
        # Usar organizer_category almacenado en lugar de consultar la BD
        if existing_turn.organizer_category:
            player_category = (
                current_user.category or "9na"
            )  # Default a 9na si no tiene categoría

            # Validar que la categoría del jugador cumpla con las restricciones
            can_join = CategoryRestrictionValidator.can_join_turn(
                player_category,
                existing_turn.organizer_category,
                existing_turn.category_restriction_type,
            )

            if not can_join:
                raise HTTPException(
                    status_code=403,
                    detail=f"No cumples con las restricciones de categoría para este turno. Tu categoría ({player_category}) no cumple con las restricciones (restricción: {existing_turn.category_restriction_type}, categoría del organizador: {existing_turn.organizer_category}).",
                )

    # Validar paridad de géneros para partidos mixtos
    if existing_turn.is_mixed_match == "true":
        # Verificar que el usuario tenga género asignado
        if not current_user.gender or current_user.gender not in [
            "Masculino",
            "Femenino",
        ]:
            raise HTTPException(
                status_code=400,
                detail="Completá tu género para unirte a un partido mixto.",
            )

        # Validar que unirse mantenga la paridad
        is_valid, error_message = validate_mixed_match_gender_balance(
            db, existing_turn, current_user.gender, check_pending_invitations=True
        )
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=error_message,
            )

        # Validar que el lado seleccionado no tenga ya un jugador del mismo género
        if player_side:
            is_valid_side, error_message_side = (
                validate_mixed_match_side_gender_balance(
                    db, existing_turn, current_user.gender, player_side
                )
            )
            if not is_valid_side:
                raise HTTPException(
                    status_code=400,
                    detail=error_message_side,
                )

    # Asignar al jugador a la primera posición disponible
    update_data = PregameTurnUpdate()

    if not existing_turn.player1_id:
        update_data.player1_id = current_user.id
        update_data.player1_side = player_side
        update_data.player1_court_position = player_position
    elif not existing_turn.player2_id:
        update_data.player2_id = current_user.id
        update_data.player2_side = player_side
        update_data.player2_court_position = player_position
    elif not existing_turn.player3_id:
        update_data.player3_id = current_user.id
        update_data.player3_side = player_side
        update_data.player3_court_position = player_position
    elif not existing_turn.player4_id:
        update_data.player4_id = current_user.id
        update_data.player4_side = player_side
        update_data.player4_court_position = player_position
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

    # CRÍTICO: Actualizar el turno SIN commit para mantener el lock
    # Haremos commit al final después de todas las validaciones y notificaciones
    updated_turn = crud.update_pregame_turn(
        db, existing_turn.id, update_data, commit=False
    )

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

    # CRÍTICO: Validación final antes de hacer commit
    # Verificar una última vez que el turno no esté completo
    # Esto previene que otro usuario haya llenado el turno mientras procesábamos
    db.refresh(updated_turn)
    final_players_count = count_players_in_turn(updated_turn)
    if final_players_count >= 4:
        db.rollback()  # Liberar el lock y revertir cualquier cambio
        raise HTTPException(
            status_code=400,
            detail="El turno ya está completo. No hay lugares disponibles.",
        )

    # CRÍTICO: Hacer commit al final después de todas las validaciones
    # Esto asegura que el lock se mantenga durante toda la operación
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar el turno: {str(e)}",
        )

    # Refrescar el turno después del commit para obtener el estado final
    db.refresh(updated_turn)

    # Recalcular players_count después del refresh
    players_count = count_players_in_turn(updated_turn)

    # Enviar notificaciones automáticas (después del commit)
    try:
        if players_count == 4:
            # Turno completo - notificar a todos los jugadores
            notification_service.notify_turn_complete(
                db=db,
                turn_id=updated_turn.id,
                club_name=club.name,
                start_time=start_time,
            )
        else:
            # Jugador se unió - notificar a otros jugadores
            notification_service.notify_turn_joined(
                db=db,
                turn_id=updated_turn.id,
                new_player_id=current_user.id,
                club_name=club.name,
                start_time=start_time,
            )
    except Exception as e:
        # Log el error pero no fallar la operación principal (ya se hizo commit)
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error sending notifications: {e}")

    # Devolver pregame_turn como dict para evitar serializar el ORM (lazy loading puede colgar la respuesta)
    return {
        "success": True,
        "message": "Successfully joined existing turn",
        "pregame_turn": {"id": updated_turn.id},
        "turn_id": updated_turn.id,
        "players_count": players_count,
        "players_needed": 4 - players_count,
    }


@router.get("/{pregame_turn_id}")
def get_pregame_turn(
    pregame_turn_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene un pregame turn específico con información completa de jugadores.
    """
    pregame_turn = crud.get_pregame_turn(db, pregame_turn_id)
    if not pregame_turn:
        raise HTTPException(status_code=404, detail="Pregame turn not found")

    # Convertir a dict para incluir información adicional de jugadores
    turn_dict = {
        "id": pregame_turn.id,
        "turn_id": pregame_turn.turn_id,
        "court_id": pregame_turn.court_id,
        "selected_court_id": pregame_turn.selected_court_id,
        "date": pregame_turn.date.isoformat() if pregame_turn.date else None,
        "start_time": pregame_turn.start_time,
        "end_time": pregame_turn.end_time,
        "price": pregame_turn.price,
        "status": pregame_turn.status.value if pregame_turn.status else None,
        "player1_id": pregame_turn.player1_id,
        "player2_id": pregame_turn.player2_id,
        "player3_id": pregame_turn.player3_id,
        "player4_id": pregame_turn.player4_id,
        "player1_side": pregame_turn.player1_side,
        "player1_court_position": pregame_turn.player1_court_position,
        "player2_side": pregame_turn.player2_side,
        "player2_court_position": pregame_turn.player2_court_position,
        "player3_side": pregame_turn.player3_side,
        "player3_court_position": pregame_turn.player3_court_position,
        "player4_side": pregame_turn.player4_side,
        "player4_court_position": pregame_turn.player4_court_position,
        "category_restricted": (
            pregame_turn.category_restricted == "true"
            if pregame_turn.category_restricted
            else False
        ),
        "category_restriction_type": pregame_turn.category_restriction_type,
        "organizer_category": pregame_turn.organizer_category,
        "is_mixed_match": (
            "true" if pregame_turn.is_mixed_match == "true" else "false"
        ),
        "free_category": pregame_turn.free_category,
        "created_at": (
            pregame_turn.created_at.isoformat() if pregame_turn.created_at else None
        ),
        "updated_at": (
            pregame_turn.updated_at.isoformat() if pregame_turn.updated_at else None
        ),
    }

    # Incluir información de jugadores con géneros
    for i in range(1, 5):
        player = getattr(pregame_turn, f"player{i}", None)
        if player:
            turn_dict[f"player{i}"] = {
                "id": player.id,
                "name": player.name,
                "last_name": player.last_name,
                "gender": player.gender,
                "email": player.email,
            }
        else:
            turn_dict[f"player{i}"] = None

    return turn_dict


@router.post("/{pregame_turn_id}/publish-to-wall")
def publish_turn_to_wall(
    pregame_turn_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Publica el turno en el muro. Solo el organizador (player1) puede hacerlo.
    A partir de ahí el turno aparece en GET /wall para otros jugadores (si está incompleto).
    """
    turn = crud.get_pregame_turn(db, pregame_turn_id)
    if not turn:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    if turn.player1_id != current_user.id:
        raise HTTPException(status_code=403, detail="Solo el organizador puede publicar el turno en el muro")
    turn.published_to_wall = "true"
    db.commit()
    db.refresh(turn)
    return {"success": True, "message": "Turno publicado en el muro", "pregame_turn_id": pregame_turn_id}


# --- Chat interno del turno (solo jugadores que aceptaron la invitación) ---
# Solo pueden ver/leer/escribir quienes están en player1_id..player4_id del turno.
# Invitaciones pendientes no tienen acceso.


@router.get("/{pregame_turn_id}/chat")
def get_turn_chat(
    pregame_turn_id: int,
    limit: int = Query(100, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lista mensajes del chat del turno. Solo jugadores que aceptaron la invitación
    (están asignados en el turno como player1..player4) pueden acceder. 403 si no es participante.
    """
    pregame_turn = crud.get_pregame_turn(db, pregame_turn_id)
    if not pregame_turn:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    if not turn_chat_crud.can_access_chat(db, pregame_turn_id, current_user.id):
        raise HTTPException(status_code=403, detail="No eres parte de este turno")
    messages = turn_chat_crud.get_messages(db, pregame_turn_id, limit=limit, offset=offset)
    # Incluir nombre del autor para cada mensaje
    from app.crud import user as user_crud
    result = []
    for m in messages:
        author = user_crud.get_user(db, m.user_id)
        result.append({
            "id": m.id,
            "pregame_turn_id": m.pregame_turn_id,
            "user_id": m.user_id,
            "sender_name": (author.name or "Jugador").split()[0] if author else "Jugador",
            "message": m.message,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "is_mine": m.user_id == current_user.id,
        })
    return {"success": True, "messages": result}


@router.post("/{pregame_turn_id}/chat")
def post_turn_chat_message(
    pregame_turn_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Envía un mensaje al chat del turno. Solo jugadores que aceptaron la invitación
    (están en el turno como player1..player4). 403 si no es participante. Body: { "message": "texto" }
    """
    pregame_turn = crud.get_pregame_turn(db, pregame_turn_id)
    if not pregame_turn:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    if not turn_chat_crud.can_access_chat(db, pregame_turn_id, current_user.id):
        raise HTTPException(status_code=403, detail="No eres parte de este turno")
    message_text = (body.get("message") or "").strip()
    if not message_text:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")
    msg = turn_chat_crud.create_message(db, pregame_turn_id, current_user.id, message_text)
    if not msg:
        raise HTTPException(status_code=400, detail="Error al crear el mensaje")
    turn_chat_crud.upsert_last_read(db, current_user.id, pregame_turn_id)
    from app.crud import user as user_crud
    author = user_crud.get_user(db, msg.user_id)
    sender_name = (author.name or "Jugador").split()[0] if author else "Jugador"
    preview = (message_text[:60] + "…") if len(message_text) > 60 else message_text
    try:
        from app.utils.notification_utils import notify_turn_chat_message
        club_name = ""
        if pregame_turn.court and pregame_turn.court.club:
            club_name = pregame_turn.court.club.name or ""
        notify_turn_chat_message(
            db=db,
            pregame_turn_id=pregame_turn_id,
            sender_user_id=current_user.id,
            sender_name=sender_name,
            message_preview=preview,
            club_name=club_name,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Error enviando notificación de chat: %s", e)
    return {
        "success": True,
        "message": {
            "id": msg.id,
            "pregame_turn_id": msg.pregame_turn_id,
            "user_id": msg.user_id,
            "sender_name": sender_name,
            "message": msg.message,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
            "is_mine": True,
        },
    }


@router.post("/{pregame_turn_id}/chat/read")
def mark_turn_chat_read(
    pregame_turn_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marca el chat del turno como leído (al abrir la pantalla del chat). Solo participantes u organizador."""
    pregame_turn = crud.get_pregame_turn(db, pregame_turn_id)
    if not pregame_turn:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    if not turn_chat_crud.can_access_chat(db, pregame_turn_id, current_user.id):
        raise HTTPException(status_code=403, detail="No eres parte de este turno")
    turn_chat_crud.upsert_last_read(db, current_user.id, pregame_turn_id)
    return {"success": True}


@router.put("/{pregame_turn_id}")
def update_pregame_turn(
    pregame_turn_id: int,
    pregame_turn: PregameTurnUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Actualiza un pregame turn.
    Permite actualizar restricciones de categoría si el usuario es el organizador del turno.
    Maneja la cancelación de turnos cuando el organizador se retira.
    """
    # CRÍTICO: BLOQUEO DE CONCURRENCIA
    # Obtener el turno existente con bloqueo de fila para prevenir condiciones de carrera
    # NOTA: No podemos usar joinedload con with_for_update porque PostgreSQL no lo permite
    # Primero obtenemos el turno con FOR UPDATE, luego cargamos la relación court si es necesario
    existing_turn = (
        db.query(PregameTurn)
        .filter(PregameTurn.id == pregame_turn_id)
        .with_for_update(
            nowait=False
        )  # BLOQUEO DE FILA - previene condiciones de carrera
        .first()
    )
    if not existing_turn:
        raise HTTPException(status_code=404, detail="Pregame turn not found")

    # CRÍTICO: Bloquear TODAS las modificaciones si el turno está cancelado
    # Un turno cancelado debe ser completamente de solo lectura
    if existing_turn.status == PregameTurnStatus.CANCELLED:
        cancellation_msg = existing_turn.cancellation_message or "El turno fue cancelado."
        raise HTTPException(
            status_code=400,
            detail=f"Este turno fue cancelado y no se pueden realizar modificaciones. {cancellation_msg}",
        )

    # Verificar si el usuario es parte del turno
    is_organizer = existing_turn.player1_id == current_user.id
    is_player = (
        existing_turn.player1_id == current_user.id
        or existing_turn.player2_id == current_user.id
        or existing_turn.player3_id == current_user.id
        or existing_turn.player4_id == current_user.id
    )

    # Verificar si el usuario es administrador del club del turno
    is_club_admin = False
    if current_user.is_admin:
        # Obtener el club_id del turno a través de la cancha
        # Cargar la relación court explícitamente después del bloqueo
        from app.models.court import Court

        court = db.query(Court).filter(Court.id == existing_turn.court_id).first()

        club_id = None
        if court:
            club_id = court.club_id
        else:
            # Si no hay cancha, obtener desde el turn template
            turn_template = turn_crud.get_turn(db, existing_turn.turn_id)
            if turn_template:
                club_id = turn_template.club_id

        if club_id and current_user.club_id == club_id:
            is_club_admin = True

    # Permitir actualización si:
    # 1. El usuario es parte del turno
    # 2. El usuario es administrador del club del turno
    if not is_player and not is_club_admin:
        raise HTTPException(
            status_code=403,
            detail="You are not part of this turn and you are not the club administrator",
        )

    # CRÍTICO: Si el turno está en estado READY_TO_PLAY (tarjeta emitida), no se pueden modificar parámetros
    # Solo se permiten cancelaciones (retirarse del turno)
    if existing_turn.status == PregameTurnStatus.READY_TO_PLAY:
        # Verificar si es una cancelación (algún player_id se está estableciendo como None)
        update_data_dict = pregame_turn.model_dump(exclude_unset=True)
        is_cancellation = any(
            update_data_dict.get(f"player{i}_id") is None
            for i in range(1, 5)
            if f"player{i}_id" in update_data_dict
        )

        # Si NO es una cancelación, verificar si se están modificando parámetros del partido
        if not is_cancellation:
            # Lista de campos que NO se pueden modificar cuando el turno está READY_TO_PLAY
            restricted_fields = [
                "is_mixed_match",
                "category_restricted",
                "category_restriction_type",
                "free_category",
            ]

            # Verificar si se está intentando modificar algún parámetro restringido
            is_modifying_restricted_params = any(
                field in update_data_dict for field in restricted_fields
            )

            # CRÍTICO: Cuando el turno está en READY_TO_PLAY, NO se permite NINGUNA modificación
            # excepto cancelaciones (retirarse del turno)
            # Esto incluye cambios de posición, parámetros del partido, etc.

            # Verificar si se está intentando modificar la posición del jugador
            allowed_position_fields = [f"player{i}_side" for i in range(1, 5)] + [
                f"player{i}_court_position" for i in range(1, 5)
            ]

            is_updating_position = any(
                field in update_data_dict for field in allowed_position_fields
            )

            # Bloquear TODAS las modificaciones (incluyendo posición) cuando el turno está READY_TO_PLAY
            if is_modifying_restricted_params:
                raise HTTPException(
                    status_code=400,
                    detail="No se pueden modificar los parámetros del partido (tipo de partido, restricciones de categoría) después de que la tarjeta de reserva ha sido emitida. El turno está completo y listo para jugar.",
                )

            if is_updating_position:
                raise HTTPException(
                    status_code=400,
                    detail="No se pueden modificar las posiciones de los jugadores después de que la tarjeta de reserva ha sido emitida. El turno está completo y listo para jugar.",
                )

            # Si no es cancelación ni modificación de posición ni parámetros, bloquear
            # (no debería llegar aquí, pero por seguridad)
            raise HTTPException(
                status_code=400,
                detail="No se pueden realizar modificaciones después de que la tarjeta de reserva ha sido emitida. El turno está completo y listo para jugar.",
            )

    # CRÍTICO: Identificar qué posición ocupa el jugador actualmente ANTES de verificar cancelación
    # Esto es necesario para determinar si el jugador está intentando cancelar su propia posición
    current_player_position = None
    if existing_turn.player1_id == current_user.id:
        current_player_position = "player1"
    elif existing_turn.player2_id == current_user.id:
        current_player_position = "player2"
    elif existing_turn.player3_id == current_user.id:
        current_player_position = "player3"
    elif existing_turn.player4_id == current_user.id:
        current_player_position = "player4"

    # Verificar si se está intentando cancelar la posición
    # IMPORTANTE: Solo considerar cancelación si el player_id del jugador actual está explícitamente
    # establecido como None en el request (usando exclude_unset=False para ver todos los campos)
    # No considerar cancelación si el campo simplemente no está presente en el request
    update_data_for_cancel_check = pregame_turn.model_dump(exclude_unset=False)
    canceling_position = False

    if current_player_position:
        player_id_field = f"{current_player_position}_id"
        # Solo es cancelación si el player_id del jugador actual está explícitamente en el request Y es None
        # O si está en el request original (exclude_unset=True) y es None
        original_update_data = pregame_turn.model_dump(exclude_unset=True)
        if (
            player_id_field in original_update_data
            and original_update_data[player_id_field] is None
        ):
            canceling_position = True

    if canceling_position:
        # Lógica de cancelación
        try:
            from app.utils.turn_cancellation import (
                cancel_complete_turn,
                cancel_individual_position,
            )

            if is_organizer:
                # CANCELACIÓN COMPLETA DEL TURNO
                # CRÍTICO: El mensaje de cancelación es OBLIGATORIO para el organizador
                # Obtener mensaje de cancelación del organizador
                cancellation_message = None
                if hasattr(pregame_turn, "cancellation_message"):
                    cancellation_message = pregame_turn.cancellation_message
                # También verificar si viene en el request body
                request_body = pregame_turn.model_dump(exclude_unset=True)
                if "cancellation_message" in request_body:
                    cancellation_message = request_body.get("cancellation_message")

                # Validar que el mensaje no esté vacío
                if not cancellation_message or not cancellation_message.strip():
                    raise HTTPException(
                        status_code=400,
                        detail="El mensaje de cancelación es obligatorio. Por favor, explicá por qué cancelás el turno.",
                    )

                result = cancel_complete_turn(
                    db,
                    pregame_turn_id,
                    current_user.id,
                    cancellation_message=cancellation_message.strip(),
                )
                return {
                    "success": True,
                    "message": "Turno cancelado exitosamente. Todos los jugadores han sido notificados.",
                    "data": result,
                }
            else:
                # CANCELACIÓN INDIVIDUAL
                # CRÍTICO: El mensaje de justificación es OBLIGATORIO
                cancellation_message = None
                if hasattr(pregame_turn, "cancellation_message"):
                    cancellation_message = pregame_turn.cancellation_message
                # También verificar si viene en el request body como campo adicional
                request_body = pregame_turn.model_dump(exclude_unset=True)
                if "cancellation_message" in request_body:
                    cancellation_message = request_body.get("cancellation_message")

                # Validar que el mensaje no esté vacío
                if not cancellation_message or not cancellation_message.strip():
                    raise HTTPException(
                        status_code=400,
                        detail="El mensaje de justificación es obligatorio. Por favor, explicá por qué te das de baja del turno.",
                    )

                result = cancel_individual_position(
                    db,
                    pregame_turn_id,
                    current_user.id,
                    cancellation_message=cancellation_message.strip(),
                )
                return {
                    "success": True,
                    "message": "Posición cancelada exitosamente",
                    "data": result,
                }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error cancelando turno: {str(e)}"
            )

    # CRÍTICO: Manejar actualización de posición/lado del jugador
    # El jugador puede cambiar su lado y posición en la cancha sin perder su pertenencia al turno
    # current_player_position ya fue identificado arriba

    # CRÍTICO: Si el jugador está actualizando su posición/lado, proteger el player_id ANTES de procesar
    # Esto asegura que el player_id se incluya en el model_dump cuando se llame al CRUD
    if current_player_position:
        player_id_field = f"{current_player_position}_id"
        side_field = f"{current_player_position}_side"
        position_field = f"{current_player_position}_court_position"

        # Obtener los campos que se están actualizando en el request original (exclude_unset=True)
        # Esto nos dice qué campos fueron enviados explícitamente en el request
        original_update_data = pregame_turn.model_dump(exclude_unset=True)

        # Verificar si está actualizando solo su lado y posición (sin tocar el player_id explícitamente)
        is_updating_side_or_position = (side_field in original_update_data) or (
            position_field in original_update_data
        )
        is_canceling_position = (
            player_id_field in original_update_data
            and original_update_data[player_id_field] is None
        )

        # CRÍTICO: Proteger el player_id ANTES de cualquier otra lógica
        # Establecer explícitamente el player_id en el objeto pregame_turn para que se incluya en el model_dump
        # cuando el CRUD lo procese. Esto es especialmente importante si solo se enviaron side y court_position.
        if current_player_position == "player1":
            # El organizador nunca puede ser removido - forzar que se mantenga
            pregame_turn.player1_id = existing_turn.player1_id
        else:
            # Para otros jugadores, asegurar que su ID se mantenga
            current_player_id = getattr(existing_turn, player_id_field, None)
            if current_player_id is not None:
                setattr(pregame_turn, player_id_field, current_player_id)

        if is_updating_side_or_position and not is_canceling_position:
            # Ahora obtener los datos actualizados después de establecer el player_id
            update_data = pregame_turn.model_dump(exclude_unset=True)
            # Validar que la nueva posición no esté ocupada por otro jugador
            new_side = update_data.get(side_field) or getattr(
                existing_turn, side_field, None
            )
            new_court_position = update_data.get(position_field) or getattr(
                existing_turn, position_field, None
            )

            if new_side and new_court_position:
                # Verificar si otro jugador ya ocupa esa combinación de lado y posición
                for other_pos in ["player1", "player2", "player3", "player4"]:
                    if other_pos == current_player_position:
                        continue  # Saltar la posición actual del jugador

                    other_player_id = getattr(existing_turn, f"{other_pos}_id", None)
                    if other_player_id is None:
                        continue  # Esta posición está vacía

                    other_side = getattr(existing_turn, f"{other_pos}_side", None)
                    other_court_pos = getattr(
                        existing_turn, f"{other_pos}_court_position", None
                    )

                    if other_side == new_side and other_court_pos == new_court_position:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Esta posición ({new_side}, {new_court_position}) ya está ocupada por otro jugador. Elegí otra.",
                        )

                # Validar composición de equipos por género en turnos mixtos
                if existing_turn.is_mixed_match == "true":
                    # Obtener el género del jugador actual
                    current_player_id = getattr(
                        existing_turn, f"{current_player_position}_id", None
                    )
                    if current_player_id:
                        # Obtener el usuario actual de la base de datos
                        current_player_user = (
                            db.query(User).filter(User.id == current_player_id).first()
                        )
                        if current_player_user and current_player_user.gender:
                            is_valid_side, error_message_side = (
                                validate_mixed_match_side_gender_balance(
                                    db,
                                    existing_turn,
                                    current_player_user.gender,
                                    new_side,
                                    exclude_player_position=current_player_position,
                                )
                            )
                            if not is_valid_side:
                                raise HTTPException(
                                    status_code=400,
                                    detail=error_message_side,
                                )
    else:
        # Si no hay current_player_position, obtener update_data normalmente
        update_data = pregame_turn.model_dump(exclude_unset=True)

    # Lógica normal de actualización
    # CRÍTICO: Verificar que solo el organizador (player1_id) puede modificar configuración del turno
    # Los jugadores invitados solo pueden modificar su posición o cancelar su turno
    
    # Obtener los campos que se están intentando actualizar
    update_data_for_validation = pregame_turn.model_dump(exclude_unset=True)
    
    # Campos que solo el organizador puede modificar
    organizer_only_fields = [
        "is_mixed_match",
        "free_category",
        "category_restricted",
        "category_restriction_type",
        "organizer_category"
    ]
    
    # Verificar si se está intentando modificar algún campo restringido
    is_modifying_organizer_only_field = any(
        field in update_data_for_validation for field in organizer_only_fields
    )
    
    # Si el usuario NO es el organizador y está intentando modificar campos restringidos
    if is_modifying_organizer_only_field and existing_turn.player1_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Solo el jugador configurador del turno puede modificar la configuración del partido (tipo mixto, restricciones de categoría). Los jugadores invitados solo pueden cambiar su posición o cancelar su turno.",
        )
    
    # CRÍTICO: Validar que los jugadores invitados solo puedan modificar su propia posición
    # No pueden modificar los player_id, side o court_position de otros jugadores
    if existing_turn.player1_id != current_user.id and not is_club_admin:
        # El usuario es un jugador invitado (no organizador ni admin)
        # Solo puede modificar campos relacionados con su propia posición
        allowed_fields_for_invited_players = set()
        
        # Identificar qué posición ocupa el jugador
        if current_player_position:
            # Puede modificar su propia posición (side y court_position)
            allowed_fields_for_invited_players.add(f"{current_player_position}_side")
            allowed_fields_for_invited_players.add(f"{current_player_position}_court_position")
            # Puede cancelar su propia posición (establecer su player_id como None)
            allowed_fields_for_invited_players.add(f"{current_player_position}_id")
            # Puede incluir el mensaje de cancelación
            allowed_fields_for_invited_players.add("cancellation_message")
        
        # Verificar si está intentando modificar campos que no le corresponden
        restricted_fields_being_modified = []
        for field in update_data_for_validation.keys():
            if field not in allowed_fields_for_invited_players:
                # Verificar si es un campo de otro jugador
                for other_pos in ["player1", "player2", "player3", "player4"]:
                    if other_pos != current_player_position:
                        if field.startswith(f"{other_pos}_"):
                            restricted_fields_being_modified.append(field)
                            break
                # Si no es un campo de posición de jugador, verificar si es otro campo restringido
                if field not in ["status", "selected_court_id"] and field not in allowed_fields_for_invited_players:
                    if field not in organizer_only_fields:  # Ya validado arriba
                        restricted_fields_being_modified.append(field)
        
        if restricted_fields_being_modified:
            raise HTTPException(
                status_code=403,
                detail=f"Los jugadores invitados solo pueden modificar su propia posición o cancelar su turno. No podés modificar: {', '.join(restricted_fields_being_modified)}",
            )
    
    # CRÍTICO: Bloquear TODOS los parámetros del partido si hay jugadores confirmados o invitaciones pendientes
    # Los parámetros del partido solo pueden modificarse durante la creación del turno
    # Una vez que hay jugadores o invitaciones, deben quedar bloqueados
    restricted_params = [
        "is_mixed_match",
        "free_category",
        "category_restricted",
        "category_restriction_type",
        "organizer_category"
    ]
    
    # Verificar si se está intentando modificar algún parámetro del partido
    is_modifying_params = any(
        field in update_data_for_validation for field in restricted_params
    )
    
    if is_modifying_params:
        # Verificar si hay jugadores confirmados (excluyendo al organizador)
        has_confirmed_players = (
            existing_turn.player2_id is not None
            or existing_turn.player3_id is not None
            or existing_turn.player4_id is not None
        )

        # Verificar si hay invitaciones pendientes o aceptadas
        from app.crud import invitation as invitation_crud

        pending_invitations = invitation_crud.get_pending_invitations_by_turn(
            db, pregame_turn_id
        )
        
        # También verificar invitaciones aceptadas (jugadores que aceptaron pero aún no están asignados)
        from app.models.invitation import Invitation
        accepted_invitations = (
            db.query(Invitation)
            .filter(
                and_(
                    Invitation.turn_id == pregame_turn_id,
                    Invitation.status == "ACCEPTED"
                )
            )
            .all()
        )

        if has_confirmed_players or len(pending_invitations) > 0 or len(accepted_invitations) > 0:
            raise HTTPException(
                status_code=400,
                detail="No se pueden modificar los parámetros del partido una vez que se enviaron invitaciones o hay jugadores confirmados. Los parámetros del partido solo pueden editarse durante la creación del turno.",
            )

    # Validar restricciones de categoría (los permisos ya fueron validados arriba)
    if (
        pregame_turn.category_restricted is not None
        or pregame_turn.category_restriction_type is not None
    ):
        # Validar restricciones de categoría
        if (
            pregame_turn.category_restricted
            and pregame_turn.category_restriction_type == "NONE"
        ):
            raise HTTPException(
                status_code=400,
                detail="category_restriction_type cannot be 'NONE' when category_restricted is true",
            )

        if (
            pregame_turn.category_restriction_type
            and not CategoryRestrictionValidator.validate_restriction_type(
                pregame_turn.category_restriction_type
            )
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid category_restriction_type. Must be 'NONE', 'SAME_CATEGORY', or 'NEARBY_CATEGORIES'",
            )

    # CRÍTICO: Si un administrador del club está agregando un jugador, crear una invitación en lugar de agregarlo directamente
    update_data = pregame_turn.model_dump(exclude_unset=True)
    players_being_added = []

    if is_club_admin and not is_player:
        # Detectar si se están agregando jugadores (player_id que antes era None ahora tiene un valor)
        for player_num in [1, 2, 3, 4]:
            player_id_field = f"player{player_num}_id"
            if player_id_field in update_data:
                new_player_id = update_data[player_id_field]
                current_player_id = getattr(existing_turn, player_id_field, None)

                # Si se está agregando un jugador nuevo (antes era None, ahora tiene un ID)
                if current_player_id is None and new_player_id is not None:
                    players_being_added.append((player_num, new_player_id))

        # Si se están agregando jugadores, crear invitaciones en lugar de agregarlos directamente
        if players_being_added:
            from app.crud import invitation as invitation_crud
            from app.schemas.invitation import InvitationCreate
            from app.models.court import Court

            # Obtener el nombre del club
            court = db.query(Court).filter(Court.id == existing_turn.court_id).first()
            club_name = court.club.name if court and court.club else "Club"

            invitations_created = []
            for player_num, player_id in players_being_added:
                # Verificar que el jugador no esté ya en el turno
                if player_id in [
                    existing_turn.player1_id,
                    existing_turn.player2_id,
                    existing_turn.player3_id,
                    existing_turn.player4_id,
                ]:
                    continue

                # Verificar que no haya una invitación pendiente o aceptada para este jugador
                existing_invitation = invitation_crud.check_existing_invitation(
                    db, pregame_turn_id, player_id
                )
                if existing_invitation and existing_invitation.status in [
                    "PENDING",
                    "ACCEPTED",
                ]:
                    continue

                # Crear la invitación
                invitation_data = InvitationCreate(
                    turn_id=pregame_turn_id,
                    inviter_id=current_user.id,  # El admin del club es el invitador
                    invited_player_id=player_id,
                    message=f"El club {club_name} te ha agregado al turno",
                    is_validated_invitation=False,  # No es una invitación validada
                )

                invitation = invitation_crud.create_invitation(db, invitation_data)
                invitations_created.append((player_num, player_id, invitation.id))

                # Enviar notificación FCM al jugador
                try:
                    invited_player = db.query(User).filter(User.id == player_id).first()
                    if invited_player:
                        notification_service.notify_turn_invitation(
                            db=db,
                            invitation_id=invitation.id,
                            inviter_name=f"{club_name} (Club)",
                            club_name=club_name,
                            turn_time=existing_turn.start_time,
                            turn_date=existing_turn.date.strftime("%Y-%m-%d"),
                        )
                except Exception as e:
                    logger.error(
                        f"Error enviando notificación de invitación del club: {e}"
                    )

            # Remover los player_id del update_data para que no se agreguen directamente
            for player_num, player_id, invitation_id in invitations_created:
                player_id_field = f"player{player_num}_id"
                if player_id_field in update_data:
                    del update_data[player_id_field]
                    # También remover del objeto pregame_turn
                    setattr(pregame_turn, player_id_field, None)

            # Si se crearon invitaciones, retornar un mensaje informativo
            if invitations_created:
                return {
                    "success": True,
                    "message": f"Se han enviado {len(invitations_created)} invitación(es) a los jugadores. Deben aceptar para unirse al turno.",
                    "invitations_created": len(invitations_created),
                    "turn": (
                        crud.update_pregame_turn(db, pregame_turn_id, pregame_turn)
                        if update_data
                        else existing_turn
                    ),
                }

    # Guardar valores anteriores para detectar cambios de gestión (horario/cancha) del club
    old_start_time = existing_turn.start_time
    old_court_id = existing_turn.court_id
    old_selected_court_id = getattr(existing_turn, "selected_court_id", None)

    updated_turn = crud.update_pregame_turn(db, pregame_turn_id, pregame_turn)
    if not updated_turn:
        raise HTTPException(status_code=404, detail="Pregame turn not found")

    # Si el club modificó horario o cancha, notificar al configurador y a los jugadores que aceptaron
    if is_club_admin and updated_turn:
        from app.models.court import Court
        from app.utils.notification_utils import notify_turn_modified_by_club

        court = db.query(Court).filter(Court.id == updated_turn.court_id).first()
        club_name = court.club.name if court and court.club else "Club"

        schedule_changed = (updated_turn.start_time or "") != (old_start_time or "")
        court_changed = (updated_turn.court_id != old_court_id) or (
            getattr(updated_turn, "selected_court_id", None) != old_selected_court_id
        )
        if schedule_changed and updated_turn.start_time:
            try:
                notify_turn_modified_by_club(
                    db=db,
                    turn=updated_turn,
                    change_type="schedule",
                    new_value_description=updated_turn.start_time,
                    club_name=club_name,
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error notificando cambio de horario: {e}")
        if court_changed:
            new_court_id = updated_turn.court_id or getattr(
                updated_turn, "selected_court_id", None
            )
            new_court = (
                db.query(Court).filter(Court.id == new_court_id).first()
                if new_court_id
                else None
            )
            new_court_name = new_court.name if new_court else "Nueva cancha"
            try:
                notify_turn_modified_by_club(
                    db=db,
                    turn=updated_turn,
                    change_type="court",
                    new_value_description=new_court_name,
                    club_name=club_name,
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error notificando cambio de cancha: {e}")

    # Si el configurador (organizador) modificó el horario, notificar a todos los jugadores
    schedule_changed = (updated_turn.start_time or "") != (old_start_time or "")
    if (
        updated_turn
        and schedule_changed
        and updated_turn.start_time
        and not is_club_admin
        and updated_turn.player1_id == current_user.id
    ):
        try:
            from app.utils.notification_utils import notify_turn_schedule_modified

            organizer_label = (
                f"El organizador {current_user.name}"
                if getattr(current_user, "name", None)
                else "El organizador"
            )
            notify_turn_schedule_modified(
                db=db,
                turn=updated_turn,
                new_time_description=updated_turn.start_time,
                modifier_label=organizer_label,
                exclude_user_id=current_user.id,
            )
        except Exception as e:
            logger.error(
                f"Error notificando a jugadores por cambio de horario del organizador: {e}"
            )

    # Si el configurador (organizador) modificó la cancha, notificar a todos los jugadores
    court_changed = (updated_turn.court_id != old_court_id) or (
        getattr(updated_turn, "selected_court_id", None) != old_selected_court_id
    )
    if (
        updated_turn
        and court_changed
        and not is_club_admin
        and updated_turn.player1_id == current_user.id
    ):
        try:
            from app.models.court import Court
            from app.utils.notification_utils import notify_turn_court_modified

            new_court_id = updated_turn.court_id or getattr(
                updated_turn, "selected_court_id", None
            )
            new_court = (
                db.query(Court).filter(Court.id == new_court_id).first()
                if new_court_id
                else None
            )
            new_court_name = new_court.name if new_court else "Nueva cancha"
            organizer_label = (
                f"El organizador {current_user.name}"
                if getattr(current_user, "name", None)
                else "El organizador"
            )
            notify_turn_court_modified(
                db=db,
                turn=updated_turn,
                new_court_description=new_court_name,
                modifier_label=organizer_label,
                exclude_user_id=current_user.id,
            )
        except Exception as e:
            logger.error(
                f"Error notificando a jugadores por cambio de cancha del organizador: {e}"
            )

    return updated_turn


@router.post("/create-turn-by-club")
def create_turn_by_club(
    club_id: int = Query(..., description="Club ID"),
    start_time: str = Query(..., description="Start time in HH:MM format"),
    target_date: date = Query(..., description="Date for the turn (YYYY-MM-DD)"),
    court_id: int = Query(..., description="Court ID (required)"),
    organizer_player_id: int = Query(
        ..., description="Player ID to assign as organizer (player1_id)"
    ),
    player_side: Optional[str] = Query(
        None, description="Organizer player side: 'reves' or 'drive'"
    ),
    player_position: Optional[str] = Query(
        None, description="Organizer player court position: 'izquierda' or 'derecha'"
    ),
    category_restricted: Optional[bool] = Query(
        False, description="Enable category restrictions for this turn"
    ),
    category_restriction_type: Optional[str] = Query(
        "NONE",
        description="Type of category restriction: 'NONE', 'SAME_CATEGORY', 'NEARBY_CATEGORIES'",
    ),
    is_mixed_match: Optional[bool] = Query(
        False, description="Is this a mixed match (accepts players of both genders)"
    ),
    free_category: Optional[str] = Query(
        None,
        description="Free category for mixed matches (required for female organizers)",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Crear un turno desde cero por el administrador del club.
    Permite asignar un jugador como organizador y aplicar todas las restricciones.
    """
    # Verificar que el usuario sea administrador del club
    if not current_user.is_admin or current_user.club_id != club_id:
        raise HTTPException(
            status_code=403, detail="Solo el administrador del club puede crear turnos"
        )

    # Verificar que el club existe
    club = club_crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    # Verificar que el jugador organizador existe y tiene token FCM activo
    organizer = db.query(User).filter(User.id == organizer_player_id).first()
    if not organizer:
        raise HTTPException(status_code=404, detail="Jugador organizador no encontrado")

    # Verificar que el jugador no sea admin
    if organizer.is_admin or organizer.is_super_admin:
        raise HTTPException(
            status_code=400,
            detail="El organizador debe ser un jugador, no un administrador",
        )

    # Verificar si el jugador tiene token FCM activo (opcional, solo para notificaciones)
    # El club puede crear turnos con cualquier jugador, incluso sin token FCM
    # Si el jugador tiene token FCM, recibirá notificaciones; si no, el turno se crea igual
    from app.crud import fcm_token as fcm_crud

    organizer_tokens = fcm_crud.get_user_fcm_tokens(
        db, organizer_player_id, active_only=True
    )
    has_fcm_token = len(organizer_tokens) > 0

    # Si el jugador no tiene token FCM, solo mostrar un warning en logs, no bloquear la creación
    if not has_fcm_token:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"⚠️ El jugador organizador {organizer_player_id} no tiene token FCM activo. "
            f"El turno se creará pero el jugador no recibirá notificaciones push hasta que inicie sesión en la app móvil."
        )

    # Validar parámetros de partidos mixtos
    if is_mixed_match:
        # Verificar que el organizador tenga género asignado
        if not organizer.gender or organizer.gender not in ["Masculino", "Femenino"]:
            raise HTTPException(
                status_code=400,
                detail="El organizador debe tener género asignado para crear un partido mixto",
            )

        # Para mujeres, usar su categoría como free_category si no la envían (no bloquear)
        if organizer.gender == "Femenino" and not free_category:
            free_category = organizer.category or "9na"
        # Para hombres, usar su categoría como free_category
        elif organizer.gender == "Masculino":
            free_category = organizer.category or "9na"

        # En partidos mixtos, no se pueden activar restricciones de categoría
        category_restricted = False
        category_restriction_type = "NONE"

    # Validar parámetros de restricción de categoría
    if category_restricted and category_restriction_type == "NONE":
        raise HTTPException(
            status_code=400,
            detail="category_restriction_type cannot be 'NONE' when category_restricted is true",
        )

    if not CategoryRestrictionValidator.validate_restriction_type(
        category_restriction_type
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid category_restriction_type. Must be 'NONE', 'SAME_CATEGORY', or 'NEARBY_CATEGORIES'",
        )

    # Obtener el template de turnos del club
    club_turns = turn_crud.get_turns(db, club_id=club_id)
    if not club_turns:
        raise HTTPException(
            status_code=404, detail="No turns template found for this club"
        )

    # Verificar que el turno existe en el template
    turns_data = club_turns[0].turns_data
    turn_info = None

    for turn_item in turns_data.get("turns", []):
        if turn_item.get("start_time") == start_time:
            turn_info = turn_item
            break

    if not turn_info:
        raise HTTPException(
            status_code=400,
            detail=f"Turno con hora {start_time} no encontrado en el template del club",
        )

    # Verificar que la cancha existe y pertenece al club
    from app.models.court import Court

    court = (
        db.query(Court).filter(Court.id == court_id, Court.club_id == club_id).first()
    )
    if not court:
        raise HTTPException(
            status_code=404, detail="Cancha no encontrada o no pertenece al club"
        )

    # ========== VALIDACIONES DE DISPONIBILIDAD ==========
    target_date_combined = datetime.combine(target_date, datetime.min.time())

    # 1. Verificar que la fecha no sea en el pasado
    now = datetime.now()
    today = now.date()
    if target_date < today:
        raise HTTPException(
            status_code=400,
            detail=f"No se pueden crear turnos en fechas pasadas. La fecha seleccionada ({target_date.strftime('%d/%m/%Y')}) es anterior a hoy.",
        )

    # 2. Verificar que el día de la semana esté disponible para el club
    day_of_week = target_date.weekday()  # 0 = lunes, 6 = domingo
    day_fields = {
        0: club.monday_open,
        1: club.tuesday_open,
        2: club.wednesday_open,
        3: club.thursday_open,
        4: club.friday_open,
        5: club.saturday_open,
        6: club.sunday_open,
    }
    day_names = {
        0: "lunes",
        1: "martes",
        2: "miércoles",
        3: "jueves",
        4: "viernes",
        5: "sábado",
        6: "domingo",
    }

    if not day_fields.get(day_of_week, False):
        raise HTTPException(
            status_code=400,
            detail=f"El club no está abierto los {day_names[day_of_week]}. Por favor, selecciona otro día.",
        )

    # 3. Verificar que el horario esté dentro del rango de horarios del club
    from app.utils.turn_overlap import parse_time_to_minutes

    start_minutes = parse_time_to_minutes(start_time)
    if start_minutes == -1:
        raise HTTPException(
            status_code=400,
            detail=f"Formato de hora inválido: {start_time}. Debe ser HH:MM (ej: 09:00, 15:30)",
        )

    # Convertir opening_time y closing_time a minutos
    opening_minutes = (
        club.opening_time.hour * 60 + club.opening_time.minute
        if club.opening_time
        else 0
    )
    closing_minutes = (
        club.closing_time.hour * 60 + club.closing_time.minute
        if club.closing_time
        else 1440
    )

    # Obtener end_time del turno
    turn_end_time = turn_info.get("end_time", "")
    if not turn_end_time:
        # Si no hay end_time, calcularlo (start_time + 90 minutos)
        end_minutes = start_minutes + 90
        if end_minutes >= 1440:
            end_minutes = 1439
    else:
        end_minutes = parse_time_to_minutes(turn_end_time)
        if end_minutes == -1:
            end_minutes = start_minutes + 90  # Fallback

    # Verificar que el turno esté dentro del horario del club
    if start_minutes < opening_minutes:
        opening_time_str = (
            f"{club.opening_time.hour:02d}:{club.opening_time.minute:02d}"
        )
        raise HTTPException(
            status_code=400,
            detail=f"El horario de inicio ({start_time}) es anterior a la hora de apertura del club ({opening_time_str}).",
        )

    if end_minutes > closing_minutes:
        closing_time_str = (
            f"{club.closing_time.hour:02d}:{club.closing_time.minute:02d}"
        )
        raise HTTPException(
            status_code=400,
            detail=f"El turno termina después de la hora de cierre del club ({closing_time_str}).",
        )

    # 4. Verificar que no exista ya un turno en la misma fecha, hora y cancha
    existing_turn = (
        db.query(PregameTurn)
        .filter(
            and_(
                PregameTurn.court_id == court_id,
                PregameTurn.date == target_date_combined,
                PregameTurn.start_time == start_time,
                PregameTurn.status.in_(
                    [PregameTurnStatus.PENDING, PregameTurnStatus.READY_TO_PLAY]
                ),
            )
        )
        .first()
    )

    if existing_turn:
        # Obtener información del turno existente para el mensaje
        existing_players_count = count_players_in_turn(existing_turn)
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe un turno en la cancha {court.name} el {target_date.strftime('%d/%m/%Y')} a las {start_time} ({existing_players_count}/4 jugadores). Por favor, selecciona otro horario o cancha.",
        )

    # 5. Verificar solapamiento de horarios en la misma cancha
    # Buscar turnos que se solapen con el horario del nuevo turno
    overlapping_turns = (
        db.query(PregameTurn)
        .filter(
            and_(
                PregameTurn.court_id == court_id,
                PregameTurn.date == target_date_combined,
                PregameTurn.status.in_(
                    [PregameTurnStatus.PENDING, PregameTurnStatus.READY_TO_PLAY]
                ),
            )
        )
        .all()
    )

    # Verificar solapamiento con cada turno existente
    for overlapping_turn in overlapping_turns:
        if overlapping_turn.start_time == start_time:
            continue  # Ya lo verificamos arriba

        existing_start_minutes = parse_time_to_minutes(overlapping_turn.start_time)
        if existing_start_minutes == -1:
            continue

        # Calcular end_time del turno existente (start_time + 90 minutos)
        existing_end_minutes = existing_start_minutes + 90
        if existing_end_minutes >= 1440:
            existing_end_minutes = 1439

        # Verificar solapamiento
        # El nuevo turno se solapa si:
        # - Comienza durante el turno existente: start_minutes >= existing_start_minutes AND start_minutes < existing_end_minutes
        # - Termina durante el turno existente: end_minutes > existing_start_minutes AND end_minutes <= existing_end_minutes
        # - Contiene completamente el turno existente: start_minutes <= existing_start_minutes AND end_minutes >= existing_end_minutes
        # - Es contenido completamente por el turno existente: start_minutes >= existing_start_minutes AND end_minutes <= existing_end_minutes

        if (
            (
                start_minutes >= existing_start_minutes
                and start_minutes < existing_end_minutes
            )
            or (
                end_minutes > existing_start_minutes
                and end_minutes <= existing_end_minutes
            )
            or (
                start_minutes <= existing_start_minutes
                and end_minutes >= existing_end_minutes
            )
            or (
                start_minutes >= existing_start_minutes
                and end_minutes <= existing_end_minutes
            )
        ):
            existing_players_count = count_players_in_turn(overlapping_turn)
            raise HTTPException(
                status_code=400,
                detail=f"El horario seleccionado ({start_time}) se solapa con un turno existente en la cancha {court.name} el {target_date.strftime('%d/%m/%Y')} a las {overlapping_turn.start_time} ({existing_players_count}/4 jugadores). Por favor, selecciona otro horario.",
            )

    # Validar que el organizador no tenga ya una reserva activa en el mismo horario y fecha

    from app.utils.turn_overlap import (
        get_user_active_reservations_time_ranges,
        does_turn_overlap_with_reservations,
    )

    organizer_reservations = get_user_active_reservations_time_ranges(
        db, organizer_player_id, target_date
    )

    if does_turn_overlap_with_reservations(
        turn_info["start_time"],
        turn_info["end_time"],
        organizer_reservations,
    ):
        raise HTTPException(
            status_code=400,
            detail="El jugador organizador ya tiene una reserva activa en este horario. No puede estar en dos canchas al mismo tiempo.",
        )

    # Obtener la categoría del organizador para restricciones
    organizer_category = organizer.category or "9na"

    # Crear el turno
    pregame_turn_data = PregameTurnCreate(
        turn_id=club_turns[0].id,
        court_id=court_id,
        selected_court_id=court_id,
        date=target_date_combined,
        start_time=turn_info["start_time"],
        end_time=turn_info["end_time"],
        price=turn_info["price"],
        status="PENDING",
        player1_id=organizer_player_id,
        player1_side=player_side,
        player1_court_position=player_position,
        category_restricted=category_restricted,
        category_restriction_type=CategoryRestrictionType(category_restriction_type),
        organizer_category=organizer_category,
        is_mixed_match=is_mixed_match,
        free_category=free_category,
    )

    try:
        created_turn = crud.create_pregame_turn(db, pregame_turn_data, commit=True)

        # Enviar notificación al organizador solo si tiene token FCM activo
        if has_fcm_token:
            try:
                from app.utils.notification_utils import send_notification_with_fcm

                send_notification_with_fcm(
                    db=db,
                    user_id=organizer_player_id,
                    title="Turno creado por el club",
                    message=f"El club {club.name} te ha asignado como organizador de un turno el {target_date.strftime('%d/%m/%Y')} a las {start_time}",
                    notification_type="turn_created",
                    data={
                        "turn_id": created_turn.id,
                        "club_name": club.name,
                        "club_id": str(club_id),
                        "start_time": start_time,
                        "date": target_date.isoformat(),
                        "court_id": str(court_id),
                        "court_name": court.name,
                    },
                )
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Error enviando notificación al organizador: {e}")
        else:
            import logging

            logger = logging.getLogger(__name__)
            logger.info(
                f"⚠️ No se envió notificación push al organizador {organizer_player_id} "
                f"porque no tiene token FCM activo. El turno fue creado exitosamente."
            )

        # Devolver pregame_turn como dict para evitar serializar el ORM
        return {
            "success": True,
            "message": "Turno creado exitosamente",
            "turn_id": created_turn.id,
            "pregame_turn": {"id": created_turn.id},
            "data": {
                "turn_id": created_turn.id,
                "is_mixed_match": is_mixed_match,
                "free_category": free_category,
                "category_restricted": category_restricted,
                "category_restriction_type": category_restriction_type,
                "organizer_category": organizer_category,
            },
        }

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error creando turno: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error al crear el turno: {str(e)}"
        )


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
