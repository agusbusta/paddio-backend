from sqlalchemy.orm import Session
from typing import List, Tuple, Optional
import logging

from app.models.pregame_turn import PregameTurn
from app.models.user import User

logger = logging.getLogger(__name__)


def count_players_in_turn(turn: PregameTurn) -> int:
    """Contar jugadores actuales en un turno"""
    count = 0
    if turn.player1_id:
        count += 1
    if turn.player2_id:
        count += 1
    if turn.player3_id:
        count += 1
    if turn.player4_id:
        count += 1
    return count


def get_available_positions_in_turn(turn: PregameTurn) -> List[str]:
    """Obtener posiciones disponibles en un turno"""
    available_positions = []

    # Verificar cada posición
    if not turn.player1_id:
        available_positions.append("player1")
    if not turn.player2_id:
        available_positions.append("player2")
    if not turn.player3_id:
        available_positions.append("player3")
    if not turn.player4_id:
        available_positions.append("player4")

    return available_positions


def assign_player_to_turn(
    db: Session, turn: PregameTurn, player: User, side: str, position: str
) -> bool:
    """Asignar jugador a un turno en la posición especificada"""
    try:
        # Buscar la primera posición disponible
        if not turn.player2_id:
            turn.player2_id = player.id
            turn.player2_side = side
            turn.player2_court_position = position
        elif not turn.player3_id:
            turn.player3_id = player.id
            turn.player3_side = side
            turn.player3_court_position = position
        elif not turn.player4_id:
            turn.player4_id = player.id
            turn.player4_side = side
            turn.player4_court_position = position
        else:
            logger.error(f"Turno {turn.id} ya está completo")
            return False

        # Actualizar estado del turno si está completo
        players_count = count_players_in_turn(turn)
        if players_count == 4:
            turn.status = "READY_TO_PLAY"

        db.commit()
        logger.info(f"Jugador {player.id} asignado al turno {turn.id}")
        return True

    except Exception as e:
        logger.error(f"Error asignando jugador al turno: {e}")
        db.rollback()
        return False


def is_player_in_turn(turn: PregameTurn, player_id: int) -> bool:
    """Verificar si un jugador ya está en el turno"""
    return (
        turn.player1_id == player_id
        or turn.player2_id == player_id
        or turn.player3_id == player_id
        or turn.player4_id == player_id
    )


def get_turn_players_info(turn: PregameTurn) -> List[dict]:
    """Obtener información de todos los jugadores del turno"""
    players = []

    if turn.player1_id and turn.player1:
        players.append(
            {
                "player_id": turn.player1_id,
                "player_name": turn.player1.name,
                "player_side": turn.player1_side,
                "player_court_position": turn.player1_court_position,
                "position": "player1",
            }
        )

    if turn.player2_id and turn.player2:
        players.append(
            {
                "player_id": turn.player2_id,
                "player_name": turn.player2.name,
                "player_side": turn.player2_side,
                "player_court_position": turn.player2_court_position,
                "position": "player2",
            }
        )

    if turn.player3_id and turn.player3:
        players.append(
            {
                "player_id": turn.player3_id,
                "player_name": turn.player3.name,
                "player_side": turn.player3_side,
                "player_court_position": turn.player3_court_position,
                "position": "player3",
            }
        )

    if turn.player4_id and turn.player4:
        players.append(
            {
                "player_id": turn.player4_id,
                "player_name": turn.player4.name,
                "player_side": turn.player4_side,
                "player_court_position": turn.player4_court_position,
                "position": "player4",
            }
        )

    return players


def get_turn_players_genders(turn: PregameTurn) -> Tuple[int, int]:
    """
    Obtener conteo de géneros en un turno.
    Retorna: (cantidad_masculino, cantidad_femenino)
    """
    masculino_count = 0
    femenino_count = 0

    if turn.player1_id and turn.player1:
        gender = turn.player1.gender
        if gender == "Masculino":
            masculino_count += 1
        elif gender == "Femenino":
            femenino_count += 1

    if turn.player2_id and turn.player2:
        gender = turn.player2.gender
        if gender == "Masculino":
            masculino_count += 1
        elif gender == "Femenino":
            femenino_count += 1

    if turn.player3_id and turn.player3:
        gender = turn.player3.gender
        if gender == "Masculino":
            masculino_count += 1
        elif gender == "Femenino":
            femenino_count += 1

    if turn.player4_id and turn.player4:
        gender = turn.player4.gender
        if gender == "Masculino":
            masculino_count += 1
        elif gender == "Femenino":
            femenino_count += 1

    return (masculino_count, femenino_count)


def get_pending_invitations_genders(
    db: Session, turn: PregameTurn, exclude_invitation_id: Optional[int] = None
) -> Tuple[int, int]:
    """
    Obtener conteo de géneros de invitaciones pendientes.

    Args:
        db: Sesión de base de datos
        turn: Turno del cual obtener las invitaciones
        exclude_invitation_id: ID de invitación a excluir del conteo (útil cuando se está aceptando)

    Retorna: (cantidad_masculino, cantidad_femenino)
    """
    from app.crud import invitation as invitation_crud

    masculino_count = 0
    femenino_count = 0

    # Obtener invitaciones pendientes del turno
    pending_invitations = invitation_crud.get_pending_invitations_by_turn(db, turn.id)

    for invitation in pending_invitations:
        # Excluir la invitación especificada (si se está aceptando)
        if exclude_invitation_id and invitation.id == exclude_invitation_id:
            continue

        if invitation.invited_player:
            gender = invitation.invited_player.gender
            if gender == "Masculino":
                masculino_count += 1
            elif gender == "Femenino":
                femenino_count += 1

    return (masculino_count, femenino_count)


