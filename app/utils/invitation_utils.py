"""
Utilidades para el manejo de invitaciones.
Centraliza la lógica común para evitar redundancias.
"""

from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.invitation import Invitation
from app.models.pregame_turn import PregameTurn
from app.schemas.invitation import InvitationResponse, InvitationUpdate
from app.crud import invitation as invitation_crud
from app.utils.turn_utils import is_player_in_turn
import logging

logger = logging.getLogger(__name__)


def validate_and_cleanup_accepted_invitation(
    db: Session, invitation: Invitation, turn: PregameTurn
) -> bool:
    """
    Valida que una invitación ACCEPTED corresponda a un jugador realmente en el turno.
    Si no está, actualiza la invitación a CANCELLED.

    Args:
        db: Sesión de base de datos
        invitation: Invitación a validar
        turn: Turno relacionado

    Returns:
        bool: True si la invitación es válida y debe mostrarse, False si fue cancelada
    """
    if invitation.status != "ACCEPTED":
        return True  # No es ACCEPTED, no necesita validación especial

    # Verificar si el jugador realmente está en el turno
    if not is_player_in_turn(turn, invitation.invited_player_id):
        # El jugador no está en el turno, cancelar la invitación
        try:
            invitation_update = InvitationUpdate(status="CANCELLED")
            invitation_crud.update_invitation(db, invitation.id, invitation_update)
            logger.info(
                f"Invitación {invitation.id} cancelada automáticamente: jugador {invitation.invited_player_id} no está en el turno {turn.id}"
            )
        except Exception as e:
            logger.error(f"Error cancelando invitación {invitation.id}: {e}")
        return False  # No mostrar esta invitación

    return True  # Invitación válida


def should_show_invitation(invitation: Invitation) -> bool:
    """
    Determina si una invitación debe mostrarse en las listas.

    Reglas:
    - PENDING: Siempre se muestra
    - ACCEPTED: Se valida con validate_and_cleanup_accepted_invitation
    - DECLINED y CANCELLED: No se muestran (solo se notifican)

    Args:
        invitation: Invitación a evaluar

    Returns:
        bool: True si debe mostrarse, False en caso contrario
    """
    # Filtrar invitaciones DECLINED y CANCELLED - no se muestran
    if invitation.status in ["DECLINED", "CANCELLED"]:
        return False

    return True  # PENDING o ACCEPTED (ACCEPTED se valida después)


def enrich_invitation_response(
    invitation: Invitation, turn: Optional[PregameTurn] = None
) -> InvitationResponse:
    """
    Enriquece una invitación con información del turno y club.

    Args:
        invitation: Invitación a enriquecer
        turn: Turno relacionado (si no se proporciona, se obtiene de invitation.turn)

    Returns:
        InvitationResponse: Respuesta enriquecida
    """
    if turn is None:
        turn = invitation.turn

    club = turn.court.club

    # Obtener género del jugador invitado para validación de partidos mixtos
    invited_player_gender = None
    if invitation.invited_player:
        invited_player_gender = invitation.invited_player.gender

    # Obtener mensaje de cancelación del turno si está cancelado
    turn_cancellation_message = None
    if turn.status.value == "CANCELLED" and turn.cancellation_message:
        turn_cancellation_message = turn.cancellation_message

    return InvitationResponse(
        id=invitation.id,
        turn_id=invitation.turn_id,
        inviter_id=invitation.inviter_id,
        inviter_name=(
            invitation.inviter.name.split()[0] if invitation.inviter.name else "Unknown"
        ),
        inviter_last_name=(
            invitation.inviter.last_name.split()[0]
            if invitation.inviter.last_name
            else ""
        ),
        invited_player_id=invitation.invited_player_id,
        invited_player_name=(
            invitation.invited_player.name.split()[0]
            if invitation.invited_player.name
            else "Unknown"
        ),
        invited_player_last_name=(
            invitation.invited_player.last_name.split()[0]
            if invitation.invited_player.last_name
            else ""
        ),
        status=invitation.status,
        created_at=invitation.created_at,
        responded_at=invitation.responded_at,
        message=invitation.message,
        club_name=club.name,
        court_name=turn.court.name,
        turn_date=turn.date.strftime("%Y-%m-%d"),
        turn_time=turn.start_time,
        price=turn.price,
        is_indoor=turn.court.is_indoor,
        has_lighting=turn.court.has_lighting,
        invited_player_gender=invited_player_gender,  # Agregar género para validación
        is_external_request=invitation.is_external_request,  # Marcar si es solicitud externa
        turn_cancellation_message=turn_cancellation_message,  # Mensaje de cancelación del organizador
        is_mixed_match=(turn.is_mixed_match == "true"),
        category_restricted=(turn.category_restricted == "true"),
        category_restriction_type=turn.category_restriction_type,
        organizer_category=turn.organizer_category,
        free_category=turn.free_category,
    )


def filter_and_enrich_invitations(
    db: Session, invitations: List[Invitation], turn: Optional[PregameTurn] = None
) -> List[InvitationResponse]:
    """
    Filtra y enriquece una lista de invitaciones.

    Aplica las reglas de filtrado y validación, y enriquece las invitaciones válidas.

    Args:
        db: Sesión de base de datos
        invitations: Lista de invitaciones a procesar
        turn: Turno relacionado (si no se proporciona, se obtiene de cada invitation.turn)

    Returns:
        List[InvitationResponse]: Lista de invitaciones enriquecidas y validadas
    """
    enriched_invitations = []

    for invitation in invitations:
        # Obtener el turno si no se proporcionó
        current_turn = turn if turn is not None else invitation.turn

        # Verificar si debe mostrarse
        if not should_show_invitation(invitation):
            continue

        # Validar y limpiar invitaciones ACCEPTED
        if not validate_and_cleanup_accepted_invitation(db, invitation, current_turn):
            continue  # La invitación fue cancelada, no incluirla

        # Enriquecer y agregar
        enriched_invitations.append(
            enrich_invitation_response(invitation, current_turn)
        )

    return enriched_invitations
