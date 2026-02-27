from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    Table,
    Boolean,
    DateTime,
)
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
from app.models.match import match_players

# Association table for user ratings
user_ratings = Table(
    "user_ratings",
    Base.metadata,
    Column("rater_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("rated_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("rating", Float),
    Column("comment", String),
    extend_existing=True,
)


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    last_name = Column(String, index=True)  # Apellido
    email = Column(String, unique=True, index=True)
    phone = Column(String)
    hashed_password = Column(String)
    overall_rating = Column(Float, default=0.0)
    is_active = Column(Boolean, default=False)  # Cambiado a False por defecto
    is_admin = Column(Boolean, default=False)
    is_super_admin = Column(Boolean, default=False)
    # Campo de ejemplo para probar migraciones
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Club que administra (solo para admins)
    club_id = Column(Integer, ForeignKey("clubs.id"), nullable=True)

    # Campos adicionales para búsqueda de jugadores
    profile_image_url = Column(String, nullable=True)  # URL de imagen de perfil
    level = Column(
        String(20), default="BEGINNER"
    )  # BEGINNER, INTERMEDIATE, ADVANCED, EXPERT
    preferred_side = Column(String(10), default="DRIVE")  # DRIVE, REVES
    location = Column(String, nullable=True)  # Ubicación del jugador
    category = Column(
        String(10), nullable=True
    )  # Categoría de juego: 9na, 8va, 7ma, 6ta, 5ta, 4ta, 3ra, 2da, 1ra

    # Nuevos campos para registro en dos pasos
    gender = Column(String(20), nullable=True)  # 'Masculino', 'Femenino', 'Otro'
    height = Column(Integer, nullable=True)  # en cm
    dominant_hand = Column(String(20), nullable=True)  # 'Izquierda', 'Derecha'
    preferred_court_type = Column(
        String(20), nullable=True
    )  # 'Cerrada', 'Abierta', 'Ambas'
    city = Column(String(100), nullable=True)
    province = Column(String(100), nullable=True)

    # Estados del usuario
    is_profile_complete = Column(Boolean, default=False)
    must_change_password = Column(Boolean, default=False)  # Para forzar cambio de contraseña en primer login

    # Verificación por email
    verification_code = Column(String(5), nullable=True)
    temp_token = Column(String(255), nullable=True)

    # Relationships
    matches = relationship("Match", secondary=match_players, back_populates="players")
    bookings = relationship(
        "Booking",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    # Relación con el club que administra
    club = relationship("Club", back_populates="admin")
    # Relación con tokens FCM
    fcm_tokens = relationship("FCMToken", back_populates="user")
    # Relación con clubs favoritos
    favorite_clubs = relationship("UserFavoriteClub", back_populates="user")
    # Relación con notificaciones
    notifications = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
    )
