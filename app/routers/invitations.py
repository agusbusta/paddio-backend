from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.services.auth import get_current_user
from app.models.user import User
from app.models.pregame_turn import PregameTurn, PregameTurnStatus
from app.models.invitation import Invitation
from app.schemas.invitation import (
    CreateInvitationRequest,
    RespondToInvitationRequest,
    InvitationResponse,
    PlayerSearchResponse,
    InvitationsListResponse,
)
from app.crud import invitation as invitation_crud
from app.utils.turn_utils import (
    count_players_in_turn,
    assign_player_to_turn,
    is_player_in_turn,
    can_invite_player_to_mixed_match,
    validate_mixed_match_gender_balance,
)
from app.utils.invitation_utils import filter_and_enrich_invitations
from app.services.notification_service import notification_service

router = APIRouter()


@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_invitations(
    request: CreateInvitationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Crear invitaciones para un turno
    Body: {
        "turn_id": int,
        "invited_player_ids": [int, int, int],  # Máximo 3
        "message": "string opcional"
    }
    """
    import logging

    logger = logging.getLogger(__name__)
    logger.info(
        f"Creating invitations for turn {request.turn_id} by user {current_user.id}"
    )

    # Verificar que el usuario sea un jugador
    if current_user.is_admin or current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los jugadores pueden crear invitaciones",
        )

    try:
        # Validar que el turno existe y pertenece al usuario
        turn = invitation_crud.get_turn_by_id(db, request.turn_id)
        if not turn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Turno no encontrado"
            )

        # CRÍTICO: Verificar que el turno no esté cancelado
        if turn.status == PregameTurnStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este turno fue cancelado. No se pueden enviar invitaciones a turnos cancelados.",
            )

        # CRÍTICO: Verificar si el usuario es el creador del turno o un jugador validado
        is_organizer = turn.player1_id == current_user.id
        is_validated_player = invitation_crud.is_player_validated(
            db, request.turn_id, current_user.id
        )

        if not is_organizer and not is_validated_player:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo el creador del turno o jugadores validados pueden invitar jugadores",
            )

        # CRÍTICO: Si es un jugador validado (no organizador), verificar límite de 1 invitación
        if is_validated_player and not is_organizer:
            validated_invitations_count = (
                invitation_crud.count_validated_invitations_sent(
                    db, request.turn_id, current_user.id
                )
            )
            if validated_invitations_count >= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Los jugadores validados solo pueden invitar a 1 persona. Ya has enviado tu invitación.",
                )

            # Validar que solo se intente invitar a 1 persona
            if len(request.invited_player_ids) > 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Los jugadores validados solo pueden invitar a 1 persona a la vez.",
                )

        # Validar que no se excedan 4 jugadores total
        current_players = count_players_in_turn(turn)

        # Obtener invitaciones pendientes para este turno
        pending_invitations = invitation_crud.get_pending_invitations_by_turn(
            db, request.turn_id
        )
        pending_invitations_count = len(pending_invitations)

        # Validar que el turno no esté completo (jugadores + invitaciones pendientes)
        if current_players + pending_invitations_count >= 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El turno ya está completo. Hay {current_players} jugadores confirmados y {pending_invitations_count} invitaciones pendientes. No se pueden enviar más invitaciones.",
            )

        # Validar que las nuevas invitaciones no excedan el límite
        if (
            current_players
            + pending_invitations_count
            + len(request.invited_player_ids)
            > 4
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se pueden invitar más jugadores. El turno tiene {current_players} jugadores confirmados y {pending_invitations_count} invitaciones pendientes. Solo se pueden invitar {4 - current_players - pending_invitations_count} jugador(es) más.",
            )

        # Validar que no se intenten invitar jugadores duplicados
        duplicate_players = []
        already_invited_players = []
        already_in_turn_players = []
        category_restriction_errors = (
            []
        )  # Jugadores que no cumplen con restricciones de categoría

        # Crear invitaciones
        invitations_created = []
        for player_id in request.invited_player_ids:
            # No invitar al mismo usuario
            if player_id == current_user.id:
                continue

            # Verificar que el jugador existe
            player = invitation_crud.get_user_by_id(db, player_id)
            if not player:
                continue

            # Verificar que no esté ya en el turno
            if is_player_in_turn(turn, player_id):
                already_in_turn_players.append(player.name or f"Jugador {player_id}")
                continue

            # Verificar que no esté ya invitado (PENDING o ACCEPTED)
            existing = invitation_crud.check_existing_invitation(
                db, request.turn_id, player_id
            )
            if existing:
                # Verificar el estado de la invitación existente
                existing_invitation = (
                    db.query(Invitation)
                    .filter(
                        and_(
                            Invitation.turn_id == request.turn_id,
                            Invitation.invited_player_id == player_id,
                        )
                    )
                    .first()
                )
                if existing_invitation:
                    if existing_invitation.status == "PENDING":
                        already_invited_players.append(
                            f"{player.name or f'Jugador {player_id}'} (pendiente)"
                        )
                    elif existing_invitation.status == "ACCEPTED":
                        already_invited_players.append(
                            f"{player.name or f'Jugador {player_id}'} (ya aceptó)"
                        )
                continue

            # CRÍTICO: Validar restricciones de categoría si el turno las tiene habilitadas
            # Verificar que category_restricted sea "true" (string) o True (boolean)
            is_category_restricted = (
                turn.category_restricted == "true" or turn.category_restricted is True
            )

            if (
                is_category_restricted
                and turn.category_restriction_type
                and turn.category_restriction_type != "NONE"
                and turn.organizer_category
            ):
                from app.utils.category_validator import CategoryRestrictionValidator

                player_category = (
                    player.category or "9na"
                )  # Default a 9na si no tiene categoría

                # Validar que la categoría del jugador cumpla con las restricciones
                can_join = CategoryRestrictionValidator.can_join_turn(
                    player_category,
                    turn.organizer_category,
                    turn.category_restriction_type,
                )

                if not can_join:
                    player_name = player.name or f"Jugador {player_id}"
                    category_restriction_errors.append(
                        f"{player_name} (categoría {player_category}) no corresponde a la categoría permitida para este turno (restricción: {turn.category_restriction_type}, categoría del organizador: {turn.organizer_category})"
                    )
                    logger.warning(
                        f"No se puede invitar a {player_id} (categoría {player_category}) al turno {request.turn_id} con restricción {turn.category_restriction_type} (categoría organizador: {turn.organizer_category})"
                    )
                    continue  # Saltar este jugador y continuar con el siguiente

            # CRÍTICO: Validar género para partidos mixtos
            if turn.is_mixed_match == "true":
                # Verificar que el jugador tenga género asignado
                if not player.gender or player.gender not in ["Masculino", "Femenino"]:
                    player_name = player.name or f"Jugador {player_id}"
                    category_restriction_errors.append(
                        f"{player_name} no tiene género asignado. Los partidos mixtos requieren que todos los jugadores tengan género definido."
                    )
                    logger.warning(
                        f"No se puede invitar a {player_id} al turno mixto {request.turn_id}: no tiene género asignado"
                    )
                    continue  # Saltar este jugador y continuar con el siguiente

                can_invite, error_message = can_invite_player_to_mixed_match(
                    db, turn, player.gender
                )
                if not can_invite:
                    player_name = player.name or f"Jugador {player_id}"
                    category_restriction_errors.append(
                        f"{player_name} ({player.gender}): {error_message}"
                    )
                    logger.warning(
                        f"No se puede invitar a {player_id} al turno mixto {request.turn_id}: {error_message}"
                    )
                    continue  # Saltar este jugador y continuar con el siguiente

            from app.schemas.invitation import InvitationCreate

            # CRÍTICO: Marcar como invitación validada si el invitador es un jugador validado
            is_validated = is_validated_player and not is_organizer

            invitation_data = InvitationCreate(
                turn_id=request.turn_id,
                inviter_id=current_user.id,
                invited_player_id=player_id,
                message=request.message,
                is_validated_invitation=is_validated,  # Marcar si viene de jugador validado
            )

            invitation = invitation_crud.create_invitation(db, invitation_data)
            invitations_created.append(invitation)

            # Enviar notificación push al invitado
            try:
                notification_service.notify_turn_invitation(
                    db=db,
                    invitation_id=invitation.id,
                    inviter_name=current_user.name,
                    club_name=turn.court.club.name,
                    turn_time=turn.start_time,
                    turn_date=turn.date.strftime("%Y-%m-%d"),
                )
            except Exception as e:
                logger.error(f"Error enviando notificación de invitación: {e}")

            # Notificar al resto del turno: "Juan invitó a Pedro al turno" (trazabilidad)
            try:
                from app.utils.notification_utils import (
                    notify_turn_participants_player_invited,
                )

                notify_turn_participants_player_invited(
                    db=db,
                    turn=turn,
                    inviter_name=current_user.name or "Un jugador",
                    invited_player_name=player.name or f"Jugador {player_id}",
                    club_name=turn.court.club.name,
                    turn_time=turn.start_time,
                    inviter_id=current_user.id,
                )
            except Exception as e:
                logger.error(f"Error notificando al turno sobre invitación: {e}")

        # Si no se creó ninguna invitación, verificar por qué
        if len(invitations_created) == 0:
            error_messages = []
            if already_in_turn_players:
                error_messages.append(
                    f"Los siguientes jugadores ya están en el turno: {', '.join(already_in_turn_players)}"
                )
            if already_invited_players:
                error_messages.append(
                    f"Los siguientes jugadores ya tienen invitaciones: {', '.join(already_invited_players)}"
                )
            if category_restriction_errors:
                error_messages.append(
                    f"Restricciones de categoría: {'; '.join(category_restriction_errors)}"
                )
            if duplicate_players:
                error_messages.append(
                    f"Se intentó invitar jugadores duplicados: {', '.join(duplicate_players)}"
                )

            if error_messages:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No se pudieron crear invitaciones. "
                    + " ".join(error_messages),
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No se pudieron crear invitaciones. Verifica que los jugadores seleccionados sean válidos.",
                )

        # Si se crearon menos invitaciones de las solicitadas, informar
        if len(invitations_created) < len(request.invited_player_ids):
            warning_messages = []
            if already_in_turn_players:
                warning_messages.append(
                    f"{len(already_in_turn_players)} ya están en el turno"
                )
            if already_invited_players:
                warning_messages.append(
                    f"{len(already_invited_players)} ya tienen invitaciones"
                )
            if category_restriction_errors:
                warning_messages.append(
                    f"{len(category_restriction_errors)} no cumplen con las restricciones de categoría"
                )

            return {
                "success": True,
                "message": f"Invitaciones enviadas a {len(invitations_created)} jugador(es). "
                + (
                    "Advertencia: " + "; ".join(warning_messages)
                    if warning_messages
                    else ""
                ),
                "invitations_created": len(invitations_created),
                "warnings": warning_messages if warning_messages else None,
            }

        return {
            "success": True,
            "message": f"Invitaciones enviadas a {len(invitations_created)} jugador(es)",
            "invitations_created": len(invitations_created),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating invitations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor",
        )


@router.get("/received", response_model=InvitationsListResponse)
async def get_received_invitations(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Obtener invitaciones recibidas por el usuario actual
    """
    invitations = invitation_crud.get_received_invitations(db, current_user.id)

    # Filtrar y enriquecer invitaciones usando función helper
    enriched_invitations = filter_and_enrich_invitations(db, invitations)

    return InvitationsListResponse(
        success=True,
        invitations=enriched_invitations,
        total_count=len(enriched_invitations),
    )


@router.get("/sent", response_model=InvitationsListResponse)
async def get_sent_invitations(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Obtener invitaciones enviadas por el usuario actual
    """
    invitations = invitation_crud.get_sent_invitations(db, current_user.id)

    # Filtrar y enriquecer invitaciones usando función helper
    # IMPORTANTE: Solo mostrar invitaciones con estado actual válido:
    # - PENDING: Invitaciones pendientes
    # - ACCEPTED: Solo si el jugador realmente está en el turno
    # - DECLINED y CANCELLED: No se muestran (solo se notifican, no aparecen en la lista)
    enriched_invitations = filter_and_enrich_invitations(db, invitations)

    return InvitationsListResponse(
        success=True,
        invitations=enriched_invitations,
        total_count=len(enriched_invitations),
    )


@router.get("/turn/{turn_id}", response_model=InvitationsListResponse)
async def get_invitations_by_turn(
    turn_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Obtener todas las invitaciones de un turno específico.
    Permite a cualquier usuario ver quiénes fueron invitados y su estado.
    Incluye solicitudes externas pendientes.
    """
    # Verificar que el turno existe
    from app.crud import pregame_turn as pregame_turn_crud

    turn = pregame_turn_crud.get_pregame_turn(db, turn_id)
    if not turn:
        raise HTTPException(
            status_code=404,
            detail="Turn not found",
        )

    # Obtener todas las invitaciones del turno (incluyendo solicitudes externas)
    invitations = invitation_crud.get_invitations_by_turn(db, turn_id)

    # Filtrar y enriquecer invitaciones usando función helper
    # IMPORTANTE: Solo mostrar invitaciones con estado actual válido:
    # - PENDING: Invitaciones pendientes (incluyendo solicitudes externas)
    # - ACCEPTED: Solo si el jugador realmente está en el turno
    # - DECLINED y CANCELLED: No se muestran (solo se notifican, no aparecen en la lista)
    enriched_invitations = filter_and_enrich_invitations(db, invitations, turn)

    return InvitationsListResponse(
        success=True,
        invitations=enriched_invitations,
        total_count=len(enriched_invitations),
    )


@router.get("/turn/{turn_id}/external-requests", response_model=InvitationsListResponse)
async def get_external_requests_by_turn(
    turn_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Obtener solo las solicitudes externas pendientes de un turno.
    Solo el configurador puede ver estas solicitudes.
    """
    # Verificar que el turno existe
    from app.crud import pregame_turn as pregame_turn_crud

    turn = pregame_turn_crud.get_pregame_turn(db, turn_id)
    if not turn:
        raise HTTPException(
            status_code=404,
            detail="Turn not found",
        )

    # Verificar que el usuario sea el configurador
    if turn.player1_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Solo el configurador del turno puede ver las solicitudes externas",
        )

    # Obtener solo las solicitudes externas pendientes
    external_requests = (
        db.query(Invitation)
        .filter(
            and_(
                Invitation.turn_id == turn_id,
                Invitation.is_external_request == True,
                Invitation.status == "PENDING",
            )
        )
        .all()
    )

    # Enriquecer solicitudes
    enriched_requests = filter_and_enrich_invitations(db, external_requests, turn)

    return InvitationsListResponse(
        success=True,
        invitations=enriched_requests,
        total_count=len(enriched_requests),
    )


@router.put("/{invitation_id}/respond")
async def respond_to_invitation(
    invitation_id: int,
    request: RespondToInvitationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Responder a una invitación
    Body: {
        "status": "ACCEPTED" | "DECLINED",
        "player_side": "reves" | "drive" (solo si ACCEPTED),
        "player_court_position": "izquierda" | "derecha" (solo si ACCEPTED)
    }
    """
    invitation = invitation_crud.get_invitation(db, invitation_id)

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invitación no encontrada"
        )

    if invitation.invited_player_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el jugador invitado puede responder",
        )

    if invitation.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta invitación ya fue respondida",
        )

    # CRÍTICO: BLOQUEO DE CONCURRENCIA
    # Obtener el turno con bloqueo de fila para evitar condiciones de carrera
    # Esto asegura que solo un usuario pueda aceptar la invitación a la vez
    from sqlalchemy import and_

    turn = (
        db.query(PregameTurn)
        .filter(PregameTurn.id == invitation.turn_id)
        .with_for_update(
            nowait=False
        )  # BLOQUEO DE FILA - previene condiciones de carrera
        .first()
    )

    if not turn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El turno asociado a esta invitación no existe",
        )

    # CRÍTICO: Validar nuevamente el estado del turno justo antes de actualizar
    # Refrescar el turno y re-bloquearlo para obtener el estado más reciente
    db.refresh(turn)

    # CRÍTICO: Re-bloquear el turno después del refresh para asegurar consistencia
    # Esto previene que otro usuario modifique el turno entre el refresh y la actualización
    locked_turn = (
        db.query(PregameTurn)
        .filter(PregameTurn.id == turn.id)
        .with_for_update(nowait=False)
        .first()
    )

    if not locked_turn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El turno ya no existe o fue cancelado.",
        )

    turn = locked_turn
    current_players = count_players_in_turn(turn)

    # CRÍTICO: Validar que el turno no esté cancelado
    if turn.status == PregameTurnStatus.CANCELLED:
        cancellation_message = (
            turn.cancellation_message or "El organizador canceló el turno"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Este turno fue cancelado. {cancellation_message}",
        )

    # CRÍTICO: Si la invitación es de un jugador validado, aceptarla automáticamente
    # Esto permite que las duplas se sumen sin necesidad de aprobación adicional
    if invitation.is_validated_invitation and request.status == "ACCEPTED":
        # Las invitaciones validadas se aceptan automáticamente sin validaciones adicionales
        # excepto las validaciones básicas de capacidad y restricciones
        pass

    if request.status == "ACCEPTED":
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
            .filter(PregameTurn.date == turn.date)
            .filter(PregameTurn.start_time == turn.start_time)
            .filter(
                PregameTurn.status.in_(
                    [PregameTurnStatus.PENDING, PregameTurnStatus.READY_TO_PLAY]
                )
            )
            .filter(
                PregameTurn.id != turn.id
            )  # Excluir el turno actual de la invitación
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
            court_name = (
                existing_turn.court.name if existing_turn.court else "una cancha"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya tenés una reserva activa en este horario ({turn.start_time}) en {court_name} de {club_name}. No podés estar en dos canchas al mismo tiempo.",
            )

        # CRÍTICO: Validar nuevamente que el turno no esté completo
        # Esto previene que dos usuarios acepten invitaciones simultáneamente
        if current_players >= 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El turno ya está completo. No hay lugares disponibles.",
            )

        # CRÍTICO: Verificar que el jugador no esté ya en el turno
        if (
            turn.player1_id == current_user.id
            or turn.player2_id == current_user.id
            or turn.player3_id == current_user.id
            or turn.player4_id == current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya estás en este turno.",
            )

        # Validar posición
        if not request.player_side or not request.player_court_position:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe especificar lado y posición para aceptar",
            )

        # CRÍTICO: Validar restricciones de categoría si el turno las tiene habilitadas
        # Verificar que category_restricted sea "true" (string) o True (boolean)
        is_category_restricted = (
            turn.category_restricted == "true" or turn.category_restricted is True
        )

        if (
            is_category_restricted
            and turn.category_restriction_type
            and turn.category_restriction_type != "NONE"
            and turn.organizer_category
        ):
            from app.utils.category_validator import CategoryRestrictionValidator

            player_category = (
                current_user.category or "9na"
            )  # Default a 9na si no tiene categoría

            # Validar que la categoría del jugador cumpla con las restricciones
            can_join = CategoryRestrictionValidator.can_join_turn(
                player_category,
                turn.organizer_category,
                turn.category_restriction_type,
            )

            if not can_join:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"No podés aceptar esta invitación. Tu categoría ({player_category}) no cumple con las restricciones del turno (restricción: {turn.category_restriction_type}, categoría del organizador: {turn.organizer_category}).",
                )

        # Validar paridad de géneros para partidos mixtos
        if turn.is_mixed_match == "true":
            # CRÍTICO: Excluir la invitación actual de las pendientes porque se está aceptando
            # Si no, se contaría dos veces (como pendiente y como nuevo jugador)
            is_valid, error_message = validate_mixed_match_gender_balance(
                db,
                turn,
                current_user.gender,
                check_pending_invitations=True,
                exclude_invitation_id=invitation.id,  # Excluir esta invitación del conteo
            )
            if not is_valid:
                # Mejorar mensaje de error para que sea más claro
                if "2 hombres y 2 mujeres" in error_message or "2-2" in error_message:
                    gender_text = (
                        "masculino"
                        if current_user.gender == "Masculino"
                        else "femenino"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"No se puede confirmar tu participación. El cupo para jugadores {gender_text} ya está completo (2/2). Otro jugador ya aceptó una invitación antes que vos.",
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"No se puede confirmar tu participación. {error_message}",
                    )

            # CRÍTICO: Validar que el lado seleccionado no tenga ya un jugador del mismo género
            # Esta validación es esencial para mantener la regla de 1M+1F por lado
            if request.player_side:
                from app.utils.turn_utils import (
                    validate_mixed_match_side_gender_balance,
                )

                is_valid_side, error_message_side = (
                    validate_mixed_match_side_gender_balance(
                        db, turn, current_user.gender, request.player_side
                    )
                )
                if not is_valid_side:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=error_message_side,
                    )

        # Asignar jugador al turno
        success = assign_player_to_turn(
            db, turn, current_user, request.player_side, request.player_court_position
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error asignando jugador al turno",
            )

    # Actualizar invitación
    from app.schemas.invitation import InvitationUpdate

    invitation_update = InvitationUpdate(
        status=request.status, responded_at=datetime.utcnow()
    )

    invitation_crud.update_invitation(db, invitation_id, invitation_update)

    # Si aceptó y el turno quedó completo (4 jugadores), notificar a todos
    if request.status == "ACCEPTED":
        db.refresh(turn)
        if count_players_in_turn(turn) == 4 and turn.status == PregameTurnStatus.READY_TO_PLAY:
            try:
                club_name = turn.court.club.name if turn.court and turn.court.club else "Club"
                notification_service.notify_turn_complete(
                    db=db,
                    turn_id=turn.id,
                    club_name=club_name,
                    start_time=turn.start_time or "",
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error enviando notificación de turno completo: {e}")

    # Enviar notificación al invitador
    try:
        notification_service.notify_invitation_response(
            db=db,
            invitation_id=invitation.id,
            responder_name=current_user.name or "Un jugador",
            response_status=request.status,
            club_name=turn.court.club.name,
            turn_time=turn.start_time,
        )
    except Exception as e:
        # Log el error pero no fallar la operación principal
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error enviando notificación de respuesta: {e}")

    # Si rechazó: notificar también al organizador y a todos los que ya aceptaron el turno
    if request.status == "DECLINED":
        try:
            from app.utils.notification_utils import (
                notify_invitation_declined_to_turn_participants,
            )

            notify_invitation_declined_to_turn_participants(
                db=db,
                turn=turn,
                decliner_name=current_user.name or "Un jugador",
                club_name=turn.court.club.name,
                turn_time=turn.start_time,
                decliner_id=current_user.id,
                inviter_id=invitation.inviter_id,
            )
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error enviando notificación de rechazo a participantes: {e}")

    return {
        "success": True,
        "message": f"Invitación {request.status.lower()}",
        "status": request.status,
    }


@router.put("/{invitation_id}/approve")
async def approve_external_request(
    invitation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Aprobar una solicitud externa (solo el configurador puede aprobar)
    Cuando se aprueba, se crea una invitación normal que el jugador puede aceptar
    """
    invitation = invitation_crud.get_invitation(db, invitation_id)

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud no encontrada",
        )

    # Verificar que sea una solicitud externa
    if not invitation.is_external_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta no es una solicitud externa",
        )

    # Verificar que el usuario sea el configurador del turno
    from app.crud import pregame_turn as pregame_turn_crud

    turn = pregame_turn_crud.get_pregame_turn(db, invitation.turn_id)

    if not turn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Turno no encontrado",
        )

    if turn.player1_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el configurador del turno puede aprobar solicitudes externas",
        )

    # Verificar que la solicitud esté pendiente
    if invitation.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta solicitud ya fue procesada",
        )

    # Verificar que el turno no esté completo
    current_players = count_players_in_turn(turn)
    if current_players >= 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El turno ya está completo. No se pueden aprobar más solicitudes.",
        )

    # Convertir la solicitud externa en una invitación normal
    # Cambiar el inviter_id al configurador (ya debería estar así, pero por seguridad)
    from app.schemas.invitation import InvitationUpdate

    invitation_update = InvitationUpdate(
        inviter_id=turn.player1_id,  # Asegurar que el configurador es el invitador
        is_external_request=False,  # Ya no es una solicitud externa, es una invitación normal
    )

    invitation_crud.update_invitation(db, invitation_id, invitation_update)

    # Refrescar la invitación actualizada
    db.refresh(invitation)

    # Enviar notificación de invitación normal al jugador (como si fuera una invitación normal)
    try:
        requesting_player = (
            db.query(User).filter(User.id == invitation.invited_player_id).first()
        )
        organizer = db.query(User).filter(User.id == turn.player1_id).first()

        if requesting_player and organizer:
            # Enviar notificación como invitación normal
            notification_service.notify_turn_invitation(
                db=db,
                invitation_id=invitation_id,
                inviter_name=organizer.name or "El configurador",
                club_name=(
                    turn.court.club.name if turn.court and turn.court.club else "Club"
                ),
                turn_time=turn.start_time,
                turn_date=turn.date.strftime("%Y-%m-%d"),
            )
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error enviando notificación de invitación: {e}")

    return {
        "success": True,
        "message": "Solicitud aprobada. El jugador recibirá una invitación que puede aceptar.",
        "invitation_id": invitation_id,
    }


@router.put("/{invitation_id}/reject")
async def reject_external_request(
    invitation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Rechazar una solicitud externa (solo el configurador puede rechazar)
    """
    invitation = invitation_crud.get_invitation(db, invitation_id)

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud no encontrada",
        )

    # Verificar que sea una solicitud externa
    if not invitation.is_external_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta no es una solicitud externa",
        )

    # Verificar que el usuario sea el configurador del turno
    from app.crud import pregame_turn as pregame_turn_crud

    turn = pregame_turn_crud.get_pregame_turn(db, invitation.turn_id)

    if not turn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Turno no encontrado",
        )

    if turn.player1_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el configurador del turno puede rechazar solicitudes externas",
        )

    # Marcar como rechazada
    from app.schemas.invitation import InvitationUpdate

    invitation_update = InvitationUpdate(status="DECLINED")
    invitation_crud.update_invitation(db, invitation_id, invitation_update)

    # Enviar notificación al jugador que solicitó
    try:
        from app.utils.notification_utils import send_notification_with_fcm

        requesting_player = (
            db.query(User).filter(User.id == invitation.invited_player_id).first()
        )
        if requesting_player:
            send_notification_with_fcm(
                db=db,
                user_id=requesting_player.id,
                title="Tu solicitud fue rechazada",
                message=f"El configurador rechazó tu solicitud para el turno de las {turn.start_time}.",
                notification_type="external_request_rejected",
                data={
                    "turn_id": turn.id,
                    "invitation_id": invitation_id,
                    "club_name": (
                        turn.court.club.name
                        if turn.court and turn.court.club
                        else "Club"
                    ),
                    "start_time": turn.start_time,
                },
            )
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error enviando notificación de rechazo: {e}")

    return {
        "success": True,
        "message": "Solicitud rechazada",
        "invitation_id": invitation_id,
    }


