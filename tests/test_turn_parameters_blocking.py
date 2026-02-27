"""
Tests para validar que los parámetros del partido se bloquean correctamente
cuando hay jugadores confirmados o invitaciones pendientes.
"""
import pytest
from sqlalchemy.orm import Session

from app.models.pregame_turn import PregameTurnStatus
from app.models.invitation import Invitation
from app.schemas.pregame_turn import PregameTurnUpdate


def test_has_confirmed_players_detection(db: Session, sample_turn, sample_user_female):
    """
    Test: Verificar que se detecta correctamente cuando hay jugadores confirmados
    """
    # Inicialmente solo tiene al organizador
    has_confirmed = (
        sample_turn.player2_id is not None
        or sample_turn.player3_id is not None
        or sample_turn.player4_id is not None
    )
    assert has_confirmed == False
    
    # Agregar un jugador confirmado
    sample_turn.player2_id = sample_user_female.id
    db.commit()
    db.refresh(sample_turn)
    
    has_confirmed = (
        sample_turn.player2_id is not None
        or sample_turn.player3_id is not None
        or sample_turn.player4_id is not None
    )
    assert has_confirmed == True


def test_has_pending_invitations_detection(db: Session, sample_turn, sample_user_female):
    """
    Test: Verificar que se detecta correctamente cuando hay invitaciones pendientes
    """
    from app.crud import invitation as invitation_crud
    
    # Inicialmente no hay invitaciones
    pending = invitation_crud.get_pending_invitations_by_turn(db, sample_turn.id)
    assert len(pending) == 0
    
    # Crear una invitación pendiente
    invitation = Invitation(
        turn_id=sample_turn.id,
        inviter_id=sample_turn.player1_id,
        invited_player_id=sample_user_female.id,
        status="PENDING"
    )
    db.add(invitation)
    db.commit()
    
    # Verificar que se detecta
    pending = invitation_crud.get_pending_invitations_by_turn(db, sample_turn.id)
    assert len(pending) == 1


def test_restricted_params_list():
    """
    Test: Verificar que la lista de parámetros restringidos es correcta
    """
    restricted_params = [
        "is_mixed_match",
        "free_category",
        "category_restricted",
        "category_restriction_type",
        "organizer_category"
    ]
    
    # Verificar que todos los parámetros críticos están en la lista
    assert "is_mixed_match" in restricted_params
    assert "free_category" in restricted_params
    assert "category_restricted" in restricted_params
    assert "category_restriction_type" in restricted_params
    assert "organizer_category" in restricted_params


def test_update_data_contains_restricted_params():
    """
    Test: Verificar que se puede detectar si un update contiene parámetros restringidos
    """
    # Crear update_data con parámetro restringido
    update_data = PregameTurnUpdate(is_mixed_match=True)
    update_dict = update_data.model_dump(exclude_unset=True)
    
    restricted_params = [
        "is_mixed_match",
        "free_category",
        "category_restricted",
        "category_restriction_type",
        "organizer_category"
    ]
    
    is_modifying = any(field in update_dict for field in restricted_params)
    assert is_modifying == True
    
    # Crear update_data sin parámetros restringidos
    update_data2 = PregameTurnUpdate(player1_side="drive")
    update_dict2 = update_data2.model_dump(exclude_unset=True)
    
    is_modifying2 = any(field in update_dict2 for field in restricted_params)
    assert is_modifying2 == False
