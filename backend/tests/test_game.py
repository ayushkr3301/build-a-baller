import random

import pytest

from app.data.attributes import ATTRIBUTES, N_CRITERIA, N_SPINS, attr_keys, overall_from
from app.data.clubs import CLUBS, DISPLAY_CLUB_BY_ID
from app.data.players_legends import POOLS as LEGEND_ROWS
from app.game import (
    Board,
    POOLS,
    draft_odds,
    draft_strength,
    draw_player,
    get_pool,
    rosters,
    tier_weights,
)

LEGEND_FLOOR = 80


def test_every_position_has_n_weighted_criteria():
    for pos, attrs in ATTRIBUTES.items():
        assert len(attrs) == N_CRITERIA
        assert sum(a.weight for a in attrs) == pytest.approx(1.0)
        assert len({a.key for a in attrs}) == N_CRITERIA, f"{pos} has duplicate keys"
    assert N_SPINS == N_CRITERIA + 1


@pytest.mark.parametrize("era,position", list(POOLS.keys()))
def test_pool_is_well_formed(era, position):
    pool = get_pool(era, position)
    assert len(pool) >= 30
    names = [p.name for p in pool]
    assert len(names) == len(set(names)), "duplicate player in pool"
    for p in pool:
        assert set(p.ratings) == set(attr_keys(position))
        assert all(0 <= v <= 100 for v in p.ratings.values())
        assert p.tier in (1, 2, 3, 4)
        assert p.club_id in DISPLAY_CLUB_BY_ID
        assert 0 < p.overall <= 100


def test_icon_odds_escalate_across_a_run():
    first = tier_weights(0)
    last = tier_weights(N_SPINS - 1)
    share = lambda w: w[1] / sum(w.values())  # noqa: E731
    assert share(last) > share(first)
    # ...but even on the last spin an Icon is still the exception, not the plan,
    # so hoarding skips early is a gamble rather than the obvious opening.
    assert share(first) > 0.01
    assert share(last) < 0.15


def test_spin_never_repeats_a_player_within_a_run():
    rng = random.Random(1)
    seen: set[str] = set()
    for i in range(N_SPINS):
        p = draw_player("current", "MID", i, rng, exclude_ids=seen)
        assert p.id not in seen
        seen.add(p.id)


def test_board_locks_slots_and_refuses_overwrites():
    board = Board(position="ST")
    player = get_pool("legends", "ST")[0]
    assert board.filled == 0
    board.take("finishing", player)
    assert board.filled == 1
    assert board.slots["finishing"] == player.ratings["finishing"]
    with pytest.raises(ValueError):
        board.take("finishing", player)
    with pytest.raises(ValueError):
        board.take("not_a_real_attribute", player)


def test_full_board_scores_exactly_like_the_source_player():
    board = Board(position="DEF")
    player = get_pool("legends", "DEF")[0]
    for key in attr_keys("DEF"):
        board.take(key, player)
    assert board.complete
    assert board.overall == player.overall


def test_unfilled_slots_count_as_zero():
    """Skipping twice leaves a hole, and the hole has to hurt."""
    board = Board(position="ST")
    player = get_pool("legends", "ST")[0]
    for key in attr_keys("ST")[:-1]:
        board.take(key, player)
    assert not board.complete
    assert board.overall < player.overall


@pytest.mark.parametrize("position", list(LEGEND_ROWS))
def test_every_legend_clears_the_eighty_floor(position):
    """The legends pool is club greats only -- an 80 overall is the entry fee."""
    keys = attr_keys(position)
    below = [
        (name, overall_from(position, dict(zip(keys, values))))
        for name, _club, _tier, values in LEGEND_ROWS[position]
        if overall_from(position, dict(zip(keys, values))) < LEGEND_FLOOR
    ]
    assert not below, f"legends under {LEGEND_FLOOR}: {below}"


def test_legends_are_spread_across_many_clubs_without_quotas():
    """Clubs are not given equal billing -- United carry a dozen, Coventry carry one."""
    clubs = {p.club_id for era, pos in POOLS for p in POOLS[(era, pos)] if era == "legends"}
    assert len(clubs) >= 20
    counts = {}
    for (era, _pos), players in POOLS.items():
        if era != "legends":
            continue
        for p in players:
            counts[p.club_id] = counts.get(p.club_id, 0) + 1
    assert max(counts.values()) > 5 * min(counts.values()), "distribution looks artificially even"


def test_rosters_cover_every_player_for_the_spin_reel():
    data = rosters()
    for (era, position), players in POOLS.items():
        by_club = data[era][position]
        assert sum(len(v) for v in by_club.values()) == len(players)
        for p in players:
            assert p.name in by_club[p.club_id]


def test_draft_is_graded_on_a_curve_within_each_era():
    """A legend build of 87 is mid-table among legends; a current 87 is elite."""
    assert draft_strength(87, "legends") < draft_strength(87, "current")
    # ...and each era still spans the full range of clubs.
    for era in ("current", "legends"):
        lo, hi = draft_strength(60, era), draft_strength(99, era)
        assert lo < 65 and hi > 87

    def top_chance(overall: int, era: str) -> float:
        return dict(draft_odds(overall, era=era))["mci"]

    # Without the curve, every legend build would be drafted to a giant.
    assert top_chance(87, "legends") < top_chance(87, "current")
    assert top_chance(92, "legends") > top_chance(83, "legends")


def test_draft_odds_are_a_distribution_and_respect_vetoes():
    odds = draft_odds(85)
    assert sum(p for _, p in odds) == pytest.approx(1.0)
    assert len(odds) == len(CLUBS)

    vetoed = {"mci", "liv", "ars"}
    odds = draft_odds(90, vetoed)
    assert sum(p for _, p in odds) == pytest.approx(1.0)
    assert not (vetoed & {cid for cid, _ in odds})


def test_better_builds_are_drafted_to_bigger_clubs():
    def chance(overall: int, club_id: str) -> float:
        return dict(draft_odds(overall))[club_id]

    assert chance(88, "mci") > chance(74, "mci")
    assert chance(74, "bur") > chance(88, "bur")
    # a great build can still, rarely, end up somewhere grim
    assert chance(88, "bur") > 0


def test_overall_is_position_weighted_not_a_flat_mean():
    keys = attr_keys("ST")
    flat = dict.fromkeys(keys, 80)
    assert overall_from("ST", flat) == 80
    # finishing is weighted heavier than heading for a striker
    heavy_finish = {**flat, "finishing": 100}
    heavy_head = {**flat, "heading": 100}
    assert overall_from("ST", heavy_finish) > overall_from("ST", heavy_head)
