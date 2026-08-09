"""Full-season simulation: 38 Premier League matches for all 20 clubs, plus the FA Cup.

Every league fixture in the division is played, so the table your club finishes in is
a real table. Your player's own numbers are derived from the matches their club
actually played -- goals are drawn from goals the team actually scored, so the
player's line and the club's line can never contradict each other.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .data import players_current
from .data.attributes import attr_keys
from .data.clubs import CLUBS, CLUB_BY_ID, CUP_CLUB_BY_ID, EFL_CLUBS

# --------------------------------------------------------------------------- #
# Match model
# --------------------------------------------------------------------------- #

BASE_XG = 1.30
ELASTICITY = 2.2
HOME_ADVANTAGE = 1.14
MAX_XG = 4.6

# League averages, used to judge a player against the club they were drafted into
# rather than against an Arsenal-shaped ideal.
LEAGUE_MEAN_ATTACK = sum(c.attack for c in CLUBS) / len(CLUBS)
LEAGUE_MEAN_DEFENCE = sum(c.defence for c in CLUBS) / len(CLUBS)

# Par output per position: (intercept, per-overall-point, club-strength exponent).
# Least-squares fitted against this simulator over overalls 60-95 x six clubs, so
# actual/expected == 1.0 is a genuinely average season for that build at that club.
# Re-fit these if you change the match model or the impact constants.
EXPECTATION_FIT = {
    "ST": (9.04, 0.532, 1.65),
    "MID": (9.33, 0.424, 2.00),
    "DEF": (5.73, 0.194, 2.55),
    "GK": (4.84, 0.151, 2.35),
}

MONTHS = [
    "Aug", "Aug", "Aug", "Sep", "Sep", "Sep", "Sep", "Oct", "Oct", "Oct",
    "Nov", "Nov", "Nov", "Nov", "Dec", "Dec", "Dec", "Dec", "Dec", "Jan",
    "Jan", "Jan", "Feb", "Feb", "Feb", "Feb", "Mar", "Mar", "Mar", "Apr",
    "Apr", "Apr", "Apr", "Apr", "May", "May", "May", "May",
]


def expected_goals(attack: float, defence: float, home: bool) -> float:
    ratio = max(attack, 1.0) / max(defence, 1.0)
    xg = BASE_XG * (ratio**ELASTICITY)
    if home:
        xg *= HOME_ADVANTAGE
    return min(xg, MAX_XG)


def poisson(lam: float, rng: random.Random) -> int:
    """Knuth's method -- lam is always small here so the loop is cheap."""
    limit = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1
        if k > 12:
            return k


# --------------------------------------------------------------------------- #
# Your player's effect on their new club
# --------------------------------------------------------------------------- #

# How your rating is split between lifting the attack and shoring up the defence.
IMPACT_SPLIT = {
    "ST": (1.0, 0.0),
    "MID": (0.6, 0.4),
    "DEF": (0.0, 1.0),
    "GK": (0.0, 1.0),
}
IMPACT_FACTOR = 0.25
IMPACT_MIN, IMPACT_MAX = -6.0, 8.0


def club_with_player(club, position: str, overall: int) -> tuple[float, float]:
    """Return (attack, defence) for the club once your player has signed."""
    att_share, def_share = IMPACT_SPLIT[position]
    att_delta = max(IMPACT_MIN, min(IMPACT_MAX, (overall - club.attack) * IMPACT_FACTOR))
    def_delta = max(IMPACT_MIN, min(IMPACT_MAX, (overall - club.defence) * IMPACT_FACTOR))
    return (club.attack + att_delta * att_share, club.defence + def_delta * def_share)


# --------------------------------------------------------------------------- #
# How much of the team's output runs through your player
# --------------------------------------------------------------------------- #


def _weighted(ratings: dict[str, int], spec: dict[str, float]) -> float:
    return sum(ratings.get(k, 0) * w for k, w in spec.items()) / 100.0


def goal_share(position: str, r: dict[str, int]) -> float:
    if position == "ST":
        s = _weighted(r, {"finishing": 0.40, "positioning": 0.30, "composure": 0.15, "heading": 0.15})
        return 0.10 + 0.35 * (s**1.6)
    if position == "MID":
        s = _weighted(r, {"long_shots": 0.45, "set_pieces": 0.25, "dribbling": 0.15, "passing": 0.15})
        return 0.04 + 0.20 * (s**1.6)
    if position == "DEF":
        s = _weighted(r, {"heading": 0.70, "strength": 0.30})
        return 0.01 + 0.06 * (s**1.6)
    return 0.0


