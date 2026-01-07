from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.services.auth import get_current_user
from app.models.user import User
from app.schemas.invitation import PlayerSearchResponse
from app.crud import invitation as invitation_crud

router = APIRouter(tags=["players"])


@router.get("/search", response_model=List[PlayerSearchResponse])
async def search_players(
    q: Optional[str] = Query(None, description="Término de búsqueda (opcional)"),
    turn_id: Optional[int] = Query(
        None,
        description="ID del turno (opcional). Si se proporciona, se excluyen jugadores que ya están en el turno o tienen invitaciones pendientes/aceptadas",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Buscar jugadores para invitar

    Lógica de búsqueda:
    - Si q está vacío o es null: Devolver todos los jugadores disponibles
    - Si q tiene valor: Buscar jugadores que coincidan con:
      * name (nombre)
      * last_name (apellido)
      * email (email)
      * Combinación de name + last_name
    - Si turn_id se proporciona: Se excluyen automáticamente:
      * Jugadores que ya están en el turno (player1, player2, player3, player4)
      * Jugadores con invitaciones pendientes o aceptadas para ese turno

    Ejemplos:
    - GET /players/search → Todos los jugadores
    - GET /players/search?q=Juan → Jugadores con "Juan" en nombre o apellido
    - GET /players/search?turn_id=123 → Jugadores disponibles para el turno 123 (excluyendo los ya invitados/aceptados)
    - GET /players/search?q=Juan&turn_id=123 → Jugadores con "Juan" disponibles para el turno 123
    """
    # IMPORTANTE: Permitir que todos los usuarios (incluidos jugadores normales) vean todos los jugadores disponibles
    # El token FCM se validará solo cuando se cree la invitación, no en la búsqueda
    # Esto permite que los jugadores vean a todos los jugadores disponibles y puedan elegir libremente
    # Las restricciones válidas (categoría, género para partidos mixtos) se aplican según el turno
    require_fcm_token = False  # No filtrar por token FCM en la búsqueda
    players = invitation_crud.search_players(
        db,
        q,
        current_user.id,
        turn_id=turn_id,
        require_fcm_token=require_fcm_token,
    )

    return [
        PlayerSearchResponse(
            id=player.id,
            name=player.name or "Sin nombre",
            last_name=player.last_name or "Sin apellido",
            email=player.email,
            phone=player.phone,
            profile_image_url=player.profile_image_url,
            level=player.level or "BEGINNER",
            preferred_side=player.preferred_side or "DRIVE",
            location=player.location,
            category=player.category,
            gender=player.gender,  # Incluir género para validación de partidos mixtos
        )
        for player in players
    ]
