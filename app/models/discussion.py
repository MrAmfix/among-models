from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Discussion(Base):
    __tablename__ = "discussions"

    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey("rounds.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("game_players.id"), nullable=False)
    text = Column(Text, nullable=False)
    message_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    round = relationship("Round", back_populates="discussions")
    player = relationship("GamePlayer", back_populates="discussions")

    def __repr__(self) -> str:
        return (
            f"<Discussion id={self.id} player_id={self.player_id} round_id={self.round_id}>"
        )
