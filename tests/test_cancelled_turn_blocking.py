"""
Tests para validar que los turnos cancelados están completamente bloqueados
"""
import pytest

from app.models.pregame_turn import PregameTurnStatus


def test_cancelled_turn_status_detection(db, sample_turn):
    """
    Test: Verificar que se detecta correctamente un turno cancelado
    """
    # Inicialmente no está cancelado
    assert sample_turn.status != PregameTurnStatus.CANCELLED
    
    # Marcar como cancelado
    sample_turn.status = PregameTurnStatus.CANCELLED
    sample_turn.cancellation_message = "Turno cancelado"
    db.commit()
    db.refresh(sample_turn)
    
    # Verificar estado
    assert sample_turn.status == PregameTurnStatus.CANCELLED
    assert sample_turn.cancellation_message is not None


def test_cannot_cancel_already_cancelled_turn_logic(db, sample_turn):
    """
    Test: Verificar la lógica que previene cancelar un turno ya cancelado
    """
    from app.utils.turn_cancellation import cancel_complete_turn
    
    # Marcar turno como cancelado
    sample_turn.status = PregameTurnStatus.CANCELLED
    db.commit()
    db.refresh(sample_turn)
    
    # Verificar que la función detecta que ya está cancelado
    # (esto debería lanzar ValueError antes de intentar cancelar)
    with pytest.raises(ValueError) as exc_info:
        cancel_complete_turn(
            db=db,
            turn_id=sample_turn.id,
            organizer_id=sample_turn.player1_id,
            cancellation_message="Intentando cancelar de nuevo"
        )
    
    assert "ya fue cancelado" in str(exc_info.value).lower()


def test_cancelled_turn_excluded_from_active_reservations_query(db, sample_turn):
    """
    Test: Verificar que la query de reservas activas excluye turnos cancelados
    """
    from app.models.pregame_turn import PregameTurn
    
    # Inicialmente el turno está PENDING, debe aparecer en la query
    query = db.query(PregameTurn).filter(
        (PregameTurn.player1_id == sample_turn.player1_id)
        | (PregameTurn.player2_id == sample_turn.player1_id)
        | (PregameTurn.player3_id == sample_turn.player1_id)
        | (PregameTurn.player4_id == sample_turn.player1_id)
    ).filter(
        PregameTurn.status.in_([PregameTurnStatus.PENDING, PregameTurnStatus.READY_TO_PLAY])
    )
    
    results = query.all()
    assert sample_turn.id in [r.id for r in results]
    
    # Marcar como cancelado
    sample_turn.status = PregameTurnStatus.CANCELLED
    db.commit()
    
    # La misma query ahora no debe incluir el turno cancelado
    results = query.all()
    assert sample_turn.id not in [r.id for r in results]
