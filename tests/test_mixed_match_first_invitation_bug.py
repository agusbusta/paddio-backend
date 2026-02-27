"""
Tests para validar el error reportado:
"Turnos Mixtos – Bloqueo incorrecto de invitaciones al mismo género del jugador configurador (primera tanda)"

Este test suite valida:
1. Que un organizador masculino puede invitar a otro masculino en la primera tanda (cuando hay 1/2 masculinos)
2. Que un organizador femenino puede invitar a otra femenina en la primera tanda (cuando hay 1/2 femeninas)
3. Que el sistema NO bloquea incorrectamente cuando el cupo muestra 1/2
4. Que la lógica del backend coincide con el estado visual del frontend
"""
import pytest
from sqlalchemy.orm import Session

from app.models.pregame_turn import PregameTurnStatus
from app.models.invitation import Invitation
from app.utils.turn_utils import (
    get_turn_players_genders,
    can_invite_player_to_mixed_match,
    get_pending_invitations_genders,
)


def test_male_organizer_can_invite_male_in_first_batch(db: Session, sample_turn, sample_user_male):
    """
    Test: Un organizador masculino DEBE poder invitar a otro masculino en la primera tanda
    cuando el cupo muestra 1/2 masculinos (solo el organizador)
    """
    # Configurar turno como mixto
    sample_turn.is_mixed_match = "true"
    db.commit()
    db.refresh(sample_turn)
    
    # Verificar estado inicial: solo el organizador (1 masculino, 0 femenino)
    masculino_count, femenino_count = get_turn_players_genders(sample_turn)
    assert masculino_count == 1  # El organizador
    assert femenino_count == 0
    
    # Verificar que NO hay invitaciones pendientes
    pending_m, pending_f = get_pending_invitations_genders(db, sample_turn)
    assert pending_m == 0
    assert pending_f == 0
    
    # CRÍTICO: El organizador debe poder invitar a otro masculino
    # El cupo muestra 1/2 masculinos, así que debe permitir invitar a 1 más
    can_invite, error_message = can_invite_player_to_mixed_match(
        db, sample_turn, "Masculino"
    )
    
    # DEBE permitir la invitación
    assert can_invite == True, f"No se puede invitar a un masculino cuando hay 1/2. Error: {error_message}"
    assert error_message == "" or "completo" not in error_message.lower()


def test_female_organizer_can_invite_female_in_first_batch(db: Session, sample_turn, sample_user_female):
    """
    Test: Un organizador femenino DEBE poder invitar a otra femenina en la primera tanda
    cuando el cupo muestra 1/2 femeninas (solo la organizadora)
    """
    # Crear un turno con organizadora femenina
    from app.models.user import User
    from app.models.turn import Turn
    from app.models.court import Court
    from app.models.club import Club
    from datetime import datetime, time
    import json
    
    # Crear club y cancha
    club = Club(
        id=2,
        name="Test Club 2",
        address="Test Address 2",
        opening_time=time(8, 0),
        closing_time=time(22, 0)
    )
    db.add(club)
    db.flush()
    
    court = Court(id=2, club_id=2, name="Court 2")
    db.add(court)
    db.flush()
    
    turn_data = {"turns": [{"start_time": "10:00", "end_time": "11:30", "price": 1000}]}
    turn = Turn(id=2, club_id=2, turns_data=turn_data)
    db.add(turn)
    db.flush()
    
    # Crear turno con organizadora femenina
    female_turn = sample_turn.__class__(
        id=2,
        turn_id=2,
        court_id=2,
        date=datetime.now(),
        start_time="10:00",
        end_time="11:30",
        price=1000,
        status=PregameTurnStatus.PENDING,
        player1_id=sample_user_female.id,
        is_mixed_match="true",
        category_restricted="false",
        category_restriction_type="NONE"
    )
    db.add(female_turn)
    db.commit()
    db.refresh(female_turn)
    
    # Verificar estado inicial: solo la organizadora (0 masculino, 1 femenino)
    masculino_count, femenino_count = get_turn_players_genders(female_turn)
    assert masculino_count == 0
    assert femenino_count == 1  # La organizadora
    
    # CRÍTICO: La organizadora debe poder invitar a otra femenina
    # El cupo muestra 1/2 femeninas, así que debe permitir invitar a 1 más
    can_invite, error_message = can_invite_player_to_mixed_match(
        db, female_turn, "Femenino"
    )
    
    # DEBE permitir la invitación
    assert can_invite == True, f"No se puede invitar a una femenina cuando hay 1/2. Error: {error_message}"
    assert error_message == "" or "completo" not in error_message.lower()


