"""Daily challenge, share text, and practice replays."""

import importlib
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from app import daily
from app.data.attributes import ATTRIBUTES, attr_keys


@pytest.fixture()
def client():
    os.environ["BAB_DB"] = os.path.join(tempfile.mkdtemp(), "daily.db")
    from app import db as db_mod

    importlib.reload(db_mod)
    from app import main as main_mod

    importlib.reload(main_mod)
    with TestClient(main_mod.app) as c:
        yield c


def build_out(client, run):
    """Play a run to a finished card, taking the best available each spin."""
    rid = run["id"]
    state = run
    while state["phase"] == "building":
        state = client.post(f"/api/runs/{rid}/spin").json()
        open_slots = [k for k, v in state["board"].items() if v is None]
        best = max(open_slots, key=lambda k: state["current_offer"]["ratings"][k])
        state = client.post(f"/api/runs/{rid}/take", json={"attribute": best}).json()
    return state


def finish(client, state):
    rid = state["id"]
    client.post(f"/api/runs/{rid}/veto", json={"club_ids": ["bur", "sun", "lee"]})
    client.post(f"/api/runs/{rid}/draft")
    return client.post(f"/api/runs/{rid}/simulate").json()


# --------------------------------------------------------------------------- #
# The shared seed
# --------------------------------------------------------------------------- #


def test_the_same_date_always_produces_the_same_challenge():
    """Everyone in the world has to face identical spins, today and forever."""
    first = daily.config("2026-09-01")
    second = daily.config("2026-09-01")
    assert (first["seed"], first["position"], first["era"]) == (
        second["seed"], second["position"], second["era"]
    )
    other = daily.config("2026-09-02")
    assert other["seed"] != first["seed"]


def test_position_and_era_rotate_across_dates():
    setups = [daily.config(f"2026-09-{d:02d}") for d in range(1, 29)]
    assert len({s["position"] for s in setups}) >= 3
    assert len({s["era"] for s in setups}) == 2


def test_day_numbering_counts_from_launch():
    assert daily.day_number(daily.LAUNCH.isoformat()) == 1
    assert daily.day_number("2026-08-19") == 11


# --------------------------------------------------------------------------- #
# Streaks
# --------------------------------------------------------------------------- #


def test_streak_counts_back_from_today():
    assert daily.streak_from_dates(
        ["2026-08-20", "2026-08-19", "2026-08-18"], reference="2026-08-20"
    ) == 3


def test_yesterday_still_counts_as_an_unbroken_streak():
    """Otherwise a streak dies at midnight UTC and punishes time zones."""
    assert daily.streak_from_dates(["2026-08-19", "2026-08-18"], reference="2026-08-20") == 2


def test_a_missed_day_breaks_the_streak():
    assert daily.streak_from_dates(
        ["2026-08-20", "2026-08-17", "2026-08-16"], reference="2026-08-20"
    ) == 1
    assert daily.streak_from_dates([], reference="2026-08-20") == 0


# --------------------------------------------------------------------------- #
# The share grid
# --------------------------------------------------------------------------- #


def test_a_perfect_card_is_all_green():
    keys = attr_keys("ST")
    board = dict.fromkeys(keys, 85)
    picks = {k: {"value": 85} for k in keys}
    grid = daily.result_grid("ST", board, picks)
    assert grid == daily.GREEN * len(keys)


def test_squares_reflect_overall_cost_not_the_raw_gap():
    """A 10-point miss in a 3%-weighted slot is nothing; in a 15% slot it's the game."""
    keys = attr_keys("ST")
    weights = {a.key: a.weight for a in ATTRIBUTES["ST"]}
    cheapest = min(weights, key=lambda k: weights[k])
    dearest = max(weights, key=lambda k: weights[k])

    board = dict.fromkeys(keys, 80)
    picks = {k: {"value": 80} for k in keys}
    picks[cheapest] = {"value": 95}
    picks[dearest] = {"value": 95}

    grid = daily.result_grid("ST", board, picks)
    order = [a.key for a in ATTRIBUTES["ST"]]
    assert grid[order.index(cheapest)] == daily.GREEN, "a cheap slot barely matters"
    assert grid[order.index(dearest)] == daily.BLANK, "an expensive slot should shout"


