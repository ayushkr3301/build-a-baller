"""Career mode.

Several constants here were derived by measurement rather than taste, and are
easy to break by "tidying". The behaviour they buy:

    strategy   peak (potential 86)   reached ceiling   Ballon d'Or
    optimal    85.0                  22/30             3/40 careers
    drift      83.9                   6/30             0/40
    money      82.9                   0/30             0/40

Above BASE_GROWTH ~2.8 every strategy maxes out and the summer decision stops
mattering; below ~1.7 nobody develops and potential is decorative.
"""

import random

import pytest

from app import career
from app.data.attributes import attr_keys, overall_from
from app.data.clubs import CLUB_BY_ID

STRIKER = dict(zip(attr_keys("ST"), (92, 90, 86, 84, 88, 88, 80, 84, 85, 84, 80, 86)))
KEEPER = dict(zip(attr_keys("GK"), (92, 90, 90, 90, 90, 86, 90, 84, 90, 88, 80, 86)))

OPTIMAL = ["loan", "step_up", "talisman", "stay"]
DRIFT = ["stay"]
MONEY = ["payday", "rotate", "stay"]


def play(strategy, seed, ratings=None, position="ST", nationality="eng"):
    rng = random.Random(seed)
    state = career.new_career(
        name="Test", position=position, era="legends", nationality=nationality,
        potential_ratings=ratings or STRIKER, seed=seed,
    )
    while not state["retired"] and len(state["seasons"]) < 26:
        options = [o["id"] for o in career.decision_options(state, rng)]
        assert options, "there must always be something to choose"
        pick = next((p for p in strategy if p in options), "stay")
        career.play_year(state, pick, rng)
    return state


# --------------------------------------------------------------------------- #
# Shape of a career
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("seed", range(6))
def test_a_career_starts_at_eighteen_and_ends_in_retirement(seed):
    state = play(OPTIMAL, seed)
    assert state["retired"]
    assert state["seasons"][0]["age"] == career.START_AGE
    ages = [s["age"] for s in state["seasons"]]
    assert ages == sorted(ages), "ages must increase"
    assert ages == list(range(ages[0], ages[0] + len(ages))), "no year may be skipped"
    assert career.RETIRE_MIN_AGE <= state["age"] <= career.RETIRE_FORCED_AGE + 1


def test_you_begin_well_below_your_potential():
    state = career.new_career(
        name="Kid", position="ST", era="legends", nationality="eng",
        potential_ratings=STRIKER, seed=1,
    )
    assert state["potential"] == overall_from("ST", STRIKER)
    assert state["overall"] == state["potential"] - career.START_GAP
    assert state["age"] == 18


@pytest.mark.parametrize("seed", range(6))
def test_overall_never_exceeds_potential(seed):
    state = play(OPTIMAL, seed)
    for s in state["seasons"]:
        assert s["overall_after"] <= state["potential"]
    assert state["peak_overall"] <= state["potential"]


# --------------------------------------------------------------------------- #
# The decisions have to matter
# --------------------------------------------------------------------------- #


def test_how_you_play_changes_where_you_finish():
    """The whole point of the mode. If these converge, there is no game here."""
    def mean_peak(strategy):
        return sum(play(strategy, s)["peak_overall"] for s in range(14)) / 14

    optimal, drift, money = mean_peak(OPTIMAL), mean_peak(DRIFT), mean_peak(MONEY)
    assert optimal > drift > money, f"{optimal=} {drift=} {money=}"
    assert optimal - money >= 1.2, "strategies are too close to be a decision"


def test_chasing_money_costs_you_the_ceiling():
    reached = sum(
        career.career_summary(play(MONEY, s))["reached_potential"] for s in range(12)
    )
    assert reached <= 2, "warming a bench for wages should not reach potential"


def test_growth_is_not_so_generous_that_everyone_maxes_out():
    reached = sum(
        career.career_summary(play(DRIFT, s))["reached_potential"] for s in range(20)
    )
    assert reached < 16, "drifting through a career should usually fall short"


# --------------------------------------------------------------------------- #
# Retraining
# --------------------------------------------------------------------------- #


def test_retraining_costs_a_bounded_amount_and_does_not_compound():
    """Regression: rebuilding unshared attributes from raw numbers cost 9 points
    a switch and compounded, turning an 86 into a 70 across two moves."""
    state = career.new_career(
        name="X", position="ST", era="legends", nationality="eng",
        potential_ratings=STRIKER, seed=1,
    )
    start = state["potential"]
    career.retrain(state, "MID", random.Random(1))
    after_one = state["potential"]
    career.retrain(state, "DEF", random.Random(1))
    after_two = state["potential"]

    assert state["position"] == "DEF"
    assert start - after_one <= career.RETRAIN_COST + 1
    assert after_one - after_two <= career.RETRAIN_COST + 1
    assert set(state["potential_ratings"]) == set(attr_keys("DEF"))


