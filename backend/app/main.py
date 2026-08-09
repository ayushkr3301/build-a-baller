"""Build A Baller -- FastAPI backend.

The server is authoritative about every random event: the spin draws, the club
draft and the season. The client can't reroll a spin it doesn't like, because the
offered player is stored server-side until it is taken or skipped.
"""

from __future__ import annotations

import functools
import json
import os
import random
import re
import secrets
import time
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import career as career_mode
from . import daily as daily_mode
from . import db, game
from .data.attributes import ERAS, N_CRITERIA, N_SPINS, POSITIONS, TIERS, attr_keys
from .data.clubs import CLUBS, CLUB_BY_ID, DISPLAY_CLUB_BY_ID
from .data.world import NATIONS, NATION_BY_ID
from .models import CareerChoice, CreateRun, StartCareer, TakeAttribute, VetoClubs
from .sim import simulate_season

# Bumped when the deployment surface changes, so /api/health proves which
# build a server is actually running.
BUILD = "2026-08-09-diagnostic"

app = FastAPI(title="Build A Baller", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _player_dict(p: game.Player) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "club": p.club_name,
        "club_short": p.club_short,
        "club_id": p.club_id,
        "tier": p.tier,
        "tier_name": TIERS[p.tier]["name"],
        "overall": p.overall,
        "ratings": p.ratings,
    }


def _load(run_id: str):
    row = db.get_run(run_id)
    if row is None:
        raise HTTPException(404, "run not found")
    return row, json.loads(row["state"])


def _require_phase(state: dict, *phases: str) -> None:
    if state["phase"] not in phases:
        raise HTTPException(
            409, f"run is in phase {state['phase']!r}; expected one of {list(phases)}"
        )


def _spin_rng(state: dict) -> random.Random:
    return random.Random(f"{state['seed']}:spin:{state['spin_index']}")


def _board(state: dict) -> game.Board:
    board = game.Board(position=state["position"])
    board.slots = dict(state["board"])
    board.sources = dict(state["sources"])
    return board


def _public(row, state: dict) -> dict:
    board = _board(state)
    payload = {
        "id": row["id"],
        "player_name": state["player_name"],
        "position": state["position"],
        "position_name": POSITIONS[state["position"]]["name"],
        "era": state["era"],
        "era_name": ERAS[state["era"]]["name"],
        "phase": state["phase"],
        "spins_used": state["spin_index"],
        "spins_total": N_SPINS,
        "spins_left": N_SPINS - state["spin_index"],
        "criteria_total": N_CRITERIA,
        "slots_filled": board.filled,
        "board": state["board"],
        "sources": state["sources"],
        "current_offer": state.get("current_offer"),
        "history": state.get("history", []),
        "overall": board.overall,
        "projected_overall": game.projected_overall(board),
        "card": dict(zip(("card_key", "card_label"), game.card_grade(board.overall))),
        "vetoed": state.get("vetoed", []),
        "club_id": state.get("club_id"),
        "mode": state.get("mode", "season"),
        "daily_date": state.get("daily_date"),
        "draft_odds": None,
        "season": json.loads(row["season"]) if row["season"] else None,
        "career": _career_payload(state),
        "best_possible": _best_possible(state),
        "share": _share_payload(row, state),
    }
    if state["phase"] in ("built", "vetoed"):
        payload["draft_odds"] = [
            {
                "club_id": cid,
                "club": CLUB_BY_ID[cid].name,
                "short": CLUB_BY_ID[cid].short,
                "chance": round(p, 4),
            }
            for cid, p in game.draft_odds(
                board.overall, set(state.get("vetoed", [])), state["era"]
            )
        ]
    if state.get("club_id"):
        club = CLUB_BY_ID[state["club_id"]]
        payload["club"] = {
            "id": club.id,
            "name": club.name,
            "short": club.short,
            "primary": club.primary,
            "secondary": club.secondary,
        }
    return payload


def _best_possible(state: dict) -> dict | None:
    """The best card the players actually drawn could have produced.

    Only once the build is over -- shown mid-run it would just be a solver telling
    you what to click.
    """
    if state["phase"] == "building":
        return None
    players = game.players_by_ids(state["era"], state["position"], state.get("seen_ids", []))
    if not players:
        return None
    overall, picks = game.best_possible_board(state["position"], players)
    board = _board(state)
    return {
        "overall": overall,
        "regret": max(0, overall - board.overall),
        "picks": picks,
        "players_seen": len(players),
    }


