from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from app.models.pregame_turn import PregameTurn
from app.models.invitation import Invitation
from app.crud import pregame_turn as pregame_turn_crud
from app.crud import invitation as invitation_crud
from app.utils.notification_utils import notify_turn_cancelled, notify_player_left
import logging

logger = logging.getLogger(__name__)


def cancel_complete_turn(
    db: Session,
    turn_id: int,
    organizer_id: int,
    cancellation_message: Optional[str] = None,
) -> dict:
    """
    Cancela el turno completo cuando el organizador se retira.

    Args:
        db: Sesión de base de datos
        turn_id: ID del turno a cancelar
        organizer_id: ID del organizador que cancela
        cancellation_message: Mensaje opcional del organizador explicando la cancelación

    Returns:
        dict: Información sobre la cancelación
    """
    # 1. Obtener el turno
    turn = pregame_turn_crud.get_pregame_turn(db, turn_id)
    if not turn:
        raise ValueError(f"Turno {turn_id} no encontrado")

    # CRÍTICO: Verificar que el turno no esté ya cancelado
    from app.models.pregame_turn import PregameTurnStatus
    if turn.status == PregameTurnStatus.CANCELLED:
        raise ValueError("Este turno ya fue cancelado y no se puede cancelar nuevamente.")

    # 2. Obtener todos los jugadores del turno
    affected_players = []
    if turn.player1_id:
        affected_players.append(turn.player1_id)
    if turn.player2_id:
        affected_players.append(turn.player2_id)
    if turn.player3_id:
        affected_players.append(turn.player3_id)
    if turn.player4_id:
        affected_players.append(turn.player4_id)

    # 3. Obtener todas las invitaciones pendientes
    pending_invitations = invitation_crud.get_pending_invitations_by_turn(db, turn_id)

    # 4. Cancelar todas las invitaciones pendientes con el mensaje del organizador
    cancelled_invitations = 0
    for invitation in pending_invitations:
        try:
            # Cancelar invitación y guardar el mensaje de cancelación del organizador
            from app.schemas.invitation import InvitationUpdate

            invitation_update = InvitationUpdate(status="CANCELLED")
            # Nota: El mensaje de cancelación del organizador se guarda en el turno, no en la invitación
            # pero podemos incluirlo en el mensaje de notificación
            invitation_crud.update_invitation(db, invitation.id, invitation_update)
            cancelled_invitations += 1
        except Exception as e:
            logger.error(f"Error cancelando invitación {invitation.id}: {e}")

    # 5. Limpiar el turno (eliminar todos los jugadores) y guardar mensaje de cancelación
    from app.schemas.pregame_turn import PregameTurnUpdate

    update_data = PregameTurnUpdate(
        player1_id=None,
        player1_side=None,
        player1_court_position=None,
        player2_id=None,
        player2_side=None,
        player2_court_position=None,
        player3_id=None,
        player3_side=None,
        player3_court_position=None,
        player4_id=None,
        player4_side=None,
        player4_court_position=None,
        status="CANCELLED",  # CRÍTICO: Marcar como cancelado para que no se cuente como ocupado
        category_restricted=False,
        category_restriction_type="NONE",
        organizer_category=None,
        cancellation_message=cancellation_message,  # Guardar mensaje del organizador
    )

    updated_turn = pregame_turn_crud.update_pregame_turn(db, turn_id, update_data)
    if not updated_turn:
        raise ValueError(f"Error actualizando turno {turn_id}")

    # 6. Enviar notificaciones a todos los afectados
    notifications_sent = 0

    # Construir mensaje de notificación
    base_reason = "El organizador canceló el turno"
    if cancellation_message and cancellation_message.strip():
        notification_reason = f"{base_reason}. Motivo: {cancellation_message.strip()}"
    else:
        notification_reason = base_reason

    # Obtener información del club
    club_name = (
        turn.court.club.name
        if turn.court and turn.court.club
        else "Club"
    )
    club_id = (
        turn.court.club.id
        if turn.court and turn.court.club
        else None
    )

    # Notificar a todos los jugadores del turno (push + BD) excepto al organizador
    other_players = [p for p in affected_players if p != organizer_id]
    if other_players:
        try:
            notify_turn_cancelled(
                db=db,
                turn_id=turn_id,
                club_name=club_name,
                start_time=turn.start_time,
                player_ids=other_players,
                reason=notification_reason,
            )
            notifications_sent += len(other_players)
        except Exception as e:
            logger.error(f"Error enviando notificaciones de cancelación a jugadores: {e}")

    # Confirmación al organizador (push + BD) para que vea que la acción se aplicó
    try:
        from app.utils.notification_utils import send_notification_with_fcm
        send_notification_with_fcm(
            db=db,
            user_id=organizer_id,
            title="Turno cancelado",
            message="Has cancelado el turno. Se notificó a los jugadores.",
            notification_type="turn_cancelled_by_you",
            data={
                "turn_id": str(turn_id),
                "club_name": club_name or "",
                "start_time": turn.start_time or "",
            },
        )
        notifications_sent += 1
    except Exception as e:
        logger.error(f"Error enviando confirmación de cancelación al organizador: {e}")

    # Notificar al administrador del club
    if club_id:
        try:
            from app.models.user import User
            from app.utils.notification_utils import send_notification_with_fcm

            # Buscar el administrador del club
            club_admin = (
                db.query(User)
                .filter(User.club_id == club_id, User.is_admin == True)
                .first()
            )

            if club_admin:
                # Obtener información del organizador
                from app.crud import user as user_crud
                organizer = user_crud.get_user(db, organizer_id)
                organizer_name = organizer.name if organizer else "Un jugador"

                # Enviar notificación al admin del club
                send_notification_with_fcm(
                    db=db,
                    user_id=club_admin.id,
                    title="Turno cancelado",
                    message=f"{organizer_name} canceló un turno de las {turn.start_time} en {club_name}. {notification_reason}",
                    notification_type="turn_cancelled",
                    data={
                        "turn_id": str(turn_id),
                        "club_name": club_name,
                        "club_id": str(club_id),
                        "start_time": turn.start_time,
                        "date": turn.date.isoformat() if turn.date else None,
                        "organizer_id": str(organizer_id),
                        "organizer_name": organizer_name,
                        "reason": notification_reason,
                        "cancellation_message": cancellation_message or "",
                    },
                )
                notifications_sent += 1
                logger.info(f"Notificación de cancelación enviada al admin del club {club_id}")
            else:
                logger.warning(f"No se encontró administrador para el club {club_id}")
        except Exception as e:
            logger.error(f"Error enviando notificación al admin del club: {e}")

    # 7. Enviar notificaciones a jugadores con invitaciones pendientes
    for invitation in pending_invitations:
        try:
            # Crear notificación de invitación cancelada
            from app.utils.notification_utils import (
                create_notification,
                send_notification_with_fcm,
            )

            # Construir mensaje con motivo si está disponible
            invitation_message = f"La invitación para el turno del {turn.date.strftime('%Y-%m-%d')} a las {turn.start_time} ha sido cancelada"
            if cancellation_message and cancellation_message.strip():
                invitation_message += f". Motivo: {cancellation_message.strip()}"

            # Enviar notificación push con el mensaje del organizador
            send_notification_with_fcm(
                db=db,
                user_id=invitation.invited_player_id,
                title="Invitación cancelada",
                message=invitation_message,
                notification_type="invitation_cancelled",
                data={
                    "turn_id": str(turn_id),
                    "invitation_id": str(invitation.id),
                    "club_name": (
                        turn.court.club.name
                        if turn.court and turn.court.club
                        else "Club"
                    ),
                    "cancellation_message": cancellation_message or "",
                    "reason": cancellation_message or "El organizador canceló el turno",
                },
            )

            # También crear notificación en BD
            create_notification(
                db=db,
                user_id=invitation.invited_player_id,
                title="Invitación cancelada",
                message=invitation_message,
                notification_type="invitation_cancelled",
                data={
                    "turn_id": turn_id,
                    "invitation_id": invitation.id,
                    "club_name": (
                        turn.court.club.name
                        if turn.court and turn.court.club
                        else "Club"
                    ),
                    "cancellation_message": cancellation_message,
                },
            )
            notifications_sent += 1
        except Exception as e:
            logger.error(f"Error enviando notificación de invitación cancelada: {e}")

    return {
        "turn_id": turn_id,
        "cancelled_by": "organizer",
        "affected_players": len(affected_players) - 1,  # Excluir al organizador
        "cancelled_invitations": cancelled_invitations,
        "notifications_sent": notifications_sent,
    }


