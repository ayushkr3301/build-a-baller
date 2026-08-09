"""SQLite persistence for runs and the hall of fame."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get("BAB_DB", Path(__file__).resolve().parent.parent / "data" / "runs.db"))

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    completed_at  TEXT,
    player_name   TEXT NOT NULL,
    position      TEXT NOT NULL,
    era           TEXT NOT NULL,
    phase         TEXT NOT NULL,
    overall       INTEGER,
    club_id       TEXT,
    grade         TEXT,
    goals         INTEGER,
    assists       INTEGER,
    clean_sheets  INTEGER,
    league_pos    INTEGER,
    avg_rating    REAL,
    state         TEXT NOT NULL,
    season        TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_overall ON runs(overall DESC);
CREATE INDEX IF NOT EXISTS idx_runs_completed ON runs(completed_at DESC);
"""


def connect() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        conn.commit()
        _local.conn = conn
    return conn


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_run(run_id: str, player_name: str, position: str, era: str, state: dict) -> None:
    conn = connect()
    conn.execute(
        "INSERT INTO runs (id, created_at, player_name, position, era, phase, state)"
        " VALUES (?,?,?,?,?,?,?)",
        (run_id, now(), player_name, position, era, state["phase"], json.dumps(state)),
    )
    conn.commit()


def save_state(run_id: str, state: dict, overall: int | None = None, club_id: str | None = None) -> None:
    conn = connect()
    conn.execute(
        "UPDATE runs SET state = ?, phase = ?, overall = COALESCE(?, overall),"
        " club_id = COALESCE(?, club_id) WHERE id = ?",
        (json.dumps(state), state["phase"], overall, club_id, run_id),
    )
    conn.commit()


def save_season(run_id: str, state: dict, season: dict) -> None:
    player = season["player"]
    conn = connect()
    conn.execute(
        "UPDATE runs SET state = ?, phase = ?, season = ?, completed_at = ?, grade = ?,"
        " goals = ?, assists = ?, clean_sheets = ?, league_pos = ?, avg_rating = ?"
        " WHERE id = ?",
        (
            json.dumps(state),
            state["phase"],
            json.dumps(season),
            now(),
            season["grade"],
            player["total_goals"],
            player["total_assists"],
            player["clean_sheets"],
            season["club"]["position"],
            player["avg_rating"],
            run_id,
        ),
    )
    conn.commit()


def get_run(run_id: str) -> sqlite3.Row | None:
    return connect().execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()


HOF_SORTS = {
    "overall": "overall DESC, avg_rating DESC",
    "goals": "goals DESC, overall DESC",
    "assists": "assists DESC, overall DESC",
    "rating": "avg_rating DESC, overall DESC",
    "recent": "completed_at DESC",
}


def hall_of_fame(sort: str = "overall", position: str | None = None, limit: int = 50) -> list[dict]:
    order = HOF_SORTS.get(sort, HOF_SORTS["overall"])
    sql = "SELECT * FROM runs WHERE completed_at IS NOT NULL"
    params: list = []
    if position:
        sql += " AND position = ?"
        params.append(position)
    sql += f" ORDER BY {order} LIMIT ?"
    params.append(limit)

    rows = connect().execute(sql, params).fetchall()
    out = []
    for r in rows:
        season = json.loads(r["season"]) if r["season"] else {}
        out.append(
            {
                "id": r["id"],
                "player_name": r["player_name"],
                "position": r["position"],
                "era": r["era"],
                "overall": r["overall"],
                "club_id": r["club_id"],
                "club": season.get("club", {}).get("name"),
                "grade": r["grade"],
                "goals": r["goals"],
                "assists": r["assists"],
                "clean_sheets": r["clean_sheets"],
                "league_pos": r["league_pos"],
                "avg_rating": r["avg_rating"],
                "completed_at": r["completed_at"],
                "awards": [a["title"] for a in season.get("awards", []) if a.get("you_won")],
            }
        )
    return out


def stats() -> dict:
    conn = connect()
    total = conn.execute("SELECT COUNT(*) c FROM runs WHERE completed_at IS NOT NULL").fetchone()["c"]
    best = conn.execute(
        "SELECT player_name, overall FROM runs WHERE completed_at IS NOT NULL"
        " ORDER BY overall DESC LIMIT 1"
    ).fetchone()
    return {
        "runs_completed": total,
        "best_overall": best["overall"] if best else None,
        "best_player": best["player_name"] if best else None,
    }