def validate_mixed_match_gender_balance(
    db: Session,
    turn: PregameTurn,
    new_player_gender: Optional[str],
    check_pending_invitations: bool = True,
    exclude_invitation_id: Optional[int] = None,
) -> Tuple[bool, str]:
    """
    Validar que agregar un jugador mantenga la paridad de géneros en partidos mixtos.

    IMPORTANTE: Esta validación es PROGRESIVA, solo valida cuando es necesario:
    - 0 jugadores: Permite cualquier género (no valida)
    - 1 jugador: Permite cualquier género (el segundo puede ser del opuesto)
    - 2 jugadores: Debe ser 1-1
    - 3 jugadores: Debe ser posible llegar a 2-2 (no puede haber 3 del mismo género)
    - 4 jugadores: Debe ser 2-2

    CRÍTICO: Esta función considera al organizador (player1) en el conteo.

    Retorna: (es_válido, mensaje_error)
    """
    if turn.is_mixed_match != "true":
        return (True, "")

    if not new_player_gender:
        return (True, "")  # Si no hay género, no validar (se validará en otro lugar)

    # Obtener géneros actuales (incluye al organizador que es player1)
    masculino_count, femenino_count = get_turn_players_genders(turn)

    # Contar invitaciones pendientes (excluyendo la que se está aceptando si aplica)
    pending_m, pending_f = get_pending_invitations_genders(
        db, turn, exclude_invitation_id
    )

    total_m = masculino_count + pending_m
    total_f = femenino_count + pending_f
    total_players = total_m + total_f

    # Simular agregar el nuevo jugador
    test_m = total_m
    test_f = total_f
    if new_player_gender == "Masculino":
        test_m += 1
    elif new_player_gender == "Femenino":
        test_f += 1
    else:
        return (True, "")  # Género no reconocido, no validar

    test_total = test_m + test_f

    # Validación estricta: máximo 2 de cada género
    if test_m > 2:
        gender_text = "masculino" if new_player_gender == "Masculino" else "femenino"
        return (
            False,
            f"El cupo para jugadores {gender_text} ya está completo (2/2). Otro jugador ya aceptó una invitación antes que vos.",
        )

    if test_f > 2:
        gender_text = "femenino" if new_player_gender == "Femenino" else "masculino"
        return (
            False,
            f"El cupo para jugadores {gender_text} ya está completo (2/2). Otro jugador ya aceptó una invitación antes que vos.",
        )

    # Validación progresiva según número de jugadores
    if test_total == 0 or test_total == 1:
        # Primer o segundo jugador: puede ser cualquiera
        return (True, "")
    elif test_total == 2:
        # Debe ser 1-1
        if test_m == 1 and test_f == 1:
            return (True, "")
        else:
            return (
                False,
                "Para completar la paridad, necesitás un jugador del género opuesto.",
            )
    elif test_total == 3:
        # No puede haber 3 del mismo género (debe ser 2-1 o 1-2)
        if test_m == 3:
            return (
                False,
                "No se puede agregar otro jugador masculino. Ya hay 2 masculinos y necesitás 1 femenino para completar la paridad (2-2).",
            )
        elif test_f == 3:
            return (
                False,
                "No se puede agregar otra jugadora femenina. Ya hay 2 femeninos y necesitás 1 masculino para completar la paridad (2-2).",
            )
        else:
            return (True, "")
    elif test_total == 4:
        # Debe ser 2-2
        if test_m == 2 and test_f == 2:
            return (True, "")
        else:
            return (
                False,
                "El turno debe tener exactamente 2 jugadores masculinos y 2 jugadoras femeninas.",
            )

    return (False, "El turno ya está completo.")