def _share_payload(row, state: dict) -> dict | None:
    """Postable result for a finished daily: squares, not spoilers."""
    if state.get("mode") not in ("daily", "practice") or state["phase"] != "complete":
        return None
    day = state.get("daily_date")
    if not day:
        return None
    season = json.loads(row["season"]) if row["season"] else None
    best = _best_possible(state) or {"overall": 0, "picks": {}}
    grid = daily_mode.result_grid(state["position"], state["board"], best["picks"])
    board = _board(state)
    streak = 0
    if state.get("mode") == "daily" and row["player_token"]:
        streak = daily_mode.streak_from_dates(db.daily_history(row["player_token"]))
    return {
        "day": day,
        "day_number": daily_mode.day_number(day),
        "grid": grid,
        "practice": state.get("mode") == "practice",
        "text": daily_mode.share_text(
            day=day,
            position_name=POSITIONS[state["position"]]["name"],
            era_name=ERAS[state["era"]]["name"],
            overall=board.overall,
            grade=season["grade"] if season else "-",
            grid=grid,
            optimum=best["overall"],
            streak=streak,
        ),
    }


def _career_payload(state: dict) -> dict | None:
    data = state.get("career")
    if not data:
        return None
    return {
        "started": True,
        "age": data["age"],
        "year": data["year"],
        "overall": data["overall"],
        "potential": data["potential"],
        "position": data["position"],
        "club": CLUB_BY_ID[data["club_id"]].name if data["club_id"] in CLUB_BY_ID else data["club_id"],
        "club_id": data["club_id"],
        "nationality": NATION_BY_ID[data["nationality"]].name,
        "caps": data["caps"],
        "international_goals": data["international_goals"],
        "retired": data["retired"],
        "seasons": data["seasons"],
        "honours": data["honours"],
        "ballon_dor": data["ballon_dor"],
        "options": state.get("career_options", []),
        "summary": career_mode.career_summary(data) if data["retired"] else None,
    }


# --------------------------------------------------------------------------- #
# Metadata
# --------------------------------------------------------------------------- #


# A connection string can appear inside a driver's error text, so anything echoed
# back to a caller goes through this first.
_CREDENTIALS = re.compile(r"(?<=://)([^:/@\s]+):([^@\s]+)(?=@)")


def _redact(text: str) -> str:
    return _CREDENTIALS.sub(r"\1:***", text)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    """Report unhandled errors instead of a bare "Internal Server Error".

    Serverless tracebacks live only in dashboard logs, which deployment
    protection can put out of reach. The message is redacted before it leaves.
    """
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Unhandled server error",
            "path": request.url.path,
            "error_type": type(exc).__name__,
            "error": _redact(str(exc))[:600],
            "build": BUILD,
        },
    )


@app.get("/api/health/db")
def health_db() -> JSONResponse:
    """Prove the database round trip specifically, and describe it when it fails.

    /api/health answers "did the code load" and /api/meta needs a working query;
    this sits between them so a storage problem names itself.
    """
    url = db.postgres_url()
    parsed = urlsplit(url) if url else None
    described = (
        {
            "scheme": parsed.scheme,
            "host": parsed.hostname,
            "port": parsed.port,
            "database": parsed.path.lstrip("/"),
            "user": parsed.username,
            "has_password": bool(parsed.password),
            "query": parsed.query,
            "pooled_endpoint": "-pooler" in (parsed.hostname or ""),
        }
        if parsed
        else None
    )

    started = time.perf_counter()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except Exception as exc:  # noqa: BLE001 -- the point is to describe any failure
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "storage": "postgres" if db.IS_POSTGRES else "sqlite",
                "error_type": type(exc).__name__,
                "error": _redact(str(exc))[:600],
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
                "connection": described,
            },
        )
    return JSONResponse(
        content={
            "ok": True,
            "storage": "postgres" if db.IS_POSTGRES else "sqlite",
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "connection": described,
        }
    )


@app.exception_handler(404)
async def _not_found(request: Request, _exc) -> JSONResponse:
    """A 404 that says which path actually arrived.

    Platform routing can rewrite a request before the app sees it, and the default
    "Not Found" gives you no way to tell that from a genuinely missing route.
    """
    return JSONResponse(
        status_code=404,
        content={
            "detail": "Not Found",
            "received_path": request.url.path,
            "build": BUILD,
            "hint": (
                "If this is not the path you requested, the platform rewrote it "
                "before the application saw it."
            ),
        },
    )


