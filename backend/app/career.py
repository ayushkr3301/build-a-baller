"""Career mode: eighteen to retirement, one decision a summer.

The card you build is not the player you start as -- it is the player you *might
become*. You begin at eighteen roughly fifteen points below it, and closing that
gap is the whole game: you need minutes, you need to perform in them, and you
need to choose the right move each summer. Sit on a bench for money and the gap
never closes. Potential is a ceiling, not a promise.

Everything else -- the league, the cups, Europe, internationals, the Ballon d'Or --
exists to make the decision each summer cost something.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .data.attributes import attr_keys, overall_from
from .data.clubs import CLUB_BY_ID, CLUBS, EFL_CLUBS
from .data.world import EURO_CLUB_BY_ID, EURO_CLUBS, NATION_BY_ID, NATIONS, UEFA_IDS
from .game import club_rank
from .sim import expected_goals, poisson, simulate_season

# --------------------------------------------------------------------------- #
# Tuning
# --------------------------------------------------------------------------- #

START_AGE = 18
START_GAP = 15  # how far below your potential you begin
FIRST_SEASON = 2026

# Growth is mostly a function of age. These are the multipliers on a season's
# worth of development; after 30 they go negative and the decline begins.
AGE_CURVE = {
    18: 1.00, 19: 1.00, 20: 0.95, 21: 0.90, 22: 0.80, 23: 0.70,
    24: 0.58, 25: 0.46, 26: 0.34, 27: 0.22, 28: 0.12, 29: 0.06,
    30: 0.00, 31: -0.25, 32: -0.45, 33: -0.70, 34: -1.00,
    35: -1.35, 36: -1.75, 37: -2.20, 38: -2.70,
}
# Calibrated so that how you play visibly changes where you finish. Above ~2.8
# every strategy maxes out and the summer decision stops meaning anything; below
# ~1.7 nobody develops at all and potential is decorative. See the spread in the
# docstring of tests/test_career.py.
BASE_GROWTH = 2.05
BASE_DECLINE = 2.4

# Attributes that arrive with experience rather than youth, and the ones that
# leave first. A 19-year-old is quick and clueless; a 34-year-old is the reverse.
MENTAL = {"composure", "positioning", "vision", "leadership", "concentration", "set_pieces"}
PHYSICAL = {"pace", "stamina", "agility", "strength", "work_rate"}

RETRAIN_COST = 4  # potential points surrendered by switching role

RETIRE_MIN_AGE = 33
RETIRE_FORCED_AGE = 39


# --------------------------------------------------------------------------- #
# Player state
# --------------------------------------------------------------------------- #


def scale_ratings(
    potential_ratings: dict[str, int], overall: int, potential: int, age: int, position: str
) -> dict[str, int]:
    """Current attributes, derived from the potential card.

    Keeps the shape of the build -- a pacey striker stays pacey -- but tilts it by
    age so a teenager is physically ready and mentally raw, and a veteran has lost
    a yard while knowing exactly where to stand.
    """
    if potential <= 0:
        return dict(potential_ratings)
    base = overall / potential
    youth = max(-1.0, min(1.0, (26 - age) / 8))  # +1 at 18, 0 at 26, -1 at 34

    out: dict[str, int] = {}
    for key, peak in potential_ratings.items():
        factor = base
        if key in MENTAL:
            factor -= 0.10 * max(0.0, youth)  # mental lags in the young
            factor += 0.06 * max(0.0, -youth)  # and lingers in the old
        elif key in PHYSICAL:
            factor += 0.07 * max(0.0, youth)  # legs arrive early
            factor -= 0.12 * max(0.0, -youth)  # and go first
        out[key] = max(30, min(99, round(peak * factor)))
    return out


def _age_factor(age: int) -> float:
    if age in AGE_CURVE:
        return AGE_CURVE[age]
    return -3.0 if age > RETIRE_FORCED_AGE else 1.0


def apply_development(state: dict, season: dict, rng: random.Random) -> dict:
    """Move the player toward -- or away from -- their potential after a season.

    Growth needs three things at once: youth, minutes, and performance. Missing
    any one of them stalls it, which is what makes the summer decision matter.
    """
    age = state["age"]
    potential = state["potential"]
    overall = state["overall"]
    factor = _age_factor(age)

    apps = season["apps"]
    minutes_share = min(1.0, season["minutes"] / 2800)
    # Below about a third of a season you are not developing, you are training.
    minutes_factor = 0.20 + 0.80 * minutes_share

    # Form has to be judged against what this overall already predicts. Match
    # ratings are anchored to ability, so scoring youth on absolute rating meant a
    # 70-rated eighteen-year-old could never post a "good" number and could never
    # grow -- a doom loop. What matters is beating your own level.
    rating = season["avg_rating"] or 6.0
    par_rating = 6.15 + (overall - 75) / 25
    form_factor = max(0.45, min(1.55, 1.0 + (rating - par_rating) * 0.9))

    modifier = state.get("growth_modifier", 1.0)

    if factor > 0:
        room = max(0, potential - overall)
        # Growth slows as the gap closes: the last two points are the hardest.
        closing = 0.35 + 0.65 * min(1.0, room / 12)
        gain = BASE_GROWTH * factor * minutes_factor * form_factor * modifier * closing
        gain *= rng.uniform(0.82, 1.18)
        new_overall = min(potential, overall + gain)
    else:
        # Decline is blunted by playing well and accelerated by not playing.
        cushion = 0.7 if rating >= 7.1 else 1.0
        if apps < 12:
            cushion *= 1.35
        drop = BASE_DECLINE * abs(factor) * cushion * rng.uniform(0.85, 1.15)
        new_overall = overall - drop

    state["overall"] = int(round(max(40, min(potential, new_overall))))
    state["peak_overall"] = max(state.get("peak_overall", 0), state["overall"])
    state["ratings"] = scale_ratings(
        state["potential_ratings"], state["overall"], potential, age + 1, state["position"]
    )
    return state


# --------------------------------------------------------------------------- #
# Clubs
# --------------------------------------------------------------------------- #


def clubs_by_rank() -> list:
    return sorted(CLUBS, key=lambda c: -club_rank(c))


def _club_tier(club_id: str) -> int:
    """0 = giant, 1 = European chaser, 2 = mid-table, 3 = strugglers."""
    order = [c.id for c in clubs_by_rank()]
    index = order.index(club_id) if club_id in order else len(order) - 1
    if index < 4:
        return 0
    if index < 9:
        return 1
    if index < 15:
        return 2
    return 3


def starting_club(overall: int, rng: random.Random) -> str:
    """Where an eighteen-year-old of this ability comes through.

    Deliberately not the best club available: the most interesting careers start
    somewhere that will actually play you.
    """
    ranked = clubs_by_rank()
    if overall >= 74:
        pool = ranked[:8]
    elif overall >= 68:
        pool = ranked[4:14]
    else:
        pool = ranked[10:]
    return rng.choice(pool).id


# --------------------------------------------------------------------------- #
# The summer decision
# --------------------------------------------------------------------------- #


@dataclass
class Option:
    id: str
    title: str
    detail: str
    club_id: str | None = None
    opportunity: float = 1.0
    growth_modifier: float = 1.0
    wage: float = 1.0
    retrain: str | None = None
    loan: bool = False
    tag: str = ""

    def as_dict(self) -> dict:
        club = CLUB_BY_ID.get(self.club_id) if self.club_id else None
        return {
            "id": self.id,
            "title": self.title,
            "detail": self.detail,
            "club_id": self.club_id,
            "club": club.name if club else None,
            "tag": self.tag,
        }


LOAN_TARGETS = [c.id for c in EFL_CLUBS[:8]]

# Recurring options wear thin if they read identically every summer, so the ones
# offered most often carry a small pool of interchangeable phrasings. Picked from a
# summer-seeded rng that never touches the decision rng, so the tuned career balance
# (measured across dozens of seeds in tests/test_career.py) is unchanged by them.
STAY_DETAIL = [
    "Fight for your place where you are. No upheaval, no guarantees.",
    "Another year in familiar colours. Prove you're still first choice.",
    "Re-sign and dig in. The badge already knows your name.",
    "Stay put and let the football do the talking for once.",
]
PAYDAY_DETAIL = [
    "Enormous wages, a smaller club, and the writers deciding you were never that serious.",
    "The bank-breaking offer from a lesser side. Your accountant is delighted; your legacy less so.",
    "Chase the money down the table. Nobody remembers a rich runner-up, but the cheque clears.",
]
LOAN_DETAIL = [
    "Drop a level for a season of guaranteed football. Nothing develops a young player like playing.",
    "A year in the second tier where you'll actually start every week. Go and learn the game.",
    "Leave the reserves behind for real minutes somewhere hungrier. Come back a player.",
]
STEP_UP_DETAIL = [
    "A bigger club, a bigger stage, and a much harder fight for minutes. Sink or swim.",
    "Move up the ladder and back yourself. The football is faster and the patience shorter.",
    "Trade a guaranteed shirt for a shot at the top. Nobody said it would be comfortable.",
]


def decision_options(state: dict, rng: random.Random) -> list[dict]:
    """Three to six options for this summer, tailored to the situation.

    The strategic backbone -- stay, loan, step up, payday, talisman, rotate,
    retrain -- is unchanged and always offered whenever it applies; its club
    targets are still drawn from `rng` in the same order, so the career balance the
    tests pin down is untouched. On top of it sit occasional *event* options, and
    the flavour text of the recurring ones varies, both driven by a separate
    summer-seeded rng so no two summers feel like a copy of the last.
    """
    age = state["age"]
    overall = state["overall"]
    club_id = state["club_id"]
    club = CLUB_BY_ID[club_id]
    tier = _club_tier(club_id)
    last = state["seasons"][-1] if state["seasons"] else None
    played_a_lot = bool(last and last["apps"] >= 22)
    ranked = clubs_by_rank()

    # Independent of `rng`: everything fresh is chosen here so the decision rng that
    # the balance depends on is consumed exactly as it always was.
    flavour = random.Random(f"{state['seed']}:summer:{len(state['seasons'])}")

    options: list[Option] = [
        Option(
            id="stay",
            title=f"Stay at {club.name}",
            detail=flavour.choice(STAY_DETAIL),
            club_id=club_id,
            tag="Steady",
        )
    ]

    # Not playing, and young enough for it to matter.
    if age <= 24 and (not played_a_lot or tier <= 1):
        target = rng.choice(LOAN_TARGETS)
        options.append(
            Option(
                id="loan",
                title="Go out on loan",
                detail=flavour.choice(LOAN_DETAIL),
                club_id=target,
                opportunity=1.45,
                growth_modifier=1.30,
                wage=0.5,
                loan=True,
                tag="Development",
            )
        )

    # Performing well: someone bigger is interested.
    if played_a_lot and last and last["avg_rating"] >= 6.9 and tier > 0:
        better = [c for c in ranked if _club_tier(c.id) < tier]
        if better:
            target = rng.choice(better[: max(3, len(better) // 2)])
            options.append(
                Option(
                    id="step_up",
                    title=f"Push for a move to {target.name}",
                    detail=flavour.choice(STEP_UP_DETAIL),
                    club_id=target.id,
                    opportunity=0.72,
                    growth_modifier=1.12,
                    wage=1.9,
                    tag="Ambition",
                )
            )

    # There is always money somewhere worse.
    poorer = [c for c in ranked if _club_tier(c.id) > tier]
    if poorer:
        target = rng.choice(poorer)
        options.append(
            Option(
                id="payday",
                title=f"Take the money at {target.name}",
                detail=flavour.choice(PAYDAY_DETAIL),
                club_id=target.id,
                opportunity=1.25,
                growth_modifier=0.82,
                wage=2.6,
                tag="Money",
            )
        )

    # Star at a big club: become the guaranteed starter.
    if tier <= 1 and played_a_lot and overall >= 78:
        options.append(
            Option(
                id="talisman",
                title="Demand to be the focal point",
                detail=(
                    "Sign a new deal as the side's main man. Every minute is yours, "
                    "and so is every bit of blame."
                ),
                club_id=club_id,
                opportunity=1.30,
                growth_modifier=1.05,
                wage=1.7,
                tag="Status",
            )
        )

    # Ageing and losing a step: a rotation role prolongs it.
    if age >= 30:
        options.append(
            Option(
                id="rotate",
                title="Accept a rotation role",
                detail=(
                    "Fewer games, fresher legs, and a couple more years at the top "
                    "before the decline really bites."
                ),
                club_id=club_id,
                opportunity=0.62,
                growth_modifier=1.0,
                wage=0.9,
                tag="Longevity",
            )
        )

    # Retraining: a real career pivot, and only sensible before the late twenties.
    if 20 <= age <= 29 and len(state["seasons"]) >= 2:
        target_position = _retrain_target(state["position"])
        options.append(
            Option(
                id="retrain",
                title=f"Retrain as a {POSITION_LABEL[target_position]}",
                detail=(
                    "Convert to a new role. You keep what transfers and rebuild what "
                    "doesn't -- costly now, but it can add years at the other end."
                ),
                club_id=club_id,
                opportunity=0.9,
                growth_modifier=0.85,
                retrain=target_position,
                tag="Reinvention",
            )
        )

    # One or two situational "events" on top, so the menu changes shape season to
    # season rather than showing the same three or four cards forever. New ids the
    # strategy tests never pick, chosen from the summer rng -- pure freshness, no
    # effect on the tuned outcomes.
    events = _event_options(state, flavour, tier, played_a_lot, ranked)
    if events:
        flavour.shuffle(events)
        slots = max(0, 6 - len(options))
        take = min(len(events), slots, flavour.choice([1, 1, 2]))
        options.extend(events[:take])

    state["_options"] = {o.id: o.__dict__ for o in options}
    return [o.as_dict() for o in options]


def _event_options(
    state: dict,
    flavour: random.Random,
    tier: int,
    played_a_lot: bool,
    ranked: list,
) -> list[Option]:
    """The pool of occasional, situation-driven offers for this summer.

    Every one reuses the same mechanics the core options do (a club, an
    opportunity/growth/wage tilt); the value they add is variety of *situation* and
    tone, not new simulation behaviour.
    """
    age = state["age"]
    overall = state["overall"]
    club_id = state["club_id"]
    club = CLUB_BY_ID[club_id]
    last = state["seasons"][-1] if state["seasons"] else None
    seasons = len(state["seasons"])
    start_club_id = state["clubs_played_for"][0] if state.get("clubs_played_for") else club_id

    def pick(pool: list, exclude: set[str]) -> object | None:
        choices = [c for c in pool if c.id not in exclude]
        return flavour.choice(choices) if choices else None

    events: list[Option] = []

    # The armband: a settled senior pro at a club that plays them.
    if seasons >= 2 and played_a_lot and 23 <= age <= 34 and tier <= 2:
        events.append(
            Option(
                id="captain",
                title=f"Take the {club.name} armband",
                detail=(
                    "Lead them out every week. More responsibility, more scrutiny, and "
                    "every result laid at your door."
                ),
                club_id=club_id,
                opportunity=1.18,
                growth_modifier=1.05,
                wage=1.25,
                tag="Status",
            )
        )

    # A giant comes calling to chase the title.
    if played_a_lot and last and last["avg_rating"] >= 7.0 and tier >= 1 and age <= 30:
        target = pick(ranked[:2], {club_id})
        if target:
            events.append(
                Option(
                    id="title_charge",
                    title=f"Chase the title with {target.name}",
                    detail=(
                        "The biggest club in the land wants you. A winner's medal is on "
                        "the table -- if you can force your way into that eleven."
                    ),
                    club_id=target.id,
                    opportunity=0.68,
                    growth_modifier=1.12,
                    wage=2.1,
                    tag="Ambition",
                )
            )

    # Drop down and be the hero of a club fighting the drop.
    if overall >= 74 and age <= 33 and tier <= 2:
        target = pick(ranked[-6:], {club_id})
        if target:
            events.append(
                Option(
                    id="rescue",
                    title=f"Be {target.name}'s star man",
                    detail=(
                        "Join a side scrapping to survive and carry them. Every attack "
                        "runs through you -- so does every post-match camera."
                    ),
                    club_id=target.id,
                    opportunity=1.35,
                    growth_modifier=1.0,
                    wage=1.35,
                    tag="Status",
                )
            )

    # Go home to where it started.
    if seasons >= 4 and age >= 26 and start_club_id != club_id and start_club_id in CLUB_BY_ID:
        home = CLUB_BY_ID[start_club_id]
        events.append(
            Option(
                id="homecoming",
                title=f"Go home to {home.name}",
                detail=(
                    "Return to where it began. The supporters never forgot you, and you "
                    "never quite stopped being one of them."
                ),
                club_id=start_club_id,
                opportunity=1.15,
                growth_modifier=1.0,
                wage=1.1,
                tag="Steady",
            )
        )

    # Something to prove after a poor year.
    if last and last["avg_rating"] < 6.6 and age <= 31:
        events.append(
            Option(
                id="prove_point",
                title="Sign a short deal to prove a point",
                detail=(
                    "One year, everything to prove. Play like your career depends on it "
                    "-- for once it might."
                ),
                club_id=club_id,
                opportunity=1.25,
                growth_modifier=1.08,
                wage=0.85,
                tag="Ambition",
            )
        )

    # A veteran's last adventure.
    if age >= 31 and tier <= 2:
        target = pick(ranked[6:14], {club_id})
        if target:
            events.append(
                Option(
                    id="swansong",
                    title=f"Take a final payday at {target.name}",
                    detail=(
                        "A last big contract somewhere new. One more adventure before the "
                        "boots go up on the wall."
                    ),
                    club_id=target.id,
                    opportunity=1.1,
                    growth_modifier=1.0,
                    wage=1.6,
                    tag="Money",
                )
            )

    return events


POSITION_LABEL = {"ST": "Striker", "MID": "Midfielder", "DEF": "Defender", "GK": "Goalkeeper"}
RETRAIN_MAP = {"ST": "MID", "MID": "DEF", "DEF": "MID", "GK": "DEF"}


def _retrain_target(position: str) -> str:
    return RETRAIN_MAP[position]


def retrain(state: dict, new_position: str, rng: random.Random) -> None:
    """Convert to a new position, carrying across whatever genuinely transfers.

    Positions share very little -- a striker and a midfielder have three of twelve
    criteria in common -- so rebuilding the other nine from raw numbers collapsed
    potential by nine points a switch, and compounded on a second switch until the
    player was unrecognisable. The cost is therefore stated rather than emergent:
    you surrender RETRAIN_COST from your ceiling, once, however many times you move.
    """
    old_ratings = state["potential_ratings"]
    old_potential = state["potential"]
    keys = attr_keys(new_position)

    carried: dict[str, int] = {}
    for key in keys:
        if key in old_ratings:
            carried[key] = old_ratings[key]  # same criterion, straight across
        else:
            # Unfamiliar criterion: a good player is a good player, roughly.
            carried[key] = int(max(40, min(95, old_potential * rng.uniform(0.90, 1.02))))

    target = max(state["overall"], old_potential - RETRAIN_COST)
    raw = overall_from(new_position, carried)
    if raw > 0:
        scale = target / raw
        carried = {k: int(max(40, min(99, round(v * scale)))) for k, v in carried.items()}

    state["position"] = new_position
    state["potential_ratings"] = carried
    # A ceiling below what the player has already reached is incoherent.
    state["potential"] = max(overall_from(new_position, carried), state["overall"])
    state["ratings"] = scale_ratings(
        carried, state["overall"], state["potential"], state["age"], new_position
    )
    state["retrained"] = state.get("retrained", []) + [new_position]


# --------------------------------------------------------------------------- #
# Europe
# --------------------------------------------------------------------------- #

EUROPEAN_ROUNDS = ["Round of 16", "Quarter-Final", "Semi-Final", "Final"]


def european_competition(position: int, cup_won: bool) -> str | None:
    if position <= 4:
        return "Champions League"
    if position <= 6 or cup_won:
        return "Europa League"
    return None


def simulate_europe(
    competition: str,
    club_id: str,
    club_attack: float,
    club_defence: float,
    player: dict,
    rng: random.Random,
) -> dict:
    """A knockout run in Europe, with your player's contribution."""
    strength_penalty = 1.0 if competition == "Champions League" else 0.88
    field = sorted(EURO_CLUBS, key=lambda c: -(c.attack + c.defence))
    pool = field[:18] if competition == "Champions League" else field[14:]

    goals = assists = apps = 0
    rounds: list[dict] = []
    alive = True
    reached = "Group Stage"

    for round_name in EUROPEAN_ROUNDS:
        if not alive:
            break
        opponent = rng.choice(pool)
        opp_att = opponent.attack * strength_penalty
        opp_def = opponent.defence * strength_penalty
        # Two legs, aggregate.
        ours = poisson(expected_goals(club_attack, opp_def, home=True), rng) + poisson(
            expected_goals(club_attack, opp_def, home=False), rng
        )
        theirs = poisson(expected_goals(opp_att, club_defence, home=True), rng) + poisson(
            expected_goals(opp_att, club_defence, home=False), rng
        )
        if round_name == "Final":
            ours = poisson(expected_goals(club_attack, opp_def, home=False), rng)
            theirs = poisson(expected_goals(opp_att, club_defence, home=False), rng)
        if ours == theirs:
            ours += 1 if rng.random() < 0.5 else 0
            theirs += 1 if ours == theirs else 0

        played = rng.random() < 0.86
        mine = mine_a = 0
        if played:
            apps += 1 if round_name == "Final" else 2
            for _ in range(ours):
                if rng.random() < player["goal_share"]:
                    mine += 1
            for _ in range(ours - mine):
                if rng.random() < player["assist_share"]:
                    mine_a += 1
            goals += mine
            assists += mine_a

        won = ours > theirs
        rounds.append(
            {
                "round": round_name,
                "opponent": opponent.name,
                "score": f"{ours}-{theirs}",
                "won": won,
                "goals": mine,
                "assists": mine_a,
            }
        )
        reached = round_name
        alive = won

    return {
        "competition": competition,
        "reached": "Winners" if alive and reached == "Final" else reached,
        "won": alive and reached == "Final",
        "rounds": rounds,
        "goals": goals,
        "assists": assists,
        "apps": apps,
    }


