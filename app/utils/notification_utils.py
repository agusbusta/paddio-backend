from typing import Optional
from sqlalchemy.orm import Session
from app.crud import notification as notification_crud
from app.schemas.notification import NotificationCreate
from app.services.fcm_service import fcm_service
from app.crud import fcm_token as fcm_crud
import logging

logger = logging.getLogger(__name__)


def create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    notification_type: str,
    data: dict = None,
):
    """
    Crear una notificación en la base de datos.

    Args:
        db: Sesión de base de datos
        user_id: ID del usuario que recibirá la notificación
        title: Título de la notificación
        message: Mensaje de la notificación
        notification_type: Tipo de notificación (turn_joined, turn_complete, etc.)
        data: Datos adicionales en formato JSON

    Returns:
        Notification: La notificación creada
    """
    try:
        notification_data = NotificationCreate(
            user_id=user_id,
            title=title,
            message=message,
            type=notification_type,
            data=data,
        )

        notification = notification_crud.create_notification(db, notification_data)
        logger.info(f"Notification created for user {user_id}: {notification_type}")
        return notification

    except Exception as e:
        logger.error(f"Error creating notification: {e}")
        raise


def _fcm_data_stringify(data: dict) -> dict:
    """FCM solo acepta datos con valores string. Convierte todos los valores a str."""
    if not data:
        return {}
    return {k: str(v) if v is not None else "" for k, v in data.items()}


def send_notification_with_fcm(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    notification_type: str,
    data: dict = None,
):
    """
    Crear una notificación en la base de datos Y enviar notificación push FCM.

    Args:
        db: Sesión de base de datos
        user_id: ID del usuario que recibirá la notificación
        title: Título de la notificación
        message: Mensaje de la notificación
        notification_type: Tipo de notificación
        data: Datos adicionales

    Returns:
        Notification: La notificación creada
    """
    try:
        # Crear notificación en la base de datos
        notification = create_notification(
            db=db,
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            data=data,
        )

        # Enviar notificación push FCM (si está configurado)
        if fcm_service.is_configured():
            try:
                # Obtener tokens FCM del usuario (activos)
                user_tokens = fcm_crud.get_user_fcm_tokens(db, user_id, active_only=True)

                if user_tokens:
                    tokens = [token.token for token in user_tokens]

                    # Preparar datos para FCM (Firebase exige valores string)
                    fcm_data = _fcm_data_stringify(data or {})
                    fcm_data.update(
                        {
                            "type": notification_type,
                            "notification_id": str(notification.id),
                        }
                    )

                    result = fcm_service.send_notification_to_multiple_tokens(
                        tokens=tokens, title=title, body=message, data=fcm_data
                    )

                    logger.info(
                        f"FCM push sent to user {user_id} ({result.get('success', 0)} ok, "
                        f"{result.get('failure', 0)} fail): {notification_type}"
                    )
                else:
                    logger.warning(
                        f"No FCM tokens for user {user_id} - push not sent for {notification_type}"
                    )

            except Exception as fcm_error:
                logger.error(f"Error sending FCM notification: {fcm_error}", exc_info=True)
                # No fallar la creación de la notificación por problemas de FCM
        else:
            logger.warning("FCM service not configured - push not sent")

        return notification

    except Exception as e:
        logger.error(f"Error in send_notification_with_fcm: {e}")
        raise


# Funciones específicas para diferentes tipos de notificaciones


def notify_turn_joined(
    db: Session,
    turn_id: int,
    new_player_id: int,
    club_name: str,
    start_time: str,
    other_player_ids: list,
):
    """
    Notificar cuando un jugador se une a un turno.
    """
    from app.crud import user as user_crud

    try:
        # Obtener información del nuevo jugador
        new_player = user_crud.get_user(db, new_player_id)
        if not new_player:
            logger.error(f"New player {new_player_id} not found")
            return

        player_name = new_player.name.split()[0] if new_player.name else "Un jugador"

        # Crear notificación para cada jugador en el turno
        for player_id in other_player_ids:
            if player_id != new_player_id:  # No notificar al mismo jugador
                send_notification_with_fcm(
                    db=db,
                    user_id=player_id,
                    title="Nuevo jugador se unió",
                    message=f"{player_name} se unió al turno de las {start_time} en {club_name}",
                    notification_type="turn_joined",
                    data={
                        "turn_id": turn_id,
                        "club_name": club_name,
                        "start_time": start_time,
                        "new_player_name": player_name,
                        "new_player_id": new_player_id,
                    },
                )

    except Exception as e:
        logger.error(f"Error notifying turn joined: {e}")