@app.get("/api/health")
def health() -> dict:
    """Liveness that deliberately touches nothing.

    /api/meta reads the hall-of-fame counters, so a database problem and a broken
    deployment look identical there. This answers only "did the code load", which
    is what you want first when a serverless function is returning 500s.
    """
    return {
        "ok": True,
        "build": BUILD,
        "storage": "postgres" if db.IS_POSTGRES else "sqlite",
        "database_env_vars": sorted(
            k for k in os.environ if "POSTGRES" in k or "DATABASE" in k
        ),
        "criteria": N_CRITERIA,
        "spins": N_SPINS,
    }


@functools.lru_cache(maxsize=1)
def _static_meta() -> dict:
    """Everything in /api/meta that can never change while the process lives.

    Positions, clubs and the full roster map are derived from constants, so this
    ~20KB structure was being rebuilt and re-serialised on every request. Only the
    hall-of-fame counters are dynamic; they get merged in per call.
    """
    return {
        "positions": [
            {
                "key": key,
                **info,
                "attributes": game.attribute_meta(key),
            }
            for key, info in POSITIONS.items()
        ],
        "eras": [{"key": key, **info} for key, info in ERAS.items()],
        "clubs": [
            {
                "id": c.id,
                "name": c.name,
                "short": c.short,
                "primary": c.primary,
                "secondary": c.secondary,
                "prestige": c.prestige,
                "rank": round(game.club_rank(c), 1),
            }
            for c in sorted(CLUBS, key=lambda c: -game.club_rank(c))
        ],
        "tiers": [{"tier": t, **info} for t, info in TIERS.items()],
        "criteria": N_CRITERIA,
        "spins": N_SPINS,
        "pool_sizes": game.pool_sizes(),
        # Every club that can appear on a card, including historic ones that only
        # exist as a legend's badge (Blackburn, Bolton, Wimbledon...).
        "display_clubs": {
            cid: {
                "id": cid,
                "name": DISPLAY_CLUB_BY_ID[cid].name,
                "short": DISPLAY_CLUB_BY_ID[cid].short,
                "primary": DISPLAY_CLUB_BY_ID[cid].primary,
            }
            for cid in sorted(game.rostered_club_ids())
        },
        # era -> position -> club -> names, so the spin reel can show real players.
        "rosters": game.rosters(),
    }


@app.get("/api/meta")
def meta() -> dict:
    return {
        **_static_meta(),
        "stats": db.stats(),
        "nations": [{"id": n.id, "name": n.name, "strength": n.strength} for n in NATIONS],
    }


@app.get("/api/daily")
def daily(player_token: str | None = None) -> dict:
    """Today's challenge, whether this token has played it, and the board."""
    setup = daily_mode.config()
    attempt = db.daily_attempt(setup["date"], player_token) if player_token else None
    history = db.daily_history(player_token) if player_token else []
    return {
        **setup,
        "already_played": attempt is not None,
        "attempt": attempt,
        "day_number": daily_mode.day_number(setup["date"]),
        "streak": daily_mode.streak_from_dates(history),
        "days_played": len(history),
        "leaderboard": db.daily_leaderboard(setup["date"]),
    }


# --------------------------------------------------------------------------- #
# Run lifecycle
# --------------------------------------------------------------------------- #


@app.post("/api/runs")
def create_run(body: CreateRun) -> dict:
    run_id = secrets.token_urlsafe(9)

    position, era, seed = body.position, body.era, secrets.randbelow(2**31)
    daily_date = None
    if body.mode in ("daily", "practice"):
        # Practice replays a specific day's spins; the daily always means today.
        day = body.daily_date if body.mode == "practice" and body.daily_date else None
        try:
            setup = daily_mode.config(day)
        except ValueError:
            raise HTTPException(400, "daily_date must look like YYYY-MM-DD") from None
        # The whole point is that everyone faces identical spins, so the client
        # does not get to choose any of this.
        position, era, seed = setup["position"], setup["era"], setup["seed"]
        daily_date = setup["date"]
        if body.mode == "daily":
            if not body.player_token:
                raise HTTPException(400, "the daily challenge needs a player token")
            if db.daily_attempt(daily_date, body.player_token):
                raise HTTPException(409, "you have already played today's challenge")

    state = {
        "player_name": body.player_name,
        "position": position,
        "era": era,
        "mode": body.mode,
        "daily_date": daily_date,
        "seed": seed,
        "phase": "building",
        "spin_index": 0,
        "current_offer": None,
        # `position`, not `body.position`: a daily run overrides what was asked
        # for, and a board keyed to the wrong position desynchronises the whole run.
        "board": {k: None for k in attr_keys(position)},
        "sources": {},
        "seen_ids": [],
        "history": [],
        "vetoed": [],
        "club_id": None,
    }
    db.create_run(
        run_id, body.player_name, position, era, state,
        mode=body.mode, daily_date=daily_date, player_token=body.player_token,
    )
    row = db.get_run(run_id)
    return _public(row, state)