# --------------------------------------------------------------------------- #
# International football
# --------------------------------------------------------------------------- #

TOURNAMENT_ROUNDS = ["Group Stage", "Round of 16", "Quarter-Final", "Semi-Final", "Final"]


def call_up_threshold(nation_strength: int) -> int:
    """How good you must be to get into this national team."""
    return int(nation_strength * 0.86)


def tournament_for_year(year: int) -> str | None:
    """A major tournament every other summer, alternating Euros and World Cup."""
    if year % 4 == 0:
        return "World Cup"
    if year % 4 == 2:
        return "European Championship"
    return None


def simulate_international(
    state: dict, season: dict, year: int, rng: random.Random
) -> dict | None:
    nation = NATION_BY_ID[state["nationality"]]
    overall = state["overall"]
    if overall < call_up_threshold(nation.strength) or season["apps"] < 8:
        return None

    # Qualifiers and friendlies across the year.
    caps = rng.randint(4, 9)
    goals = 0
    for _ in range(caps):
        if rng.random() < state["goal_share"] * 0.9:
            goals += 1

    result: dict = {
        "nation": nation.name,
        "caps": caps,
        "goals": goals,
        "tournament": None,
    }

    competition = tournament_for_year(year)
    if not competition:
        return result

    is_euros = competition == "European Championship"
    if is_euros and nation.confederation != "UEFA":
        return result

    rivals = [
        NATION_BY_ID[i] for i in (UEFA_IDS if is_euros else [n.id for n in NATIONS])
        if i != nation.id
    ] if is_euros else [n for n in NATIONS if n.id != nation.id]

    reached = "Group Stage"
    alive = True
    t_caps = t_goals = 0
    for round_name in TOURNAMENT_ROUNDS:
        if not alive:
            break
        opponent = rng.choice(rivals)
        ours = poisson(expected_goals(nation.strength, opponent.strength, home=False), rng)
        theirs = poisson(expected_goals(opponent.strength, nation.strength, home=False), rng)
        if ours == theirs:
            ours += 1 if rng.random() < 0.5 else 0
            theirs += 1 if ours == theirs else 0
        t_caps += 1
        for _ in range(ours):
            if rng.random() < state["goal_share"]:
                t_goals += 1
        reached = round_name
        alive = ours > theirs

    result["caps"] += t_caps
    result["goals"] += t_goals
    result["tournament"] = {
        "name": competition,
        "reached": "Winners" if alive and reached == "Final" else reached,
        "won": alive and reached == "Final",
        "goals": t_goals,
    }
    return result


