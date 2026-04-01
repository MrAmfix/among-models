"""
Core game logic: creation, round management, answer collection,
discussion generation, voting, tiebreak resolution.
"""

import asyncio
import logging
import random
from collections import Counter
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.answer import Answer
from app.models.discussion import Discussion
from app.models.game import Game, GamePlayer, GameStatus
from app.models.model_catalog import ModelCatalog
from app.models.question import Question
from app.models.round import Round
from app.models.topic import Topic
from app.models.user import User
from app.models.vote import Vote
from app.services.openrouter import openrouter_client, OpenRouterError
from app.services.prompts import (
    build_answer_messages,
    build_discussion_messages,
    build_question_messages,
    build_vote_messages,
)

logger = logging.getLogger(__name__)

ROUNDS_PER_GAME = 3
TOPICS_COUNT = 3

_answer_generation_tasks: dict[int, asyncio.Task] = {}
_discussion_generation_tasks: dict[int, asyncio.Task] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_topics(db: Session, count: int = TOPICS_COUNT) -> list[Topic]:
    all_topics = db.query(Topic).all()
    if len(all_topics) < count:
        raise ValueError(f"Not enough topics in DB (need {count}, have {len(all_topics)})")
    return random.sample(all_topics, count)


NICKNAME_ADJECTIVES = [
    "Быстрый",
    "Тихий",
    "Лунный",
    "Хитрый",
    "Дерзкий",
    "Смелый",
    "Жгучий",
    "Северный",
    "Южный",
    "Стальной",
    "Огненный",
    "Ледяной",
    "Яркий",
    "Темный",
    "Дикий",
    "Резкий",
    "Мудрый",
    "Шальной",
    "Грозный",
    "Скрытный",
]

NICKNAME_NOUNS = [
    "Ворон",
    "Лис",
    "Тигр",
    "Сокол",
    "Ветер",
    "Шторм",
    "Феникс",
    "Медведь",
    "Ястреб",
    "Пилигрим",
    "Волк",
    "Ниндзя",
    "Капитан",
    "Странник",
    "Рыцарь",
    "Механик",
    "Кочевник",
    "Пират",
    "Гонщик",
    "Шифр",
]


def _pick_display_names(count: int) -> list[str]:
    all_names = [
        f"{adj} {noun}" for adj in NICKNAME_ADJECTIVES for noun in NICKNAME_NOUNS
    ]
    if count > len(all_names):
        raise ValueError("Недостаточно уникальных имён для числа участников")
    random.shuffle(all_names)
    return all_names[:count]


# ---------------------------------------------------------------------------
# Game creation
# ---------------------------------------------------------------------------

def create_game(
    db: Session,
    title: str,
    creator: User,
    model_ids: list[int],
) -> Game:
    """
    Create a new game with the given LLM models and the human creator as a player.
    Deducts allowed_games for non-admin users.
    """
    if not creator.is_admin:
        if creator.allowed_games <= 0:
            raise PermissionError("У вас нет доступных игр")
        creator.allowed_games -= 1

    game = Game(
        title=title,
        creator_id=creator.id,
        status=GameStatus.LOBBY,
        current_round=0,
    )
    db.add(game)
    db.flush()  # get game.id without committing

    models = db.query(ModelCatalog).filter(
        ModelCatalog.id.in_(model_ids), ModelCatalog.is_active == True
    ).all()
    if not models:
        raise ValueError("Не выбрана ни одна модель")

    total_players = len(models) + 1  # llms + human
    display_names = _pick_display_names(total_players)
    name_iter = iter(display_names)

    # Add human player
    human_player = GamePlayer(
        game_id=game.id,
        user_id=creator.id,
        player_type="human",
        display_name=next(name_iter),
    )
    db.add(human_player)

    # Add LLM players
    for model in models:
        llm_player = GamePlayer(
            game_id=game.id,
            player_type="llm",
            model_id=model.id,
            display_name=next(name_iter),
        )
        db.add(llm_player)

    db.flush()

    game.human_player_id = human_player.id
    db.commit()
    db.refresh(game)
    return game