def validate_mixed_match_side_gender_balance(
    db: Session,
    turn: PregameTurn,
    new_player_gender: Optional[str],
    new_player_side: Optional[str],
    exclude_player_position: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Validar que en un turno mixto, cada lado (reves/drive) tenga exactamente 1 hombre y 1 mujer.

    Esta validación se aplica cuando un jugador selecciona un lado específico.
    Regla: Cada equipo (lado) debe tener 1 Masculino + 1 Femenino.

    Args:
        db: Sesión de base de datos
        turn: Turno a validar
        new_player_gender: Género del nuevo jugador (Masculino/Femenino)
        new_player_side: Lado que el nuevo jugador quiere ocupar (reves/drive)
        exclude_player_position: Posición del jugador a excluir (útil cuando se actualiza posición)

    Retorna: (es_válido, mensaje_error)
    """
    if turn.is_mixed_match != "true":
        return (True, "")  # No es partido mixto, no validar

    if not new_player_gender or not new_player_side:
        return (True, "")  # Si no hay género o lado, no validar

    # Normalizar el lado
    new_player_side = new_player_side.lower()
    if new_player_side not in ["reves", "drive"]:
        return (True, "")  # Lado inválido, se validará en otro lugar

    # Contar géneros por lado
    reves_masculino = 0
    reves_femenino = 0
    drive_masculino = 0
    drive_femenino = 0

    # Revisar cada posición del turno
    for pos_num in [1, 2, 3, 4]:
        pos_str = f"player{pos_num}"

        # Excluir la posición del jugador que se está actualizando
        if exclude_player_position and exclude_player_position == pos_str:
            continue

        player_id = getattr(turn, f"{pos_str}_id", None)
        if not player_id:
            continue

        player_side = getattr(turn, f"{pos_str}_side", None)
        if not player_side:
            continue

        # Obtener el género del jugador
        player = getattr(turn, pos_str, None)
        if not player or not player.gender:
            continue

        player_gender = player.gender
        player_side_lower = player_side.lower()

        # Contar por lado
        if player_side_lower == "reves":
            if player_gender == "Masculino":
                reves_masculino += 1
            elif player_gender == "Femenino":
                reves_femenino += 1
        elif player_side_lower == "drive":
            if player_gender == "Masculino":
                drive_masculino += 1
            elif player_gender == "Femenino":
                drive_femenino += 1

    # Agregar el nuevo jugador al conteo
    if new_player_side == "reves":
        if new_player_gender == "Masculino":
            reves_masculino += 1
        elif new_player_gender == "Femenino":
            reves_femenino += 1
    elif new_player_side == "drive":
        if new_player_gender == "Masculino":
            drive_masculino += 1
        elif new_player_gender == "Femenino":
            drive_femenino += 1

    # Validar que cada lado tenga máximo 1 de cada género
    # (permitimos que esté incompleto, pero no que tenga 2 del mismo género)
    if new_player_side == "reves":
        if new_player_gender == "Masculino" and reves_masculino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador masculino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
        elif new_player_gender == "Femenino" and reves_femenino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador femenino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
    elif new_player_side == "drive":
        if new_player_gender == "Masculino" and drive_masculino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador masculino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
        elif new_player_gender == "Femenino" and drive_femenino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador femenino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )

    return (True, "")


def validate_mixed_match_side_gender_balance(
    db: Session,
    turn: PregameTurn,
    new_player_gender: Optional[str],
    new_player_side: Optional[str],
    exclude_player_position: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Validar que en un turno mixto, cada lado (reves/drive) tenga exactamente 1 hombre y 1 mujer.

    Esta validación se aplica cuando un jugador selecciona un lado específico.
    Regla: Cada equipo (lado) debe tener 1 Masculino + 1 Femenino.

    Args:
        db: Sesión de base de datos
        turn: Turno a validar
        new_player_gender: Género del nuevo jugador (Masculino/Femenino)
        new_player_side: Lado que el nuevo jugador quiere ocupar (reves/drive)
        exclude_player_position: Posición del jugador a excluir (útil cuando se actualiza posición)

    Retorna: (es_válido, mensaje_error)
    """
    if turn.is_mixed_match != "true":
        return (True, "")  # No es partido mixto, no validar

    if not new_player_gender or not new_player_side:
        return (True, "")  # Si no hay género o lado, no validar

    # Normalizar el lado
    new_player_side = new_player_side.lower()
    if new_player_side not in ["reves", "drive"]:
        return (True, "")  # Lado inválido, se validará en otro lugar

    # Contar géneros por lado
    reves_masculino = 0
    reves_femenino = 0
    drive_masculino = 0
    drive_femenino = 0

    # Revisar cada posición del turno
    for pos_num in [1, 2, 3, 4]:
        pos_str = f"player{pos_num}"

        # Excluir la posición del jugador que se está actualizando
        if exclude_player_position and exclude_player_position == pos_str:
            continue

        player_id = getattr(turn, f"{pos_str}_id", None)
        if not player_id:
            continue

        player_side = getattr(turn, f"{pos_str}_side", None)
        if not player_side:
            continue

        # Obtener el género del jugador
        player = getattr(turn, pos_str, None)
        if not player or not player.gender:
            continue

        player_gender = player.gender
        player_side_lower = player_side.lower()

        # Contar por lado
        if player_side_lower == "reves":
            if player_gender == "Masculino":
                reves_masculino += 1
            elif player_gender == "Femenino":
                reves_femenino += 1
        elif player_side_lower == "drive":
            if player_gender == "Masculino":
                drive_masculino += 1
            elif player_gender == "Femenino":
                drive_femenino += 1

    # Agregar el nuevo jugador al conteo
    if new_player_side == "reves":
        if new_player_gender == "Masculino":
            reves_masculino += 1
        elif new_player_gender == "Femenino":
            reves_femenino += 1
    elif new_player_side == "drive":
        if new_player_gender == "Masculino":
            drive_masculino += 1
        elif new_player_gender == "Femenino":
            drive_femenino += 1

    # Validar que cada lado tenga máximo 1 de cada género
    # (permitimos que esté incompleto, pero no que tenga 2 del mismo género)
    if new_player_side == "reves":
        if new_player_gender == "Masculino" and reves_masculino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador masculino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
        elif new_player_gender == "Femenino" and reves_femenino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador femenino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
    elif new_player_side == "drive":
        if new_player_gender == "Masculino" and drive_masculino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador masculino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
        elif new_player_gender == "Femenino" and drive_femenino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador femenino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )

    return (True, "")


