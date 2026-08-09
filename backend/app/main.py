"""Build A Baller -- FastAPI backend.

The server is authoritative about every random event: the spin draws, the club
draft and the season. The client can't reroll a spin it doesn't like, because the
offered player is stored server-side until it is taken or skipped.
"""

from __future__ import annotations

import json
import os
import random
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db, game
from .data.attributes import ERAS, N_CRITERIA, N_SPINS, POSITIONS, TIERS, attr_keys
from .data.clubs import CLUBS, CLUB_BY_ID, DISPLAY_CLUB_BY_ID
from .models import CreateRun, TakeAttribute, VetoClubs
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
        "draft_odds": None,
        "season": json.loads(row["season"]) if row["season"] else None,
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


# --------------------------------------------------------------------------- #
# Metadata
# --------------------------------------------------------------------------- #


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


@app.get("/api/meta")
def meta() -> dict:
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
        "stats": db.stats(),
    }


# --------------------------------------------------------------------------- #
# Run lifecycle
# --------------------------------------------------------------------------- #


@app.post("/api/runs")
def create_run(body: CreateRun) -> dict:
    run_id = secrets.token_urlsafe(9)
    state = {
        "player_name": body.player_name,
        "position": body.position,
        "era": body.era,
        "seed": secrets.randbelow(2**31),
        "phase": "building",
        "spin_index": 0,
        "current_offer": None,
        "board": {k: None for k in attr_keys(body.position)},
        "sources": {},
        "seen_ids": [],
        "history": [],
        "vetoed": [],
        "club_id": None,
    }
    db.create_run(run_id, body.player_name, body.position, body.era, state)
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