@app.get("/api/runs/{run_id}")
def read_run(run_id: str) -> dict:
    row, state = _load(run_id)
    return _public(row, state)


@app.post("/api/runs/{run_id}/spin")
def spin(run_id: str) -> dict:
    row, state = _load(run_id)
    _require_phase(state, "building")

    # An offer already on the table is not re-rollable.
    if state.get("current_offer") is None:
        if state["spin_index"] >= N_SPINS:
            raise HTTPException(409, "no spins left")
        player = game.draw_player(
            era=state["era"],
            position=state["position"],
            spin_index=state["spin_index"],
            rng=_spin_rng(state),
            exclude_ids=set(state["seen_ids"]),
        )
        state["current_offer"] = _player_dict(player)
        state["seen_ids"].append(player.id)
        db.save_state(run_id, state)
        row = db.get_run(run_id)
    return _public(row, state)


@app.post("/api/runs/{run_id}/take")
def take(run_id: str, body: TakeAttribute) -> dict:
    row, state = _load(run_id)
    _require_phase(state, "building")
    offer = state.get("current_offer")
    if offer is None:
        raise HTTPException(409, "spin first")

    board = _board(state)
    try:
        value = offer["ratings"][body.attribute]
    except KeyError:
        raise HTTPException(400, f"{body.attribute!r} is not an attribute of this player") from None
    if body.attribute not in board.slots:
        raise HTTPException(400, f"{body.attribute!r} is not a criterion for {state['position']}")
    if board.slots[body.attribute] is not None:
        raise HTTPException(409, "that slot is already locked -- no overwrites")

    board.slots[body.attribute] = value
    board.sources[body.attribute] = offer["name"]
    state["board"] = board.slots
    state["sources"] = board.sources
    state["history"].append(
        {
            "spin": state["spin_index"] + 1,
            "player": offer["name"],
            "tier": offer["tier"],
            "action": "take",
            "attribute": body.attribute,
            "value": value,
        }
    )
    state["spin_index"] += 1
    state["current_offer"] = None
    _advance(state, board)

    db.save_state(run_id, state, overall=board.overall if board.complete else None)
    return _public(db.get_run(run_id), state)


@app.post("/api/runs/{run_id}/skip")
def skip(run_id: str) -> dict:
    row, state = _load(run_id)
    _require_phase(state, "building")
    offer = state.get("current_offer")
    if offer is None:
        raise HTTPException(409, "spin first")

    state["history"].append(
        {
            "spin": state["spin_index"] + 1,
            "player": offer["name"],
            "tier": offer["tier"],
            "action": "skip",
            "attribute": None,
            "value": None,
        }
    )
    state["spin_index"] += 1
    state["current_offer"] = None
    board = _board(state)
    _advance(state, board)

    db.save_state(run_id, state, overall=board.overall if board.complete else None)
    return _public(db.get_run(run_id), state)


def _advance(state: dict, board: game.Board) -> None:
    """Move out of the build phase once the board is full or the spins run out."""
    if board.complete or state["spin_index"] >= N_SPINS:
        state["phase"] = "built"


@app.post("/api/runs/{run_id}/veto")
def veto(run_id: str, body: VetoClubs) -> dict:
    row, state = _load(run_id)
    _require_phase(state, "built")

    ids = list(dict.fromkeys(body.club_ids))
    if len(ids) != 3:
        raise HTTPException(400, "pick exactly three clubs to veto")
    unknown = [c for c in ids if c not in CLUB_BY_ID]
    if unknown:
        raise HTTPException(400, f"unknown club id(s): {unknown}")

    state["vetoed"] = ids
    state["phase"] = "vetoed"
    db.save_state(run_id, state)
    return _public(db.get_run(run_id), state)


@app.post("/api/runs/{run_id}/draft")
def draft(run_id: str) -> dict:
    row, state = _load(run_id)
    _require_phase(state, "vetoed")

    board = _board(state)
    rng = random.Random(f"{state['seed']}:draft")
    club_id = game.draft_club(board.overall, rng, set(state["vetoed"]), state["era"])
    state["club_id"] = club_id
    state["phase"] = "drafted"
    db.save_state(run_id, state, overall=board.overall, club_id=club_id)
    return _public(db.get_run(run_id), state)


