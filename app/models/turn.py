from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class TurnStatus(enum.Enum):
    AVAILABLE = "AVAILABLE"
    BOOKED = "BOOKED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class Turn(Base):
    __tablename__ = "turns"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    club_id = Column(Integer, ForeignKey("clubs.id"), nullable=False)
    turns_data = Column(
        JSON, nullable=False
    )  # Almacena todos los turnos posibles del club
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    club = relationship("app.models.club.Club", back_populates="turns")
    bookings = relationship("app.models.booking.Booking", back_populates="turn")