def validate_mixed_match_side_gender_balance(
    db: Session,
    turn: PregameTurn,
    new_player_gender: Optional[str],
    new_player_side: Optional[str],
    exclude_player_position: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Validar que en un turno mixto, cada lado (reves/drive) tenga exactamente 1 hombre y 1 mujer.

    Esta validación se aplica cuando un jugador selecciona un lado específico.
    Regla: Cada equipo (lado) debe tener 1 Masculino + 1 Femenino.

    Args:
        db: Sesión de base de datos
        turn: Turno a validar
        new_player_gender: Género del nuevo jugador (Masculino/Femenino)
        new_player_side: Lado que el nuevo jugador quiere ocupar (reves/drive)
        exclude_player_position: Posición del jugador a excluir (útil cuando se actualiza posición)

    Retorna: (es_válido, mensaje_error)
    """
    if turn.is_mixed_match != "true":
        return (True, "")  # No es partido mixto, no validar

    if not new_player_gender or not new_player_side:
        return (True, "")  # Si no hay género o lado, no validar

    # Normalizar el lado
    new_player_side = new_player_side.lower()
    if new_player_side not in ["reves", "drive"]:
        return (True, "")  # Lado inválido, se validará en otro lugar

    # Contar géneros por lado
    reves_masculino = 0
    reves_femenino = 0
    drive_masculino = 0
    drive_femenino = 0

    # Revisar cada posición del turno
    for pos_num in [1, 2, 3, 4]:
        pos_str = f"player{pos_num}"

        # Excluir la posición del jugador que se está actualizando
        if exclude_player_position and exclude_player_position == pos_str:
            continue

        player_id = getattr(turn, f"{pos_str}_id", None)
        if not player_id:
            continue

        player_side = getattr(turn, f"{pos_str}_side", None)
        if not player_side:
            continue

        # Obtener el género del jugador
        player = getattr(turn, pos_str, None)
        if not player or not player.gender:
            continue

        player_gender = player.gender
        player_side_lower = player_side.lower()

        # Contar por lado
        if player_side_lower == "reves":
            if player_gender == "Masculino":
                reves_masculino += 1
            elif player_gender == "Femenino":
                reves_femenino += 1
        elif player_side_lower == "drive":
            if player_gender == "Masculino":
                drive_masculino += 1
            elif player_gender == "Femenino":
                drive_femenino += 1

    # Agregar el nuevo jugador al conteo
    if new_player_side == "reves":
        if new_player_gender == "Masculino":
            reves_masculino += 1
        elif new_player_gender == "Femenino":
            reves_femenino += 1
    elif new_player_side == "drive":
        if new_player_gender == "Masculino":
            drive_masculino += 1
        elif new_player_gender == "Femenino":
            drive_femenino += 1

    # Validar que cada lado tenga máximo 1 de cada género
    # (permitimos que esté incompleto, pero no que tenga 2 del mismo género)
    if new_player_side == "reves":
        if new_player_gender == "Masculino" and reves_masculino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador masculino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
        elif new_player_gender == "Femenino" and reves_femenino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador femenino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
    elif new_player_side == "drive":
        if new_player_gender == "Masculino" and drive_masculino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador masculino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
        elif new_player_gender == "Femenino" and drive_femenino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador femenino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )

    return (True, "")


def validate_mixed_match_side_gender_balance(
    db: Session,
    turn: PregameTurn,
    new_player_gender: Optional[str],
    new_player_side: Optional[str],
    exclude_player_position: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Validar que en un turno mixto, cada lado (reves/drive) tenga exactamente 1 hombre y 1 mujer.

    Esta validación se aplica cuando un jugador selecciona un lado específico.
    Regla: Cada equipo (lado) debe tener 1 Masculino + 1 Femenino.

    Args:
        db: Sesión de base de datos
        turn: Turno a validar
        new_player_gender: Género del nuevo jugador (Masculino/Femenino)
        new_player_side: Lado que el nuevo jugador quiere ocupar (reves/drive)
        exclude_player_position: Posición del jugador a excluir (útil cuando se actualiza posición)

    Retorna: (es_válido, mensaje_error)
    """
    if turn.is_mixed_match != "true":
        return (True, "")  # No es partido mixto, no validar

    if not new_player_gender or not new_player_side:
        return (True, "")  # Si no hay género o lado, no validar

    # Normalizar el lado
    new_player_side = new_player_side.lower()
    if new_player_side not in ["reves", "drive"]:
        return (True, "")  # Lado inválido, se validará en otro lugar

    # Contar géneros por lado
    reves_masculino = 0
    reves_femenino = 0
    drive_masculino = 0
    drive_femenino = 0

    # Revisar cada posición del turno
    for pos_num in [1, 2, 3, 4]:
        pos_str = f"player{pos_num}"

        # Excluir la posición del jugador que se está actualizando
        if exclude_player_position and exclude_player_position == pos_str:
            continue

        player_id = getattr(turn, f"{pos_str}_id", None)
        if not player_id:
            continue

        player_side = getattr(turn, f"{pos_str}_side", None)
        if not player_side:
            continue

        # Obtener el género del jugador
        player = getattr(turn, pos_str, None)
        if not player or not player.gender:
            continue

        player_gender = player.gender
        player_side_lower = player_side.lower()

        # Contar por lado
        if player_side_lower == "reves":
            if player_gender == "Masculino":
                reves_masculino += 1
            elif player_gender == "Femenino":
                reves_femenino += 1
        elif player_side_lower == "drive":
            if player_gender == "Masculino":
                drive_masculino += 1
            elif player_gender == "Femenino":
                drive_femenino += 1

    # Agregar el nuevo jugador al conteo
    if new_player_side == "reves":
        if new_player_gender == "Masculino":
            reves_masculino += 1
        elif new_player_gender == "Femenino":
            reves_femenino += 1
    elif new_player_side == "drive":
        if new_player_gender == "Masculino":
            drive_masculino += 1
        elif new_player_gender == "Femenino":
            drive_femenino += 1

    # Validar que cada lado tenga máximo 1 de cada género
    # (permitimos que esté incompleto, pero no que tenga 2 del mismo género)
    if new_player_side == "reves":
        if new_player_gender == "Masculino" and reves_masculino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador masculino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
        elif new_player_gender == "Femenino" and reves_femenino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador femenino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
    elif new_player_side == "drive":
        if new_player_gender == "Masculino" and drive_masculino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador masculino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
        elif new_player_gender == "Femenino" and drive_femenino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador femenino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )

    return (True, "")