@router.delete("/{invitation_id}")
async def cancel_invitation(
    invitation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cancelar una invitación.
    Puede cancelar:
    - El invitador (inviter_id)
    - El organizador del turno (player1_id del turno)
    - El administrador del club al que pertenece el turno
    """
    invitation = invitation_crud.get_invitation(db, invitation_id)

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invitación no encontrada"
        )

    if invitation.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden cancelar invitaciones pendientes",
        )

    # Verificar permisos: invitador, organizador del turno, o administrador del club
    can_cancel = False

    # 1. Verificar si es el invitador
    if invitation.inviter_id == current_user.id:
        can_cancel = True
    else:
        # 2. Obtener el turno para verificar si es organizador o admin del club
        from app.crud import pregame_turn as pregame_turn_crud
        from sqlalchemy.orm import joinedload
        from app.models.pregame_turn import PregameTurn

        # Cargar el turno con las relaciones necesarias
        turn = (
            db.query(PregameTurn)
            .options(joinedload(PregameTurn.court))
            .filter(PregameTurn.id == invitation.turn_id)
            .first()
        )

        if turn:
            # 3. Verificar si es el organizador del turno (player1_id)
            if turn.player1_id == current_user.id:
                can_cancel = True
            else:
                # 4. Verificar si es administrador del club del turno
                club_id = None

                # Intentar obtener club_id desde la cancha (relación directa)
                if turn.court:
                    club_id = turn.court.club_id
                else:
                    # Si no está cargada la relación, obtener desde el turn template
                    from app.crud import turn as turn_crud

                    turn_template = turn_crud.get_turn(db, turn.turn_id)
                    if turn_template:
                        club_id = turn_template.club_id

                # Verificar si el usuario es admin del club del turno
                if (
                    club_id
                    and current_user.is_admin
                    and current_user.club_id == club_id
                ):
                    can_cancel = True

    if not can_cancel:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para cancelar esta invitación. Solo el invitador, el organizador del turno o el administrador del club pueden cancelarla.",
        )

    from app.schemas.invitation import InvitationUpdate

    invitation_update = InvitationUpdate(status="CANCELLED")
    invitation_crud.update_invitation(db, invitation_id, invitation_update)

    return {"success": True, "message": "Invitación cancelada"}


@router.get("/turn/{turn_id}/can-invite")
async def can_invite_to_turn(
    turn_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verificar si el usuario actual puede invitar jugadores a un turno.
    Retorna información sobre si es organizador, si está validado, y cuántas invitaciones puede enviar.
    """
    # Verificar que el turno existe
    from app.crud import pregame_turn as pregame_turn_crud

    turn = pregame_turn_crud.get_pregame_turn(db, turn_id)
    if not turn:
        raise HTTPException(
            status_code=404,
            detail="Turn not found",
        )

    # CRÍTICO: Verificar que el turno esté en un estado válido para invitar
    # Solo se puede invitar si el turno está en PENDING o READY_TO_PLAY
    if turn.status in [PregameTurnStatus.CANCELLED, PregameTurnStatus.COMPLETED]:
        return {
            "can_invite": False,
            "is_organizer": False,
            "is_validated": False,
            "validated_invitations_sent": 0,
            "remaining_invitations": 0,
            "max_invitations": None,
        }

    # Verificar si es organizador
    is_organizer = turn.player1_id == current_user.id

    # Verificar si está validado
    is_validated = invitation_crud.is_player_validated(db, turn_id, current_user.id)

    # Contar invitaciones validadas enviadas
    validated_invitations_sent = 0
    can_invite = False
    remaining_invitations = 0

    if is_organizer:
        # El organizador puede invitar sin límite (hasta completar el turno)
        # CRÍTICO: El organizador puede invitar incluso si hay invitaciones pendientes
        # porque esas invitaciones pueden ser rechazadas
        current_players = count_players_in_turn(turn)
        # CRÍTICO: Calcular lugares disponibles basándose solo en jugadores confirmados
        # Las invitaciones pendientes no bloquean nuevas invitaciones del organizador
        # Solo permitir invitar si hay lugares disponibles (menos de 4 jugadores)
        can_invite = current_players < 4
        remaining_invitations = max(0, 4 - current_players)
    elif is_validated:
        # Jugador validado puede invitar a 1 persona
        validated_invitations_sent = invitation_crud.count_validated_invitations_sent(
            db, turn_id, current_user.id
        )
        current_players = count_players_in_turn(turn)
        # Solo permitir invitar si hay lugares disponibles y no ha alcanzado su límite
        can_invite = validated_invitations_sent < 1 and current_players < 4
        remaining_invitations = (
            1 - validated_invitations_sent if current_players < 4 else 0
        )

    return {
        "can_invite": can_invite,
        "is_organizer": is_organizer,
        "is_validated": is_validated,
        "validated_invitations_sent": validated_invitations_sent,
        "remaining_invitations": remaining_invitations,
        "max_invitations": (
            1 if is_validated and not is_organizer else None
        ),  # None = sin límite
    }


@router.get("/players/search", response_model=List[PlayerSearchResponse])
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
    - GET /invitations/players/search → Todos los jugadores
    - GET /invitations/players/search?q=Juan → Jugadores con "Juan" en nombre o apellido
    - GET /invitations/players/search?turn_id=123 → Jugadores disponibles para el turno 123 (excluyendo los ya invitados/aceptados)
    - GET /invitations/players/search?q=Juan&turn_id=123 → Jugadores con "Juan" disponibles para el turno 123
    """
    players = invitation_crud.search_players(db, q, current_user.id, turn_id=turn_id)

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
        )
        for player in players
    ]
