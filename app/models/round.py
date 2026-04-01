from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class Round(Base):
    __tablename__ = "rounds"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    round_number = Column(Integer, nullable=False)  # 1, 2, 3
    status = Column(String(32), nullable=False, default="question")
    # statuses: question, answering, discussing, done
    created_at = Column(DateTime, default=datetime.utcnow)

    game = relationship("Game", back_populates="rounds")
    topic = relationship("Topic", back_populates="rounds")
    question = relationship("Question", back_populates="round", uselist=False)
    answers = relationship("Answer", back_populates="round", cascade="all, delete-orphan")
    discussions = relationship(
        "Discussion", back_populates="round", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Round id={self.id} game_id={self.game_id} number={self.round_number}>"
