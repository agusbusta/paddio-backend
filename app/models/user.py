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
    email = Column(String, unique=True, index=True)
    phone = Column(String)
    hashed_password = Column(String)
    overall_rating = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    is_super_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    matches = relationship("Match", secondary=match_players, back_populates="players")
    bookings = relationship(
        "Booking",
        back_populates="user",
        cascade="all, delete-orphan",
    )