def notify_turn_complete(
    db: Session, turn_id: int, club_name: str, start_time: str, player_ids: list
):
    """
    Notificar cuando un turno está completo (4 jugadores).
    """
    try:
        for player_id in player_ids:
            send_notification_with_fcm(
                db=db,
                user_id=player_id,
                title="Turno completo",
                message=f"¡El turno de las {start_time} en {club_name} está completo!",
                notification_type="turn_complete",
                data={
                    "turn_id": turn_id,
                    "club_name": club_name,
                    "start_time": start_time,
                },
            )

    except Exception as e:
        logger.error(f"Error notifying turn complete: {e}")


def notify_turn_invitation(
    db: Session,
    invitation_id: int,
    inviter_name: str,
    invited_player_id: int,
    club_name: str,
    turn_time: str,
    turn_date: str,
):
    """
    Notificar cuando se envía una invitación.
    """
    try:
        send_notification_with_fcm(
            db=db,
            user_id=invited_player_id,
            title="Invitación recibida",
            message=f"{inviter_name} te invitó a jugar padel",
            notification_type="turn_invitation",
            data={
                "invitation_id": invitation_id,
                "inviter_name": inviter_name,
                "club_name": club_name,
                "turn_time": turn_time,
                "turn_date": turn_date,
            },
        )

    except Exception as e:
        logger.error(f"Error notifying turn invitation: {e}")


def notify_invitation_response(
    db: Session,
    invitation_id: int,
    responder_name: str,
    response_status: str,
    inviter_id: int,
    club_name: str,
    turn_time: str,
):
    """
    Notificar cuando alguien responde a una invitación.
    """
    try:
        if response_status == "ACCEPTED":
            title = "Respuesta a invitación"
            message = f"{responder_name} aceptó tu invitación"
        else:
            title = "Respuesta a invitación"
            message = f"{responder_name} rechazó tu invitación"

        send_notification_with_fcm(
            db=db,
            user_id=inviter_id,
            title=title,
            message=message,
            notification_type="invitation_response",
            data={
                "invitation_id": invitation_id,
                "responder_name": responder_name,
                "response_status": response_status,
                "club_name": club_name,
                "turn_time": turn_time,
            },
        )

    except Exception as e:
        logger.error(f"Error notifying invitation response: {e}")


def notify_turn_reminder(
    db: Session,
    turn_id: int,
    club_name: str,
    start_time: str,
    player_ids: list,
    minutes_before: int = 60,
):
    """
    Notificar recordatorio de turno (ej: 1 hora antes).
    """
    try:
        for player_id in player_ids:
            send_notification_with_fcm(
                db=db,
                user_id=player_id,
                title="Recordatorio de turno",
                message=f"Tu turno en {club_name} empieza en {minutes_before} minutos ({start_time})",
                notification_type="turn_reminder",
                data={
                    "turn_id": turn_id,
                    "club_name": club_name,
                    "start_time": start_time,
                    "minutes_before": minutes_before,
                },
            )

    except Exception as e:
        logger.error(f"Error notifying turn reminder: {e}")


def notify_turn_cancelled(
    db: Session,
    turn_id: int,
    club_name: str,
    start_time: str,
    player_ids: list,
    reason: str = "Turno cancelado",
):
    """
    Notificar por push y en BD cuando un turno es cancelado (organizador o club).
    Mensaje claro: "El turno fue cancelado por el organizador" + motivo si existe.
    """
    title = "Turno cancelado"
    # Mensaje directo para aviso activo (push + badge)
    if reason and reason.strip() and reason != "El organizador canceló el turno":
        message = f"El turno fue cancelado por el organizador. Motivo: {reason.strip()}"
    else:
        message = "El turno fue cancelado por el organizador."
    try:
        for player_id in player_ids:
            send_notification_with_fcm(
                db=db,
                user_id=player_id,
                title=title,
                message=message,
                notification_type="turn_cancelled",
                data={
                    "turn_id": str(turn_id),
                    "club_name": club_name or "",
                    "start_time": start_time or "",
                    "reason": reason or "",
                    "cancellation_message": reason or "",
                },
            )
    except Exception as e:
        logger.error(f"Error notifying turn cancelled: {e}", exc_info=True)


