import logging
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.answer import Answer
from app.models.discussion import Discussion
from app.models.game import Game, GamePlayer, GameStatus
from app.models.model_catalog import ModelCatalog
from app.models.question import Question
from app.models.round import Round
from app.models.vote import Vote
from app.routes.deps import get_current_user
from app.services import game_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/game")
templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_game_or_404(db: Session, game_id: int) -> Game:
    game = db.query(Game).filter(Game.id == game_id).first()
    if game is None:
        raise HTTPException(status_code=404, detail="Игра не найдена")
    return game


def _require_creator(game: Game, user_id: int):
    if game.creator_id != user_id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")


def _get_current_round(db: Session, game: Game) -> Round | None:
    if game.current_round == 0:
        return None
    return (
        db.query(Round)
        .filter(Round.game_id == game.id, Round.round_number == game.current_round)
        .first()
    )


# ---------------------------------------------------------------------------
# Create game
# ---------------------------------------------------------------------------

@router.get("/create", response_class=HTMLResponse)
def create_game_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not user.is_admin and user.allowed_games <= 0:
        return RedirectResponse("/dashboard?error=no_games", status_code=302)

    models = db.query(ModelCatalog).filter(ModelCatalog.is_active == True).all()
    return templates.TemplateResponse(
        "game/create.html",
        {"request": request, "user": user, "models": models, "error": None},
    )


@router.post("/create", response_class=HTMLResponse)
async def create_game_submit(
    request: Request,
    title: str = Form(...),
    model_ids: list[int] = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)

    models = db.query(ModelCatalog).filter(ModelCatalog.is_active == True).all()
    error = None

    if not title.strip():
        error = "Введите название игры"
    elif len(model_ids) < 1:
        error = "Выберите хотя бы одну модель"
    elif len(model_ids) > 5:
        error = "Выберите не более 5 моделей"

    if error:
        return templates.TemplateResponse(
            "game/create.html",
            {"request": request, "user": user, "models": models, "error": error},
        )

    try:
        game = game_service.create_game(
            db=db, title=title.strip(), creator=user, model_ids=model_ids
        )
    except PermissionError as exc:
        return templates.TemplateResponse(
            "game/create.html",
            {"request": request, "user": user, "models": models, "error": str(exc)},
        )

    return RedirectResponse(f"/game/{game.id}", status_code=302)


# ---------------------------------------------------------------------------
# Game lobby / overview
# ---------------------------------------------------------------------------

@router.get("/{game_id}", response_class=HTMLResponse)
def game_overview(request: Request, game_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)

    game = _get_game_or_404(db, game_id)
    _require_creator(game, user.id)

    current_round = _get_current_round(db, game)
    return templates.TemplateResponse(
        "game/overview.html",
        {
            "request": request,
            "user": user,
            "game": game,
            "current_round": current_round,
            "GameStatus": GameStatus,
        },
    )


# ---------------------------------------------------------------------------
# Start next round
# ---------------------------------------------------------------------------

@router.post("/{game_id}/start-round", response_class=HTMLResponse)
async def start_round(request: Request, game_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)

    game = _get_game_or_404(db, game_id)
    _require_creator(game, user.id)

    if game.status == GameStatus.FINISHED:
        return RedirectResponse(f"/game/{game_id}/results", status_code=302)

    try:
        new_round = await game_service.start_next_round(db, game)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    game_service.schedule_llm_answers_generation(game.id, new_round.id)
    return RedirectResponse(f"/game/{game_id}/round/{new_round.round_number}", status_code=302)


# ---------------------------------------------------------------------------
# Round page
# ---------------------------------------------------------------------------

