from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Boolean,
    Table,
    Enum,
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base
from app.models.court import MatchStatus

match_players = Table(
    "match_players",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("match_id", Integer, ForeignKey("matches.id"), primary_key=True),
    extend_existing=True,
)


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    court_id = Column(Integer, ForeignKey("courts.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(Enum(MatchStatus), default=MatchStatus.AVAILABLE)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    score = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    court = relationship("app.models.court.Court", back_populates="matches")
    creator = relationship(
        "app.models.user.User", foreign_keys=[creator_id], backref="created_matches"
    )
    players = relationship(
        "app.models.user.User", secondary=match_players, back_populates="matches"
    )
    bookings = relationship("app.models.booking.Booking", back_populates="match")
