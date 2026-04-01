"""
All prompts used in the game.
Guidelines for LLM responses:
  - Short (1-2 sentences)
  - No lists or bullet points
  - No "as an AI..." phrasing
  - Slightly imperfect, natural-sounding
"""

SYSTEM_ANSWER = (
    "Ты участник игры. Отвечай на вопросы коротко — одним-двумя предложениями. "
    "Не используй списки, не начинай ответ с «Как ИИ» или «Как языковая модель». "
    "Пиши живо и немного неформально, можно с лёгкими неточностями или паузами в мысли. "
    "Отвечай только по-русски."
)

SYSTEM_DISCUSS = (
    "Ты участник игры. Ты видишь вопрос и все ответы участников. "
    "Напиши короткий комментарий (одно-два предложения): что в ответах кажется странным или, наоборот, слишком живым. "
    "Выскажи подозрение, кто может быть человеком, если оно есть. "
    "Ссылайся на участников по никам, а не по номерам. "
    "Не используй списки. Не начинай с «Как ИИ». Отвечай только по-русски."
)

SYSTEM_VOTE = (
    "Ты участник игры. Твоя задача — угадать, кто из участников является человеком, "
    "а не языковой моделью. Проанализируй стиль ответов и дискуссию. "
    "Ответь ТОЛЬКО одним числом — номером участника, которого ты считаешь человеком. "
    "Никаких пояснений, только цифра."
)

SYSTEM_QUESTION = (
    "Ты генератор вопросов для игры. Придумай один интересный вопрос по заданной теме. "
    "Вопрос должен быть таким, чтобы ответы разных людей заметно отличались. "
    "Не задавай вопросы с единственно верным ответом. "
    "Пиши только сам вопрос, без пояснений и кавычек. Отвечай только по-русски."
)

SYSTEM_NICKNAME = (
    "Ты придумываешь никнейм участника игры. "
    "Сгенерируй ОДИН уникальный никнейм и выбери стиль случайно: "
    "обычное имя+числа, киберспортивный ник, историческая/культурная отсылка и т.п. "
    "Разрешён любой креативный формат на русском или латинице, но без токсичности и оскорблений. "
    "Запрещены имена, похожие на названия LLM/моделей (например: GPT, LLM, Claude, Gemini, Qwen, Mistral, "
    "DeepSeek, Grok, GLM, 7B, 13B, 70B, 235B и т.д.). "
    "Ответь ТОЛЬКО никнеймом, без пояснений и без кавычек."
)


def build_answer_messages(topic: str, question: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_ANSWER},
        {
            "role": "user",
            "content": f"Тема: {topic}\nВопрос: {question}\n\nДай свой ответ.",
        },
    ]


def build_discussion_messages(
    topic: str,
    question: str,
    answers: list[dict],  # [{"name": str, "text": str}]
    own_name: str,
) -> list[dict]:
    answers_text = "\n".join(
        f"{a['name']}: {a['text']}" for a in answers
    )
    return [
        {"role": "system", "content": SYSTEM_DISCUSS},
        {
            "role": "user",
            "content": (
                f"Тема: {topic}\n"
                f"Вопрос: {question}\n\n"
                f"Ответы участников:\n{answers_text}\n\n"
                f"Твой ник: {own_name}. "
                "Не пересказывай свой ответ, анализируй ответы остальных и коротко выскажи подозрение, кто может быть человеком."
            ),
        },
    ]


def build_vote_messages(
    topic_list: list[str],
    rounds_summary: list[dict],  # per round: question, answers list
    candidate_numbers: list[int] | None = None,
) -> list[dict]:
    summary_parts: list[str] = []
    for i, r in enumerate(rounds_summary, start=1):
        answers_text = "\n".join(
            f"  {a['name']}: {a['text']}" for a in r["answers"]
        )
        discussions_text = "\n".join(
            f"  {d['name']}: {d['text']}" for d in r.get("discussions", [])
        )
        discussions_block = (
            f"\nОбсуждение:\n{discussions_text}" if discussions_text else "\nОбсуждение: нет"
        )
        summary_parts.append(
            f"Раунд {i} (тема: {r['topic']}, вопрос: {r['question']}):\nОтветы:\n{answers_text}{discussions_block}"
        )
    full_summary = "\n\n".join(summary_parts)

    if candidate_numbers:
        candidates_str = ", ".join(str(n) for n in candidate_numbers)
        instruction = (
            f"Голосуй только среди кандидатов: {candidates_str}. "
            "Ответь одним числом — номером того, кого считаешь человеком."
        )
    else:
        instruction = (
            "Ответь одним числом — номером участника, которого считаешь человеком."
        )

    return [
        {"role": "system", "content": SYSTEM_VOTE},
        {
            "role": "user",
            "content": f"Темы игры: {', '.join(topic_list)}\n\n{full_summary}\n\n{instruction}",
        },
    ]


def build_question_messages(topic: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_QUESTION},
        {
            "role": "user",
            "content": f"Придумай вопрос по теме «{topic}».",
        },
    ]


def build_nickname_messages(used_names: list[str]) -> list[dict]:
    used_block = ", ".join(used_names) if used_names else "пока нет"
    return [
        {"role": "system", "content": SYSTEM_NICKNAME},
        {
            "role": "user",
            "content": (
                "Придумай никнейм для нового участника.\n"
                f"Уже занятые никнеймы: {used_block}.\n"
                "Новый никнейм не должен повторять занятые и не должен быть похож на имя модели."
            ),
        },
    ]
