from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Enum,
    Boolean,
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum
from datetime import datetime


class CourtType(enum.Enum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"


class CourtSurface(enum.Enum):
    ARTIFICIAL_GRASS = "artificial_grass"
    CEMENT = "cement"
    CARPET = "carpet"


class MatchStatus(enum.Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class Court(Base):
    __tablename__ = "courts"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    club_id = Column(Integer, ForeignKey("clubs.id"), nullable=False)
    surface_type = Column(String)  # e.g., clay, grass, hard
    is_indoor = Column(Boolean, default=False)
    has_lighting = Column(Boolean, default=False)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    club = relationship("app.models.club.Club", back_populates="courts")
    matches = relationship("app.models.match.Match", back_populates="court")
    bookings = relationship("app.models.booking.Booking", back_populates="court")
