"""Estado de lectura del chat por usuario y turno (para indicador "mensaje nuevo")."""
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class TurnChatRead(Base):
    __tablename__ = "turn_chat_read"
    __table_args__ = (UniqueConstraint("user_id", "pregame_turn_id", name="uq_turn_chat_read_user_turn"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    pregame_turn_id = Column(Integer, ForeignKey("pregame_turns.id", ondelete="CASCADE"), nullable=False, index=True)
    last_read_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
