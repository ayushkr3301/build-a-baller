"""Core game rules: the pools, the spin, the slot board, and the club draft.

Rules as specified:
  * n = 8 criteria per position, n + 1 = 9 spins.
  * Each spin offers one player. You take exactly one of their 8 attributes into
    the matching empty slot, or you skip. Filled slots are locked -- no overwrite.
    The spare spin is your one luxury pass (or a wasted spin if you get greedy).
  * Spin odds are tiered AND escalate: elite players get likelier as the run goes on.
  * After the build you veto three clubs, then a weighted spin drafts you somewhere.
"""

from __future__ import annotations

import math
import random
import re
import unicodedata
from dataclasses import dataclass, field

from .data import players_current, players_legends
from .data.attributes import ATTRIBUTES, N_CRITERIA, N_SPINS, attr_keys, overall_from
from .data.clubs import CLUBS, DISPLAY_CLUB_BY_ID

# --------------------------------------------------------------------------- #
# Tuning knobs -- these are the dials worth playing with after a few runs.
# --------------------------------------------------------------------------- #

# Relative draw weight per tier on the FIRST spin and on the LAST spin.
TIER_WEIGHTS_START = {1: 1.0, 2: 5.0, 3: 12.0, 4: 18.0}
TIER_WEIGHTS_END = {1: 6.0, 2: 12.0, 3: 14.0, 4: 10.0}

# How much of the way from START to END we actually travel across a run.
# 0.0 = flat tiered odds (no escalation), 1.0 = full escalation.
# Kept below 1.0 on purpose: a strong ramp makes "skip everything early" the
# strictly correct opening, which flattens the strategy.
ESCALATION = 0.7

# Club draft: how tightly your overall is matched to the club's standing.
# Larger sigma = more chaos, more chance a great build lands somewhere grim.
DRAFT_SIGMA = 9.0

# The draft is judged on a curve *within your era*, not on the absolute scale.
# Every legend is 80+ by design, so legend builds land ~83-92 while current-era
# builds land ~73-88. Graded absolutely, every legend run would be drafted to a
# top-six club and the veto/draft phase would stop being a decision. These are the
# 5th-to-95th percentile build ranges per era, measured against the pools.
DRAFT_CALIBRATION = {
    "current": (73.0, 88.0),
    "legends": (80.0, 92.0),
}
# ...mapped onto the span of club standings (Burnley ~62 up to Man City ~90).
DRAFT_CLUB_FLOOR = 62.0
DRAFT_CLUB_CEILING = 90.0


@dataclass(frozen=True)
class Player:
    id: str
    name: str
    position: str
    era: str
    club_id: str
    club_name: str
    club_short: str
    tier: int
    ratings: dict[str, int]

    @property
    def overall(self) -> int:
        return overall_from(self.position, self.ratings)


def _slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def _build_pools() -> dict[tuple[str, str], list[Player]]:
    pools: dict[tuple[str, str], list[Player]] = {}
    sources = {"current": players_current.POOLS, "legends": players_legends.POOLS}
    for era, by_pos in sources.items():
        for position, rows in by_pos.items():
            keys = attr_keys(position)
            players = []
            for name, club_id, tier, values in rows:
                club = DISPLAY_CLUB_BY_ID[club_id]
                players.append(
                    Player(
                        id=f"{era}-{position.lower()}-{_slug(name)}",
                        name=name,
                        position=position,
                        era=era,
                        club_id=club_id,
                        club_name=club.name,
                        club_short=club.short,
                        tier=tier,
                        ratings=dict(zip(keys, values)),
                    )
                )
            pools[(era, position)] = players
    return pools


POOLS = _build_pools()


def get_pool(era: str, position: str) -> list[Player]:
    try:
        return POOLS[(era, position)]
    except KeyError:
        raise ValueError(f"no pool for era={era!r} position={position!r}") from None


def pool_sizes() -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for (era, position), players in POOLS.items():
        out.setdefault(era, {})[position] = len(players)
    return out


