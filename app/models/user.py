from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    login = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(16), nullable=False, default="user")  # "user" | "admin"
    allowed_games = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    games_created = relationship("Game", back_populates="creator", foreign_keys="Game.creator_id")
    game_participations = relationship("GamePlayer", back_populates="user")

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def __repr__(self) -> str:
        return f"<User id={self.id} login={self.login} role={self.role}>"
