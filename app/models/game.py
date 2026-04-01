import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class GameStatus(str, enum.Enum):
    LOBBY = "lobby"
    PLAYING = "playing"
    VOTING = "voting"
    TIEBREAK = "tiebreak"
    FINISHED = "finished"


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(128), nullable=False)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(
        Enum(
            GameStatus,
            name="gamestatus",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=GameStatus.LOBBY,
    )
    current_round = Column(Integer, default=0)  # 0 = not started, 1-3 = round number
    human_player_id = Column(Integer, ForeignKey("game_players.id"), nullable=True)
    winner_player_id = Column(Integer, ForeignKey("game_players.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    creator = relationship("User", back_populates="games_created", foreign_keys=[creator_id])
    players = relationship(
        "GamePlayer",
        back_populates="game",
        foreign_keys="GamePlayer.game_id",
        cascade="all, delete-orphan",
    )
    rounds = relationship("Round", back_populates="game", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Game id={self.id} title={self.title} status={self.status}>"


class GamePlayer(Base):
    """Represents a participant in a game — either an LLM or the human."""

    __tablename__ = "game_players"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # set only for human
    player_type = Column(String(8), nullable=False)  # "human" | "llm"
    model_id = Column(Integer, ForeignKey("model_catalog.id"), nullable=True)  # set only for llm
    display_name = Column(String(64), nullable=False)  # e.g. "Участник 1"

    game = relationship("Game", back_populates="players", foreign_keys=[game_id])
    user = relationship("User", back_populates="game_participations")
    model = relationship("ModelCatalog")
    answers = relationship("Answer", back_populates="player", cascade="all, delete-orphan")
    discussions = relationship("Discussion", back_populates="player", cascade="all, delete-orphan")
    votes_cast = relationship(
        "Vote", back_populates="voter_player", foreign_keys="Vote.voter_player_id"
    )
    votes_received = relationship(
        "Vote", back_populates="target_player", foreign_keys="Vote.target_player_id"
    )

    def __repr__(self) -> str:
        return f"<GamePlayer id={self.id} type={self.player_type} name={self.display_name}>"
