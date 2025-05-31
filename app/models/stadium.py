from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class Stadium(Base):
    __tablename__ = "stadiums"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    club_id = Column(Integer, ForeignKey("clubs.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    club = relationship("Club", back_populates="stadiums")
    courts = relationship(
        "Court", back_populates="stadium", cascade="all, delete-orphan"
    )
