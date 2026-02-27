"""
Configuración compartida para tests pytest
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db

# Importar todos los modelos para que SQLAlchemy pueda resolver las relaciones
# Esto es necesario para que las relaciones entre modelos funcionen correctamente
from app.models.user import User
from app.models.club import Club
from app.models.court import Court
from app.models.turn import Turn
from app.models.pregame_turn import PregameTurn, PregameTurnStatus
from app.models.invitation import Invitation
from app.models.booking import Booking
from app.models.match import Match
from app.models.fcm_token import FCMToken
from app.models.notification import Notification
from app.models.user_favorite_club import UserFavoriteClub


# Base de datos en memoria para tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    """Crear base de datos de test y limpiarla después"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def override_get_db(db):
    """Override de get_db para tests"""
    def _get_db():
        try:
            yield db
        finally:
            pass
    return _get_db


@pytest.fixture
def sample_user_male(db):
    """Usuario de prueba masculino"""
    user = User(
        id=1,
        name="Test",
        last_name="User",
        email="test@example.com",
        hashed_password="hashed",
        is_active=True,
        gender="Masculino",
        category="6ta"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def sample_user_female(db):
    """Usuario de prueba femenino"""
    user = User(
        id=2,
        name="Test",
        last_name="User Female",
        email="test_female@example.com",
        hashed_password="hashed",
        is_active=True,
        gender="Femenino",
        category="7ma"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def sample_turn(db, sample_user_male):
    """Turno de prueba"""
    from app.models.turn import Turn
    from app.models.court import Court
    from app.models.club import Club
    from datetime import datetime, time
    import json
    
    # Crear club y cancha necesarios
    club = Club(
        id=1, 
        name="Test Club", 
        address="Test Address",
        opening_time=time(8, 0),
        closing_time=time(22, 0)
    )
    db.add(club)
    db.flush()
    
    court = Court(id=1, club_id=1, name="Court 1")
    db.add(court)
    db.flush()
    
    # Crear turn template (Turn tiene estructura JSON)
    turn_data = {
        "turns": [
            {
                "start_time": "10:00",
                "end_time": "11:30",
                "price": 1000
            }
        ]
    }
    turn = Turn(
        id=1,
        club_id=1,
        turns_data=turn_data
    )
    db.add(turn)
    db.flush()
    
    pregame_turn = PregameTurn(
        id=1,
        turn_id=1,
        court_id=1,
        date=datetime.now(),
        start_time="10:00",
        end_time="11:30",
        price=1000,
        status=PregameTurnStatus.PENDING,
        player1_id=sample_user_male.id,
        is_mixed_match="false",
        category_restricted="false",
        category_restriction_type="NONE"
    )
    db.add(pregame_turn)
    db.commit()
    db.refresh(pregame_turn)
    return pregame_turn