# --------------------------------------------------------------------------- #
# Ballon d'Or
# --------------------------------------------------------------------------- #


# The world's best seasons, as a decay curve rather than a bell. A Ballon d'Or
# race is a handful of enormous years and then a long tail, not a normal
# distribution -- modelled as a bell, the field's best was around 95 and an
# ordinary good season beat the entire planet every single year.
# Calibrated against measured season scores: median ~74 lands unranked, the top
# 10% land inside the top fifteen, and only the very best years win it.
BALLON_DOR_BEST = 150.0
BALLON_DOR_DECAY = 63.5
BALLON_DOR_FIELD = 80


def ballon_dor_rank(score: float, rng: random.Random) -> int:
    """Where a season places against a synthetic field of the world's best.

    Redrawn each year, so a monstrous season usually wins and occasionally runs
    into someone having a better one -- which is roughly how it goes.
    """
    rivals = sorted(
        (
            BALLON_DOR_BEST * math.exp(-i / BALLON_DOR_DECAY) * rng.uniform(0.82, 1.18)
            for i in range(BALLON_DOR_FIELD)
        ),
        reverse=True,
    )
    rank = 1
    for value in rivals:
        if value > score:
            rank += 1
        else:
            break
    return rank


def season_score(season: dict, europe: dict | None, intl: dict | None, position: str) -> float:
    goals = season["goals"] + (europe["goals"] if europe else 0)
    assists = season["assists"] + (europe["assists"] if europe else 0)
    if position in ("DEF", "GK"):
        base = season["clean_sheets"] * 2.6 + goals * 2.0 + assists * 1.4
    else:
        base = goals * 2.2 + assists * 1.5
    base += max(0.0, (season["avg_rating"] - 6.6)) * 14
    if season["league_position"] == 1:
        base += 16
    elif season["league_position"] <= 4:
        base += 7
    if europe and europe["won"]:
        base += 20
    elif europe and europe["reached"] in ("Final", "Semi-Final"):
        base += 8
    if intl and intl.get("tournament", {}) and intl["tournament"] and intl["tournament"]["won"]:
        base += 18
    return base