# ---------------------------------------------------------------------------
# Starting a round
# ---------------------------------------------------------------------------

async def start_next_round(db: Session, game: Game) -> Round:
    """
    Advance the game to the next round:
    - Pick the next topic
    - Generate a question via LLM
    - Generate LLM answers
    Returns the new Round.
    """
    next_round_number = game.current_round + 1
    if next_round_number > ROUNDS_PER_GAME:
        raise ValueError("Все раунды уже сыграны")

    # Select topics for this game (consistent across rounds using already-created rounds)
    existing_rounds = db.query(Round).filter(Round.game_id == game.id).all()
    used_topic_ids = {r.topic_id for r in existing_rounds}

    if next_round_number == 1:
        # Pick 3 random topics for the whole game
        topics = _get_topics(db, ROUNDS_PER_GAME)
    else:
        # Reuse topics already assigned to this game but pick unused one
        all_game_topic_ids = [r.topic_id for r in existing_rounds]
        # We need to have pre-selected them — fallback: pick random unused
        all_topics = db.query(Topic).filter(Topic.id.notin_(used_topic_ids)).all()
        if not all_topics:
            raise ValueError("Нет доступных тем для нового раунда")
        topics = [random.choice(all_topics)]

    topic = topics[0] if next_round_number == 1 else topics[0]
    # For consistency: on round 1 store all 3, on round 2/3 reuse stored order
    if next_round_number == 1:
        # We'll assign topic[0] now; later rounds get topic[1] and topic[2]
        # Store selection in game metadata by creating placeholder rounds — instead,
        # we generate rounds on-the-fly keeping the topic list in DB order.
        # Simple approach: pick topic by offset from sorted list of all pre-selected.
        # We'll do a one-time selection and store in a GameTopicSelection (reuse rounds).
        topic = topics[0]
    else:
        # Round 2/3: find topics not yet used
        all_topics_unused = db.query(Topic).filter(
            Topic.id.notin_(used_topic_ids)
        ).all()
        if not all_topics_unused:
            raise ValueError("Темы закончились")
        topic = random.choice(all_topics_unused)

    # Generate question
    llm_players = [p for p in game.players if p.player_type == "llm"]
    question_model = random.choice(llm_players).model
    question_text = await _generate_question(topic.name, question_model.model_id)

    new_round = Round(
        game_id=game.id,
        topic_id=topic.id,
        round_number=next_round_number,
        status="answering",
    )
    db.add(new_round)
    db.flush()

    question = Question(
        round_id=new_round.id,
        text=question_text,
        generated_by_model=question_model.id,
    )
    db.add(question)
    db.flush()

    game.current_round = next_round_number
    game.status = GameStatus.PLAYING
    db.commit()
    db.refresh(new_round)
    return new_round


# ---------------------------------------------------------------------------
# Human submits their answer
# ---------------------------------------------------------------------------

def submit_human_answer(db: Session, game: Game, round_obj: Round, text: str) -> Answer:
    human_player = db.query(GamePlayer).filter(
        GamePlayer.id == game.human_player_id
    ).first()
    if human_player is None:
        raise ValueError("Человек-игрок не найден")

    existing = db.query(Answer).filter(
        Answer.round_id == round_obj.id,
        Answer.player_id == human_player.id,
    ).first()
    if existing:
        raise ValueError("Ответ уже отправлен")

    question = db.query(Question).filter(Question.round_id == round_obj.id).first()
    if question is None:
        raise ValueError("Вопрос не найден")

    answer = Answer(
        round_id=round_obj.id,
        question_id=question.id,
        player_id=human_player.id,
        text=text.strip(),
    )
    db.add(answer)

    db.flush()
    round_became_discussing = _try_advance_round_to_discussing(db, game, round_obj)
    db.commit()
    db.refresh(answer)
    if round_became_discussing:
        schedule_discussion_generation(game.id, round_obj.id)
    return answer


# ---------------------------------------------------------------------------
# Discussion generation
# ---------------------------------------------------------------------------