def rosters() -> dict[str, dict[str, dict[str, list[str]]]]:
    """era -> position -> club id -> player names, for the two-stage spin reel.

    The client needs this to animate "reel the clubs, land on one, then reel that
    club's players". It is only presentation -- the actual draw already happened
    server-side -- but the reel has to show real names to feel like anything.
    """
    out: dict[str, dict[str, dict[str, list[str]]]] = {}
    for (era, position), players in POOLS.items():
        by_club = out.setdefault(era, {}).setdefault(position, {})
        for p in players:
            by_club.setdefault(p.club_id, []).append(p.name)
    return out


def rostered_club_ids() -> set[str]:
    return {p.club_id for players in POOLS.values() for p in players}


# --------------------------------------------------------------------------- #
# The spin
# --------------------------------------------------------------------------- #


def tier_weights(spin_index: int, n_spins: int = N_SPINS) -> dict[int, float]:
    """Draw weight per tier for a given spin. Escalates toward the end of a run."""
    if n_spins <= 1:
        t = 0.0
    else:
        t = spin_index / (n_spins - 1)
    ramp = ESCALATION * t
    return {
        tier: TIER_WEIGHTS_START[tier] + ramp * (TIER_WEIGHTS_END[tier] - TIER_WEIGHTS_START[tier])
        for tier in TIER_WEIGHTS_START
    }


def draw_player(
    era: str,
    position: str,
    spin_index: int,
    rng: random.Random,
    exclude_ids: set[str] | None = None,
) -> Player:
    """Draw one player for this spin. Players already seen in the run can't repeat."""
    exclude_ids = exclude_ids or set()
    pool = [p for p in get_pool(era, position) if p.id not in exclude_ids]
    if not pool:  # only reachable with an absurdly small pool
        pool = get_pool(era, position)

    weights_by_tier = tier_weights(spin_index)
    # Split the tier's weight across its members so tier size doesn't skew the odds.
    per_tier_count: dict[int, int] = {}
    for p in pool:
        per_tier_count[p.tier] = per_tier_count.get(p.tier, 0) + 1
    weights = [weights_by_tier[p.tier] / per_tier_count[p.tier] for p in pool]
    return rng.choices(pool, weights=weights, k=1)[0]


# --------------------------------------------------------------------------- #
# The slot board
# --------------------------------------------------------------------------- #


@dataclass
class Board:
    """The n=8 criteria being filled, and where each locked value came from."""

    position: str
    slots: dict[str, int | None] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)  # attr key -> player name

    def __post_init__(self) -> None:
        if not self.slots:
            self.slots = {k: None for k in attr_keys(self.position)}

    @property
    def filled(self) -> int:
        return sum(1 for v in self.slots.values() if v is not None)

    @property
    def complete(self) -> bool:
        return self.filled == N_CRITERIA

    def open_slots(self) -> list[str]:
        return [k for k, v in self.slots.items() if v is None]

    def take(self, attr_key: str, player: Player) -> None:
        if attr_key not in self.slots:
            raise ValueError(f"{attr_key!r} is not a criterion for {self.position}")
        if self.slots[attr_key] is not None:
            raise ValueError(f"{attr_key!r} is already locked -- no overwrites")
        self.slots[attr_key] = player.ratings[attr_key]
        self.sources[attr_key] = player.name

    @property
    def overall(self) -> int:
        return overall_from(self.position, {k: v for k, v in self.slots.items() if v is not None})


def players_by_ids(era: str, position: str, ids: list[str]) -> list[Player]:
    """Rebuild the players a run was offered, in the order they were drawn."""
    index = {p.id: p for p in get_pool(era, position)}
    return [index[i] for i in ids if i in index]