# --------------------------------------------------------------------------- #
# Playing a year
# --------------------------------------------------------------------------- #


def new_career(
    *,
    name: str,
    position: str,
    era: str,
    nationality: str,
    potential_ratings: dict[str, int],
    seed: int,
) -> dict:
    rng = random.Random(f"{seed}:career:start")
    potential = overall_from(position, potential_ratings)
    overall = max(45, potential - START_GAP)
    club_id = starting_club(overall, rng)
    return {
        "name": name,
        "position": position,
        "starting_position": position,
        "era": era,
        "nationality": nationality,
        "seed": seed,
        "potential": potential,
        "potential_ratings": potential_ratings,
        "overall": overall,
        "peak_overall": overall,
        "ratings": scale_ratings(potential_ratings, overall, potential, START_AGE, position),
        "age": START_AGE,
        "year": FIRST_SEASON,
        "club_id": club_id,
        "clubs_played_for": [club_id],
        "seasons": [],
        "honours": [],
        "caps": 0,
        "international_goals": 0,
        "tournaments_won": [],
        "ballon_dor": [],
        "earnings": 0.0,
        "retired": False,
        "opportunity": 1.0,
        "growth_modifier": 1.0,
        "wage_level": 1.0,
        "goal_share": 0.0,
        "assist_share": 0.0,
        "retrained": [],
    }