async def generate_discussion(db: Session, game: Game, round_obj: Round) -> list[Discussion]:
    """Generate discussion comments for all LLM players."""
    llm_players = [p for p in game.players if p.player_type == "llm"]
    question = db.query(Question).filter(Question.round_id == round_obj.id).first()
    answers = (
        db.query(Answer)
        .filter(Answer.round_id == round_obj.id)
        .order_by(Answer.display_order)
        .all()
    )

    topic_name = round_obj.topic.name
    answers_data = [
        {"name": a.player.display_name if a.player else f"Участник {a.display_order}", "text": a.text}
        for a in answers
    ]

    discussions: list[Discussion] = []
    for order, player in enumerate(llm_players):
        existing = db.query(Discussion).filter(
            Discussion.round_id == round_obj.id,
            Discussion.player_id == player.id,
        ).first()
        if existing:
            discussions.append(existing)
            continue

        messages = build_discussion_messages(
            topic=topic_name,
            question=question.text,
            answers=answers_data,
            own_name=player.display_name,
        )
        try:
            text = await openrouter_client.chat(
                model=player.model.model_id,
                messages=messages,
                max_tokens=200,
            )
        except OpenRouterError as exc:
            logger.error("Discussion generation failed for player %d: %s", player.id, exc)
            text = "Интересные ответы, есть над чем подумать."

        disc = Discussion(
            round_id=round_obj.id,
            player_id=player.id,
            text=text,
            message_order=order,
        )
        db.add(disc)
        discussions.append(disc)

    round_obj.status = "done"
    db.commit()
    return discussions


def _try_advance_round_to_discussing(db: Session, game: Game, round_obj: Round) -> bool:
    players_count = len(game.players)
    answers = db.query(Answer).filter(Answer.round_id == round_obj.id).all()
    if len(answers) < players_count:
        return False

    if any(a.display_order is None for a in answers):
        order = list(range(1, len(answers) + 1))
        random.shuffle(order)
        for ans, ord_val in zip(answers, order):
            ans.display_order = ord_val

    if round_obj.status == "answering":
        round_obj.status = "discussing"
        return True
    return False


def schedule_llm_answers_generation(game_id: int, round_id: int) -> None:
    task = _answer_generation_tasks.get(round_id)
    if task and not task.done():
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Called from sync/threaded context (e.g. sync route) without active loop.
        # In this case we skip scheduling here; async routes will schedule it safely.
        return
    _answer_generation_tasks[round_id] = loop.create_task(
        _run_llm_answers_generation(game_id, round_id)
    )


def schedule_discussion_generation(game_id: int, round_id: int) -> None:
    task = _discussion_generation_tasks.get(round_id)
    if task and not task.done():
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Called from sync/threaded context without active loop.
        return
    _discussion_generation_tasks[round_id] = loop.create_task(
        _run_discussion_generation(game_id, round_id)
    )


async def _run_llm_answers_generation(game_id: int, round_id: int) -> None:
    db = SessionLocal()
    try:
        game = db.query(Game).filter(Game.id == game_id).first()
        round_obj = db.query(Round).filter(Round.id == round_id).first()
        question = db.query(Question).filter(Question.round_id == round_id).first()
        if not game or not round_obj or not question:
            return

        llm_players = [p for p in game.players if p.player_type == "llm"]
        topic_name = round_obj.topic.name

        for player in llm_players:
            existing = db.query(Answer).filter(
                Answer.round_id == round_id,
                Answer.player_id == player.id,
            ).first()
            if existing:
                continue

            answer_text = await _generate_llm_answer(
                topic_name, question.text, player.model.model_id
            )
            answer = Answer(
                round_id=round_id,
                question_id=question.id,
                player_id=player.id,
                text=answer_text,
            )
            db.add(answer)
            round_became_discussing = _try_advance_round_to_discussing(db, game, round_obj)
            db.commit()
            if round_became_discussing:
                schedule_discussion_generation(game_id, round_id)
    except Exception:
        logger.exception("Background LLM answer generation failed for round %d", round_id)
    finally:
        db.close()