def assist_share(position: str, r: dict[str, int]) -> float:
    if position == "ST":
        s = _weighted(r, {"linkup": 0.70, "dribbling": 0.30})
        return 0.05 + 0.20 * (s**1.6)
    if position == "MID":
        s = _weighted(r, {"vision": 0.45, "passing": 0.30, "set_pieces": 0.25})
        return 0.08 + 0.32 * (s**1.6)
    if position == "DEF":
        s = _weighted(r, {"passing": 0.75, "pace": 0.25})
        return 0.02 + 0.13 * (s**1.6)
    s = _weighted(r, {"distribution": 1.0})
    return 0.004 * s


def card_risk(position: str, r: dict[str, int]) -> float:
    if position == "DEF":
        return 0.06 + 0.10 * _weighted(r, {"aggression": 0.7, "tackling": 0.3})
    if position == "MID":
        return 0.05 + 0.09 * _weighted(r, {"tackling": 1.0})
    if position == "GK":
        return 0.012
    return 0.05


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def build_fixtures(club_ids: list[str], rng: random.Random) -> list[list[tuple[str, str]]]:
    """Double round-robin: 38 matchdays for 20 clubs.

    The circle method fixes the pairings; venues are then assigned greedily rather
    than by index parity. Parity looks like it alternates but doesn't -- a club's
    position in the rotation shifts by one each round, so its parity barely changes
    and you end up with clubs playing nineteen straight matches at home.
    """
    ids = list(club_ids)
    rng.shuffle(ids)
    n = len(ids)

    rotation = ids[:]
    pairings: list[list[tuple[str, str]]] = []
    for _ in range(n - 1):
        pairings.append([(rotation[i], rotation[n - 1 - i]) for i in range(n // 2)])
        rotation = [rotation[0]] + [rotation[-1]] + rotation[1:-1]

    home_count = dict.fromkeys(ids, 0)
    last: dict[str, str | None] = dict.fromkeys(ids, None)
    streak = dict.fromkeys(ids, 0)

    def penalty(team: str) -> int:
        """How bad a choice this team is for the home slot. Lower wins."""
        p = home_count[team] * 2
        if last[team] == "H":
            p += streak[team] * 2
        return p

    rounds: list[list[tuple[str, str]]] = []
    for pairs in pairings:
        rnd: list[tuple[str, str]] = []
        for a, b in pairs:
            pa, pb = penalty(a), penalty(b)
            if pa < pb or (pa == pb and rng.random() < 0.5):
                home, away = a, b
            else:
                home, away = b, a
            rnd.append((home, away))
            home_count[home] += 1
            for team, mark in ((home, "H"), (away, "A")):
                streak[team] = streak[team] + 1 if last[team] == mark else 1
                last[team] = mark
        rounds.append(rnd)

    # Second half: same pairings, venues reversed, so everyone ends 19 home / 19 away
    # and each club's second-half venue run is the inverse of its first.
    rounds += [[(away, home) for home, away in rnd] for rnd in rounds]
    return rounds


# --------------------------------------------------------------------------- #
# League table
# --------------------------------------------------------------------------- #


@dataclass
class Row:
    club_id: str
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    gf: int = 0
    ga: int = 0

    @property
    def points(self) -> int:
        return self.won * 3 + self.drawn

    @property
    def gd(self) -> int:
        return self.gf - self.ga

    def record(self, scored: int, conceded: int) -> None:
        self.played += 1
        self.gf += scored
        self.ga += conceded
        if scored > conceded:
            self.won += 1
        elif scored == conceded:
            self.drawn += 1
        else:
            self.lost += 1


def sort_table(rows: dict[str, Row]) -> list[Row]:
    return sorted(rows.values(), key=lambda r: (-r.points, -r.gd, -r.gf, CLUB_BY_ID[r.club_id].name))


# --------------------------------------------------------------------------- #
# League-wide supporting cast, so the awards mean something
# --------------------------------------------------------------------------- #


def _squad_scorers() -> dict[str, list[tuple[str, float, float]]]:
    """(name, goal weight, assist weight) for real 2025/26 players, grouped by club."""
    by_club: dict[str, list[tuple[str, float, float]]] = {c.id: [] for c in CLUBS}
    for name, club_id, _tier, values in players_current.POOLS["ST"]:
        if club_id not in by_club:
            continue
        r = dict(zip(attr_keys("ST"), values))
        by_club[club_id].append((name, goal_share("ST", r), assist_share("ST", r)))
    for name, club_id, _tier, values in players_current.POOLS["MID"]:
        if club_id not in by_club:
            continue
        r = dict(zip(attr_keys("MID"), values))
        by_club[club_id].append((name, goal_share("MID", r), assist_share("MID", r) * 0.9))
    for name, club_id, _tier, values in players_current.POOLS["DEF"]:
        if club_id not in by_club:
            continue
        r = dict(zip(attr_keys("DEF"), values))
        by_club[club_id].append((name, goal_share("DEF", r), assist_share("DEF", r)))
    return by_club


SQUAD_SCORERS = _squad_scorers()


def _first_choice_keepers() -> dict[str, str]:
    best: dict[str, tuple[str, int]] = {}
    keys = attr_keys("GK")
    for name, club_id, _tier, values in players_current.POOLS["GK"]:
        if club_id not in CLUB_BY_ID:
            continue
        rating = sum(dict(zip(keys, values))[k] for k in keys)
        if club_id not in best or rating > best[club_id][1]:
            best[club_id] = (name, rating)
    return {cid: name for cid, (name, _) in best.items()}


CLUB_KEEPERS = _first_choice_keepers()


# --------------------------------------------------------------------------- #
# The simulation
# --------------------------------------------------------------------------- #


@dataclass
class PlayerMatch:
    matchday: int
    month: str
    opponent: str
    opponent_short: str
    home: bool
    scored: int
    conceded: int
    result: str
    status: str  # played | bench | injured | suspended
    minutes: int
    started: bool = False
    goals: int = 0
    assists: int = 0
    clean_sheet: bool = False
    saves: int = 0
    yellow: bool = False
    red: bool = False
    rating: float = 0.0
    motm: bool = False


@dataclass
class SeasonResult:
    table: list[dict]
    player: dict
    club: dict
    matches: list[dict]
    cup: dict
    awards: list[dict]
    monthly: list[dict]
    headlines: list[str]
    grade: str
    verdict: str
    top_scorers: list[dict] = field(default_factory=list)
    top_assists: list[dict] = field(default_factory=list)


def simulate_season(
    *,
    position: str,
    overall: int,
    ratings: dict[str, int],
    club_id: str,
    player_name: str,
    seed: int,
    opportunity: float = 1.0,
) -> SeasonResult:
    """Play a full season.

    `opportunity` scales how often the player starts, which is how career mode
    expresses the difference between a loan for minutes and a big-money move to
    a bench role. 1.0 is the ordinary case.
    """
    rng = random.Random(seed)
    my_club = CLUB_BY_ID[club_id]

    strengths: dict[str, tuple[float, float]] = {
        c.id: (float(c.attack), float(c.defence)) for c in CLUBS
    }
    strengths[club_id] = club_with_player(my_club, position, overall)

    fixtures = build_fixtures([c.id for c in CLUBS], rng)
    rows = {c.id: Row(c.id) for c in CLUBS}

    g_share = goal_share(position, ratings)
    a_share = assist_share(position, ratings)
    yellow_rate = card_risk(position, ratings)

    my_matches: list[PlayerMatch] = []
    injured_until = -1
    suspended_for = 0
    yellows_total = 0

    for matchday, round_fixtures in enumerate(fixtures, start=1):
        for home_id, away_id in round_fixtures:
            h_att, h_def = strengths[home_id]
            a_att, a_def = strengths[away_id]
            hg = poisson(expected_goals(h_att, a_def, home=True), rng)
            ag = poisson(expected_goals(a_att, h_def, home=False), rng)
            rows[home_id].record(hg, ag)
            rows[away_id].record(ag, hg)

            if club_id not in (home_id, away_id):
                continue

            is_home = home_id == club_id
            scored, conceded = (hg, ag) if is_home else (ag, hg)
            opponent = CLUB_BY_ID[away_id if is_home else home_id]
            result = "W" if scored > conceded else ("D" if scored == conceded else "L")

            pm = PlayerMatch(
                matchday=matchday,
                month=MONTHS[matchday - 1],
                opponent=opponent.name,
                opponent_short=opponent.short,
                home=is_home,
                scored=scored,
                conceded=conceded,
                result=result,
                status="played",
                minutes=0,
            )

            if matchday <= injured_until:
                pm.status = "injured"
            elif suspended_for > 0:
                pm.status = "suspended"
                suspended_for -= 1
            else:
                _play_match(
                    pm, position, overall, ratings, g_share, a_share, yellow_rate, rng,
                    opportunity,
                )
                if pm.yellow:
                    yellows_total += 1
                    if yellows_total % 5 == 0:
                        suspended_for = 1
                if pm.red:
                    suspended_for = max(suspended_for, 3)
                if pm.status == "played" and rng.random() < 0.014:
                    injured_until = matchday + rng.randint(2, 8)

            my_matches.append(pm)

    _award_motm(my_matches)

    table = sort_table(rows)
    positions = {row.club_id: i + 1 for i, row in enumerate(table)}
    my_row = rows[club_id]
    my_position = positions[club_id]

    cup = _simulate_cup(strengths, club_id, position, overall, ratings, g_share, a_share, rng)

    league_goals = sum(m.goals for m in my_matches)
    league_assists = sum(m.assists for m in my_matches)
    scorers, assisters = _league_awards(
        rows, player_name, club_id, league_goals, league_assists, position, rng
    )
    keeper_board = _golden_glove(rows, table, player_name, club_id, position, my_matches, rng)

    player_summary = _summarise(
        my_matches, cup, player_name, position, overall, my_row, my_position
    )
    awards = _build_awards(
        scorers, assisters, keeper_board, player_summary, player_name, table, positions
    )
    monthly = _monthly_breakdown(my_matches)
    grade, verdict, headlines = _verdict(
        player_summary, position, overall, my_club, my_position, my_row, cup, awards, player_name
    )

    return SeasonResult(
        table=[
            {
                "position": i + 1,
                "club_id": r.club_id,
                "club": CLUB_BY_ID[r.club_id].name,
                "short": CLUB_BY_ID[r.club_id].short,
                "played": r.played,
                "won": r.won,
                "drawn": r.drawn,
                "lost": r.lost,
                "gf": r.gf,
                "ga": r.ga,
                "gd": r.gd,
                "points": r.points,
                "is_you": r.club_id == club_id,
            }
            for i, r in enumerate(table)
        ],
        player=player_summary,
        club={
            "id": my_club.id,
            "name": my_club.name,
            "short": my_club.short,
            "primary": my_club.primary,
            "secondary": my_club.secondary,
            "position": my_position,
            "points": my_row.points,
            "record": f"{my_row.won}W {my_row.drawn}D {my_row.lost}L",
            "gf": my_row.gf,
            "ga": my_row.ga,
            "qualification": _qualification(my_position, cup),
        },
        matches=[_match_dict(m) for m in my_matches],
        cup=cup,
        awards=awards,
        monthly=monthly,
        headlines=headlines,
        grade=grade,
        verdict=verdict,
        top_scorers=leaderboard(scorers),
        top_assists=leaderboard(assisters),
    )


def _play_match(
    pm: PlayerMatch,
    position: str,
    overall: int,
    ratings: dict[str, int],
    g_share: float,
    a_share: float,
    yellow_rate: float,
    rng: random.Random,
    opportunity: float = 1.0,
) -> None:
    # Better players start more often; opportunity is career mode's thumb on the
    # scale for loans, bench roles and being a teenager at a huge club.
    start_chance = (0.72 + min(0.26, max(0.0, (overall - 68) / 100))) * opportunity
    start_chance = max(0.04, min(0.98, start_chance))
    if rng.random() > start_chance:
        pm.status = "bench"
        pm.minutes = rng.choice([0, 0, 8, 15, 22, 30])
        if pm.minutes == 0:
            pm.rating = 0.0
            return
    else:
        pm.started = True
        pm.minutes = 90 if rng.random() > 0.22 else rng.randint(58, 89)

    share_scale = pm.minutes / 90

    for _ in range(pm.scored):
        if rng.random() < g_share * share_scale:
            pm.goals += 1
    remaining = pm.scored - pm.goals
    for _ in range(remaining):
        if rng.random() < a_share * share_scale:
            pm.assists += 1

    if position in ("DEF", "GK"):
        pm.clean_sheet = pm.conceded == 0 and pm.minutes >= 80

    if position == "GK":
        shots_faced = max(pm.conceded, poisson(2.6 + pm.conceded * 1.4, rng))
        pm.saves = max(0, shots_faced - pm.conceded)

    if rng.random() < yellow_rate * share_scale:
        pm.yellow = True
    if rng.random() < 0.006 * share_scale:
        pm.red = True

    pm.rating = _rate(pm, position, overall, rng)


def _rate(pm: PlayerMatch, position: str, overall: int, rng: random.Random) -> float:
    r = 6.0 + (overall - 75) / 25
    r += 0.9 * pm.goals + 0.5 * pm.assists
    if position in ("DEF", "GK"):
        if pm.clean_sheet:
            r += 0.45
        elif pm.conceded >= 3:
            r -= 0.35
    if position == "GK":
        r += min(0.6, pm.saves * 0.12)
    r += {"W": 0.28, "D": 0.0, "L": -0.22}[pm.result]
    if pm.yellow:
        r -= 0.12
    if pm.red:
        r -= 0.9
    r += rng.gauss(0, 0.42)
    return round(max(4.0, min(10.0, r)), 1)


def _award_motm(matches: list[PlayerMatch]) -> None:
    for m in matches:
        if m.minutes >= 60 and m.rating >= 8.3 and m.result != "L":
            m.motm = True


def _match_dict(m: PlayerMatch) -> dict:
    return {
        "matchday": m.matchday,
        "month": m.month,
        "opponent": m.opponent,
        "opponent_short": m.opponent_short,
        "home": m.home,
        "score": f"{m.scored}-{m.conceded}",
        "result": m.result,
        "status": m.status,
        "started": m.started,
        "minutes": m.minutes,
        "goals": m.goals,
        "assists": m.assists,
        "clean_sheet": m.clean_sheet,
        "saves": m.saves,
        "yellow": m.yellow,
        "red": m.red,
        "rating": m.rating,
        "motm": m.motm,
    }


# --------------------------------------------------------------------------- #
# FA Cup
# --------------------------------------------------------------------------- #

CUP_ROUNDS = ["Third Round", "Fourth Round", "Fifth Round", "Quarter-Final", "Semi-Final", "Final"]


def _simulate_cup(
    strengths: dict[str, tuple[float, float]],
    club_id: str,
    position: str,
    overall: int,
    ratings: dict[str, int],
    g_share: float,
    a_share: float,
    rng: random.Random,
) -> dict:
    field_ids = [c.id for c in CLUBS] + [c.id for c in EFL_CLUBS]
    for c in EFL_CLUBS:
        strengths.setdefault(c.id, (float(c.attack), float(c.defence)))
    rng.shuffle(field_ids)

    runs: list[dict] = []
    goals = assists = apps = 0
    alive = field_ids
    round_index = 0
    winner = None

    while len(alive) > 1:
        name = CUP_ROUNDS[min(round_index, len(CUP_ROUNDS) - 1)]
        survivors = []
        for i in range(0, len(alive), 2):
            a_id, b_id = alive[i], alive[i + 1]
            a_att, a_def = strengths[a_id]
            b_att, b_def = strengths[b_id]
            neutral = name in ("Semi-Final", "Final")
            ag = poisson(expected_goals(a_att, b_def, home=not neutral), rng)
            bg = poisson(expected_goals(b_att, a_def, home=False), rng)
            if ag == bg:  # extra time, then penalties
                if rng.random() < 0.5:
                    ag += 1
                else:
                    bg += 1
            won_id = a_id if ag > bg else b_id
            survivors.append(won_id)

            if club_id in (a_id, b_id):
                is_a = a_id == club_id
                scored, conceded = (ag, bg) if is_a else (bg, ag)
                opponent = CUP_CLUB_BY_ID[b_id if is_a else a_id]
                mine = 0
                mine_a = 0
                played = rng.random() < 0.82
                if played:
                    apps += 1
                    for _ in range(scored):
                        if rng.random() < g_share:
                            mine += 1
                    for _ in range(scored - mine):
                        if rng.random() < a_share:
                            mine_a += 1
                    goals += mine
                    assists += mine_a
                runs.append(
                    {
                        "round": name,
                        "opponent": opponent.name,
                        "opponent_short": opponent.short,
                        "score": f"{scored}-{conceded}",
                        "won": won_id == club_id,
                        "played": played,
                        "goals": mine,
                        "assists": mine_a,
                    }
                )
        alive = survivors
        round_index += 1
        if len(alive) == 1:
            winner = alive[0]

    reached = runs[-1]["round"] if runs else "Third Round"
    won_cup = winner == club_id
    if won_cup:
        exit_at = "Winners"
    elif runs:
        exit_at = f"Out in the {reached}"
    else:
        exit_at = "Out in the Third Round"

    return {
        "winner": CUP_CLUB_BY_ID[winner].name if winner else "-",
        "winner_id": winner,
        "won": won_cup,
        "reached": reached,
        "summary": exit_at,
        "matches": runs,
        "goals": goals,
        "assists": assists,
        "apps": apps,
    }


# --------------------------------------------------------------------------- #
# Awards
# --------------------------------------------------------------------------- #


def _league_awards(
    rows: dict[str, Row],
    player_name: str,
    club_id: str,
    my_goals: int,
    my_assists: int,
    position: str,
    rng: random.Random,
) -> tuple[list[dict], list[dict]]:
    scorers: list[dict] = [
        {"name": player_name, "club": CLUB_BY_ID[club_id].short, "value": my_goals, "is_you": True}
    ]
    assisters: list[dict] = [
        {"name": player_name, "club": CLUB_BY_ID[club_id].short, "value": my_assists, "is_you": True}
    ]

    for cid, row in rows.items():
        squad = SQUAD_SCORERS.get(cid, [])
        if not squad:
            continue
        pool_goals = row.gf - (my_goals if cid == club_id else 0)
        pool_assists = int(row.gf * 0.68) - (my_assists if cid == club_id else 0)
        g_weights = [w for _, w, _ in squad]
        a_weights = [w for _, _, w in squad]
        g_tally = _distribute(max(pool_goals, 0), g_weights, rng)
        a_tally = _distribute(max(pool_assists, 0), a_weights, rng)
        short = CLUB_BY_ID[cid].short
        for (name, _, _), g, a in zip(squad, g_tally, a_tally):
            if g:
                scorers.append({"name": name, "club": short, "value": g, "is_you": False})
            if a:
                assisters.append({"name": name, "club": short, "value": a, "is_you": False})

    scorers.sort(key=lambda x: (-x["value"], not x["is_you"], x["name"]))
    assisters.sort(key=lambda x: (-x["value"], not x["is_you"], x["name"]))
    for board in (scorers, assisters):
        for i, entry in enumerate(board, start=1):
            entry["rank"] = i
    return scorers, assisters


def leaderboard(board: list[dict], limit: int = 10) -> list[dict]:
    """Top N, plus your own row appended if you finished outside it.

    A defender who scored twice should still be able to see where they placed
    rather than just dropping off the bottom of the table.
    """
    top = board[:limit]
    if any(e["is_you"] for e in top):
        return top
    mine = next((e for e in board if e["is_you"]), None)
    return top + [mine] if mine else top


def _distribute(total: int, weights: list[float], rng: random.Random) -> list[int]:
    if total <= 0 or not weights:
        return [0] * len(weights)
    s = sum(weights)
    if s <= 0:
        return [0] * len(weights)
    # Sharpen: real squads funnel goals through two or three players, they don't
    # spread them evenly across everyone who can theoretically score.
    sharp = [w**1.9 for w in weights]
    s = sum(sharp)
    if s <= 0:
        return [0] * len(weights)
    probs = [w / s for w in sharp]
    tally = [0] * len(weights)
    for _ in range(total):
        tally[rng.choices(range(len(weights)), weights=probs, k=1)[0]] += 1
    return tally


def _golden_glove(
    rows: dict[str, Row],
    table: list[Row],
    player_name: str,
    club_id: str,
    position: str,
    my_matches: list[PlayerMatch],
    rng: random.Random,
) -> list[dict]:
    board = []
    for row in table:
        # A club's clean sheets track its goals-against, with noise for shape.
        expected = 38 * math.exp(-row.ga / 38 * 1.05)
        sheets = max(0, min(row.played, int(round(rng.gauss(expected, 1.4)))))
        if row.club_id == club_id and position == "GK":
            sheets = sum(1 for m in my_matches if m.clean_sheet)
            name = player_name
            is_you = True
        else:
            name = CLUB_KEEPERS.get(row.club_id, f"{CLUB_BY_ID[row.club_id].short} keeper")
            is_you = False
        board.append(
            {
                "name": name,
                "club": CLUB_BY_ID[row.club_id].short,
                "value": sheets,
                "is_you": is_you,
            }
        )
    board.sort(key=lambda x: (-x["value"], not x["is_you"], x["name"]))
    for i, entry in enumerate(board, start=1):
        entry["rank"] = i
    return board


def _build_awards(
    scorers: list[dict],
    assisters: list[dict],
    keepers: list[dict],
    summary: dict,
    player_name: str,
    table: list[Row],
    positions: dict[str, int],
) -> list[dict]:
    def rank_of(board: list[dict]) -> int | None:
        for i, entry in enumerate(board, start=1):
            if entry["is_you"]:
                return i
        return None

    champion = table[0]
    potm_pool = [
        {
            "name": s["name"],
            "club": s["club"],
            "is_you": s["is_you"],
            "score": s["value"] * 1.0
            + next((a["value"] for a in assisters if a["name"] == s["name"]), 0) * 0.7
            + (6 if s["club"] == CLUB_BY_ID[champion.club_id].short else 0),
        }
        for s in scorers[:25]
    ]
    if summary["avg_rating"]:
        for entry in potm_pool:
            if entry["is_you"]:
                entry["score"] += (summary["avg_rating"] - 6.8) * 8
    potm_pool.sort(key=lambda x: -x["score"])

    return [
        {
            "id": "golden_boot",
            "title": "Golden Boot",
            "winner": scorers[0]["name"] if scorers else "-",
            "club": scorers[0]["club"] if scorers else "-",
            "value": f"{scorers[0]['value']} goals" if scorers else "-",
            "you_won": bool(scorers and scorers[0]["is_you"]),
            "your_rank": rank_of(scorers),
        },
        {
            "id": "playmaker",
            "title": "Playmaker Award",
            "winner": assisters[0]["name"] if assisters else "-",
            "club": assisters[0]["club"] if assisters else "-",
            "value": f"{assisters[0]['value']} assists" if assisters else "-",
            "you_won": bool(assisters and assisters[0]["is_you"]),
            "your_rank": rank_of(assisters),
        },
        {
            "id": "golden_glove",
            "title": "Golden Glove",
            "winner": keepers[0]["name"] if keepers else "-",
            "club": keepers[0]["club"] if keepers else "-",
            "value": f"{keepers[0]['value']} clean sheets" if keepers else "-",
            "you_won": bool(keepers and keepers[0]["is_you"]),
            "your_rank": rank_of(keepers),
        },
        {
            "id": "potm",
            "title": "Player of the Season",
            "winner": potm_pool[0]["name"] if potm_pool else "-",
            "club": potm_pool[0]["club"] if potm_pool else "-",
            "value": "PFA vote",
            "you_won": bool(potm_pool and potm_pool[0]["is_you"]),
            "your_rank": next((i for i, e in enumerate(potm_pool, 1) if e["is_you"]), None),
        },
    ]


# --------------------------------------------------------------------------- #
# Summaries and narrative
# --------------------------------------------------------------------------- #


def _summarise(
    matches: list[PlayerMatch],
    cup: dict,
    player_name: str,
    position: str,
    overall: int,
    row: Row,
    league_position: int,
) -> dict:
    # A cameo off the bench is still an appearance -- and its goals still count.
    played = [m for m in matches if m.status in ("played", "bench") and m.minutes > 0]
    rated = [m for m in played if m.rating > 0]
    goals = sum(m.goals for m in played)
    assists = sum(m.assists for m in played)
    minutes = sum(m.minutes for m in played)
    return {
        "name": player_name,
        "position": position,
        "overall": overall,
        "apps": len(played),
        "starts": sum(1 for m in played if m.started),
        "sub_apps": sum(1 for m in played if not m.started),
        "minutes": minutes,
        "goals": goals,
        "assists": assists,
        "goal_contributions": goals + assists,
        "clean_sheets": sum(1 for m in played if m.clean_sheet),
        "saves": sum(m.saves for m in played),
        "yellows": sum(1 for m in played if m.yellow),
        "reds": sum(1 for m in played if m.red),
        "motm": sum(1 for m in played if m.motm),
        "avg_rating": round(sum(m.rating for m in rated) / len(rated), 2) if rated else 0.0,
        "best_rating": max((m.rating for m in rated), default=0.0),
        "matches_missed_injured": sum(1 for m in matches if m.status == "injured"),
        "matches_missed_suspended": sum(1 for m in matches if m.status == "suspended"),
        "per_90": round(goals / (minutes / 90), 2) if minutes >= 90 else 0.0,
        "cup_goals": cup["goals"],
        "cup_assists": cup["assists"],
        "cup_apps": cup["apps"],
        "total_goals": goals + cup["goals"],
        "total_assists": assists + cup["assists"],
    }


def _monthly_breakdown(matches: list[PlayerMatch]) -> list[dict]:
    order: list[str] = []
    acc: dict[str, dict] = {}
    for m in matches:
        if m.month not in acc:
            acc[m.month] = {"month": m.month, "goals": 0, "assists": 0, "apps": 0, "ratings": []}
            order.append(m.month)
        bucket = acc[m.month]
        bucket["goals"] += m.goals
        bucket["assists"] += m.assists
        if m.minutes > 0:
            bucket["apps"] += 1
            if m.rating:
                bucket["ratings"].append(m.rating)
    out = []
    for month in order:
        b = acc[month]
        ratings = b.pop("ratings")
        b["avg_rating"] = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
        out.append(b)
    return out


def _qualification(position: int, cup: dict) -> str:
    if position == 1:
        return "Champions of England"
    if position <= 4:
        return "Champions League"
    if position == 5:
        return "Champions League (via league)" if cup["won"] else "Europa League"
    if position == 6:
        return "Europa League" if cup["won"] else "Conference League play-off"
    if position >= 18:
        return "Relegated to the Championship"
    if position == 17:
        return "Survived, barely"
    return "Mid-table"


def _verdict(
    summary: dict,
    position: str,
    overall: int,
    club,
    league_position: int,
    row: Row,
    cup: dict,
    awards: list[dict],
    player_name: str,
) -> tuple[str, str, list[str]]:
    # Expectation scales with your overall AND with the club you were drafted into.
    # A 90-rated striker at Burnley is not held to the same bar as one at City.
    # Coefficients are least-squares fitted against the simulator itself over a grid
    # of overalls x clubs (see EXPECTATION_FIT), so ratio ~= 1.0 means "par".
    a, b, k = EXPECTATION_FIT[position]
    if position in ("ST", "MID"):
        club_factor = (club.attack / LEAGUE_MEAN_ATTACK) ** k
    else:
        club_factor = (club.defence / LEAGUE_MEAN_DEFENCE) ** k
    expected = (a + b * (overall - 60)) * club_factor

    if position == "ST":
        actual = summary["goals"] + summary["assists"] * 0.6
    elif position == "MID":
        actual = summary["goals"] * 0.8 + summary["assists"]
    elif position == "DEF":
        actual = summary["clean_sheets"] + summary["goals"] * 1.5
    else:
        actual = summary["clean_sheets"] * 1.2

    ratio = actual / expected if expected > 0 else 0.0

    # Rating is judged against what the overall already predicts, so an elite build
    # doesn't get credit twice for simply being elite.
    if summary["avg_rating"]:
        baseline_rating = 6.15 + (overall - 75) / 25
        rating_bonus = (summary["avg_rating"] - baseline_rating) * 0.45
    else:
        rating_bonus = -0.25
    score = ratio + max(-0.4, min(0.4, rating_bonus))

    if score >= 1.52:
        grade = "A+"
    elif score >= 1.30:
        grade = "A"
    elif score >= 1.13:
        grade = "B+"
    elif score >= 0.94:
        grade = "B"
    elif score >= 0.79:
        grade = "C+"
    elif score >= 0.64:
        grade = "C"
    elif score >= 0.47:
        grade = "D"
    else:
        grade = "F"

    won = [a["title"] for a in awards if a["you_won"]]
    headlines: list[str] = []

    if league_position == 1:
        headlines.append(f"CHAMPIONS. {club.name} lift the Premier League with {row.points} points.")
    elif league_position <= 4:
        headlines.append(f"{club.name} finish {_ordinal(league_position)} and are back in the Champions League.")
    elif league_position >= 18:
        headlines.append(f"Relegation. {club.name} go down in {_ordinal(league_position)} on {row.points} points.")
    else:
        headlines.append(f"{club.name} finish {_ordinal(league_position)} on {row.points} points.")

    if cup["won"]:
        headlines.append(f"FA Cup winners — {player_name} has a medal in the cabinet.")
    elif cup["reached"] in ("Final", "Semi-Final"):
        headlines.append(f"An FA Cup run all the way to the {cup['reached'].lower()}.")

    if position in ("ST", "MID"):
        headlines.append(
            f"{summary['goals']} goals and {summary['assists']} assists in {summary['apps']} league appearances."
        )
    elif position == "DEF":
        headlines.append(
            f"{summary['clean_sheets']} clean sheets in {summary['apps']} appearances, average rating {summary['avg_rating']}."
        )
    else:
        headlines.append(
            f"{summary['clean_sheets']} clean sheets and {summary['saves']} saves across {summary['apps']} appearances."
        )

    for title in won:
        headlines.append(f"Wins the {title}.")

    if summary["matches_missed_injured"] >= 6:
        headlines.append(f"Injuries cost {summary['matches_missed_injured']} league matches.")
    if summary["reds"]:
        headlines.append(f"Sent off {summary['reds']} time(s) — one to work on.")

    verdicts = {
        "A+": "A season people will still be talking about in twenty years.",
        "A": "Outstanding. Everything the build promised, delivered.",
        "B+": "A genuinely strong campaign — comfortably above expectations.",
        "B": "Solid. Did the job, roughly what the rating suggested.",
        "C+": "Decent enough, but there was more in there.",
        "C": "Underwhelming. The numbers never really got going.",
        "D": "A season to forget. Not much went right.",
        "F": "Grim. The kind of year that gets a manager sacked and a player shipped out.",
    }
    return grade, verdicts[grade], headlines


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
