from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional
import logging

from app.models.invitation import Invitation
from app.models.pregame_turn import PregameTurn
from app.models.user import User
from app.schemas.invitation import InvitationCreate, InvitationUpdate

logger = logging.getLogger(__name__)


def create_invitation(db: Session, invitation_data: InvitationCreate) -> Invitation:
    """Crear una nueva invitación"""
    db_invitation = Invitation(**invitation_data.model_dump())
    db.add(db_invitation)
    db.commit()
    db.refresh(db_invitation)
    logger.info(f"Invitación creada: {db_invitation.id}")
    return db_invitation


def get_invitation(db: Session, invitation_id: int) -> Optional[Invitation]:
    """Obtener una invitación por ID"""
    return db.query(Invitation).filter(Invitation.id == invitation_id).first()


def get_invitations_by_turn(db: Session, turn_id: int) -> List[Invitation]:
    """Obtener todas las invitaciones de un turno"""
    return db.query(Invitation).filter(Invitation.turn_id == turn_id).all()


def get_received_invitations(db: Session, user_id: int) -> List[Invitation]:
    """Obtener invitaciones recibidas por un usuario"""
    return (
        db.query(Invitation)
        .filter(Invitation.invited_player_id == user_id)
        .order_by(Invitation.created_at.desc())
        .all()
    )


def get_sent_invitations(db: Session, user_id: int) -> List[Invitation]:
    """Obtener invitaciones enviadas por un usuario"""
    return (
        db.query(Invitation)
        .filter(Invitation.inviter_id == user_id)
        .order_by(Invitation.created_at.desc())
        .all()
    )


def get_pending_invitations_by_turn(db: Session, turn_id: int) -> List[Invitation]:
    """Obtener invitaciones pendientes de un turno"""
    return (
        db.query(Invitation)
        .filter(and_(Invitation.turn_id == turn_id, Invitation.status == "PENDING"))
        .all()
    )


def update_invitation(
    db: Session, invitation_id: int, invitation_update: InvitationUpdate
) -> Optional[Invitation]:
    """Actualizar una invitación"""
    db_invitation = db.query(Invitation).filter(Invitation.id == invitation_id).first()

    if not db_invitation:
        return None

    update_data = invitation_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_invitation, field, value)

    db.commit()
    db.refresh(db_invitation)
    logger.info(f"Invitación actualizada: {invitation_id}")
    return db_invitation


def delete_invitation(db: Session, invitation_id: int) -> bool:
    """Eliminar una invitación"""
    db_invitation = db.query(Invitation).filter(Invitation.id == invitation_id).first()

    if not db_invitation:
        return False

    db.delete(db_invitation)
    db.commit()
    logger.info(f"Invitación eliminada: {invitation_id}")
    return True


def is_player_validated(db: Session, turn_id: int, player_id: int) -> bool:
    """
    Determinar si un jugador está validado (fue invitado por el configurador).
    Un jugador está validado si:
    1. Fue invitado directamente por el configurador (player1_id del turno)
    2. Y esa invitación fue aceptada (status = ACCEPTED)
    """
    # Obtener el turno
    turn = db.query(PregameTurn).filter(PregameTurn.id == turn_id).first()
    if not turn:
        return False

    # El configurador siempre está validado
    if turn.player1_id == player_id:
        return True

    # Verificar si el jugador fue invitado por el configurador
    invitation = (
        db.query(Invitation)
        .filter(
            and_(
                Invitation.turn_id == turn_id,
                Invitation.invited_player_id == player_id,
                Invitation.inviter_id
                == turn.player1_id,  # Invitado por el configurador
                Invitation.status == "ACCEPTED",  # Y aceptó la invitación
            )
        )
        .first()
    )

    return invitation is not None


def count_validated_invitations_sent(db: Session, turn_id: int, inviter_id: int) -> int:
    """
    Contar cuántas invitaciones validadas ha enviado un jugador en un turno.
    Esto se usa para limitar a 1 invitación por jugador validado.
    """
    return (
        db.query(Invitation)
        .filter(
            and_(
                Invitation.turn_id == turn_id,
                Invitation.inviter_id == inviter_id,
                Invitation.is_validated_invitation == True,
            )
        )
        .count()
    )