def notify_player_left(
    db: Session,
    turn_id: int,
    club_name: str,
    start_time: str,
    player_ids: list,
):
    """
    Notificar cuando un jugador se retira de un turno.
    """
    try:
        for player_id in player_ids:
            send_notification_with_fcm(
                db=db,
                user_id=player_id,
                title="Jugador se retiró",
                message=f"Un jugador se retiró del turno de las {start_time} en {club_name}",
                notification_type="player_left",
                data={
                    "turn_id": turn_id,
                    "club_name": club_name,
                    "start_time": start_time,
                },
            )

    except Exception as e:
        logger.error(f"Error notifying player left: {e}")


def notify_invitation_declined_to_turn_participants(
    db: Session,
    turn,
    decliner_name: str,
    club_name: str,
    turn_time: str,
    decliner_id: int,
    inviter_id: int,
):
    """
    Notificar al organizador del turno y a todos los jugadores que ya aceptaron
    cuando un invitado rechaza la invitación.
    inviter_id se excluye para no duplicar (ya recibe notify_invitation_response).
    """
    try:
        player_ids = [
            turn.player1_id,
            turn.player2_id,
            turn.player3_id,
            turn.player4_id,
        ]
        # Jugadores en el turno (ya aceptaron), sin el que rechazó ni el invitador (ya notificado)
        ids_to_notify = [
            pid for pid in player_ids
            if pid is not None and pid != decliner_id and pid != inviter_id
        ]
        title = "Invitación rechazada"
        message = (
            f"{decliner_name} rechazó la invitación al turno de las {turn_time} en {club_name}"
        )
        for user_id in ids_to_notify:
            send_notification_with_fcm(
                db=db,
                user_id=user_id,
                title=title,
                message=message,
                notification_type="invitation_declined",
                data={
                    "turn_id": turn.id,
                    "club_name": club_name,
                    "turn_time": turn_time,
                    "decliner_name": decliner_name,
                },
            )
    except Exception as e:
        logger.error(f"Error notifying turn participants of declined invitation: {e}")


def notify_turn_participants_player_invited(
    db: Session,
    turn,
    inviter_name: str,
    invited_player_name: str,
    club_name: str,
    turn_time: str,
    inviter_id: int,
):
    """
    Notificar a todos los jugadores del turno (excepto el invitador) cuando alguien
    invita a otro al turno. Ej: "Juan invitó a Pedro al turno".
    Da trazabilidad de quién trae a quién (invitación secundaria / dupla).
    """
    try:
        player_ids = [
            turn.player1_id,
            turn.player2_id,
            turn.player3_id,
            turn.player4_id,
        ]
        ids_to_notify = [
            pid for pid in player_ids
            if pid is not None and pid != inviter_id
        ]
        title = "Nueva invitación al turno"
        message = f"{inviter_name} invitó a {invited_player_name} al turno"
        for user_id in ids_to_notify:
            send_notification_with_fcm(
                db=db,
                user_id=user_id,
                title=title,
                message=message,
                notification_type="player_invited_to_turn",
                data={
                    "turn_id": turn.id,
                    "club_name": club_name,
                    "turn_time": turn_time,
                    "inviter_name": inviter_name,
                    "invited_player_name": invited_player_name,
                },
            )
    except Exception as e:
        logger.error(f"Error notifying turn participants of player invited: {e}")


def notify_turn_modified_by_club(
    db: Session,
    turn,
    change_type: str,
    new_value_description: str,
    club_name: str,
):
    """
    Notificar al configurador y a todos los jugadores que aceptaron cuando el club
    modifica el horario o la cancha del turno (Gestión - Horario/Cancha modificada).
    change_type: "schedule" | "court"
    new_value_description: ej. "18:00" o "Cancha 2"
    """
    try:
        player_ids = [
            turn.player1_id,
            turn.player2_id,
            turn.player3_id,
            turn.player4_id,
        ]
        ids_to_notify = [pid for pid in player_ids if pid is not None]
        if change_type == "schedule":
            title = "Horario del turno modificado"
            message = f"El club {club_name} modificó el horario del turno. Nueva hora: {new_value_description}"
            notification_type = "turn_schedule_modified"
        else:
            title = "Cancha del turno modificada"
            message = f"El club {club_name} modificó la cancha del turno. Nueva cancha: {new_value_description}"
            notification_type = "turn_court_modified"
        for user_id in ids_to_notify:
            send_notification_with_fcm(
                db=db,
                user_id=user_id,
                title=title,
                message=message,
                notification_type=notification_type,
                data={
                    "turn_id": turn.id,
                    "club_name": club_name,
                    "change_type": change_type,
                    "new_value": new_value_description,
                },
            )
    except Exception as e:
        logger.error(f"Error notifying turn participants of club modification: {e}")