def test_male_organizer_cannot_invite_third_male(db: Session, sample_turn, sample_user_male):
    """
    Test: Un organizador masculino NO debe poder invitar a un tercer masculino
    cuando ya hay 2 masculinos (organizador + 1 confirmado)
    """
    # Configurar turno como mixto
    sample_turn.is_mixed_match = "true"
    
    # Agregar un segundo masculino confirmado
    from app.models.user import User
    second_male = User(
        id=3,
        name="Second",
        last_name="Male",
        email="second_male@example.com",
        hashed_password="hashed",
        is_active=True,
        gender="Masculino",
        category="6ta"
    )
    db.add(second_male)
    db.commit()
    db.refresh(second_male)
    
    sample_turn.player2_id = second_male.id
    db.commit()
    db.refresh(sample_turn)
    
    # Verificar estado: 2 masculinos, 0 femenino
    masculino_count, femenino_count = get_turn_players_genders(sample_turn)
    assert masculino_count == 2
    assert femenino_count == 0
    
    # CRÍTICO: NO debe permitir invitar a un tercer masculino
    can_invite, error_message = can_invite_player_to_mixed_match(
        db, sample_turn, "Masculino"
    )
    
    # DEBE rechazar la invitación
    assert can_invite == False, "Se permitió invitar a un tercer masculino cuando ya hay 2"
    assert "2 masculinos" in error_message.lower() or "completo" in error_message.lower()


def test_male_organizer_can_invite_male_after_inviting_female(db: Session, sample_turn, sample_user_male, sample_user_female):
    """
    Test: Un organizador masculino DEBE poder invitar a un masculino
    después de haber invitado a una femenina (en segunda tanda)
    """
    # Configurar turno como mixto
    sample_turn.is_mixed_match = "true"
    db.commit()
    db.refresh(sample_turn)
    
    # Crear una invitación pendiente a una femenina
    invitation = Invitation(
        turn_id=sample_turn.id,
        inviter_id=sample_turn.player1_id,
        invited_player_id=sample_user_female.id,
        status="PENDING",
        is_validated_invitation=False,
        is_external_request=False
    )
    db.add(invitation)
    db.commit()
    
    # Verificar estado: 1 masculino (organizador), 0 femenino confirmado, 1 femenino pendiente
    masculino_count, femenino_count = get_turn_players_genders(sample_turn)
    assert masculino_count == 1
    assert femenino_count == 0
    
    pending_m, pending_f = get_pending_invitations_genders(db, sample_turn)
    assert pending_m == 0
    assert pending_f == 1
    
    # CRÍTICO: Debe poder invitar a un masculino (el cupo muestra 1/2 masculinos)
    can_invite, error_message = can_invite_player_to_mixed_match(
        db, sample_turn, "Masculino"
    )
    
    # DEBE permitir la invitación
    assert can_invite == True, f"No se puede invitar a un masculino después de invitar a una femenina. Error: {error_message}"


def test_gender_balance_calculation_includes_organizer(db: Session, sample_turn):
    """
    Test: El cálculo de balance de géneros DEBE incluir al organizador desde el inicio
    """
    # Configurar turno como mixto
    sample_turn.is_mixed_match = "true"
    db.commit()
    db.refresh(sample_turn)
    
    # Verificar que el organizador está contado
    masculino_count, femenino_count = get_turn_players_genders(sample_turn)
    
    # El organizador es masculino, así que debe haber 1 masculino
    assert masculino_count == 1, "El organizador no está siendo contado en el balance de géneros"
    assert femenino_count == 0
    
    # El total debe ser 1 (solo el organizador)
    total = masculino_count + femenino_count
    assert total == 1, f"El total de jugadores debe ser 1 (solo organizador), pero es {total}"


def test_can_invite_same_gender_when_1_of_2_available(db: Session, sample_turn, sample_user_male):
    """
    Test: Se DEBE poder invitar al mismo género cuando hay 1/2 disponibles
    Este es el caso específico del error reportado
    """
    # Configurar turno como mixto
    sample_turn.is_mixed_match = "true"
    db.commit()
    db.refresh(sample_turn)
    
    # Estado: 1 masculino (organizador), 0 femenino
    # Cupo visual: 1/2 masculinos, 0/2 femeninos
    masculino_count, femenino_count = get_turn_players_genders(sample_turn)
    pending_m, pending_f = get_pending_invitations_genders(db, sample_turn)
    
    total_m = masculino_count + pending_m
    total_f = femenino_count + pending_f
    
    # Verificar que el cupo muestra 1/2 masculinos
    assert total_m == 1, f"El cupo debe mostrar 1/2 masculinos, pero muestra {total_m}/2"
    assert total_f == 0
    
    # CRÍTICO: Debe poder invitar a otro masculino
    # El error reportado dice que esto se bloquea incorrectamente
    can_invite, error_message = can_invite_player_to_mixed_match(
        db, sample_turn, "Masculino"
    )
    
    # DEBE permitir (este es el test que valida si el error existe)
    assert can_invite == True, (
        f"ERROR REPRODUCIDO: No se puede invitar a un masculino cuando hay 1/2. "
        f"Error: {error_message}. "
        f"Estado: {total_m}/2 masculinos, {total_f}/2 femeninos"
    )
