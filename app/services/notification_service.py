import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.crud import fcm_token as fcm_crud
from app.crud import pregame_turn as pregame_turn_crud
from app.crud import user as user_crud
from app.services.fcm_service import fcm_service

logger = logging.getLogger(__name__)


class NotificationService:
    """Servicio para enviar notificaciones automáticas relacionadas con turnos de padel"""

    def __init__(self):
        self.fcm_service = fcm_service

    def notify_turn_joined(
        self,
        db: Session,
        turn_id: int,
        new_player_id: int,
        club_name: str,
        start_time: str,
    ) -> bool:
        """
        Notifica a otros jugadores cuando alguien se une a un turno

        Args:
            db: Sesión de base de datos
            turn_id: ID del turno
            new_player_id: ID del jugador que se unió
            club_name: Nombre del club
            start_time: Hora de inicio del turno

        Returns:
            True si se enviaron notificaciones exitosamente
        """
        try:
            # Obtener el turno
            turn = pregame_turn_crud.get_pregame_turn(db, turn_id)
            if not turn:
                logger.error(f"Turn {turn_id} not found")
                return False

            # Obtener información del nuevo jugador
            new_player = user_crud.get_user(db, new_player_id)
            if not new_player:
                logger.error(f"Player {new_player_id} not found")
                return False

            # Obtener IDs de otros jugadores en el turno
            other_player_ids = []
            for player_id in [
                turn.player1_id,
                turn.player2_id,
                turn.player3_id,
                turn.player4_id,
            ]:
                if player_id and player_id != new_player_id:
                    other_player_ids.append(player_id)

            if not other_player_ids:
                logger.info(f"No other players to notify for turn {turn_id}")
                return True

            # Obtener tokens FCM de otros jugadores
            tokens = fcm_crud.get_active_tokens_for_users(db, other_player_ids)

            if not tokens:
                logger.info(f"No FCM tokens found for other players in turn {turn_id}")
                return True

            # Preparar mensaje
            player_name = (
                new_player.name.split()[0] if new_player.name else "Un jugador"
            )
            title = "¡Alguien se unió a tu turno!"
            body = f"{player_name} se unió al turno de las {start_time} en {club_name}"

            data = {
                "type": "turn_joined",
                "turn_id": str(turn_id),
                "new_player_id": str(new_player_id),
                "club_name": club_name,
                "start_time": start_time,
            }

            # Enviar notificaciones
            result = self.fcm_service.send_notification_to_multiple_tokens(
                tokens=tokens, title=title, body=body, data=data
            )

            # Eliminar tokens inválidos de la base de datos
            if result.get("invalid_tokens"):
                self._cleanup_invalid_tokens(db, result["invalid_tokens"])

            logger.info(f"Turn joined notification sent: {result}")
            # Considerar exitoso si no hay tokens o si se enviaron algunos
            return result["success"] > 0 or len(tokens) == 0

        except Exception as e:
            logger.error(f"Error sending turn joined notification: {e}")
            return False

    def notify_turn_complete(
        self, db: Session, turn_id: int, club_name: str, start_time: str
    ) -> bool:
        """
        Notifica cuando un turno está completo (4 jugadores)

        Args:
            db: Sesión de base de datos
            turn_id: ID del turno
            club_name: Nombre del club
            start_time: Hora de inicio del turno

        Returns:
            True si se enviaron notificaciones exitosamente
        """
        try:
            # Obtener el turno
            turn = pregame_turn_crud.get_pregame_turn(db, turn_id)
            if not turn:
                logger.error(f"Turn {turn_id} not found")
                return False

            # Obtener IDs de todos los jugadores
            player_ids = []
            for player_id in [
                turn.player1_id,
                turn.player2_id,
                turn.player3_id,
                turn.player4_id,
            ]:
                if player_id:
                    player_ids.append(player_id)

            if len(player_ids) != 4:
                logger.warning(f"Turn {turn_id} doesn't have exactly 4 players")
                return False

            # Obtener tokens FCM de todos los jugadores
            tokens = fcm_crud.get_active_tokens_for_users(db, player_ids)

            if not tokens:
                logger.info(f"No FCM tokens found for players in turn {turn_id}")
                return True

            # Preparar mensaje
            title = "¡Turno completo!"
            body = (
                f"El turno de las {start_time} en {club_name} está completo. ¡A jugar!"
            )

            data = {
                "type": "turn_complete",
                "turn_id": str(turn_id),
                "club_name": club_name,
                "start_time": start_time,
            }

            # Enviar notificaciones
            result = self.fcm_service.send_notification_to_multiple_tokens(
                tokens=tokens, title=title, body=body, data=data
            )

            logger.info(f"Turn complete notification sent: {result}")
            # Considerar exitoso si no hay tokens o si se enviaron algunos
            return result["success"] > 0 or len(tokens) == 0

        except Exception as e:
            logger.error(f"Error sending turn complete notification: {e}")
            return False

    def notify_turn_reminder(
        self,
        db: Session,
        turn_id: int,
        club_name: str,
        start_time: str,
        minutes_before: int = 60,
    ) -> bool:
        """
        Envía recordatorio de turno (por ejemplo, 1 hora antes)

        Args:
            db: Sesión de base de datos
            turn_id: ID del turno
            club_name: Nombre del club
            start_time: Hora de inicio del turno
            minutes_before: Minutos antes del turno para enviar recordatorio

        Returns:
            True si se enviaron notificaciones exitosamente
        """
        try:
            # Obtener el turno
            turn = pregame_turn_crud.get_pregame_turn(db, turn_id)
            if not turn:
                logger.error(f"Turn {turn_id} not found")
                return False

            # Obtener IDs de todos los jugadores
            player_ids = []
            for player_id in [
                turn.player1_id,
                turn.player2_id,
                turn.player3_id,
                turn.player4_id,
            ]:
                if player_id:
                    player_ids.append(player_id)

            if not player_ids:
                logger.warning(f"No players found in turn {turn_id}")
                return False

            # Obtener tokens FCM de todos los jugadores
            tokens = fcm_crud.get_active_tokens_for_users(db, player_ids)

            if not tokens:
                logger.info(f"No FCM tokens found for players in turn {turn_id}")
                return True

            # Preparar mensaje
            title = "Recordatorio de turno"
            body = f"Tu turno en {club_name} empieza en {minutes_before} minutos ({start_time})"

            data = {
                "type": "turn_reminder",
                "turn_id": str(turn_id),
                "club_name": club_name,
                "start_time": start_time,
                "minutes_before": str(minutes_before),
            }

            # Enviar notificaciones
            result = self.fcm_service.send_notification_to_multiple_tokens(
                tokens=tokens, title=title, body=body, data=data
            )

            # Eliminar tokens inválidos de la base de datos
            if result.get("invalid_tokens"):
                self._cleanup_invalid_tokens(db, result["invalid_tokens"])

            logger.info(f"Turn reminder notification sent: {result}")
            return result["success"] > 0

        except Exception as e:
            logger.error(f"Error sending turn reminder notification: {e}")
            return False

    def notify_turn_cancelled(
        self,
        db: Session,
        turn_id: int,
        club_name: str,
        start_time: str,
        reason: str = "Turno cancelado",
    ) -> bool:
        """
        Notifica cuando un turno es cancelado

        Args:
            db: Sesión de base de datos
            turn_id: ID del turno
            club_name: Nombre del club
            start_time: Hora de inicio del turno
            reason: Razón de la cancelación

        Returns:
            True si se enviaron notificaciones exitosamente
        """
        try:
            # Obtener el turno
            turn = pregame_turn_crud.get_pregame_turn(db, turn_id)
            if not turn:
                logger.error(f"Turn {turn_id} not found")
                return False

            # Obtener IDs de todos los jugadores
            player_ids = []
            for player_id in [
                turn.player1_id,
                turn.player2_id,
                turn.player3_id,
                turn.player4_id,
            ]:
                if player_id:
                    player_ids.append(player_id)

            if not player_ids:
                logger.warning(f"No players found in turn {turn_id}")
                return False

            # Obtener tokens FCM de todos los jugadores
            tokens = fcm_crud.get_active_tokens_for_users(db, player_ids)

            if not tokens:
                logger.info(f"No FCM tokens found for players in turn {turn_id}")
                return True

            # Preparar mensaje
            title = "Turno cancelado"
            body = (
                f"El turno de las {start_time} en {club_name} fue cancelado: {reason}"
            )

            data = {
                "type": "turn_cancelled",
                "turn_id": str(turn_id),
                "club_name": club_name,
                "start_time": start_time,
                "reason": reason,
            }

            # Enviar notificaciones
            result = self.fcm_service.send_notification_to_multiple_tokens(
                tokens=tokens, title=title, body=body, data=data
            )

            # Eliminar tokens inválidos de la base de datos
            if result.get("invalid_tokens"):
                self._cleanup_invalid_tokens(db, result["invalid_tokens"])

            logger.info(f"Turn cancelled notification sent: {result}")
            return result["success"] > 0

        except Exception as e:
            logger.error(f"Error sending turn cancelled notification: {e}")
            return False

    def notify_turn_invitation(
        self,
        db: Session,
        invitation_id: int,
        inviter_name: str,
        club_name: str,
        turn_time: str,
        turn_date: str,
    ) -> bool:
        """
        Notifica cuando se recibe una invitación a un turno

        Args:
            db: Sesión de base de datos
            invitation_id: ID de la invitación
            inviter_name: Nombre del invitador
            club_name: Nombre del club
            turn_time: Hora del turno
            turn_date: Fecha del turno

        Returns:
            True si se envió correctamente, False en caso contrario
        """
        try:
            from app.crud import invitation as invitation_crud

            # Obtener la invitación
            invitation = invitation_crud.get_invitation(db, invitation_id)
            if not invitation:
                logger.error(f"Invitation {invitation_id} not found")
                return False

            # Obtener tokens FCM del jugador invitado
            tokens = fcm_crud.get_active_tokens_for_users(
                db, [invitation.invited_player_id]
            )

            if not tokens:
                logger.info(
                    f"No FCM tokens found for invited player {invitation.invited_player_id}"
                )
                return True

            # Preparar mensaje
            title = "¡Invitación a jugar!"
            body = f"{inviter_name} te invitó a jugar el {turn_date} a las {turn_time} en {club_name}"

            data = {
                "type": "turn_invitation",
                "invitation_id": str(invitation_id),
                "turn_id": str(invitation.turn_id),
                "inviter_name": inviter_name,
                "club_name": club_name,
                "turn_time": turn_time,
                "turn_date": turn_date,
            }

            # Enviar notificación
            result = self.fcm_service.send_notification_to_multiple_tokens(
                tokens=tokens, title=title, body=body, data=data
            )

            # Eliminar tokens inválidos de la base de datos
            if result.get("invalid_tokens"):
                self._cleanup_invalid_tokens(db, result["invalid_tokens"])

            logger.info(f"Turn invitation notification sent: {result}")
            # Considerar exitoso si no hay tokens o si se enviaron algunos
            return result["success"] > 0 or len(tokens) == 0

        except Exception as e:
            logger.error(f"Error sending turn invitation notification: {e}")
            return False

    def notify_invitation_response(
        self,
        db: Session,
        invitation_id: int,
        responder_name: str,
        response_status: str,
        club_name: str,
        turn_time: str,
    ) -> bool:
        """
        Notifica cuando alguien responde a una invitación

        Args:
            db: Sesión de base de datos
            invitation_id: ID de la invitación
            responder_name: Nombre del que responde
            response_status: Estado de la respuesta (ACCEPTED/DECLINED)
            club_name: Nombre del club
            turn_time: Hora del turno

        Returns:
            True si se envió correctamente, False en caso contrario
        """
        try:
            from app.crud import invitation as invitation_crud

            # Obtener la invitación
            invitation = invitation_crud.get_invitation(db, invitation_id)
            if not invitation:
                logger.error(f"Invitation {invitation_id} not found")
                return False

            # Obtener tokens FCM del invitador
            tokens = fcm_crud.get_active_tokens_for_users(db, [invitation.inviter_id])

            if not tokens:
                logger.info(f"No FCM tokens found for inviter {invitation.inviter_id}")
                return True

            # Preparar mensaje según la respuesta
            if response_status == "ACCEPTED":
                title = "¡Invitación aceptada!"
                body = f"{responder_name} aceptó tu invitación para jugar a las {turn_time} en {club_name}"
            else:
                title = "Invitación rechazada"
                body = f"{responder_name} rechazó tu invitación para jugar a las {turn_time} en {club_name}"

            data = {
                "type": "invitation_response",
                "invitation_id": str(invitation_id),
                "turn_id": str(invitation.turn_id),
                "responder_name": responder_name,
                "response_status": response_status,
                "club_name": club_name,
                "turn_time": turn_time,
            }

            # Enviar notificación
            result = self.fcm_service.send_notification_to_multiple_tokens(
                tokens=tokens, title=title, body=body, data=data
            )

            # Eliminar tokens inválidos de la base de datos
            if result.get("invalid_tokens"):
                self._cleanup_invalid_tokens(db, result["invalid_tokens"])

            logger.info(f"Invitation response notification sent: {result}")
            # Considerar exitoso si no hay tokens o si se enviaron algunos
            return result["success"] > 0 or len(tokens) == 0

        except Exception as e:
            logger.error(f"Error sending invitation response notification: {e}")
            return False

    def _cleanup_invalid_tokens(self, db: Session, invalid_tokens: List[str]) -> None:
        """
        Elimina tokens FCM inválidos de la base de datos.

        Args:
            db: Sesión de base de datos
            invalid_tokens: Lista de tokens inválidos a eliminar
        """
        if not invalid_tokens:
            return

        try:
            from app.crud import fcm_token as fcm_crud

            # Eliminar duplicados para evitar intentos múltiples de eliminación
            unique_tokens = list(set(invalid_tokens))

            deleted_count = 0
            for token_string in unique_tokens:
                # Buscar el token en la base de datos
                db_token = fcm_crud.get_fcm_token_by_token(db, token_string)
                if db_token:
                    # Eliminar el token
                    fcm_crud.delete_fcm_token(db, db_token.id)
                    deleted_count += 1
                    logger.info(
                        f"🗑️ Token FCM inválido eliminado: ID {db_token.id}, "
                        f"Usuario {db_token.user_id}, Token: {token_string[:20]}..."
                    )

            if deleted_count > 0:
                logger.info(
                    f"✅ Limpieza completada: {deleted_count} token(s) inválido(s) eliminado(s) "
                    f"(de {len(invalid_tokens)} detectados, {len(unique_tokens)} únicos)"
                )
        except Exception as e:
            logger.error(f"Error eliminando tokens inválidos: {e}")


# Instancia global del servicio
notification_service = NotificationService()