def play_year(state: dict, option_id: str, rng: random.Random) -> dict:
    """Apply the summer decision, play the season, then age the player."""
    from .sim import assist_share, goal_share

    options = state.get("_options") or {}
    chosen = options.get(option_id)
    if chosen is None:
        chosen = {"id": "stay", "club_id": state["club_id"], "opportunity": 1.0,
                  "growth_modifier": 1.0, "wage": 1.0, "retrain": None, "title": "Stay"}

    if chosen.get("retrain"):
        retrain(state, chosen["retrain"], rng)

    on_loan = bool(chosen.get("loan"))
    parent_club = state["club_id"]
    if chosen.get("club_id") and chosen["club_id"] != state["club_id"]:
        state["club_id"] = chosen["club_id"]
        if chosen["club_id"] not in state["clubs_played_for"]:
            state["clubs_played_for"].append(chosen["club_id"])

    state["opportunity"] = chosen.get("opportunity", 1.0)
    state["growth_modifier"] = chosen.get("growth_modifier", 1.0)
    state["wage_level"] = chosen.get("wage", 1.0)
    state["last_decision"] = chosen.get("title", "Stay")

    # A loan to an EFL side isn't in the Premier League table, so the season is
    # played against a domestic club of equivalent standing instead.
    club_id = state["club_id"]
    simulated_club = club_id if club_id in CLUB_BY_ID else _nearest_pl_club(club_id)

    year = state["year"]
    result = simulate_season(
        position=state["position"],
        overall=state["overall"],
        ratings=state["ratings"],
        club_id=simulated_club,
        player_name=state["name"],
        seed=state["seed"] + year * 7919,
        opportunity=state["opportunity"],
    )

    state["goal_share"] = goal_share(state["position"], state["ratings"])
    state["assist_share"] = assist_share(state["position"], state["ratings"])

    player = result.player
    season = {
        "year": year,
        "age": state["age"],
        "club_id": club_id,
        "club": (CLUB_BY_ID.get(club_id) or _efl_name(club_id)).name
        if club_id in CLUB_BY_ID
        else _efl_name(club_id),
        "on_loan": club_id not in CLUB_BY_ID,
        "decision": state["last_decision"],
        "league_position": result.club["position"],
        "points": result.club["points"],
        "apps": player["apps"],
        "minutes": player["minutes"],
        "goals": player["goals"],
        "assists": player["assists"],
        "clean_sheets": player["clean_sheets"],
        "avg_rating": player["avg_rating"],
        "grade": result.grade,
        "overall_before": state["overall"],
        "trophies": [],
    }

    if result.cup["won"]:
        season["trophies"].append("FA Cup")
    if result.club["position"] == 1:
        season["trophies"].append("Premier League")

    # Europe, based on where the club finished.
    competition = european_competition(result.club["position"], result.cup["won"])
    europe = None
    if competition and not season["on_loan"]:
        club = CLUB_BY_ID[simulated_club]
        europe = simulate_europe(
            competition,
            simulated_club,
            club.attack,
            club.defence,
            {"goal_share": state["goal_share"], "assist_share": state["assist_share"]},
            rng,
        )
        if europe["won"]:
            season["trophies"].append(competition)
    season["europe"] = europe

    intl = simulate_international(state, season, year, rng)
    season["international"] = intl
    if intl:
        state["caps"] += intl["caps"]
        state["international_goals"] += intl["goals"]
        if intl.get("tournament") and intl["tournament"]["won"]:
            state["tournaments_won"].append(f"{intl['tournament']['name']} {year}")
            season["trophies"].append(intl["tournament"]["name"])

    score = season_score(season, europe, intl, state["position"])
    rank = ballon_dor_rank(score, rng)
    season["ballon_dor_rank"] = rank
    if rank <= 30:
        state["ballon_dor"].append({"year": year, "rank": rank})

    for trophy in season["trophies"]:
        state["honours"].append({"year": year, "trophy": trophy, "club": season["club"]})

    state["earnings"] += 2.6 * state["wage_level"] * (0.5 + state["overall"] / 100)

    apply_development(state, season, rng)
    season["overall_after"] = state["overall"]
    state["seasons"].append(season)

    # A loan is for one season. Without sending the player home, next summer's
    # options would look up an EFL side in the Premier League table and raise.
    if on_loan:
        state["club_id"] = parent_club

    state["age"] += 1
    state["year"] += 1
    state["retired"] = should_retire(state, rng)
    return season


