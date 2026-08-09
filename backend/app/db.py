"""Persistence for runs and the hall of fame.

Runs on SQLite locally and Postgres in production. Vercel's filesystem is
ephemeral and per-instance, so a disk-backed SQLite file there would lose a run
between two requests of the same game -- hence Postgres whenever a connection
string is present.

Set POSTGRES_URL (or DATABASE_URL) to use Postgres; otherwise it's SQLite at
BAB_DB. The only dialect differences that matter here are the parameter marker
and a couple of column types, both handled below.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get("BAB_DB", Path(__file__).resolve().parent.parent / "data" / "runs.db"))


def postgres_url() -> str | None:
    """Vercel/Neon inject several aliases; prefer the pooled one for serverless."""
    for key in ("POSTGRES_PRISMA_URL", "POSTGRES_URL", "DATABASE_URL"):
        value = os.environ.get(key)
        if value:
            return value
    return None


IS_POSTGRES = postgres_url() is not None

if os.environ.get("VERCEL") and not IS_POSTGRES:
    # Fail loudly at import rather than throwing read-only-filesystem 500s later:
    # the lambda can only write to /tmp, and /tmp isn't shared between instances,
    # so a run would vanish between the spin that created it and the next request.
    raise RuntimeError(
        "Deployed on Vercel with no Postgres connection string. Vercel's filesystem "
        "is ephemeral and per-instance, so SQLite cannot hold a run together across "
        "requests. Add a Postgres database (Vercel dashboard -> Storage -> Create "
        "Database -> Neon) and redeploy -- it injects POSTGRES_URL automatically."
    )

_local = threading.local()

# `id` is a short opaque token, not a serial -- it's the URL the client holds.
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
    avg_rating    {REAL},
    state         TEXT NOT NULL,
    season        TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_overall ON runs(overall DESC);
CREATE INDEX IF NOT EXISTS idx_runs_completed ON runs(completed_at DESC);
"""


def _schema() -> str:
    return SCHEMA.replace("{REAL}", "DOUBLE PRECISION" if IS_POSTGRES else "REAL")


def _sql(query: str) -> str:
    """SQLite takes ? placeholders, Postgres takes %s. Author once, translate here."""
    return query.replace("?", "%s") if IS_POSTGRES else query


def _connect_postgres():
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(postgres_url(), row_factory=dict_row, autocommit=True)


def _connect_sqlite() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


_initialised = False


def _ensure_schema(conn) -> None:
    global _initialised
    if _initialised:
        return
    if IS_POSTGRES:
        with conn.cursor() as cur:
            for statement in filter(None, (s.strip() for s in _schema().split(";"))):
                cur.execute(statement)
    else:
        conn.executescript(_schema())
        conn.commit()
    _initialised = True


@contextmanager
def cursor():
    """A cursor over the right backend.

    Postgres connections are opened per call: serverless instances are frozen
    between invocations, so a cached socket is usually dead by the next request.
    SQLite is a local file, so the connection is kept per-thread.
    """
    if IS_POSTGRES:
        conn = _connect_postgres()
        try:
            _ensure_schema(conn)
            with conn.cursor() as cur:
                yield cur
        finally:
            conn.close()
    else:
        conn = getattr(_local, "conn", None)
        if conn is None:
            conn = _connect_sqlite()
            _local.conn = conn
        _ensure_schema(conn)
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        finally:
            cur.close()


def _row_to_dict(row) -> dict | None:
    if row is None:
        return None
    return dict(row)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #


def create_run(run_id: str, player_name: str, position: str, era: str, state: dict) -> None:
    with cursor() as cur:
        cur.execute(
            _sql(
                "INSERT INTO runs (id, created_at, player_name, position, era, phase, state)"
                " VALUES (?,?,?,?,?,?,?)"
            ),
            (run_id, now(), player_name, position, era, state["phase"], json.dumps(state)),
        )


def save_state(
    run_id: str, state: dict, overall: int | None = None, club_id: str | None = None
) -> None:
    with cursor() as cur:
        cur.execute(
            _sql(
                "UPDATE runs SET state = ?, phase = ?, overall = COALESCE(?, overall),"
                " club_id = COALESCE(?, club_id) WHERE id = ?"
            ),
            (json.dumps(state), state["phase"], overall, club_id, run_id),
        )


def save_season(run_id: str, state: dict, season: dict) -> None:
    player = season["player"]
    with cursor() as cur:
        cur.execute(
            _sql(
                "UPDATE runs SET state = ?, phase = ?, season = ?, completed_at = ?, grade = ?,"
                " goals = ?, assists = ?, clean_sheets = ?, league_pos = ?, avg_rating = ?"
                " WHERE id = ?"
            ),
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


def get_run(run_id: str) -> dict | None:
    with cursor() as cur:
        cur.execute(_sql("SELECT * FROM runs WHERE id = ?"), (run_id,))
        return _row_to_dict(cur.fetchone())


# --------------------------------------------------------------------------- #
# Hall of fame
# --------------------------------------------------------------------------- #

HOF_SORTS = {
    "overall": "overall DESC, avg_rating DESC",
    "goals": "goals DESC, overall DESC",
    "assists": "assists DESC, overall DESC",
    "rating": "avg_rating DESC, overall DESC",
    "recent": "completed_at DESC",
}


def hall_of_fame(sort: str = "overall", position: str | None = None, limit: int = 50) -> list[dict]:
    # `order` is chosen from a fixed allow-list, never interpolated from user input.
    order = HOF_SORTS.get(sort, HOF_SORTS["overall"])
    query = "SELECT * FROM runs WHERE completed_at IS NOT NULL"
    params: list = []
    if position:
        query += " AND position = ?"
        params.append(position)
    query += f" ORDER BY {order} LIMIT ?"
    params.append(limit)

    with cursor() as cur:
        cur.execute(_sql(query), tuple(params))
        rows = [dict(r) for r in cur.fetchall()]

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
    with cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM runs WHERE completed_at IS NOT NULL")
        total = dict(cur.fetchone())["c"]
        cur.execute(
            "SELECT player_name, overall FROM runs WHERE completed_at IS NOT NULL"
            " ORDER BY overall DESC LIMIT 1"
        )
        best = _row_to_dict(cur.fetchone())
    return {
        "runs_completed": total,
        "best_overall": best["overall"] if best else None,
        "best_player": best["player_name"] if best else None,
    }
