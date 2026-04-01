from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class Vote(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    voter_player_id = Column(Integer, ForeignKey("game_players.id"), nullable=False)
    target_player_id = Column(Integer, ForeignKey("game_players.id"), nullable=False)
    vote_phase = Column(String(16), nullable=False, default="final")  # "final" | "tiebreak"
    created_at = Column(DateTime, default=datetime.utcnow)

    voter_player = relationship(
        "GamePlayer", back_populates="votes_cast", foreign_keys=[voter_player_id]
    )
    target_player = relationship(
        "GamePlayer", back_populates="votes_received", foreign_keys=[target_player_id]
    )

    def __repr__(self) -> str:
        return (
            f"<Vote id={self.id} voter={self.voter_player_id} "
            f"target={self.target_player_id} phase={self.vote_phase}>"
        )
