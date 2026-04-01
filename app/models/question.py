from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey("rounds.id"), nullable=False, unique=True)
    text = Column(Text, nullable=False)
    generated_by_model = Column(Integer, ForeignKey("model_catalog.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    round = relationship("Round", back_populates="question")
    answers = relationship("Answer", back_populates="question", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Question id={self.id} round_id={self.round_id}>"
