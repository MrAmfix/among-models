"""initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("login", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default="user"),
        sa.Column("allowed_games", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_login"), "users", ["login"], unique=True)

    # model_catalog
    op.create_table(
        "model_catalog",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("model_id", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_id"),
    )
    op.create_index(op.f("ix_model_catalog_id"), "model_catalog", ["id"], unique=False)

    # topics
    op.create_table(
        "topics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_topics_id"), "topics", ["id"], unique=False)

    # games
    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "lobby", "playing", "voting", "tiebreak", "finished", name="gamestatus"
            ),
            nullable=False,
        ),
        sa.Column("current_round", sa.Integer(), nullable=True),
        sa.Column("human_player_id", sa.Integer(), nullable=True),
        sa.Column("winner_player_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_games_id"), "games", ["id"], unique=False)

    # game_players
    op.create_table(
        "game_players",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("player_type", sa.String(length=8), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=True),
        sa.Column("display_name", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["model_id"], ["model_catalog.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_game_players_id"), "game_players", ["id"], unique=False)

    # add FK from games to game_players (human_player_id, winner_player_id)
    op.create_foreign_key(
        "fk_games_human_player_id",
        "games",
        "game_players",
        ["human_player_id"],
        ["id"],
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_games_winner_player_id",
        "games",
        "game_players",
        ["winner_player_id"],
        ["id"],
        use_alter=True,
    )

    # rounds
    op.create_table(
        "rounds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="question"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rounds_id"), "rounds", ["id"], unique=False)

    # questions
    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("round_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("generated_by_model", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["generated_by_model"], ["model_catalog.id"]),
        sa.ForeignKeyConstraint(["round_id"], ["rounds.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("round_id"),
    )
    op.create_index(op.f("ix_questions_id"), "questions", ["id"], unique=False)

    # answers
    op.create_table(
        "answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("round_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["player_id"], ["game_players.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.ForeignKeyConstraint(["round_id"], ["rounds.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_answers_id"), "answers", ["id"], unique=False)

    # discussions
    op.create_table(
        "discussions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("round_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("message_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["player_id"], ["game_players.id"]),
        sa.ForeignKeyConstraint(["round_id"], ["rounds.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_discussions_id"), "discussions", ["id"], unique=False)

    # votes
    op.create_table(
        "votes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("voter_player_id", sa.Integer(), nullable=False),
        sa.Column("target_player_id", sa.Integer(), nullable=False),
        sa.Column("vote_phase", sa.String(length=16), nullable=False, server_default="final"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["voter_player_id"], ["game_players.id"]),
        sa.ForeignKeyConstraint(["target_player_id"], ["game_players.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_votes_id"), "votes", ["id"], unique=False)

    # seed topics
    op.bulk_insert(
        sa.table(
            "topics",
            sa.column("name", sa.String),
        ),
        [
            {"name": "Логика"},
            {"name": "Философия"},
            {"name": "Странный запрос"},
            {"name": "Официальный ответ"},
            {"name": "Эмоциональный интеллект"},
            {"name": "Объяснение простого"},
            {"name": "Креатив"},
        ],
    )

    # seed model_catalog
    op.bulk_insert(
        sa.table(
            "model_catalog",
            sa.column("name", sa.String),
            sa.column("model_id", sa.String),
            sa.column("description", sa.Text),
            sa.column("is_active", sa.Boolean),
        ),
        [
            {
                "name": "GPT-4o Mini",
                "model_id": "openai/gpt-4o-mini",
                "description": "Быстрая и дешёвая модель от OpenAI",
                "is_active": True,
            },
            {
                "name": "Claude 3 Haiku",
                "model_id": "anthropic/claude-3-haiku",
                "description": "Быстрая модель от Anthropic",
                "is_active": True,
            },
            {
                "name": "Gemini Flash 1.5",
                "model_id": "google/gemini-flash-1.5",
                "description": "Быстрая модель от Google",
                "is_active": True,
            },
            {
                "name": "Mistral 7B",
                "model_id": "mistralai/mistral-7b-instruct",
                "description": "Открытая модель от Mistral AI",
                "is_active": True,
            },
            {
                "name": "Llama 3.1 8B",
                "model_id": "meta-llama/llama-3.1-8b-instruct",
                "description": "Открытая модель от Meta",
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("votes")
    op.drop_table("discussions")
    op.drop_table("answers")
    op.drop_table("questions")
    op.drop_table("rounds")
    op.drop_constraint("fk_games_winner_player_id", "games", type_="foreignkey")
    op.drop_constraint("fk_games_human_player_id", "games", type_="foreignkey")
    op.drop_table("game_players")
    op.drop_table("games")
    op.drop_table("topics")
    op.drop_table("model_catalog")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS gamestatus")