async def _run_discussion_generation(game_id: int, round_id: int) -> None:
    db = SessionLocal()
    try:
        game = db.query(Game).filter(Game.id == game_id).first()
        round_obj = db.query(Round).filter(Round.id == round_id).first()
        if not game or not round_obj:
            return
        if round_obj.status != "discussing":
            return
        await generate_discussion(db, game, round_obj)
    except Exception:
        logger.exception("Background discussion generation failed for round %d", round_id)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Human submits discussion comment
# ---------------------------------------------------------------------------

def submit_human_discussion(
    db: Session, game: Game, round_obj: Round, text: str
) -> Discussion:
    human_player = db.query(GamePlayer).filter(
        GamePlayer.id == game.human_player_id
    ).first()

    # Find the next message_order
    max_order = (
        db.query(Discussion)
        .filter(Discussion.round_id == round_obj.id)
        .count()
    )

    disc = Discussion(
        round_id=round_obj.id,
        player_id=human_player.id,
        text=text.strip(),
        message_order=max_order,
    )
    db.add(disc)
    db.commit()
    db.refresh(disc)
    return disc


# ---------------------------------------------------------------------------
# Voting
# ---------------------------------------------------------------------------

def _build_rounds_summary(db: Session, game: Game) -> tuple[list[str], list[dict]]:
    rounds = (
        db.query(Round)
        .filter(Round.game_id == game.id)
        .order_by(Round.round_number)
        .all()
    )
    topic_names = [r.topic.name for r in rounds]
    summary = []
    for r in rounds:
        q = db.query(Question).filter(Question.round_id == r.id).first()
        answers = (
            db.query(Answer)
            .filter(Answer.round_id == r.id)
            .order_by(Answer.display_order)
            .all()
        )
        discussions = (
            db.query(Discussion)
            .filter(Discussion.round_id == r.id)
            .order_by(Discussion.message_order)
            .all()
        )
        summary.append(
            {
                "topic": r.topic.name,
                "question": q.text if q else "",
                "answers": [
                    {
                        "name": a.player.display_name if a.player else f"Участник {a.display_order}",
                        "text": a.text,
                    }
                    for a in answers
                ],
                "discussions": [
                    {
                        "name": d.player.display_name if d.player else "Участник",
                        "text": d.text,
                    }
                    for d in discussions
                ],
            }
        )
    return topic_names, summary


async def generate_llm_votes(
    db: Session,
    game: Game,
    phase: str = "final",
    candidate_player_ids: list[int] | None = None,
) -> list[Vote]:
    """Generate votes for all LLM players."""
    llm_players = [p for p in game.players if p.player_type == "llm"]
    topic_names, rounds_summary = _build_rounds_summary(db, game)

    # Compute candidate display numbers if tiebreak
    all_answers_round1 = (
        db.query(Answer)
        .filter(Answer.round_id == db.query(Round.id).filter(
            Round.game_id == game.id, Round.round_number == 1
        ).scalar_subquery())
        .order_by(Answer.display_order)
        .all()
    )

    # Map player_id -> display_number (use round 1 display_order as stable reference)
    player_display: dict[int, int] = {}
    for a in all_answers_round1:
        player_display[a.player_id] = a.display_order

    candidate_numbers: list[int] | None = None
    if candidate_player_ids:
        candidate_numbers = [
            player_display.get(pid, 0) for pid in candidate_player_ids
        ]

    votes: list[Vote] = []
    for voter in llm_players:
        messages = build_vote_messages(
            topic_list=topic_names,
            rounds_summary=rounds_summary,
            candidate_numbers=candidate_numbers,
        )
        try:
            raw = await openrouter_client.chat(
                model=voter.model.model_id,
                messages=messages,
                max_tokens=10,
                temperature=0.3,
            )
            chosen_number = int("".join(filter(str.isdigit, raw.strip()[:5])))
        except (OpenRouterError, ValueError) as exc:
            logger.error("Vote generation failed for player %d: %s", voter.id, exc)
            # fallback: pick random candidate
            chosen_number = (
                random.choice(candidate_numbers) if candidate_numbers else 1
            )

        # Find target player by display number
        target = _find_player_by_display_number(
            db, game, player_display, chosen_number
        )
        if target is None or target.id == voter.id:
            # fallback to human
            target = db.query(GamePlayer).filter(
                GamePlayer.id == game.human_player_id
            ).first()

        vote = Vote(
            game_id=game.id,
            voter_player_id=voter.id,
            target_player_id=target.id,
            vote_phase=phase,
        )
        db.add(vote)
        votes.append(vote)

    db.commit()
    return votes


