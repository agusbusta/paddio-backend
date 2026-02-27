from sqlalchemy import Column, Integer, String, DateTime, Time, Boolean
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime


class Club(Base):
    __tablename__ = "clubs"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Horarios del club
    opening_time = Column(Time, nullable=False)  # Hora de apertura
    closing_time = Column(Time, nullable=False)  # Hora de cierre
    turn_duration_minutes = Column(
        Integer, default=90
    )  # Duración de cada turno en minutos (1.5 horas)
    price_per_turn = Column(Integer, default=0)
    # Días de la semana que está abierto
    monday_open = Column(Boolean, default=True)
    tuesday_open = Column(Boolean, default=True)
    wednesday_open = Column(Boolean, default=True)
    thursday_open = Column(Boolean, default=True)
    friday_open = Column(Boolean, default=True)
    saturday_open = Column(Boolean, default=True)
    sunday_open = Column(Boolean, default=True)

    # Relationships
    courts = relationship("Court", back_populates="club", cascade="all, delete-orphan")
    # Relación con el admin que administra este club
    admin = relationship("User", back_populates="club")
    # Relación con los turnos del club
    turns = relationship("Turn", back_populates="club", cascade="all, delete-orphan")
    # Relación con usuarios que tienen este club como favorito
    favorited_by_users = relationship("UserFavoriteClub", back_populates="club")