def validate_mixed_match_side_gender_balance(
    db: Session,
    turn: PregameTurn,
    new_player_gender: Optional[str],
    new_player_side: Optional[str],
    exclude_player_position: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Validar que en un turno mixto, cada lado (reves/drive) tenga exactamente 1 hombre y 1 mujer.

    Esta validación se aplica cuando un jugador selecciona un lado específico.
    Regla: Cada equipo (lado) debe tener 1 Masculino + 1 Femenino.

    Args:
        db: Sesión de base de datos
        turn: Turno a validar
        new_player_gender: Género del nuevo jugador (Masculino/Femenino)
        new_player_side: Lado que el nuevo jugador quiere ocupar (reves/drive)
        exclude_player_position: Posición del jugador a excluir (útil cuando se actualiza posición)

    Retorna: (es_válido, mensaje_error)
    """
    if turn.is_mixed_match != "true":
        return (True, "")  # No es partido mixto, no validar

    if not new_player_gender or not new_player_side:
        return (True, "")  # Si no hay género o lado, no validar

    # Normalizar el lado
    new_player_side = new_player_side.lower()
    if new_player_side not in ["reves", "drive"]:
        return (True, "")  # Lado inválido, se validará en otro lugar

    # Contar géneros por lado
    reves_masculino = 0
    reves_femenino = 0
    drive_masculino = 0
    drive_femenino = 0

    # Revisar cada posición del turno
    for pos_num in [1, 2, 3, 4]:
        pos_str = f"player{pos_num}"

        # Excluir la posición del jugador que se está actualizando
        if exclude_player_position and exclude_player_position == pos_str:
            continue

        player_id = getattr(turn, f"{pos_str}_id", None)
        if not player_id:
            continue

        player_side = getattr(turn, f"{pos_str}_side", None)
        if not player_side:
            continue

        # Obtener el género del jugador
        player = getattr(turn, pos_str, None)
        if not player or not player.gender:
            continue

        player_gender = player.gender
        player_side_lower = player_side.lower()

        # Contar por lado
        if player_side_lower == "reves":
            if player_gender == "Masculino":
                reves_masculino += 1
            elif player_gender == "Femenino":
                reves_femenino += 1
        elif player_side_lower == "drive":
            if player_gender == "Masculino":
                drive_masculino += 1
            elif player_gender == "Femenino":
                drive_femenino += 1

    # Agregar el nuevo jugador al conteo
    if new_player_side == "reves":
        if new_player_gender == "Masculino":
            reves_masculino += 1
        elif new_player_gender == "Femenino":
            reves_femenino += 1
    elif new_player_side == "drive":
        if new_player_gender == "Masculino":
            drive_masculino += 1
        elif new_player_gender == "Femenino":
            drive_femenino += 1

    # Validar que cada lado tenga máximo 1 de cada género
    # (permitimos que esté incompleto, pero no que tenga 2 del mismo género)
    if new_player_side == "reves":
        if new_player_gender == "Masculino" and reves_masculino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador masculino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
        elif new_player_gender == "Femenino" and reves_femenino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador femenino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
    elif new_player_side == "drive":
        if new_player_gender == "Masculino" and drive_masculino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador masculino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
        elif new_player_gender == "Femenino" and drive_femenino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador femenino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )

    return (True, "")


def can_invite_player_to_mixed_match(
    db: Session, turn: PregameTurn, invited_player_gender: str
) -> Tuple[bool, str]:
    """
    Verificar si se puede invitar a un jugador a un partido mixto.
    CRÍTICO: Esta función considera al organizador (player1) en el conteo.
    Retorna: (puede_invitar, mensaje_error)
    """
    if turn.is_mixed_match != "true":
        return (True, "")

    # Obtener géneros actuales (incluye al organizador que es player1)
    masculino_count, femenino_count = get_turn_players_genders(turn)
    pending_m, pending_f = get_pending_invitations_genders(db, turn)

    total_m = masculino_count + pending_m
    total_f = femenino_count + pending_f
    total_players = total_m + total_f

    # Si ya hay 4 jugadores (confirmados + pendientes), no se puede invitar más
    if total_players >= 4:
        return (False, "El turno ya está completo. No hay lugares disponibles.")

    # Simular agregar el nuevo jugador
    test_m = total_m
    test_f = total_f
    if invited_player_gender == "Masculino":
        test_m += 1
    elif invited_player_gender == "Femenino":
        test_f += 1
    else:
        return (False, "El jugador debe tener género definido (Masculino o Femenino)")

    test_total = test_m + test_f

    # Validación estricta: máximo 2 de cada género
    if test_m > 2:
        needed_f = 2 - total_f
        if needed_f > 0:
            return (
                False,
                f"Ya hay 2 masculinos confirmados/invitados. Necesitás invitar {needed_f} mujer{'es' if needed_f > 1 else ''} para completar la paridad (2-2).",
            )
        else:
            return (
                False,
                "Ya hay 2 masculinos confirmados/invitados. No se puede invitar más jugadores masculinos.",
            )

    if test_f > 2:
        needed_m = 2 - total_m
        if needed_m > 0:
            return (
                False,
                f"Ya hay 2 femeninos confirmados/invitados. Necesitás invitar {needed_m} hombre{'s' if needed_m > 1 else ''} para completar la paridad (2-2).",
            )
        else:
            return (
                False,
                "Ya hay 2 femeninos confirmados/invitados. No se puede invitar más jugadoras femeninas.",
            )

    # Validación progresiva según número de jugadores
    # CRÍTICO: La validación debe ser más flexible en las primeras etapas
    # para permitir que se complete el cupo de cada género (2/2)
    if test_total == 1:
        # Solo el organizador - puede invitar cualquiera
        return (True, "")
    elif test_total == 2:
        # Con 2 jugadores totales, puede ser:
        # - 2-0 (organizador + 1 del mismo género) - PERMITIDO para completar cupo
        # - 1-1 (organizador + 1 del género opuesto) - PERMITIDO
        # - 0-2 (organizador + 1 del mismo género si organizador es femenino) - PERMITIDO
        # Solo bloquear si ya hay 2 de un género y se intenta agregar otro del mismo
        if test_m == 2 and test_f == 0:
            # 2 masculinos, 0 femeninos - PERMITIDO (puede invitar después a 2 femeninas)
            return (True, "")
        elif test_m == 0 and test_f == 2:
            # 0 masculinos, 2 femeninas - PERMITIDO (puede invitar después a 2 masculinos)
            return (True, "")
        elif test_m == 1 and test_f == 1:
            # 1-1 - PERMITIDO (paridad inicial)
            return (True, "")
        else:
            # Cualquier otra combinación con 2 jugadores es válida
            return (True, "")
    elif test_total == 3:
        # No puede haber 3 del mismo género (debe ser 2-1 o 1-2)
        if test_m == 3:
            return (
                False,
                "No se puede invitar otro jugador masculino. Ya hay 2 masculinos y necesitás 1 femenino para completar la paridad (2-2).",
            )
        elif test_f == 3:
            return (
                False,
                "No se puede invitar otra jugadora femenina. Ya hay 2 femeninos y necesitás 1 masculino para completar la paridad (2-2).",
            )
        else:
            return (True, "")
    elif test_total == 4:
        # Debe ser 2-2
        if test_m == 2 and test_f == 2:
            return (True, "")
        else:
            return (
                False,
                "El turno debe tener exactamente 2 jugadores masculinos y 2 jugadoras femeninas.",
            )

    return (False, "El turno ya está completo.")


def validate_mixed_match_side_gender_balance(
    db: Session,
    turn: PregameTurn,
    new_player_gender: Optional[str],
    new_player_side: Optional[str],
    exclude_player_position: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Validar que en un turno mixto, cada lado (reves/drive) tenga exactamente 1 hombre y 1 mujer.

    Esta validación se aplica cuando un jugador selecciona un lado específico.
    Regla: Cada equipo (lado) debe tener 1 Masculino + 1 Femenino.

    Args:
        db: Sesión de base de datos
        turn: Turno a validar
        new_player_gender: Género del nuevo jugador (Masculino/Femenino)
        new_player_side: Lado que el nuevo jugador quiere ocupar (reves/drive)
        exclude_player_position: Posición del jugador a excluir (útil cuando se actualiza posición)

    Retorna: (es_válido, mensaje_error)
    """
    if turn.is_mixed_match != "true":
        return (True, "")  # No es partido mixto, no validar

    if not new_player_gender or not new_player_side:
        return (True, "")  # Si no hay género o lado, no validar

    # Normalizar el lado
    new_player_side = new_player_side.lower()
    if new_player_side not in ["reves", "drive"]:
        return (True, "")  # Lado inválido, se validará en otro lugar

    # Contar géneros por lado
    reves_masculino = 0
    reves_femenino = 0
    drive_masculino = 0
    drive_femenino = 0

    # Revisar cada posición del turno
    for pos_num in [1, 2, 3, 4]:
        pos_str = f"player{pos_num}"

        # Excluir la posición del jugador que se está actualizando
        if exclude_player_position and exclude_player_position == pos_str:
            continue

        player_id = getattr(turn, f"{pos_str}_id", None)
        if not player_id:
            continue

        player_side = getattr(turn, f"{pos_str}_side", None)
        if not player_side:
            continue

        # Obtener el género del jugador
        player = getattr(turn, pos_str, None)
        if not player or not player.gender:
            continue

        player_gender = player.gender
        player_side_lower = player_side.lower()

        # Contar por lado
        if player_side_lower == "reves":
            if player_gender == "Masculino":
                reves_masculino += 1
            elif player_gender == "Femenino":
                reves_femenino += 1
        elif player_side_lower == "drive":
            if player_gender == "Masculino":
                drive_masculino += 1
            elif player_gender == "Femenino":
                drive_femenino += 1

    # Agregar el nuevo jugador al conteo
    if new_player_side == "reves":
        if new_player_gender == "Masculino":
            reves_masculino += 1
        elif new_player_gender == "Femenino":
            reves_femenino += 1
    elif new_player_side == "drive":
        if new_player_gender == "Masculino":
            drive_masculino += 1
        elif new_player_gender == "Femenino":
            drive_femenino += 1

    # Validar que cada lado tenga máximo 1 de cada género
    # (permitimos que esté incompleto, pero no que tenga 2 del mismo género)
    if new_player_side == "reves":
        if new_player_gender == "Masculino" and reves_masculino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador masculino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
        elif new_player_gender == "Femenino" and reves_femenino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador femenino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
    elif new_player_side == "drive":
        if new_player_gender == "Masculino" and drive_masculino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador masculino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
        elif new_player_gender == "Femenino" and drive_femenino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador femenino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )

    return (True, "")  # No es partido mixto

    # Obtener géneros actuales
    masculino_count, femenino_count = get_turn_players_genders(turn)
    pending_m, pending_f = get_pending_invitations_genders(db, turn)

    total_m = masculino_count + pending_m
    total_f = femenino_count + pending_f
    total_players = total_m + total_f

    # Si ya hay 4 jugadores (confirmados + pendientes), no se puede invitar más
    if total_players >= 4:
        return (False, "El turno ya está completo")

    # Calcular cuántos de cada género se necesitan
    if total_players == 0:
        # Primer jugador: puede ser cualquiera
        return (True, "")


