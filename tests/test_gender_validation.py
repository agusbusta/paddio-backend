"""
Tests para validar la lógica de géneros en turnos mixtos
"""
import pytest

from app.utils.turn_utils import (
    get_turn_players_genders,
    can_invite_player_to_mixed_match,
    validate_mixed_match_gender_balance
)


def test_organizer_counted_in_gender_balance(db, sample_turn, sample_user_male):
    """
    Test: El organizador debe ser contado en el balance de géneros
    """
    # El turno tiene solo al organizador (masculino)
    masculino_count, femenino_count = get_turn_players_genders(sample_turn)
    
    assert masculino_count == 1  # El organizador
    assert femenino_count == 0


def test_cannot_invite_male_when_2_males_already_present(db, sample_turn, sample_user_male):
    """
    Test: No se puede invitar un masculino cuando ya hay 2 masculinos (organizador + 1 confirmado)
    """
    # Configurar turno como mixto
    sample_turn.is_mixed_match = "true"
    
    # Agregar un jugador masculino confirmado
    sample_turn.player2_id = sample_user_male.id
    db.commit()
    db.refresh(sample_turn)
    
    # Intentar invitar otro masculino
    can_invite, error_message = can_invite_player_to_mixed_match(
        db, sample_turn, "Masculino"
    )
    
    assert can_invite == False
    assert "2 masculinos" in error_message.lower() or "masculino" in error_message.lower()


def test_can_invite_female_when_1_male_1_female(db, sample_turn, sample_user_female):
    """
    Test: Se puede invitar una femenina cuando hay 1 masculino (organizador) y 1 femenina
    """
    # Configurar turno como mixto
    sample_turn.is_mixed_match = "true"
    
    # Agregar una jugadora femenina
    sample_turn.player2_id = sample_user_female.id
    db.commit()
    db.refresh(sample_turn)
    
    # Intentar invitar otra femenina
    can_invite, error_message = can_invite_player_to_mixed_match(
        db, sample_turn, "Femenino"
    )
    
    assert can_invite == True


def test_cannot_accept_invitation_when_gender_quota_full(db, sample_turn, sample_user_male):
    """
    Test: No se puede aceptar invitación cuando el cupo del género está completo
    """
    # Configurar turno como mixto
    sample_turn.is_mixed_match = "true"
    
    # Agregar 2 masculinos (organizador + 1 confirmado)
    sample_turn.player2_id = sample_user_male.id
    db.commit()
    db.refresh(sample_turn)
    
    # Intentar aceptar como masculino
    is_valid, error_message = validate_mixed_match_gender_balance(
        db, sample_turn, "Masculino", check_pending_invitations=True
    )
    
    assert is_valid == False
    assert "cupo" in error_message.lower() or "completo" in error_message.lower() or "2" in error_message