def check_existing_invitation(
    db: Session, turn_id: int, invited_player_id: int
) -> Optional[Invitation]:
    """Verificar si ya existe una invitación para un jugador en un turno"""
    return (
        db.query(Invitation)
        .filter(
            and_(
                Invitation.turn_id == turn_id,
                Invitation.invited_player_id == invited_player_id,
                Invitation.status == "PENDING",
            )
        )
        .first()
    )


def search_players(
    db: Session,
    query: Optional[str],
    current_user_id: int,
    turn_id: Optional[int] = None,
    limit: int = 50,
    require_fcm_token: bool = True,
) -> List[User]:
    """Buscar jugadores para invitar con lógica mejorada

    Args:
        db: Sesión de base de datos
        query: Término de búsqueda (opcional)
        current_user_id: ID del usuario actual (se excluye de los resultados)
        turn_id: ID del turno (opcional). Si se proporciona, se excluyen jugadores que ya están en el turno o tienen invitaciones pendientes/aceptadas
        limit: Límite de resultados
        require_fcm_token: Si es True, solo incluir jugadores con token FCM activo. Si es False, incluir todos los jugadores.
    """

    # Base query: excluir usuario actual y solo usuarios activos
    from app.models.fcm_token import FCMToken

    if require_fcm_token:
        # CRÍTICO: Solo incluir jugadores que tengan tokens FCM activos para poder recibir notificaciones
        base_query = (
            db.query(User)
            .join(
                FCMToken, and_(FCMToken.user_id == User.id, FCMToken.is_active == True)
            )
            .filter(
                and_(
                    User.id != current_user_id,  # Excluir al usuario actual
                    User.is_active == True,
                    User.is_admin == False,  # Excluir admins
                    User.is_super_admin == False,  # Excluir super admins
                )
            )
            .group_by(User.id)
        )  # Evitar duplicados si un usuario tiene múltiples tokens (usar group_by en lugar de distinct para compatibilidad con ORDER BY)
    else:
        # Para admins del club: permitir buscar todos los jugadores, incluso sin token FCM
        base_query = db.query(User).filter(
            and_(
                User.id != current_user_id,  # Excluir al usuario actual
                User.is_active == True,
                User.is_admin == False,  # Excluir admins
                User.is_super_admin == False,  # Excluir super admins
            )
        )

    # Si se proporciona turn_id, excluir jugadores que ya están en el turno o tienen invitaciones
    # y filtrar por categoría si el turno tiene restricciones
    # CRÍTICO: NO filtrar por género aquí. Las restricciones de género para partidos mixtos
    # se validan al momento de crear la invitación, no al buscar jugadores.
    # Todos los jugadores deben aparecer en la lista de búsqueda, independientemente de su género.
    if turn_id is not None:
        from app.models.pregame_turn import PregameTurn
        from app.models.invitation import Invitation

        # Obtener el turno
        turn = db.query(PregameTurn).filter(PregameTurn.id == turn_id).first()
        if turn:
            # IDs de jugadores que ya están en el turno
            players_in_turn = [
                turn.player1_id,
                turn.player2_id,
                turn.player3_id,
                turn.player4_id,
            ]
            players_in_turn = [pid for pid in players_in_turn if pid is not None]

            # IDs de jugadores con invitaciones pendientes o aceptadas para este turno
            existing_invitations = (
                db.query(Invitation)
                .filter(
                    and_(
                        Invitation.turn_id == turn_id,
                        Invitation.status.in_(["PENDING", "ACCEPTED"]),
                    )
                )
                .all()
            )
            invited_player_ids = [inv.invited_player_id for inv in existing_invitations]

            # Combinar ambas listas de IDs a excluir
            excluded_player_ids = list(set(players_in_turn + invited_player_ids))

            # Excluir estos jugadores de la búsqueda
            if excluded_player_ids:
                base_query = base_query.filter(~User.id.in_(excluded_player_ids))

            # CRÍTICO: Filtrar por categoría si el turno tiene restricciones de categoría habilitadas
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

                # Obtener todas las categorías permitidas según la restricción
                allowed_categories = CategoryRestrictionValidator.get_valid_categories(
                    turn.organizer_category, turn.category_restriction_type
                )

                # Filtrar jugadores que tengan una categoría permitida
                # Si un jugador no tiene categoría, usar "9na" como default
                # Solo incluir jugadores cuya categoría esté en la lista permitida
                if allowed_categories:
                    # Crear condición: categoría del jugador debe estar en allowed_categories
                    # O si no tiene categoría, usar "9na" como default
                    from sqlalchemy import case

                    player_category_expr = case(
                        (User.category.is_(None), "9na"),
                        (User.category == "", "9na"),
                        else_=User.category,
                    )
                    base_query = base_query.filter(
                        player_category_expr.in_(allowed_categories)
                    )

                    logger.info(
                        f"Filtrado por categoría: turn_id={turn_id}, "
                        f"organizer_category={turn.organizer_category}, "
                        f"restriction_type={turn.category_restriction_type}, "
                        f"allowed_categories={allowed_categories}"
                    )

    # Si no hay query o está vacío, devolver todos los jugadores disponibles
    # CRÍTICO: No filtrar por género. Todos los jugadores deben ser visibles en la lista.
    if not query or (isinstance(query, str) and len(query.strip()) < 1):
        return base_query.order_by(User.name.asc()).limit(limit).all()

    # Limpiar y preparar el término de búsqueda
    search_term = query.strip().lower()
    search_pattern = f"%{search_term}%"

    # Búsqueda por múltiples campos con ordenamiento por relevancia
    players = (
        base_query.filter(
            or_(
                # Coincidencias exactas primero (mayor relevancia)
                User.name.ilike(search_term),  # Nombre exacto
                User.last_name.ilike(search_term),  # Apellido exacto
                User.email.ilike(search_term),  # Email exacto
                # Combinación de nombre + apellido
                User.name.ilike(f"{search_term}%"),  # Nombre que empiece con el término
                User.last_name.ilike(
                    f"{search_term}%"
                ),  # Apellido que empiece con el término
                # Coincidencias parciales
                User.name.ilike(search_pattern),  # Nombre parcial
                User.last_name.ilike(search_pattern),  # Apellido parcial
                User.email.ilike(search_pattern),  # Email parcial
            )
        )
        .order_by(
            # Ordenamiento por relevancia:
            # 1. Coincidencias exactas en nombre
            User.name.ilike(search_term).desc(),
            # 2. Coincidencias exactas en apellido
            User.last_name.ilike(search_term).desc(),
            # 3. Coincidencias exactas en email
            User.email.ilike(search_term).desc(),
            # 4. Coincidencias que empiecen con el término
            User.name.ilike(f"{search_term}%").desc(),
            User.last_name.ilike(f"{search_term}%").desc(),
            # 5. Ordenamiento alfabético por nombre
            User.name.asc(),
        )
        .limit(limit)
        .all()
    )

    return players


def get_pending_invitations_by_turn(db: Session, turn_id: int) -> List[Invitation]:
    """Obtener todas las invitaciones pendientes de un turno"""
    return (
        db.query(Invitation)
        .filter(and_(Invitation.turn_id == turn_id, Invitation.status == "PENDING"))
        .all()
    )


def cancel_invitation(db: Session, invitation_id: int) -> bool:
    """Cancelar una invitación"""
    invitation = get_invitation(db, invitation_id)
    if not invitation:
        return False

    invitation.status = "CANCELLED"
    db.commit()
    db.refresh(invitation)
    return True


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Obtener un usuario por ID"""
    return db.query(User).filter(User.id == user_id).first()


def get_turn_by_id(db: Session, turn_id: int) -> Optional[PregameTurn]:
    """Obtener un turno por ID"""
    return db.query(PregameTurn).filter(PregameTurn.id == turn_id).first()
