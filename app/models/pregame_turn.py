from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class PregameTurnStatus(enum.Enum):
    AVAILABLE = "AVAILABLE"  # Disponible para reservar
    PENDING = "PENDING"  # Algunos jugadores asignados
    READY_TO_PLAY = "READY_TO_PLAY"  # 4 jugadores asignados, listo para jugar
    CANCELLED = "CANCELLED"  # Cancelado por algún motivo
    COMPLETED = "COMPLETED"  # Convertido a partido


class PregameTurn(Base):
    __tablename__ = "pregame_turns"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    turn_id = Column(Integer, ForeignKey("turns.id"), nullable=False)
    court_id = Column(Integer, ForeignKey("courts.id"), nullable=False)
    date = Column(DateTime, nullable=False)  # Fecha del turno
    start_time = Column(String, nullable=False)  # Hora de inicio "HH:MM"
    end_time = Column(String, nullable=False)  # Hora de fin "HH:MM"
    price = Column(Integer, nullable=False)  # Precio en centavos
    status = Column(Enum(PregameTurnStatus), default=PregameTurnStatus.AVAILABLE)

    # Jugadores asignados (máximo 4)
    player1_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    player2_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    player3_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    player4_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    turn = relationship("app.models.turn.Turn")
    court = relationship("app.models.court.Court")

    # Relaciones con jugadores
    player1 = relationship("app.models.user.User", foreign_keys=[player1_id])
    player2 = relationship("app.models.user.User", foreign_keys=[player2_id])
    player3 = relationship("app.models.user.User", foreign_keys=[player3_id])
    player4 = relationship("app.models.user.User", foreign_keys=[player4_id])
