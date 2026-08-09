import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.data.attributes import N_CRITERIA, N_SPINS


@pytest.fixture()
def client(monkeypatch):
    tmp = tempfile.mkdtemp()
    os.environ["BAB_DB"] = os.path.join(tmp, "test.db")
    import importlib

    from app import db as db_mod

    importlib.reload(db_mod)
    from app import main as main_mod

    importlib.reload(main_mod)
    with TestClient(main_mod.app) as c:
        yield c


def start(client, position="ST", era="current", name="Test Baller"):
    r = client.post("/api/runs", json={"player_name": name, "position": position, "era": era})
    assert r.status_code == 200, r.text
    return r.json()


def test_meta_describes_the_whole_game(client):
    m = client.get("/api/meta").json()
    assert m["criteria"] == N_CRITERIA and m["spins"] == N_SPINS
    assert {p["key"] for p in m["positions"]} == {"ST", "MID", "DEF", "GK"}
    assert all(len(p["attributes"]) == N_CRITERIA for p in m["positions"])
    assert len(m["clubs"]) == 20
    assert {e["key"] for e in m["eras"]} == {"current", "legends"}


def test_create_run_starts_empty(client):
    run = start(client)
    assert run["phase"] == "building"
    assert run["spins_left"] == N_SPINS
    assert run["slots_filled"] == 0
    assert all(v is None for v in run["board"].values())
    assert run["current_offer"] is None


def test_spin_is_not_rerollable(client):
    run = start(client)
    a = client.post(f"/api/runs/{run['id']}/spin").json()
    b = client.post(f"/api/runs/{run['id']}/spin").json()
    assert a["current_offer"]["id"] == b["current_offer"]["id"]
    assert a["spins_used"] == 0  # the spin isn't spent until you take or skip


def test_take_locks_the_slot_and_rejects_a_second_take(client):
    run = start(client)
    rid = run["id"]
    offer = client.post(f"/api/runs/{rid}/spin").json()["current_offer"]
    key = "finishing"
    after = client.post(f"/api/runs/{rid}/take", json={"attribute": key}).json()
    assert after["board"][key] == offer["ratings"][key]
    assert after["sources"][key] == offer["name"]
    assert after["spins_used"] == 1
    assert after["current_offer"] is None

    client.post(f"/api/runs/{rid}/spin")
    dup = client.post(f"/api/runs/{rid}/take", json={"attribute": key})
    assert dup.status_code == 409


def test_take_without_spinning_is_rejected(client):
    run = start(client)
    r = client.post(f"/api/runs/{run['id']}/take", json={"attribute": "pace"})
    assert r.status_code == 409


def test_full_run_through_to_a_simulated_season(client):
    run = start(client, position="ST", era="legends", name="Ayush FC")
    rid = run["id"]

    state = run
    while state["phase"] == "building":
        spun = client.post(f"/api/runs/{rid}/spin")
        assert spun.status_code == 200, spun.text
        state = spun.json()
        offer = state["current_offer"]
        open_slots = [k for k, v in state["board"].items() if v is None]
        best = max(open_slots, key=lambda k: offer["ratings"][k])
        state = client.post(f"/api/runs/{rid}/take", json={"attribute": best}).json()

    # Filling every slot ends the build, so the spare spin never gets offered.
    assert state["spins_used"] == N_CRITERIA
    assert client.post(f"/api/runs/{rid}/spin").status_code == 409
    assert state["phase"] == "built"
    assert state["slots_filled"] == N_CRITERIA
    assert 0 < state["overall"] <= 100
    assert state["draft_odds"] and len(state["draft_odds"]) == 20

    vetoes = [o["club_id"] for o in state["draft_odds"][:3]]
    state = client.post(f"/api/runs/{rid}/veto", json={"club_ids": vetoes}).json()
    assert state["phase"] == "vetoed"
    assert {o["club_id"] for o in state["draft_odds"]}.isdisjoint(vetoes)

    state = client.post(f"/api/runs/{rid}/draft").json()
    assert state["phase"] == "drafted"
    assert state["club_id"] not in vetoes

    state = client.post(f"/api/runs/{rid}/simulate").json()
    assert state["phase"] == "complete"
    season = state["season"]
    assert len(season["table"]) == 20
    assert len(season["matches"]) == 38
    assert season["player"]["name"] == "Ayush FC"
    assert season["grade"]
    assert any(row["is_you"] for row in season["table"])

    hof = client.get("/api/hall-of-fame").json()["entries"]
    assert any(e["id"] == rid for e in hof)
    assert hof[0]["overall"] is not None


def test_skipping_twice_leaves_a_hole_in_the_board(client):
    run = start(client, position="GK")
    rid = run["id"]
    state = run
    skips = 0
    while state["phase"] == "building":
        spun = client.post(f"/api/runs/{rid}/spin")
        assert spun.status_code == 200, spun.text
        state = spun.json()
        if skips < 2:
            skips += 1
            state = client.post(f"/api/runs/{rid}/skip").json()
            continue
        open_slots = [k for k, v in state["board"].items() if v is None]
        best = max(open_slots, key=lambda k: state["current_offer"]["ratings"][k])
        state = client.post(f"/api/runs/{rid}/take", json={"attribute": best}).json()

    assert state["phase"] == "built"
    assert state["spins_used"] == N_SPINS
    assert state["slots_filled"] == N_CRITERIA - 1
    assert sum(1 for v in state["board"].values() if v is None) == 1


def test_phase_order_is_enforced(client):
    run = start(client)
    rid = run["id"]
    assert client.post(f"/api/runs/{rid}/draft").status_code == 409
    assert client.post(f"/api/runs/{rid}/simulate").status_code == 409
    assert client.post(f"/api/runs/{rid}/veto", json={"club_ids": ["ars", "liv", "mci"]}).status_code == 409


def test_veto_needs_exactly_three_real_clubs(client):
    run = start(client, position="DEF")
    rid = run["id"]
    for _ in range(N_CRITERIA):
        state = client.post(f"/api/runs/{rid}/spin").json()
        open_slots = [k for k, v in state["board"].items() if v is None]
        client.post(f"/api/runs/{rid}/take", json={"attribute": open_slots[0]})

    assert client.post(f"/api/runs/{rid}/veto", json={"club_ids": ["ars", "liv"]}).status_code == 400
    bad = client.post(f"/api/runs/{rid}/veto", json={"club_ids": ["ars", "liv", "nope"]})
    assert bad.status_code == 400
    ok = client.post(f"/api/runs/{rid}/veto", json={"club_ids": ["ars", "liv", "mci"]})
    assert ok.status_code == 200


def test_unknown_run_is_a_404(client):
    assert client.get("/api/runs/does-not-exist").status_code == 404


def test_bad_position_is_rejected(client):
    r = client.post("/api/runs", json={"player_name": "X", "position": "SWEEPER", "era": "current"})
    assert r.status_code == 422
