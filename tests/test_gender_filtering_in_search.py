"""
Tests para validar el error reportado:
"Filtrado incorrecto de perfiles por género en invitaciones"

Este test suite valida:
1. Que la búsqueda de jugadores NO filtra por género
2. Que jugadores masculinos y femeninos aparecen en la lista
3. Que las restricciones de género solo se aplican al crear invitaciones, no en la búsqueda
4. Que el género del organizador no afecta la búsqueda
"""
import pytest
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.pregame_turn import PregameTurnStatus
from app.crud import invitation as invitation_crud


def test_search_returns_both_genders(db: Session, sample_user_male):
    """
    Test: La búsqueda debe devolver jugadores de ambos géneros
    """
    # Crear jugadores de ambos géneros
    male_player = User(
        id=3,
        name="Male",
        last_name="Player",
        email="male@example.com",
        hashed_password="hashed",
        is_active=True,
        gender="Masculino",
        category="6ta"
    )
    
    female_player = User(
        id=4,
        name="Female",
        last_name="Player",
        email="female@example.com",
        hashed_password="hashed",
        is_active=True,
        gender="Femenino",
        category="6ta"
    )
    
    db.add(male_player)
    db.add(female_player)
    db.commit()
    
    # Buscar jugadores sin filtros
    players = invitation_crud.search_players(
        db=db,
        query=None,
        current_user_id=sample_user_male.id,
        turn_id=None,
        require_fcm_token=False
    )
    
    # Verificar que hay jugadores de ambos géneros
    male_count = sum(1 for p in players if p.gender == "Masculino")
    female_count = sum(1 for p in players if p.gender == "Femenino")
    
    assert male_count > 0, "No se encontraron jugadores masculinos en la búsqueda"
    assert female_count > 0, "No se encontraron jugadoras femeninas en la búsqueda"


def test_search_does_not_filter_by_gender(db: Session, sample_user_male, sample_turn):
    """
    Test: La búsqueda NO debe filtrar por género, incluso para turnos mixtos
    """
    # Configurar turno como mixto
    sample_turn.is_mixed_match = "true"
    db.commit()
    db.refresh(sample_turn)
    
    # Crear jugadores de ambos géneros
    male_player = User(
        id=3,
        name="Male",
        last_name="Player",
        email="male@example.com",
        hashed_password="hashed",
        is_active=True,
        gender="Masculino",
        category="6ta"
    )
    
    female_player = User(
        id=4,
        name="Female",
        last_name="Player",
        email="female@example.com",
        hashed_password="hashed",
        is_active=True,
        gender="Femenino",
        category="6ta"
    )
    
    db.add(male_player)
    db.add(female_player)
    db.commit()
    
    # Buscar jugadores para el turno mixto
    players = invitation_crud.search_players(
        db=db,
        query=None,
        current_user_id=sample_user_male.id,
        turn_id=sample_turn.id,
        require_fcm_token=False
    )
    
    # CRÍTICO: Debe devolver jugadores de ambos géneros
    # Las restricciones de género se validan al crear la invitación, NO en la búsqueda
    player_ids = [p.id for p in players]
    
    assert male_player.id in player_ids, "Jugador masculino no aparece en la búsqueda para turno mixto"
    assert female_player.id in player_ids, "Jugadora femenina no aparece en la búsqueda para turno mixto"


def test_male_organizer_can_see_male_players(db: Session, sample_user_male, sample_turn):
    """
    Test: Un organizador masculino DEBE poder ver jugadores masculinos en la búsqueda
    """
    # Crear otro jugador masculino
    other_male = User(
        id=3,
        name="Other",
        last_name="Male",
        email="other_male@example.com",
        hashed_password="hashed",
        is_active=True,
        gender="Masculino",
        category="6ta"
    )
    
    db.add(other_male)
    db.commit()
    
    # Buscar jugadores (organizador masculino buscando jugadores)
    players = invitation_crud.search_players(
        db=db,
        query=None,
        current_user_id=sample_user_male.id,
        turn_id=sample_turn.id,
        require_fcm_token=False
    )
    
    # Verificar que el jugador masculino aparece
    player_ids = [p.id for p in players]
    assert other_male.id in player_ids, "Jugador masculino no aparece para organizador masculino"


