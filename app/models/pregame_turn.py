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
    selected_court_id = Column(
        Integer, ForeignKey("courts.id"), nullable=True
    )  # Cancha seleccionada por el primer jugador
    date = Column(DateTime, nullable=False)  # Fecha del turno
    start_time = Column(String, nullable=False)  # Hora de inicio "HH:MM"
    end_time = Column(String, nullable=False)  # Hora de fin "HH:MM"
    price = Column(Integer, nullable=False)  # Precio en centavos
    status = Column(Enum(PregameTurnStatus), default=PregameTurnStatus.AVAILABLE)

    # Restricciones de categoría
    category_restricted = Column(
        String(5), nullable=False, default="false"
    )  # "true" o "false"
    category_restriction_type = Column(
        String(20), nullable=False, default="NONE"
    )  # "NONE", "SAME_CATEGORY", "NEARBY_CATEGORIES"
    organizer_category = Column(
        String(10), nullable=True
    )  # Categoría del organizador del turno

    # Campos para partidos mixtos
    is_mixed_match = Column(
        String(5), nullable=False, default="false"
    )  # "true" o "false" - Indica si es un partido mixto
    free_category = Column(
        String(10), nullable=True
    )  # Categoría libre de referencia para partidos mixtos

    # Jugadores asignados (máximo 4)
    player1_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    player2_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    player3_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    player4_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Posiciones de cada jugador en la cancha
    player1_side = Column(String(10), nullable=True)  # "reves" o "drive"
    player1_court_position = Column(
        String(15), nullable=True
    )  # "izquierda" o "derecha"
    player2_side = Column(String(10), nullable=True)
    player2_court_position = Column(String(15), nullable=True)
    player3_side = Column(String(10), nullable=True)
    player3_court_position = Column(String(15), nullable=True)
    player4_side = Column(String(10), nullable=True)
    player4_court_position = Column(String(15), nullable=True)

    # Mensaje de justificación cuando un jugador se retira
    cancellation_message = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Recordatorio push enviado cuando el turno quedó vacío (solo organizador) y pasaron X minutos
    incomplete_reminder_sent_at = Column(DateTime, nullable=True)

    # Si True, el organizador publicó el turno en el muro; solo esos turnos aparecen en GET /wall
    published_to_wall = Column(String(5), nullable=False, default="false")

    # Relationships
    turn = relationship("app.models.turn.Turn")
    court = relationship("app.models.court.Court", foreign_keys=[court_id])
    selected_court = relationship(
        "app.models.court.Court", foreign_keys=[selected_court_id]
    )

    # Relaciones con jugadores
    player1 = relationship("app.models.user.User", foreign_keys=[player1_id])
    player2 = relationship("app.models.user.User", foreign_keys=[player2_id])
    player3 = relationship("app.models.user.User", foreign_keys=[player3_id])
    player4 = relationship("app.models.user.User", foreign_keys=[player4_id])

    # Relación con invitaciones
    invitations = relationship("Invitation", back_populates="turn")