def test_share_text_hides_which_players_came_up():
    keys = attr_keys("GK")
    board = dict.fromkeys(keys, 84)
    text = daily.share_text(
        day="2026-08-15",
        position_name="Goalkeeper",
        era_name="Current Era",
        overall=84,
        grade="B+",
        grid=daily.result_grid("GK", board, {k: {"value": 88} for k in keys}),
        optimum=88,
        streak=4,
    )
    assert "Day 7" in text
    assert "84 OVR (B+)" in text
    assert "left 4 on the table" in text
    assert "4 day streak" in text
    # The whole point: postable before your friends have played.
    assert "Alisson" not in text and "Pope" not in text


# --------------------------------------------------------------------------- #
# One attempt, and practice afterwards
# --------------------------------------------------------------------------- #


def test_one_daily_attempt_per_token(client):
    body = {"player_name": "A", "position": "ST", "era": "current",
            "mode": "daily", "player_token": "tok-a"}
    assert client.post("/api/runs", json=body).status_code == 200
    assert client.post("/api/runs", json=body).status_code == 409
    # ...but a different player is unaffected.
    body["player_token"] = "tok-b"
    assert client.post("/api/runs", json=body).status_code == 200


def test_daily_ignores_the_position_and_era_the_client_asks_for(client):
    setup = client.get("/api/daily?player_token=tok-c").json()
    run = client.post("/api/runs", json={
        "player_name": "C", "position": "DEF", "era": "legends",
        "mode": "daily", "player_token": "tok-c",
    }).json()
    assert run["position"] == setup["position"]
    assert run["era"] == setup["era"]
    assert set(run["board"]) == set(attr_keys(setup["position"]))


def test_practice_replays_the_same_seed_without_using_your_attempt(client):
    token = "tok-practice"
    daily_run = client.post("/api/runs", json={
        "player_name": "P", "position": "ST", "era": "current",
        "mode": "daily", "player_token": token,
    }).json()

    practice = client.post("/api/runs", json={
        "player_name": "P", "position": "ST", "era": "current",
        "mode": "practice", "player_token": token,
    })
    assert practice.status_code == 200, "practice must never be blocked"
    practice_run = practice.json()
    assert practice_run["mode"] == "practice"
    assert practice_run["position"] == daily_run["position"]
    assert practice_run["daily_date"] == daily_run["daily_date"]

    # Identical spins: the point of a replay is the same cards.
    def first_offer(run_id):
        return client.post(f"/api/runs/{run_id}/spin").json()["current_offer"]["id"]

    assert first_offer(daily_run["id"]) == first_offer(practice_run["id"])
    # ...and practice can be replayed as often as you like.
    assert client.post("/api/runs", json={
        "player_name": "P", "position": "ST", "era": "current",
        "mode": "practice", "player_token": token,
    }).status_code == 200


def test_practice_stays_off_the_leaderboards(client):
    token = "tok-board"
    practice = client.post("/api/runs", json={
        "player_name": "Grinder", "position": "ST", "era": "current",
        "mode": "practice", "player_token": token,
    }).json()
    finish(client, build_out(client, practice))

    day = client.get(f"/api/daily?player_token={token}").json()
    assert day["leaderboard"] == [], "practice must not appear on the daily board"
    assert day["already_played"] is False, "practice must not consume the attempt"
    assert day["streak"] == 0, "practice must not build a streak"
    assert client.get("/api/hall-of-fame").json()["entries"] == []


def test_a_finished_daily_produces_postable_share_text(client):
    token = "tok-share"
    run = client.post("/api/runs", json={
        "player_name": "Sharer", "position": "ST", "era": "current",
        "mode": "daily", "player_token": token,
    }).json()
    state = finish(client, build_out(client, run))

    share = state["share"]
    assert share is not None
    assert share["day_number"] >= 1
    assert len(share["grid"]) == len(attr_keys(state["position"]))
    assert "Build A Baller" in share["text"]
    assert share["grid"] in share["text"]
    assert share["practice"] is False


def test_season_runs_have_no_share_block(client):
    run = client.post("/api/runs", json={
        "player_name": "Normal", "position": "ST", "era": "current", "mode": "season",
    }).json()
    state = finish(client, build_out(client, run))
    assert state["share"] is None
