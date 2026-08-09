import random

import pytest

from app.data.attributes import attr_keys, overall_from
from app.data.clubs import CLUBS
from app.sim import build_fixtures, simulate_season

ELITE_ST = dict(zip(attr_keys("ST"), (92, 90, 86, 84, 88, 88, 80, 84, 85, 84, 80, 86)))
ELITE_GK = dict(zip(attr_keys("GK"), (92, 90, 90, 90, 90, 86, 90, 84, 90, 88, 80, 86)))


def run(position="ST", ratings=None, club_id="ars", seed=7):
    ratings = ratings or ELITE_ST
    return simulate_season(
        position=position,
        overall=overall_from(position, ratings),
        ratings=ratings,
        club_id=club_id,
        player_name="Test Baller",
        seed=seed,
    )


def _venue_sequence(fixtures, club_id):
    seq = []
    for rnd in fixtures:
        for home, away in rnd:
            if home == club_id:
                seq.append("H")
            elif away == club_id:
                seq.append("A")
    return seq


def _longest_run(seq):
    best = run = 1
    for i in range(1, len(seq)):
        run = run + 1 if seq[i] == seq[i - 1] else 1
        best = max(best, run)
    return best


@pytest.mark.parametrize("seed", range(20))
def test_fixture_list_is_a_real_double_round_robin(seed):
    fixtures = build_fixtures([c.id for c in CLUBS], random.Random(seed))
    assert len(fixtures) == 38

    played = {}
    for rnd in fixtures:
        assert len(rnd) == 10
        teams = [t for pair in rnd for t in pair]
        assert len(set(teams)) == 20, "a club is scheduled twice on one matchday"
        for home, away in rnd:
            played[(home, away)] = played.get((home, away), 0) + 1

    assert len(played) == 380
    assert all(v == 1 for v in played.values()), "duplicate fixture at the same venue"

    for club in CLUBS:
        seq = _venue_sequence(fixtures, club.id)
        assert len(seq) == 38
        assert seq.count("H") == 19, f"{club.id} is not 19 home / 19 away"


@pytest.mark.parametrize("seed", range(20))
def test_no_club_gets_a_absurd_run_of_home_or_away_games(seed):
    """Regression: index-parity venue assignment gave clubs 19 straight home games."""
    fixtures = build_fixtures([c.id for c in CLUBS], random.Random(seed))
    for club in CLUBS:
        run = _longest_run(_venue_sequence(fixtures, club.id))
        assert run <= 6, f"{club.id} has {run} consecutive matches at the same venue"


@pytest.mark.parametrize("seed", range(6))
def test_league_table_is_internally_consistent(seed):
    res = run(seed=seed)
    assert len(res.table) == 20
    assert all(r["played"] == 38 for r in res.table)
    assert sum(r["gf"] for r in res.table) == sum(r["ga"] for r in res.table)
    for r in res.table:
        assert r["won"] + r["drawn"] + r["lost"] == 38
        assert r["points"] == r["won"] * 3 + r["drawn"]
        assert r["gd"] == r["gf"] - r["ga"]
    points = [r["points"] for r in res.table]
    assert points == sorted(points, reverse=True)
    assert sum(r["won"] for r in res.table) == sum(r["lost"] for r in res.table)


@pytest.mark.parametrize("seed", range(6))
def test_player_cannot_outscore_their_own_team(seed):
    res = run(seed=seed)
    for m in res.matches:
        scored = int(m["score"].split("-")[0])
        assert m["goals"] + m["assists"] <= scored, m


def test_player_plays_thirty_eight_league_matches():
    res = run()
    assert len(res.matches) == 38
    assert {m["matchday"] for m in res.matches} == set(range(1, 39))
    p = res.player
    accounted = p["apps"] + p["matches_missed_injured"] + p["matches_missed_suspended"]
    assert accounted <= 38


def test_player_totals_match_the_match_log():
    res = run()
    assert res.player["goals"] == sum(m["goals"] for m in res.matches)
    assert res.player["assists"] == sum(m["assists"] for m in res.matches)
    assert res.player["clean_sheets"] == sum(1 for m in res.matches if m["clean_sheet"])
    assert res.player["total_goals"] == res.player["goals"] + res.cup["goals"]


def test_golden_boot_table_agrees_with_the_player_summary():
    res = run()
    you = [s for s in res.top_scorers if s["is_you"]]
    assert len(you) == 1
    assert you[0]["value"] == res.player["goals"]


def test_outfield_scoring_and_keeper_shape():
    st = run("ST", ELITE_ST)
    assert st.player["goals"] > 0
    assert st.player["saves"] == 0

    gk = run("GK", ELITE_GK)
    assert gk.player["goals"] == 0
    assert gk.player["saves"] > 0
    assert gk.player["clean_sheets"] > 0


def test_cup_run_terminates_with_one_winner():
    res = run()
    assert res.cup["winner_id"] is not None
    assert len(res.cup["matches"]) >= 1
    if res.cup["won"]:
        assert all(m["won"] for m in res.cup["matches"])
        assert res.cup["reached"] == "Final"
    else:
        assert not res.cup["matches"][-1]["won"]


def test_same_seed_reproduces_the_season():
    a, b = run(seed=99), run(seed=99)
    assert a.table == b.table
    assert a.player == b.player
    assert a.grade == b.grade


def test_the_same_build_does_better_at_a_better_club():
    strong = [run(club_id="mci", seed=s).player["goals"] for s in range(25)]
    weak = [run(club_id="bur", seed=s).player["goals"] for s in range(25)]
    assert sum(strong) / 25 > sum(weak) / 25


def test_grades_are_relative_to_the_club_you_were_drafted_into():
    """An elite build shouldn't be doomed to an F just for landing at a small club."""
    grades = [run(club_id="bur", seed=s).grade for s in range(40)]
    assert len({g for g in grades}) >= 3
    assert sum(1 for g in grades if g in ("A+", "A", "B+", "B")) >= 10


def test_awards_and_narrative_are_populated():
    res = run()
    assert {a["id"] for a in res.awards} == {
        "golden_boot",
        "playmaker",
        "golden_glove",
        "potm",
    }
    assert res.grade in ("A+", "A", "B+", "B", "C+", "C", "D", "F")
    assert res.verdict and res.headlines
    assert res.monthly and sum(m["goals"] for m in res.monthly) == res.player["goals"]
    assert res.club["qualification"]
