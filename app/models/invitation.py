from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class Invitation(Base):
    __tablename__ = "invitations"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    turn_id = Column(Integer, ForeignKey("pregame_turns.id"), nullable=False)
    inviter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    invited_player_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(
        String(20), default="PENDING"
    )  # PENDING, ACCEPTED, DECLINED, EXPIRED, CANCELLED
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    responded_at = Column(DateTime, nullable=True)
    # CRÍTICO: Marca si esta invitación viene de un jugador validado (invitado por el configurador)
    # Las invitaciones de jugadores validados se aceptan automáticamente
    is_validated_invitation = Column(Boolean, default=False, nullable=False)
    # CRÍTICO: Marca si es una solicitud externa (jugador que encontró el turno y quiere unirse)
    # Las solicitudes externas requieren aprobación del configurador
    is_external_request = Column(Boolean, default=False, nullable=False)

    # Relaciones
    turn = relationship(
        "app.models.pregame_turn.PregameTurn", back_populates="invitations"
    )
    inviter = relationship("app.models.user.User", foreign_keys=[inviter_id])
    invited_player = relationship(
        "app.models.user.User", foreign_keys=[invited_player_id]
    )