def validate_mixed_match_side_gender_balance(
    db: Session,
    turn: PregameTurn,
    new_player_gender: Optional[str],
    new_player_side: Optional[str],
    exclude_player_position: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Validar que en un turno mixto, cada lado (reves/drive) tenga exactamente 1 hombre y 1 mujer.

    Esta validación se aplica cuando un jugador selecciona un lado específico.
    Regla: Cada equipo (lado) debe tener 1 Masculino + 1 Femenino.

    Args:
        db: Sesión de base de datos
        turn: Turno a validar
        new_player_gender: Género del nuevo jugador (Masculino/Femenino)
        new_player_side: Lado que el nuevo jugador quiere ocupar (reves/drive)
        exclude_player_position: Posición del jugador a excluir (útil cuando se actualiza posición)

    Retorna: (es_válido, mensaje_error)
    """
    if turn.is_mixed_match != "true":
        return (True, "")  # No es partido mixto, no validar

    if not new_player_gender or not new_player_side:
        return (True, "")  # Si no hay género o lado, no validar

    # Normalizar el lado
    new_player_side = new_player_side.lower()
    if new_player_side not in ["reves", "drive"]:
        return (True, "")  # Lado inválido, se validará en otro lugar

    # Contar géneros por lado
    reves_masculino = 0
    reves_femenino = 0
    drive_masculino = 0
    drive_femenino = 0

    # Revisar cada posición del turno
    for pos_num in [1, 2, 3, 4]:
        pos_str = f"player{pos_num}"

        # Excluir la posición del jugador que se está actualizando
        if exclude_player_position and exclude_player_position == pos_str:
            continue

        player_id = getattr(turn, f"{pos_str}_id", None)
        if not player_id:
            continue

        player_side = getattr(turn, f"{pos_str}_side", None)
        if not player_side:
            continue

        # Obtener el género del jugador
        player = getattr(turn, pos_str, None)
        if not player or not player.gender:
            continue

        player_gender = player.gender
        player_side_lower = player_side.lower()

        # Contar por lado
        if player_side_lower == "reves":
            if player_gender == "Masculino":
                reves_masculino += 1
            elif player_gender == "Femenino":
                reves_femenino += 1
        elif player_side_lower == "drive":
            if player_gender == "Masculino":
                drive_masculino += 1
            elif player_gender == "Femenino":
                drive_femenino += 1

    # Agregar el nuevo jugador al conteo
    if new_player_side == "reves":
        if new_player_gender == "Masculino":
            reves_masculino += 1
        elif new_player_gender == "Femenino":
            reves_femenino += 1
    elif new_player_side == "drive":
        if new_player_gender == "Masculino":
            drive_masculino += 1
        elif new_player_gender == "Femenino":
            drive_femenino += 1

    # Validar que cada lado tenga máximo 1 de cada género
    # (permitimos que esté incompleto, pero no que tenga 2 del mismo género)
    if new_player_side == "reves":
        if new_player_gender == "Masculino" and reves_masculino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador masculino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
        elif new_player_gender == "Femenino" and reves_femenino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador femenino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
    elif new_player_side == "drive":
        if new_player_gender == "Masculino" and drive_masculino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador masculino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
        elif new_player_gender == "Femenino" and drive_femenino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador femenino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )

    return (True, "")


def validate_mixed_match_side_gender_balance(
    db: Session,
    turn: PregameTurn,
    new_player_gender: Optional[str],
    new_player_side: Optional[str],
    exclude_player_position: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Validar que en un turno mixto, cada lado (reves/drive) tenga exactamente 1 hombre y 1 mujer.

    Esta validación se aplica cuando un jugador selecciona un lado específico.
    Regla: Cada equipo (lado) debe tener 1 Masculino + 1 Femenino.

    Args:
        db: Sesión de base de datos
        turn: Turno a validar
        new_player_gender: Género del nuevo jugador (Masculino/Femenino)
        new_player_side: Lado que el nuevo jugador quiere ocupar (reves/drive)
        exclude_player_position: Posición del jugador a excluir (útil cuando se actualiza posición)

    Retorna: (es_válido, mensaje_error)
    """
    if turn.is_mixed_match != "true":
        return (True, "")  # No es partido mixto, no validar

    if not new_player_gender or not new_player_side:
        return (True, "")  # Si no hay género o lado, no validar

    # Normalizar el lado
    new_player_side = new_player_side.lower()
    if new_player_side not in ["reves", "drive"]:
        return (True, "")  # Lado inválido, se validará en otro lugar

    # Contar géneros por lado
    reves_masculino = 0
    reves_femenino = 0
    drive_masculino = 0
    drive_femenino = 0

    # Revisar cada posición del turno
    for pos_num in [1, 2, 3, 4]:
        pos_str = f"player{pos_num}"

        # Excluir la posición del jugador que se está actualizando
        if exclude_player_position and exclude_player_position == pos_str:
            continue

        player_id = getattr(turn, f"{pos_str}_id", None)
        if not player_id:
            continue

        player_side = getattr(turn, f"{pos_str}_side", None)
        if not player_side:
            continue

        # Obtener el género del jugador
        player = getattr(turn, pos_str, None)
        if not player or not player.gender:
            continue

        player_gender = player.gender
        player_side_lower = player_side.lower()

        # Contar por lado
        if player_side_lower == "reves":
            if player_gender == "Masculino":
                reves_masculino += 1
            elif player_gender == "Femenino":
                reves_femenino += 1
        elif player_side_lower == "drive":
            if player_gender == "Masculino":
                drive_masculino += 1
            elif player_gender == "Femenino":
                drive_femenino += 1

    # Agregar el nuevo jugador al conteo
    if new_player_side == "reves":
        if new_player_gender == "Masculino":
            reves_masculino += 1
        elif new_player_gender == "Femenino":
            reves_femenino += 1
    elif new_player_side == "drive":
        if new_player_gender == "Masculino":
            drive_masculino += 1
        elif new_player_gender == "Femenino":
            drive_femenino += 1

    # Validar que cada lado tenga máximo 1 de cada género
    # (permitimos que esté incompleto, pero no que tenga 2 del mismo género)
    if new_player_side == "reves":
        if new_player_gender == "Masculino" and reves_masculino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador masculino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
        elif new_player_gender == "Femenino" and reves_femenino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador femenino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
    elif new_player_side == "drive":
        if new_player_gender == "Masculino" and drive_masculino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador masculino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
        elif new_player_gender == "Femenino" and drive_femenino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador femenino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )

    return (True, "")