def notify_turn_schedule_modified(
    db: Session,
    turn,
    new_time_description: str,
    modifier_label: str,
    exclude_user_id: Optional[int] = None,
):
    """
    Notificar a todos los jugadores del turno que el horario fue modificado
    (ya sea por el club o por el organizador).
    modifier_label: ej. "El club Club Name" o "El organizador"
    exclude_user_id: si se indica, no se envía notificación a ese usuario (ej. quien hizo el cambio).
    """
    try:
        player_ids = [
            turn.player1_id,
            turn.player2_id,
            turn.player3_id,
            turn.player4_id,
        ]
        ids_to_notify = [pid for pid in player_ids if pid is not None]
        if exclude_user_id is not None:
            ids_to_notify = [pid for pid in ids_to_notify if pid != exclude_user_id]
        title = "Horario del turno modificado"
        message = f"{modifier_label} modificó el horario del turno. Nueva hora: {new_time_description}"
        for user_id in ids_to_notify:
            send_notification_with_fcm(
                db=db,
                user_id=user_id,
                title=title,
                message=message,
                notification_type="turn_schedule_modified",
                data={
                    "turn_id": turn.id,
                    "change_type": "schedule",
                    "new_value": new_time_description,
                },
            )
    except Exception as e:
        logger.error(f"Error notifying turn participants of schedule modification: {e}")


def notify_turn_court_modified(
    db: Session,
    turn,
    new_court_description: str,
    modifier_label: str,
    exclude_user_id: Optional[int] = None,
):
    """
    Notificar a todos los jugadores del turno que la cancha fue modificada
    (ya sea por el club o por el organizador).
    modifier_label: ej. "El club Club Name" o "El organizador"
    exclude_user_id: si se indica, no se envía notificación a ese usuario (ej. quien hizo el cambio).
    """
    try:
        player_ids = [
            turn.player1_id,
            turn.player2_id,
            turn.player3_id,
            turn.player4_id,
        ]
        ids_to_notify = [pid for pid in player_ids if pid is not None]
        if exclude_user_id is not None:
            ids_to_notify = [pid for pid in ids_to_notify if pid != exclude_user_id]
        title = "Cancha del turno modificada"
        message = f"{modifier_label} modificó la cancha del turno. Nueva cancha: {new_court_description}"
        for user_id in ids_to_notify:
            send_notification_with_fcm(
                db=db,
                user_id=user_id,
                title=title,
                message=message,
                notification_type="turn_court_modified",
                data={
                    "turn_id": turn.id,
                    "change_type": "court",
                    "new_value": new_court_description,
                },
            )
    except Exception as e:
        logger.error(f"Error notifying turn participants of court modification: {e}")


def notify_turn_incomplete_reminder(
    db: Session,
    turn,
    club_name: str,
):
    """
    Envía recordatorio al organizador: el turno sigue sin jugadores.
    Se llama cuando el turno fue creado vacío y pasaron X minutos.
    """
    if not turn or not turn.player1_id:
        return
    try:
        send_notification_with_fcm(
            db=db,
            user_id=turn.player1_id,
            title="Turno sin jugadores",
            message="Tu turno sigue sin jugadores. Invita ahora para completarlo.",
            notification_type="turn_incomplete_reminder",
            data={
                "turn_id": str(turn.id),
                "club_name": club_name or "",
                "start_time": turn.start_time or "",
                "date": turn.date.strftime("%Y-%m-%d") if turn.date else "",
            },
        )
    except Exception as e:
        logger.error(f"Error enviando recordatorio de turno incompleto: {e}")


def notify_turn_chat_message(
    db: Session,
    pregame_turn_id: int,
    sender_user_id: int,
    sender_name: str,
    message_preview: str,
    club_name: str = "",
):
    """
    Envía notificación push a los demás participantes del turno cuando alguien escribe en el chat.
    No se notifica al remitente.
    """
    from app.crud import turn_chat as turn_chat_crud

    participant_ids = turn_chat_crud.get_turn_participant_ids(db, pregame_turn_id)
    title = "Nuevo mensaje en el turno"
    if club_name:
        title = f"Nuevo mensaje · {club_name}"
    body = f"{sender_name}: {message_preview}"
    for user_id in participant_ids:
        if user_id == sender_user_id:
            continue
        try:
            send_notification_with_fcm(
                db=db,
                user_id=user_id,
                title=title,
                message=body,
                notification_type="turn_chat_message",
                data={
                    "pregame_turn_id": str(pregame_turn_id),
                    "sender_name": sender_name,
                    "club_name": club_name or "",
                },
            )
        except Exception as e:
            logger.warning("Error notificando chat a user %s: %s", user_id, e)
