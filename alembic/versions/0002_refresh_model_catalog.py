"""refresh model catalog

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-01 05:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_MODELS = [
    {
        "name": "GPT-4o Mini",
        "model_id": "openai/gpt-4o-mini",
        "description": "Быстрая и недорогая универсальная модель для генерации и классификации.",
        "is_active": True,
    },
    {
        "name": "Gemini 2.5 Flash Lite",
        "model_id": "google/gemini-2.5-flash-lite",
        "description": "Лёгкая версия Gemini 2.5 для быстрых ответов и коротких итераций.",
        "is_active": True,
    },
    {
        "name": "Claude 3 Haiku",
        "model_id": "anthropic/claude-3-haiku",
        "description": "Быстрая модель с ровным качеством текста и хорошей устойчивостью стиля.",
        "is_active": True,
    },
    {
        "name": "Deepseek V3.2",
        "model_id": "deepseek/deepseek-v3.2",
        "description": "Сильная универсальная модель для reasoning-задач и кода.",
        "is_active": True,
    },
    {
        "name": "Mistral-3.2 24B",
        "model_id": "mistralai/mistral-small-3.2-24b-instruct",
        "description": "Инструкционная модель среднего размера с быстрым откликом и стабильным качеством.",
        "is_active": True,
    },
    {
        "name": "Qwen3-235B-A22B",
        "model_id": "qwen/qwen3-235b-a22b-2507",
        "description": "Крупная модель Qwen для сложных ответов и многослойной аргументации.",
        "is_active": True,
    },
    {
        "name": "Qwen3.5 flash",
        "model_id": "qwen/qwen3.5-flash-02-23",
        "description": "Быстрый вариант Qwen для недорогих массовых запросов.",
        "is_active": True,
    },
    {
        "name": "Minimax M2.7",
        "model_id": "minimax/minimax-m2.7",
        "description": "Универсальная модель MiniMax для диалогов и творческих задач.",
        "is_active": True,
    },
    {
        "name": "GLM-4.7 flash",
        "model_id": "z-ai/glm-4.7-flash",
        "description": "Быстрая GLM-модель для кратких ответов и интерактивных сценариев.",
        "is_active": True,
    },
    {
        "name": "Grok-4.1 fast",
        "model_id": "x-ai/grok-4.1-fast",
        "description": "Скоростной Grok для диалогов с минимальной задержкой.",
        "is_active": True,
    },
    {
        "name": "Mimo V2 omni",
        "model_id": "xiaomi/mimo-v2-omni",
        "description": "Мультимодальная модель Xiaomi с фокусом на универсальные ответы.",
        "is_active": True,
    },
]


OLD_MODELS = [
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
]


def _deactivate_all_models() -> None:
    op.execute("UPDATE model_catalog SET is_active = false")


def _upsert_models(models: list[dict[str, object]]) -> None:
    stmt = sa.text(
        """
        INSERT INTO model_catalog (name, model_id, description, is_active)
        VALUES (:name, :model_id, :description, :is_active)
        ON CONFLICT (model_id)
        DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            is_active = EXCLUDED.is_active
        """
    )
    conn = op.get_bind()
    for model in models:
        conn.execute(stmt, model)


def upgrade() -> None:
    _deactivate_all_models()
    _upsert_models(NEW_MODELS)


def downgrade() -> None:
    _deactivate_all_models()
    _upsert_models(OLD_MODELS)