@app.post("/api/runs/{run_id}/simulate")
def simulate(run_id: str) -> dict:
    row, state = _load(run_id)
    _require_phase(state, "drafted")

    board = _board(state)
    ratings = {k: (v if v is not None else 0) for k, v in board.slots.items()}
    result = simulate_season(
        position=state["position"],
        overall=board.overall,
        ratings=ratings,
        club_id=state["club_id"],
        player_name=state["player_name"],
        seed=state["seed"],
    )
    season = {
        "table": result.table,
        "player": result.player,
        "club": result.club,
        "matches": result.matches,
        "cup": result.cup,
        "awards": result.awards,
        "monthly": result.monthly,
        "headlines": result.headlines,
        "grade": result.grade,
        "verdict": result.verdict,
        "top_scorers": result.top_scorers,
        "top_assists": result.top_assists,
    }
    state["phase"] = "complete"
    db.save_season(run_id, state, season)
    return _public(db.get_run(run_id), state)


# --------------------------------------------------------------------------- #
# Career mode
# --------------------------------------------------------------------------- #


@app.post("/api/runs/{run_id}/career/start")
def career_start(run_id: str, body: StartCareer) -> dict:
    """Turn a finished card into a potential, and begin at eighteen."""
    row, state = _load(run_id)
    _require_phase(state, "built")
    if body.nationality not in NATION_BY_ID:
        raise HTTPException(400, "unknown nationality")

    board = _board(state)
    ratings = {k: (v if v is not None else 0) for k, v in board.slots.items()}
    data = career_mode.new_career(
        name=state["player_name"],
        position=state["position"],
        era=state["era"],
        nationality=body.nationality,
        potential_ratings=ratings,
        seed=state["seed"],
    )
    rng = random.Random(f"{state['seed']}:career:0")
    state["career"] = data
    state["career_options"] = career_mode.decision_options(data, rng)
    state["phase"] = "career"
    db.save_state(run_id, state, overall=board.overall, club_id=data["club_id"])
    return _public(db.get_run(run_id), state)


@app.post("/api/runs/{run_id}/career/advance")
def career_advance(run_id: str, body: CareerChoice) -> dict:
    """Take the summer decision, play the season, present the next one."""
    row, state = _load(run_id)
    _require_phase(state, "career")
    data = state.get("career")
    if not data or data["retired"]:
        raise HTTPException(409, "this career is over")

    year_index = len(data["seasons"])
    rng = random.Random(f"{state['seed']}:career:{year_index}")
    career_mode.play_year(data, body.option_id, rng)

    if data["retired"]:
        state["career_options"] = []
        state["phase"] = "complete"
        summary = career_mode.career_summary(data)
        season_like = _career_as_season(data, summary)
        db.save_season(run_id, state, season_like)
    else:
        state["career_options"] = career_mode.decision_options(data, rng)
        db.save_state(run_id, state, club_id=data["club_id"])
    return _public(db.get_run(run_id), state)


def _career_as_season(data: dict, summary: dict) -> dict:
    """Shape a finished career so it can share the hall-of-fame row format."""
    return {
        "career": True,
        "grade": summary["title"],
        "verdict": summary["verdict"],
        "summary": summary,
        "seasons": data["seasons"],
        "player": {
            "total_goals": summary["totals"]["goals"],
            "total_assists": summary["totals"]["assists"],
            "clean_sheets": summary["totals"]["clean_sheets"],
            "avg_rating": summary["totals"]["avg_rating"],
        },
        "club": {
            "name": summary["longest_club"],
            "position": data["seasons"][-1]["league_position"] if data["seasons"] else 0,
        },
        "awards": [
            {"title": h["trophy"], "you_won": True} for h in data["honours"]
        ],
    }


# --------------------------------------------------------------------------- #
# Hall of fame
# --------------------------------------------------------------------------- #


@app.get("/api/hall-of-fame")
def hall_of_fame(
    sort: str = Query("overall", pattern="^(overall|goals|assists|rating|recent)$"),
    position: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    if position and position not in POSITIONS:
        raise HTTPException(400, "unknown position")
    return {"entries": db.hall_of_fame(sort=sort, position=position, limit=limit)}


# --------------------------------------------------------------------------- #
# Serve the built frontend when it exists (single-process production mode)
# --------------------------------------------------------------------------- #

_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = _DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