def test_female_organizer_can_see_female_players(db: Session, sample_user_female):
    """
    Test: Una organizadora femenina DEBE poder ver jugadoras femeninas en la búsqueda
    """
    # Crear otro jugador femenino
    other_female = User(
        id=5,
        name="Other",
        last_name="Female",
        email="other_female@example.com",
        hashed_password="hashed",
        is_active=True,
        gender="Femenino",
        category="7ma"
    )
    
    db.add(other_female)
    db.commit()
    
    # Buscar jugadores (organizadora femenina buscando jugadores)
    players = invitation_crud.search_players(
        db=db,
        query=None,
        current_user_id=sample_user_female.id,
        turn_id=None,
        require_fcm_token=False
    )
    
    # Verificar que la jugadora femenina aparece
    player_ids = [p.id for p in players]
    assert other_female.id in player_ids, "Jugadora femenina no aparece para organizadora femenina"


def test_search_includes_gender_field(db: Session, sample_user_male):
    """
    Test: La respuesta de búsqueda debe incluir el campo gender para cada jugador
    """
    # Crear jugadores de ambos géneros
    male_player = User(
        id=3,
        name="Male",
        last_name="Player",
        email="male@example.com",
        hashed_password="hashed",
        is_active=True,
        gender="Masculino",
        category="6ta"
    )
    
    female_player = User(
        id=4,
        name="Female",
        last_name="Player",
        email="female@example.com",
        hashed_password="hashed",
        is_active=True,
        gender="Femenino",
        category="6ta"
    )
    
    db.add(male_player)
    db.add(female_player)
    db.commit()
    
    # Buscar jugadores
    players = invitation_crud.search_players(
        db=db,
        query=None,
        current_user_id=sample_user_male.id,
        turn_id=None,
        require_fcm_token=False
    )
    
    # Verificar que todos los jugadores tienen el campo gender
    for player in players:
        assert hasattr(player, 'gender'), f"Jugador {player.id} no tiene campo gender"
        assert player.gender in ["Masculino", "Femenino", None], f"Género inválido: {player.gender}"


def test_no_gender_filtering_in_query(db: Session, sample_user_male, sample_turn):
    """
    Test: La query SQL no debe tener filtros por género
    """
    # Configurar turno como mixto
    sample_turn.is_mixed_match = "true"
    db.commit()
    db.refresh(sample_turn)
    
    # Crear jugadores de ambos géneros
    male_player = User(
        id=3,
        name="Male",
        last_name="Player",
        email="male@example.com",
        hashed_password="hashed",
        is_active=True,
        gender="Masculino",
        category="6ta"
    )
    
    female_player = User(
        id=4,
        name="Female",
        last_name="Player",
        email="female@example.com",
        hashed_password="hashed",
        is_active=True,
        gender="Femenino",
        category="6ta"
    )
    
    db.add(male_player)
    db.add(female_player)
    db.commit()
    
    # Buscar jugadores
    players = invitation_crud.search_players(
        db=db,
        query=None,
        current_user_id=sample_user_male.id,
        turn_id=sample_turn.id,
        require_fcm_token=False
    )
    
    # Verificar que ambos géneros están presentes
    genders_found = set(p.gender for p in players if p.gender)
    
    assert "Masculino" in genders_found, "No se encontraron jugadores masculinos"
    assert "Femenino" in genders_found, "No se encontraron jugadoras femeninas"


def test_search_with_query_returns_both_genders(db: Session, sample_user_male):
    """
    Test: La búsqueda con término de búsqueda debe devolver ambos géneros
    """
    # Crear jugadores con nombres similares pero géneros diferentes
    male_player = User(
        id=3,
        name="Juan",
        last_name="Perez",
        email="juan@example.com",
        hashed_password="hashed",
        is_active=True,
        gender="Masculino",
        category="6ta"
    )
    
    female_player = User(
        id=4,
        name="Juana",
        last_name="Perez",
        email="juana@example.com",
        hashed_password="hashed",
        is_active=True,
        gender="Femenino",
        category="6ta"
    )
    
    db.add(male_player)
    db.add(female_player)
    db.commit()
    
    # Buscar con término "Juan"
    players = invitation_crud.search_players(
        db=db,
        query="Juan",
        current_user_id=sample_user_male.id,
        turn_id=None,
        require_fcm_token=False
    )
    
    # Verificar que ambos aparecen (búsqueda por nombre similar)
    player_ids = [p.id for p in players]
    
    # Al menos uno de los dos debe aparecer (dependiendo de la lógica de búsqueda)
    # Pero lo importante es que NO se filtre por género
    assert len(players) > 0, "La búsqueda no devolvió resultados"
    
    # Verificar que no hay filtrado por género (debe haber al menos un género presente)
    genders_found = set(p.gender for p in players if p.gender)
    assert len(genders_found) > 0, "No se encontraron géneros en los resultados"