def cancel_individual_position(
    db: Session, turn_id: int, user_id: int, cancellation_message: Optional[str] = None
) -> dict:
    """
    Cancela la posición de un jugador individual.

    Args:
        db: Sesión de base de datos
        turn_id: ID del turno
        user_id: ID del usuario que se retira
        cancellation_message: Mensaje opcional de justificación de la baja

    Returns:
        dict: Información sobre la cancelación
    """
    # 1. Obtener el turno
    turn = pregame_turn_crud.get_pregame_turn(db, turn_id)
    if not turn:
        raise ValueError(f"Turno {turn_id} no encontrado")

    # CRÍTICO: Verificar que el turno no esté ya cancelado
    from app.models.pregame_turn import PregameTurnStatus
    if turn.status == PregameTurnStatus.CANCELLED:
        raise ValueError("Este turno ya fue cancelado. No se pueden realizar más acciones sobre él.")

    # 2. Determinar qué posición ocupa el usuario
    player_position = None
    if turn.player1_id == user_id:
        player_position = "player1"
    elif turn.player2_id == user_id:
        player_position = "player2"
    elif turn.player3_id == user_id:
        player_position = "player3"
    elif turn.player4_id == user_id:
        player_position = "player4"

    if not player_position:
        raise ValueError("No eres parte de este turno")

    # 3. Eliminar solo esa posición
    from app.schemas.pregame_turn import PregameTurnUpdate

    update_data = PregameTurnUpdate()
    setattr(update_data, f"{player_position}_id", None)
    setattr(update_data, f"{player_position}_side", None)
    setattr(update_data, f"{player_position}_court_position", None)

    # CRÍTICO: Guardar el mensaje de justificación en el turno
    if cancellation_message:
        update_data.cancellation_message = cancellation_message

    updated_turn = pregame_turn_crud.update_pregame_turn(db, turn_id, update_data)
    if not updated_turn:
        raise ValueError(f"Error actualizando turno {turn_id}")

    # 3.25. CRÍTICO: Si el turno queda vacío (sin jugadores), marcarlo como CANCELLED
    # para que vuelva a aparecer como disponible en la grilla
    from app.utils.turn_utils import count_players_in_turn

    # Refrescar el turno actualizado para obtener el conteo correcto
    db.refresh(updated_turn)
    remaining_players_count = count_players_in_turn(updated_turn)

    # CRÍTICO: Actualizar estado del turno según la cantidad de jugadores restantes
    # Siempre recalcular el estado basándose en la cantidad de jugadores, independientemente del estado anterior
    status_update_needed = False
    new_status = None

    if remaining_players_count == 0:
        # El turno quedó vacío, marcarlo como cancelado para que vuelva a estar disponible
        new_status = "CANCELLED"
        status_update_needed = True
        logger.info(
            f"Turno {turn_id} marcado como CANCELLED porque quedó vacío después de la cancelación individual"
        )
    elif remaining_players_count < 4:
        # CRÍTICO: Si el turno tiene menos de 4 jugadores, cambiar el estado a PENDING
        # para permitir nuevas invitaciones, independientemente del estado anterior
        # Esto asegura que el turno se marque como incompleto y se habilite el botón de invitar
        if updated_turn.status != "PENDING":
            new_status = "PENDING"
            status_update_needed = True
            logger.info(
                f"Turno {turn_id} cambió de {updated_turn.status} a PENDING porque quedó con {remaining_players_count} jugadores después de la cancelación individual"
            )

    if status_update_needed:
        status_update = PregameTurnUpdate(status=new_status)
        updated_turn = pregame_turn_crud.update_pregame_turn(db, turn_id, status_update, commit=True)
        db.refresh(updated_turn)
        logger.info(f"Estado del turno {turn_id} actualizado a {new_status} después de cancelación individual")

    # 3.5. CRÍTICO: Actualizar invitaciones ACCEPTED del jugador que se retira
    # Si el jugador tenía una invitación ACCEPTED y se retira, debemos cancelarla
    # para que el estado quede limpio y no aparezca como aceptada cuando ya no está
    from app.schemas.invitation import InvitationUpdate
    from app.crud import user as user_crud

    player_accepted_invitations = (
        db.query(Invitation)
        .filter(
            and_(
                Invitation.turn_id == turn_id,
                Invitation.invited_player_id == user_id,
                Invitation.status == "ACCEPTED",
            )
        )
        .all()
    )

    cancelled_invitations_count = 0
    player_had_accepted_invitation = len(player_accepted_invitations) > 0

    # Obtener nombre del jugador que se retira para la notificación
    leaving_player = user_crud.get_user(db, user_id)
    leaving_player_name = (
        leaving_player.name.split()[0]
        if leaving_player and leaving_player.name
        else "Un jugador"
    )

    for invitation in player_accepted_invitations:
        try:
            # Marcar como CANCELLED para mantener historial pero indicar que ya no está activa
            invitation_update = InvitationUpdate(status="CANCELLED")
            invitation_crud.update_invitation(db, invitation.id, invitation_update)
            cancelled_invitations_count += 1
            logger.info(
                f"Invitación {invitation.id} cancelada porque el jugador {user_id} se retiró del turno {turn_id}"
            )
        except Exception as e:
            logger.error(f"Error cancelando invitación {invitation.id}: {e}")

    # 4. Obtener jugadores restantes para notificar
    # CRÍTICO: Usar updated_turn para obtener los jugadores DESPUÉS de la actualización
    remaining_players = []
    organizer_id = updated_turn.player1_id  # Guardar ID del organizador (puede ser None si se retiró)

    if updated_turn.player1_id and updated_turn.player1_id != user_id:
        remaining_players.append(updated_turn.player1_id)
    if updated_turn.player2_id and updated_turn.player2_id != user_id:
        remaining_players.append(updated_turn.player2_id)
    if updated_turn.player3_id and updated_turn.player3_id != user_id:
        remaining_players.append(updated_turn.player3_id)
    if updated_turn.player4_id and updated_turn.player4_id != user_id:
        remaining_players.append(updated_turn.player4_id)

    # 5. Enviar notificaciones a los demás jugadores
    notifications_sent = 0

    # Obtener información del club
    club_name = (
        turn.court.club.name
        if turn.court and turn.court.club
        else "Club"
    )
    club_id = (
        turn.court.club.id
        if turn.court and turn.court.club
        else None
    )

    # Construir mensaje de notificación con justificación si está disponible
    base_message = f"{leaving_player_name} se dio de baja del turno de las {turn.start_time} en {club_name}"
    if cancellation_message and cancellation_message.strip():
        full_message = f"{base_message}. Motivo: {cancellation_message.strip()}"
    else:
        full_message = base_message

    # Determinar si el turno quedó incompleto (menos de 4 jugadores)
    turn_is_incomplete = remaining_players_count < 4
    incomplete_message = (
        f" El turno ahora está incompleto ({remaining_players_count}/4 jugadores) y se pueden invitar nuevos jugadores."
        if turn_is_incomplete
        else ""
    )
    final_message = full_message + incomplete_message

    # CRÍTICO: Si el jugador que se retira había aceptado una invitación,
    # enviar notificación específica al organizador
    if player_had_accepted_invitation and organizer_id and organizer_id != user_id:
        try:
            from app.utils.notification_utils import send_notification_with_fcm

            send_notification_with_fcm(
                db=db,
                user_id=organizer_id,
                title="Jugador se retiró del turno",
                message=final_message,
                notification_type="player_left",
                data={
                    "turn_id": turn_id,
                    "club_name": (
                        turn.court.club.name
                        if turn.court and turn.court.club
                        else "Club"
                    ),
                    "start_time": turn.start_time,
                    "leaving_player_name": leaving_player_name,
                    "leaving_player_id": user_id,
                    "was_invited": True,  # Indica que había aceptado una invitación
                    "cancellation_message": cancellation_message,
                    "turn_is_incomplete": turn_is_incomplete,
                    "remaining_players": remaining_players_count,
                },
            )
            notifications_sent += 1
            logger.info(
                f"Notificación específica enviada al organizador {organizer_id} porque el jugador {user_id} que había aceptado una invitación se retiró"
            )
        except Exception as e:
            logger.error(f"Error enviando notificación específica al organizador: {e}")

    # Notificar a los demás jugadores (excluyendo al organizador si ya fue notificado específicamente)
    other_players = [
        p
        for p in remaining_players
        if not (player_had_accepted_invitation and p == organizer_id)
    ]

    for player_id in other_players:
        try:
            # Usar send_notification_with_fcm para incluir el mensaje de justificación
            from app.utils.notification_utils import send_notification_with_fcm

            send_notification_with_fcm(
                db=db,
                user_id=player_id,
                title="Un jugador se retiró del turno",
                message=final_message,
                notification_type="player_left",
                data={
                    "turn_id": turn_id,
                    "club_name": (
                        turn.court.club.name
                        if turn.court and turn.court.club
                        else "Club"
                ),
                    "start_time": turn.start_time,
                    "leaving_player_name": leaving_player_name,
                    "leaving_player_id": user_id,
                    "cancellation_message": cancellation_message,
                    "turn_is_incomplete": turn_is_incomplete,
                    "remaining_players": remaining_players_count,
                },
            )
            notifications_sent += 1
        except Exception as e:
            logger.error(f"Error enviando notificación a jugador {player_id}: {e}")

    # Notificar al administrador del club cuando el turno queda incompleto (lugar disponible o vacío)
    if turn_is_incomplete and club_id:
        try:
            from app.models.user import User
            from app.utils.notification_utils import send_notification_with_fcm

            club_admin = (
                db.query(User)
                .filter(User.club_id == club_id, User.is_admin == True)
                .first()
            )

            if club_admin:
                if remaining_players_count == 0:
                    admin_message = (
                        f"{leaving_player_name} canceló su participación y el turno de las {turn.start_time} quedó vacío en {club_name}"
                    )
                    if cancellation_message and cancellation_message.strip():
                        admin_message += f". Mensaje: {cancellation_message.strip()}"
                    admin_title = "Turno cancelado"
                    notification_type = "turn_cancelled"
                    data_extra = {"turn_is_empty": True}
                else:
                    admin_message = (
                        f"{leaving_player_name} se dio de baja del turno de las {turn.start_time} en {club_name}. "
                        f"Queda lugar disponible ({remaining_players_count}/4 jugadores)."
                    )
                    if cancellation_message and cancellation_message.strip():
                        admin_message += f" Motivo: {cancellation_message.strip()}"
                    admin_title = "Turno incompleto - Lugar disponible"
                    notification_type = "turn_incomplete_spot_available"
                    data_extra = {"turn_is_empty": False, "remaining_players": remaining_players_count}

                send_notification_with_fcm(
                    db=db,
                    user_id=club_admin.id,
                    title=admin_title,
                    message=admin_message,
                    notification_type=notification_type,
                    data={
                        "turn_id": str(turn_id),
                        "club_name": club_name,
                        "club_id": str(club_id),
                        "start_time": turn.start_time,
                        "date": turn.date.isoformat() if turn.date else None,
                        "leaving_player_id": str(user_id),
                        "leaving_player_name": leaving_player_name,
                        "cancellation_message": cancellation_message or "",
                        **data_extra,
                    },
                )
                notifications_sent += 1
                logger.info(
                    f"Notificación enviada al admin del club {club_id} (turno incompleto/vacío)"
                )
            else:
                logger.warning(f"No se encontró administrador para el club {club_id}")
        except Exception as e:
            logger.error(f"Error enviando notificación al admin del club: {e}")

    return {
        "turn_id": turn_id,
        "cancelled_by": "individual",
        "player_position": player_position,
        "affected_players": len(remaining_players),
        "notifications_sent": notifications_sent,
        "turn_is_incomplete": remaining_players_count
        < 4,  # CRÍTICO: Indicar si el turno quedó incompleto
        "remaining_players": remaining_players_count,
        "cancellation_message": cancellation_message,  # Incluir mensaje de justificación en la respuesta
    }
