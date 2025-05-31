from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class BookingStatus(enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    turn_id = Column(Integer, ForeignKey("turns.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    court_id = Column(Integer, ForeignKey("courts.id"))
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=True)
    status = Column(Enum(BookingStatus), default=BookingStatus.PENDING)
    payment_status = Column(String, default="pending")  # pending, paid, refunded
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    turn = relationship("app.models.turn.Turn", back_populates="bookings")
    user = relationship("app.models.user.User", back_populates="bookings")
    court = relationship("app.models.court.Court", back_populates="bookings")
    match = relationship("app.models.match.Match", back_populates="bookings")