@router.get("/{game_id}/round/{round_number}", response_class=HTMLResponse)
def round_page(
    request: Request, game_id: int, round_number: int, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)

    game = _get_game_or_404(db, game_id)
    _require_creator(game, user.id)

    round_obj = (
        db.query(Round)
        .filter(Round.game_id == game_id, Round.round_number == round_number)
        .first()
    )
    if round_obj is None:
        raise HTTPException(status_code=404, detail="Раунд не найден")

    question = db.query(Question).filter(Question.round_id == round_obj.id).first()
    human_player = db.query(GamePlayer).filter(
        GamePlayer.id == game.human_player_id
    ).first()

    human_answer = db.query(Answer).filter(
        Answer.round_id == round_obj.id,
        Answer.player_id == human_player.id,
    ).first() if human_player else None

    answers = (
        db.query(Answer)
        .filter(Answer.round_id == round_obj.id)
        .order_by(Answer.display_order)
        .all()
    )
    answers_map = {a.player_id: a for a in answers}
    players = db.query(GamePlayer).filter(GamePlayer.game_id == game_id).all()
    waiting_for_player_ids = [
        p.id for p in players if p.id not in answers_map
    ]
    waiting_for_models = [p for p in players if p.player_type == "llm" and p.id in waiting_for_player_ids]

    if round_obj.status == "answering":
        game_service.schedule_llm_answers_generation(game.id, round_obj.id)
    if round_obj.status == "discussing":
        game_service.schedule_discussion_generation(game.id, round_obj.id)

    discussions = (
        db.query(Discussion)
        .filter(Discussion.round_id == round_obj.id)
        .order_by(Discussion.message_order)
        .all()
    )

    human_discussion = db.query(Discussion).filter(
        Discussion.round_id == round_obj.id,
        Discussion.player_id == human_player.id,
    ).first() if human_player else None

    return templates.TemplateResponse(
        "game/round.html",
        {
            "request": request,
            "user": user,
            "game": game,
            "round": round_obj,
            "question": question,
            "answers": answers,
            "answers_map": answers_map,
            "players": players,
            "waiting_for_models": waiting_for_models,
            "discussions": discussions,
            "human_answer": human_answer,
            "human_discussion": human_discussion,
            "human_player": human_player,
            "total_rounds": game_service.ROUNDS_PER_GAME,
        },
    )


# ---------------------------------------------------------------------------
# Submit human answer
# ---------------------------------------------------------------------------