def _nearest_pl_club(club_id: str) -> str:
    """Map a loan club to the Premier League side closest to its actual level.

    A loan spell still needs a real league to be played in, so the EFL side is
    stood in for by whichever top-flight club it most resembles.
    """
    target = next((c for c in EFL_CLUBS if c.id == club_id), None)
    if target is None:
        return clubs_by_rank()[-1].id
    level = (target.attack + target.defence) / 2
    return min(CLUBS, key=lambda c: abs((c.attack + c.defence) / 2 - level)).id


def _efl_name(club_id: str) -> str:
    for club in EFL_CLUBS:
        if club.id == club_id:
            return club.name
    return club_id.upper()


def should_retire(state: dict, rng: random.Random) -> bool:
    age = state["age"]
    if age >= RETIRE_FORCED_AGE:
        return True
    if age < RETIRE_MIN_AGE:
        return False
    last = state["seasons"][-1]
    # Declining, barely playing, or simply done.
    pressure = (age - RETIRE_MIN_AGE) * 0.16
    if state["overall"] < 66:
        pressure += 0.30
    if last["apps"] < 12:
        pressure += 0.25
    return rng.random() < pressure


# --------------------------------------------------------------------------- #
# The verdict
# --------------------------------------------------------------------------- #


def career_summary(state: dict) -> dict:
    seasons = state["seasons"]
    total = {
        "apps": sum(s["apps"] for s in seasons),
        "goals": sum(s["goals"] for s in seasons),
        "assists": sum(s["assists"] for s in seasons),
        "clean_sheets": sum(s["clean_sheets"] for s in seasons),
        "minutes": sum(s["minutes"] for s in seasons),
        "seasons": len(seasons),
    }
    rated = [s["avg_rating"] for s in seasons if s["avg_rating"]]
    total["avg_rating"] = round(sum(rated) / len(rated), 2) if rated else 0.0
    total["europe_goals"] = sum(s["europe"]["goals"] for s in seasons if s.get("europe"))

    honours: dict[str, int] = {}
    for entry in state["honours"]:
        honours[entry["trophy"]] = honours.get(entry["trophy"], 0) + 1

    # Time at each club, which is what separates a legend from a journeyman.
    club_years: dict[str, int] = {}
    for s in seasons:
        club_years[s["club"]] = club_years.get(s["club"], 0) + 1
    longest_club, longest_years = max(club_years.items(), key=lambda kv: kv[1]) if club_years else ("-", 0)

    golden = [b for b in state["ballon_dor"] if b["rank"] == 1]
    podiums = [b for b in state["ballon_dor"] if b["rank"] <= 3]

    verdict, title = _legacy(state, total, honours, longest_years, len(club_years), golden)

    return {
        "totals": total,
        "honours": [{"trophy": k, "count": v} for k, v in sorted(honours.items(), key=lambda kv: -kv[1])],
        "clubs": [{"club": k, "years": v} for k, v in sorted(club_years.items(), key=lambda kv: -kv[1])],
        "longest_club": longest_club,
        "longest_years": longest_years,
        "peak_overall": state["peak_overall"],
        "potential": state["potential"],
        "reached_potential": state["peak_overall"] >= state["potential"] - 1,
        "caps": state["caps"],
        "international_goals": state["international_goals"],
        "tournaments_won": state["tournaments_won"],
        "ballon_dor_wins": len(golden),
        "ballon_dor_podiums": len(podiums),
        "ballon_dor": state["ballon_dor"],
        "earnings": round(state["earnings"], 1),
        "retired_at": state["age"],
        "title": title,
        "verdict": verdict,
        "retrained": state.get("retrained", []),
    }


