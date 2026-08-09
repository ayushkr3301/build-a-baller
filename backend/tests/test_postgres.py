"""Runs the storage layer against a real Postgres, not just SQLite.

Vercel deploys against Postgres, so the dialect differences (parameter markers,
DOUBLE PRECISION, cursor semantics) need exercising somewhere. Skipped unless
BAB_TEST_POSTGRES_URL points at a throwaway database, e.g.

    docker run -d --name bab-pg -e POSTGRES_PASSWORD=bab -e POSTGRES_DB=bab \\
        -p 55432:5432 postgres:16-alpine
    BAB_TEST_POSTGRES_URL=postgresql://postgres:bab@127.0.0.1:55432/bab pytest
"""

import importlib
import os

import pytest
from fastapi.testclient import TestClient

PG_URL = os.environ.get("BAB_TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(not PG_URL, reason="BAB_TEST_POSTGRES_URL not set")


@pytest.fixture()
def pg_client():
    """A TestClient wired to Postgres with a clean runs table."""
    previous = {k: os.environ.get(k) for k in ("POSTGRES_URL", "DATABASE_URL", "BAB_DB")}
    os.environ["POSTGRES_URL"] = PG_URL
    os.environ.pop("DATABASE_URL", None)

    from app import db as db_mod

    importlib.reload(db_mod)
    assert db_mod.IS_POSTGRES, "expected the Postgres backend"

    with db_mod.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS runs")
    db_mod._initialised = False

    from app import main as main_mod

    importlib.reload(main_mod)
    try:
        with TestClient(main_mod.app) as client:
            yield client
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        importlib.reload(db_mod)
        importlib.reload(main_mod)


def test_placeholder_translation_targets_the_right_dialect():
    from app import db as db_mod

    importlib.reload(db_mod)
    sqlite_sql = db_mod._sql("SELECT * FROM runs WHERE id = ? AND era = ?")
    assert "?" in sqlite_sql and "%s" not in sqlite_sql

    os.environ["POSTGRES_URL"] = PG_URL
    importlib.reload(db_mod)
    pg_sql = db_mod._sql("SELECT * FROM runs WHERE id = ? AND era = ?")
    assert "%s" in pg_sql and "?" not in pg_sql
    os.environ.pop("POSTGRES_URL", None)
    importlib.reload(db_mod)


def test_a_whole_run_survives_on_postgres(pg_client):
    from app.data.attributes import N_CRITERIA

    run = pg_client.post(
        "/api/runs", json={"player_name": "Neon Nine", "position": "MID", "era": "legends"}
    ).json()
    rid = run["id"]

    state = run
    while state["phase"] == "building":
        spun = pg_client.post(f"/api/runs/{rid}/spin")
        assert spun.status_code == 200, spun.text
        state = spun.json()
        offer = state["current_offer"]
        open_slots = [k for k, v in state["board"].items() if v is None]
        best = max(open_slots, key=lambda k: offer["ratings"][k])
        state = pg_client.post(f"/api/runs/{rid}/take", json={"attribute": best}).json()

    assert state["slots_filled"] == N_CRITERIA
    state = pg_client.post(f"/api/runs/{rid}/veto", json={"club_ids": ["bur", "sun", "lee"]}).json()
    state = pg_client.post(f"/api/runs/{rid}/draft", json={}).json()
    state = pg_client.post(f"/api/runs/{rid}/simulate", json={}).json()

    assert state["phase"] == "complete"
    assert len(state["season"]["table"]) == 20
    assert len(state["season"]["matches"]) == 38

    # ...and it comes back out of the database intact on a fresh request.
    reread = pg_client.get(f"/api/runs/{rid}").json()
    assert reread["season"]["grade"] == state["season"]["grade"]
    assert reread["overall"] == state["overall"]


def test_hall_of_fame_reads_back_from_postgres(pg_client):
    from app.data.attributes import N_CRITERIA

    for name in ("First Legend", "Second Legend"):
        run = pg_client.post(
            "/api/runs", json={"player_name": name, "position": "ST", "era": "current"}
        ).json()
        rid = run["id"]
        state = run
        while state["phase"] == "building":
            state = pg_client.post(f"/api/runs/{rid}/spin").json()
            open_slots = [k for k, v in state["board"].items() if v is None]
            best = max(open_slots, key=lambda k: state["current_offer"]["ratings"][k])
            state = pg_client.post(f"/api/runs/{rid}/take", json={"attribute": best}).json()
        assert state["slots_filled"] == N_CRITERIA
        pg_client.post(f"/api/runs/{rid}/veto", json={"club_ids": ["bur", "sun", "lee"]})
        pg_client.post(f"/api/runs/{rid}/draft", json={})
        pg_client.post(f"/api/runs/{rid}/simulate", json={})

    entries = pg_client.get("/api/hall-of-fame").json()["entries"]
    assert len(entries) == 2
    assert {e["player_name"] for e in entries} == {"First Legend", "Second Legend"}
    assert all(e["overall"] and e["grade"] for e in entries)

    # every sort mode has to be valid Postgres, not just valid SQLite
    for sort in ("overall", "goals", "assists", "rating", "recent"):
        res = pg_client.get(f"/api/hall-of-fame?sort={sort}")
        assert res.status_code == 200, res.text
        assert len(res.json()["entries"]) == 2

    filtered = pg_client.get("/api/hall-of-fame?position=ST").json()["entries"]
    assert len(filtered) == 2
    assert pg_client.get("/api/hall-of-fame?position=GK").json()["entries"] == []


def test_stats_and_missing_run_behave_on_postgres(pg_client):
    meta = pg_client.get("/api/meta").json()
    assert meta["stats"]["runs_completed"] == 0
    assert pg_client.get("/api/runs/nope").status_code == 404