@router.post("/{game_id}/round/{round_number}/answer")
async def submit_answer(
    request: Request,
    game_id: int,
    round_number: int,
    answer_text: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)

    game = _get_game_or_404(db, game_id)
    _require_creator(game, user.id)

    round_obj = (
        db.query(Round)
        .filter(Round.game_id == game_id, Round.round_number == round_number)
        .first()
    )
    if round_obj is None:
        raise HTTPException(status_code=404, detail="Раунд не найден")

    if not answer_text.strip():
        raise HTTPException(status_code=400, detail="Ответ не может быть пустым")

    try:
        game_service.submit_human_answer(db, game, round_obj, answer_text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return RedirectResponse(
        f"/game/{game_id}/round/{round_number}", status_code=302
    )


# ---------------------------------------------------------------------------
# Submit human discussion comment
# ---------------------------------------------------------------------------

@router.post("/{game_id}/round/{round_number}/discuss")
async def submit_discussion(
    request: Request,
    game_id: int,
    round_number: int,
    discussion_text: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)

    game = _get_game_or_404(db, game_id)
    _require_creator(game, user.id)

    round_obj = (
        db.query(Round)
        .filter(Round.game_id == game_id, Round.round_number == round_number)
        .first()
    )
    if round_obj is None:
        raise HTTPException(status_code=404, detail="Раунд не найден")

    if not discussion_text.strip():
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")

    game_service.submit_human_discussion(db, game, round_obj, discussion_text)
    return RedirectResponse(
        f"/game/{game_id}/round/{round_number}", status_code=302
    )


# ---------------------------------------------------------------------------
# Voting page
# ---------------------------------------------------------------------------

@router.get("/{game_id}/vote", response_class=HTMLResponse)
async def vote_page(request: Request, game_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)

    game = _get_game_or_404(db, game_id)
    _require_creator(game, user.id)

    if game.status not in (GameStatus.PLAYING, GameStatus.VOTING):
        return RedirectResponse(f"/game/{game_id}", status_code=302)

    # Trigger LLM votes if not yet done
    existing_llm_votes = db.query(Vote).filter(
        Vote.game_id == game_id,
        Vote.vote_phase == "final",
    ).count()
    if existing_llm_votes == 0:
        game.status = GameStatus.VOTING
        db.commit()
        await game_service.generate_llm_votes(db, game, phase="final")

    human_player = db.query(GamePlayer).filter(
        GamePlayer.id == game.human_player_id
    ).first()
    human_voted = db.query(Vote).filter(
        Vote.game_id == game_id,
        Vote.voter_player_id == human_player.id,
        Vote.vote_phase == "final",
    ).first() if human_player else None

    players = db.query(GamePlayer).filter(GamePlayer.game_id == game_id).all()

    # Build vote counts for display (only after human votes)
    vote_counts: dict[int, int] = {}
    if human_voted:
        from collections import Counter
        all_votes = db.query(Vote).filter(
            Vote.game_id == game_id, Vote.vote_phase == "final"
        ).all()
        vote_counts = dict(Counter(v.target_player_id for v in all_votes))

    return templates.TemplateResponse(
        "game/vote.html",
        {
            "request": request,
            "user": user,
            "game": game,
            "players": players,
            "human_voted": human_voted,
            "vote_counts": vote_counts,
            "phase": "final",
        },
    )


@router.post("/{game_id}/vote")
async def submit_vote(
    request: Request,
    game_id: int,
    target_player_id: int = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)

    game = _get_game_or_404(db, game_id)
    _require_creator(game, user.id)

    try:
        game_service.submit_human_vote(db, game, target_player_id, phase="final")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Resolve
    result = game_service.resolve_voting(db, game, phase="final")
    if result["winner"]:
        return RedirectResponse(f"/game/{game_id}/results", status_code=302)
    else:
        return RedirectResponse(f"/game/{game_id}/tiebreak", status_code=302)


# ---------------------------------------------------------------------------
# Tiebreak
# ---------------------------------------------------------------------------

@router.get("/{game_id}/tiebreak", response_class=HTMLResponse)
async def tiebreak_page(request: Request, game_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)

    game = _get_game_or_404(db, game_id)
    _require_creator(game, user.id)

    if game.status != GameStatus.TIEBREAK:
        return RedirectResponse(f"/game/{game_id}", status_code=302)

    # Find tiebreak candidates (leaders from final vote)
    from collections import Counter
    final_votes = db.query(Vote).filter(
        Vote.game_id == game_id, Vote.vote_phase == "final"
    ).all()
    counts = Counter(v.target_player_id for v in final_votes)
    max_v = max(counts.values())
    leader_ids = [pid for pid, cnt in counts.items() if cnt == max_v]
    tiebreak_players = db.query(GamePlayer).filter(
        GamePlayer.id.in_(leader_ids)
    ).all()

    # Generate LLM tiebreak votes if not done
    existing_tb = db.query(Vote).filter(
        Vote.game_id == game_id, Vote.vote_phase == "tiebreak"
    ).count()
    if existing_tb == 0:
        await game_service.generate_llm_votes(
            db, game, phase="tiebreak", candidate_player_ids=leader_ids
        )

    human_player = db.query(GamePlayer).filter(
        GamePlayer.id == game.human_player_id
    ).first()
    human_voted_tb = db.query(Vote).filter(
        Vote.game_id == game_id,
        Vote.voter_player_id == human_player.id,
        Vote.vote_phase == "tiebreak",
    ).first() if human_player else None

    return templates.TemplateResponse(
        "game/tiebreak.html",
        {
            "request": request,
            "user": user,
            "game": game,
            "tiebreak_players": tiebreak_players,
            "human_voted_tb": human_voted_tb,
            "phase": "tiebreak",
        },
    )


@router.post("/{game_id}/tiebreak")
async def submit_tiebreak_vote(
    request: Request,
    game_id: int,
    target_player_id: int = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)

    game = _get_game_or_404(db, game_id)
    _require_creator(game, user.id)

    try:
        game_service.submit_human_vote(db, game, target_player_id, phase="tiebreak")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    result = game_service.resolve_voting(db, game, phase="tiebreak")
    # Even if another tie — just pick first leader
    if not result["winner"] and result["tiebreak_players"]:
        winner = result["tiebreak_players"][0]
        from datetime import datetime
        game.winner_player_id = winner.id
        game.status = GameStatus.FINISHED
        game.finished_at = datetime.utcnow()
        db.commit()

    return RedirectResponse(f"/game/{game_id}/results", status_code=302)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@router.get("/{game_id}/results", response_class=HTMLResponse)
def results_page(request: Request, game_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)

    game = _get_game_or_404(db, game_id)
    _require_creator(game, user.id)

    winner = db.query(GamePlayer).filter(
        GamePlayer.id == game.winner_player_id
    ).first() if game.winner_player_id else None

    human_player = db.query(GamePlayer).filter(
        GamePlayer.id == game.human_player_id
    ).first()

    rounds = (
        db.query(Round).filter(Round.game_id == game_id).order_by(Round.round_number).all()
    )

    from collections import Counter
    all_votes = db.query(Vote).filter(Vote.game_id == game_id).all()
    vote_counts = dict(Counter(v.target_player_id for v in all_votes))

    players = db.query(GamePlayer).filter(GamePlayer.game_id == game_id).all()

    human_won = bool(winner and winner.id != game.human_player_id)

    return templates.TemplateResponse(
        "game/results.html",
        {
            "request": request,
            "user": user,
            "game": game,
            "winner": winner,
            "human_player": human_player,
            "human_won": human_won,
            "rounds": rounds,
            "vote_counts": vote_counts,
            "players": players,
        },
    )
