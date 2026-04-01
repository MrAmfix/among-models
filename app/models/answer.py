from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import relationship

from app.db.base import Base


class Answer(Base):
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey("rounds.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("game_players.id"), nullable=False)
    text = Column(Text, nullable=False)
    display_order = Column(Integer, nullable=True)  # shuffled order shown to voters
    created_at = Column(DateTime, default=datetime.utcnow)

    round = relationship("Round", back_populates="answers")
    question = relationship("Question", back_populates="answers")
    player = relationship("GamePlayer", back_populates="answers")

    def __repr__(self) -> str:
        return f"<Answer id={self.id} player_id={self.player_id} round_id={self.round_id}>"