def validate_mixed_match_side_gender_balance(
    db: Session,
    turn: PregameTurn,
    new_player_gender: Optional[str],
    new_player_side: Optional[str],
    exclude_player_position: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Validar que en un turno mixto, cada lado (reves/drive) tenga exactamente 1 hombre y 1 mujer.

    Esta validación se aplica cuando un jugador selecciona un lado específico.
    Regla: Cada equipo (lado) debe tener 1 Masculino + 1 Femenino.

    Args:
        db: Sesión de base de datos
        turn: Turno a validar
        new_player_gender: Género del nuevo jugador (Masculino/Femenino)
        new_player_side: Lado que el nuevo jugador quiere ocupar (reves/drive)
        exclude_player_position: Posición del jugador a excluir (útil cuando se actualiza posición)

    Retorna: (es_válido, mensaje_error)
    """
    if turn.is_mixed_match != "true":
        return (True, "")  # No es partido mixto, no validar

    if not new_player_gender or not new_player_side:
        return (True, "")  # Si no hay género o lado, no validar

    # Normalizar el lado
    new_player_side = new_player_side.lower()
    if new_player_side not in ["reves", "drive"]:
        return (True, "")  # Lado inválido, se validará en otro lugar

    # Contar géneros por lado
    reves_masculino = 0
    reves_femenino = 0
    drive_masculino = 0
    drive_femenino = 0

    # Revisar cada posición del turno
    for pos_num in [1, 2, 3, 4]:
        pos_str = f"player{pos_num}"

        # Excluir la posición del jugador que se está actualizando
        if exclude_player_position and exclude_player_position == pos_str:
            continue

        player_id = getattr(turn, f"{pos_str}_id", None)
        if not player_id:
            continue

        player_side = getattr(turn, f"{pos_str}_side", None)
        if not player_side:
            continue

        # Obtener el género del jugador
        player = getattr(turn, pos_str, None)
        if not player or not player.gender:
            continue

        player_gender = player.gender
        player_side_lower = player_side.lower()

        # Contar por lado
        if player_side_lower == "reves":
            if player_gender == "Masculino":
                reves_masculino += 1
            elif player_gender == "Femenino":
                reves_femenino += 1
        elif player_side_lower == "drive":
            if player_gender == "Masculino":
                drive_masculino += 1
            elif player_gender == "Femenino":
                drive_femenino += 1

    # Agregar el nuevo jugador al conteo
    if new_player_side == "reves":
        if new_player_gender == "Masculino":
            reves_masculino += 1
        elif new_player_gender == "Femenino":
            reves_femenino += 1
    elif new_player_side == "drive":
        if new_player_gender == "Masculino":
            drive_masculino += 1
        elif new_player_gender == "Femenino":
            drive_femenino += 1

    # Validar que cada lado tenga máximo 1 de cada género
    # (permitimos que esté incompleto, pero no que tenga 2 del mismo género)
    if new_player_side == "reves":
        if new_player_gender == "Masculino" and reves_masculino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador masculino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
        elif new_player_gender == "Femenino" and reves_femenino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador femenino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
    elif new_player_side == "drive":
        if new_player_gender == "Masculino" and drive_masculino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador masculino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )
        elif new_player_gender == "Femenino" and drive_femenino > 1:
            return (
                False,
                "Ese lado ya tiene un jugador femenino. En turnos mixtos cada equipo debe estar conformado por 1 hombre y 1 mujer.",
            )

    return (True, "")
