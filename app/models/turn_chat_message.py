"""Mensajes del chat interno de un turno (pregame_turn). Solo visible cuando hay al menos 2 jugadores."""
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class TurnChatMessage(Base):
    __tablename__ = "turn_chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    pregame_turn_id = Column(Integer, ForeignKey("pregame_turns.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "pregame_turn_id": self.pregame_turn_id,
            "user_id": self.user_id,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
