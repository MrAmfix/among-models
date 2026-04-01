from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


FIXED_TOPICS = [
    "Логика",
    "Философия",
    "Странный запрос",
    "Официальный ответ",
    "Эмоциональный интеллект",
    "Объяснение простого",
    "Креатив",
]


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), unique=True, nullable=False)

    rounds = relationship("Round", back_populates="topic")

    def __repr__(self) -> str:
        return f"<Topic id={self.id} name={self.name}>"