def _find_player_by_display_number(
    db: Session,
    game: Game,
    player_display: dict[int, int],
    number: int,
) -> GamePlayer | None:
    for pid, num in player_display.items():
        if num == number:
            return db.query(GamePlayer).filter(GamePlayer.id == pid).first()
    return None


def submit_human_vote(
    db: Session,
    game: Game,
    target_player_id: int,
    phase: str = "final",
) -> Vote:
    human_player = db.query(GamePlayer).filter(
        GamePlayer.id == game.human_player_id
    ).first()

    existing = db.query(Vote).filter(
        Vote.game_id == game.id,
        Vote.voter_player_id == human_player.id,
        Vote.vote_phase == phase,
    ).first()
    if existing:
        raise ValueError("Вы уже проголосовали")

    vote = Vote(
        game_id=game.id,
        voter_player_id=human_player.id,
        target_player_id=target_player_id,
        vote_phase=phase,
    )
    db.add(vote)
    db.commit()
    db.refresh(vote)
    return vote


# ---------------------------------------------------------------------------
# Resolving the vote
# ---------------------------------------------------------------------------

def resolve_voting(db: Session, game: Game, phase: str = "final") -> dict:
    """
    Count votes for the given phase.
    Returns {"winner": GamePlayer | None, "tiebreak_players": [GamePlayer], "counts": dict}
    """
    votes = db.query(Vote).filter(
        Vote.game_id == game.id,
        Vote.vote_phase == phase,
    ).all()

    counts: Counter = Counter(v.target_player_id for v in votes)
    if not counts:
        return {"winner": None, "tiebreak_players": [], "counts": {}}

    max_votes = max(counts.values())
    leaders = [pid for pid, cnt in counts.items() if cnt == max_votes]

    if len(leaders) == 1:
        winner = db.query(GamePlayer).filter(GamePlayer.id == leaders[0]).first()
        game.winner_player_id = winner.id
        game.status = GameStatus.FINISHED
        game.finished_at = datetime.utcnow()
        db.commit()
        return {"winner": winner, "tiebreak_players": [], "counts": dict(counts)}
    else:
        # Tiebreak
        tiebreak_players = [
            db.query(GamePlayer).filter(GamePlayer.id == pid).first()
            for pid in leaders
        ]
        game.status = GameStatus.TIEBREAK
        db.commit()
        return {"winner": None, "tiebreak_players": tiebreak_players, "counts": dict(counts)}


# ---------------------------------------------------------------------------
# Internal LLM calls
# ---------------------------------------------------------------------------

async def _generate_question(topic: str, model_id: str) -> str:
    messages = build_question_messages(topic)
    try:
        return await openrouter_client.chat(
            model=model_id, messages=messages, max_tokens=150, temperature=1.0
        )
    except OpenRouterError as exc:
        logger.error("Question generation failed: %s", exc)
        return f"Что для вас означает понятие «{topic}»?"


async def _generate_llm_answer(topic: str, question: str, model_id: str) -> str:
    messages = build_answer_messages(topic, question)
    try:
        return await openrouter_client.chat(
            model=model_id, messages=messages, max_tokens=200, temperature=0.95
        )
    except OpenRouterError as exc:
        logger.error("Answer generation failed for %s: %s", model_id, exc)
        return "Сложный вопрос, надо подумать."