def _legacy(state, total, honours, longest_years, club_count, golden) -> tuple[str, str]:
    """A one-line judgement on the whole career."""
    trophies = sum(honours.values())
    peak = state["peak_overall"]
    gap = state["potential"] - peak

    if golden:
        return (
            "One of the greatest careers the league has seen. The kind of player "
            "children are named after.",
            "Generational",
        )
    if trophies >= 8 and longest_years >= 6:
        return (
            f"A one-club great: {longest_years} years, {trophies} trophies, and a "
            "statue's worth of goodwill.",
            "Club Legend",
        )
    if trophies >= 6:
        return (
            "A serial winner who was always where the trophies were, even if the "
            "shirt kept changing.",
            "Serial Winner",
        )
    if club_count >= 6:
        return (
            f"{club_count} clubs in {total['seasons']} seasons. Always wanted, never "
            "quite settled.",
            "Journeyman",
        )
    if gap >= 12:
        return (
            f"Peaked {gap} short of what the talent promised. Everyone who saw it "
            "still argues about why.",
            "What Might Have Been",
        )
    if peak >= 85:
        return (
            "A genuinely excellent player who gave a decade of very high-level "
            "football.",
            "Elite",
        )
    if total["seasons"] >= 14:
        return (
            f"{total['seasons']} seasons of honest professional football. Not a star, "
            "but every squad needs one.",
            "The Professional",
        )
    return ("A solid career at a good level, cut a little shorter than hoped.", "Solid")