def best_possible_board(position: str, players: list[Player]) -> tuple[int, dict[str, dict]]:
    """The best card that could have been built from the players actually drawn.

    This is an assignment problem -- each player may donate exactly one attribute,
    each slot takes exactly one player -- so a greedy pass over the biggest numbers
    gets it wrong: taking a 95 Pace off a player whose 92 Finishing is the only 90+
    Finishing you were ever offered can cost more than it gains.

    Solved exactly with a DP over subsets of slots. Twelve slots means 4096 states,
    and unreachable states are pruned, so the true optimum is cheap.
    """
    keys = attr_keys(position)
    weights = [a.weight for a in ATTRIBUTES[position]]
    n = len(keys)
    size = 1 << n

    best = [-1.0] * size
    best[0] = 0.0

    # One back-pointer layer per player. Sharing a single array across layers
    # looks like it works and silently lets the reconstruction walk into a later
    # player's decision, producing a board where one player donates several
    # attributes. Each layer records only how *this* player reached a state:
    # None means the state was carried over untouched.
    layers: list[list[tuple[int, int] | None]] = []

    for player in players:
        values = [weights[s] * player.ratings[keys[s]] for s in range(n)]
        nxt = best[:]  # carry the previous layer forward = "skip this player"
        step: list[tuple[int, int] | None] = [None] * size
        for mask in range(size):
            score = best[mask]
            if score < 0:
                continue
            for s in range(n):
                bit = 1 << s
                if mask & bit:
                    continue
                candidate = score + values[s]
                target = mask | bit
                if candidate > nxt[target]:
                    nxt[target] = candidate
                    step[target] = (mask, s)
        layers.append(step)
        best = nxt

    # Every slot filled if there were enough players; otherwise the fullest board.
    final = max(range(size), key=lambda m: (best[m], bin(m).count("1")))
    if best[(1 << n) - 1] >= 0:
        final = (1 << n) - 1

    chosen: dict[str, dict] = {}
    mask = final
    for index in range(len(players) - 1, -1, -1):
        move = layers[index][mask]
        if move is None:
            continue  # this player wasn't the one that filled a slot here
        previous, slot = move
        chosen[keys[slot]] = {
            "value": players[index].ratings[keys[slot]],
            "player": players[index].name,
        }
        mask = previous

    ratings = {key: entry["value"] for key, entry in chosen.items()}
    return overall_from(position, ratings), chosen


def projected_overall(board: Board) -> int:
    """Overall if every remaining slot came in at the league-average value (~72)."""
    filled = {k: v for k, v in board.slots.items() if v is not None}
    for k in board.open_slots():
        filled[k] = 72
    return overall_from(board.position, filled)


# --------------------------------------------------------------------------- #
# The club draft
# --------------------------------------------------------------------------- #


def club_rank(club) -> float:
    """A single 0-100 number for 'how big is this club', used to match your overall."""
    quality = (club.attack + club.defence) / 2
    return 0.55 * quality + 0.45 * club.prestige


def draft_strength(overall: int, era: str) -> float:
    """Map a build's overall onto the club-standing scale, relative to its era."""
    lo, hi = DRAFT_CALIBRATION.get(era, DRAFT_CALIBRATION["current"])
    t = (overall - lo) / (hi - lo)
    t = max(0.0, min(1.0, t))
    return DRAFT_CLUB_FLOOR + t * (DRAFT_CLUB_CEILING - DRAFT_CLUB_FLOOR)


def draft_odds(
    overall: int, vetoed: set[str] | None = None, era: str = "current"
) -> list[tuple[str, float]]:
    """Probability of each club coming up on the draft spin, best chance first."""
    vetoed = vetoed or set()
    eligible = [c for c in CLUBS if c.id not in vetoed]
    if not eligible:
        eligible = list(CLUBS)

    strength = draft_strength(overall, era)
    raw = []
    for club in eligible:
        gap = strength - club_rank(club)
        affinity = math.exp(-(gap**2) / (2 * DRAFT_SIGMA**2))
        raw.append((club.id, max(affinity, 1e-6)))

    total = sum(w for _, w in raw)
    return sorted(((cid, w / total) for cid, w in raw), key=lambda x: -x[1])


def draft_club(
    overall: int, rng: random.Random, vetoed: set[str] | None = None, era: str = "current"
) -> str:
    odds = draft_odds(overall, vetoed, era)
    return rng.choices([c for c, _ in odds], weights=[w for _, w in odds], k=1)[0]


# --------------------------------------------------------------------------- #
# Presentation helpers
# --------------------------------------------------------------------------- #

CARD_TIERS = [
    (88, "icon", "Icon"),
    (83, "gold", "Gold"),
    (76, "silver", "Silver"),
    (0, "bronze", "Bronze"),
]


def card_grade(overall: int) -> tuple[str, str]:
    for threshold, key, label in CARD_TIERS:
        if overall >= threshold:
            return key, label
    return "bronze", "Bronze"


def attribute_meta(position: str) -> list[dict]:
    return [
        {"key": a.key, "label": a.label, "short": a.short, "weight": a.weight}
        for a in ATTRIBUTES[position]
    ]