def test_a_ceiling_below_current_ability_is_impossible():
    state = career.new_career(
        name="X", position="ST", era="legends", nationality="eng",
        potential_ratings=STRIKER, seed=2,
    )
    state["overall"] = state["potential"]  # a player who has maxed out
    career.retrain(state, "MID", random.Random(2))
    assert state["potential"] >= state["overall"]


# --------------------------------------------------------------------------- #
# Loans
# --------------------------------------------------------------------------- #


def test_a_loan_returns_you_to_your_parent_club():
    """Regression: staying at the EFL club made next summer look up an EFL id in
    the Premier League table and raise KeyError."""
    rng = random.Random(4)
    state = career.new_career(
        name="X", position="ST", era="legends", nationality="eng",
        potential_ratings=STRIKER, seed=4,
    )
    parent = state["club_id"]
    for _ in range(6):
        options = [o["id"] for o in career.decision_options(state, rng)]
        if "loan" in options:
            season = career.play_year(state, "loan", rng)
            assert season["on_loan"]
            assert state["club_id"] == parent, "a loan is for one season"
            assert state["club_id"] in CLUB_BY_ID
            return
        career.play_year(state, "stay", rng)
    pytest.skip("no loan was offered in this run")


# --------------------------------------------------------------------------- #
# Honours, Europe, internationals
# --------------------------------------------------------------------------- #


def test_ballon_dor_is_rare_but_reachable():
    wins = sum(career.career_summary(play(OPTIMAL, s))["ballon_dor_wins"] for s in range(40))
    assert wins >= 1, "an outstanding career should occasionally win it"
    assert wins <= 12, "it should not be routine"


def test_a_drifting_career_never_wins_the_ballon_dor():
    wins = sum(career.career_summary(play(DRIFT, s))["ballon_dor_wins"] for s in range(20))
    assert wins == 0


@pytest.mark.parametrize("seed", range(4))
def test_european_and_international_records_are_coherent(seed):
    state = play(OPTIMAL, seed)
    for s in state["seasons"]:
        europe = s.get("europe")
        if europe:
            assert europe["competition"] in ("Champions League", "Europa League")
            if europe["won"]:
                assert europe["reached"] == "Winners"
                assert all(r["won"] for r in europe["rounds"])
            assert europe["goals"] >= 0
        intl = s.get("international")
        if intl:
            assert intl["caps"] > 0
            assert intl["goals"] <= intl["caps"] * 4
    assert state["caps"] == sum(
        s["international"]["caps"] for s in state["seasons"] if s.get("international")
    )


def test_europe_is_only_reachable_by_qualifying():
    for seed in range(6):
        for s in play(OPTIMAL, seed)["seasons"]:
            if s.get("europe") is None:
                continue
            assert s["league_position"] <= 6 or "FA Cup" in s["trophies"]


# --------------------------------------------------------------------------- #
# The summary
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("seed", range(5))
def test_summary_totals_match_the_season_log(seed):
    state = play(OPTIMAL, seed)
    summary = career.career_summary(state)
    assert summary["totals"]["goals"] == sum(s["goals"] for s in state["seasons"])
    assert summary["totals"]["apps"] == sum(s["apps"] for s in state["seasons"])
    assert summary["totals"]["seasons"] == len(state["seasons"])
    assert sum(c["years"] for c in summary["clubs"]) == len(state["seasons"])
    assert summary["title"] and summary["verdict"]


def test_verdicts_are_not_all_the_same():
    titles = {career.career_summary(play(OPTIMAL, s))["title"] for s in range(20)}
    assert len(titles) >= 3, f"legacy titles lack variety: {titles}"


def test_a_keeper_career_runs_without_striker_assumptions():
    state = play(OPTIMAL, 3, ratings=KEEPER, position="GK")
    summary = career.career_summary(state)
    assert summary["totals"]["clean_sheets"] > 0
    assert summary["totals"]["goals"] == 0


@pytest.mark.parametrize("seed", range(3))
def test_a_whole_career_is_fast_enough_to_serve(seed):
    import time

    started = time.perf_counter()
    play(OPTIMAL, seed)
    assert time.perf_counter() - started < 2.0
