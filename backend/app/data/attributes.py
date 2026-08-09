"""Position definitions: the n=12 criteria per position and their overall-rating weights.

The order of ATTRIBUTES[pos] is authoritative -- every player row in
players_current.py / players_legends.py lists its 12 ratings in exactly this order.
"""

from typing import NamedTuple


class Attr(NamedTuple):
    key: str
    label: str
    short: str
    weight: float


POSITIONS = {
    "ST": {
        "name": "Striker / Forward",
        "blurb": "Score the goals, carry the front line.",
        "icon": "⚽",
    },
    "MID": {
        "name": "Midfielder",
        "blurb": "Run the game from the engine room.",
        "icon": "\U0001f9e0",
    },
    "DEF": {
        "name": "Defender",
        "blurb": "Nothing gets past you.",
        "icon": "\U0001f6e1",
    },
    "GK": {
        "name": "Goalkeeper",
        "blurb": "The last line. All glory, all blame.",
        "icon": "\U0001f9e4",
    },
}

ATTRIBUTES: dict[str, list[Attr]] = {
    "ST": [
        Attr("finishing", "Finishing", "FIN", 0.15),
        Attr("positioning", "Positioning", "POS", 0.12),
        Attr("pace", "Pace", "PAC", 0.10),
        Attr("dribbling", "Dribbling", "DRI", 0.09),
        Attr("composure", "Composure", "CMP", 0.09),
        Attr("first_touch", "First Touch", "TCH", 0.08),
        Attr("heading", "Heading", "HEA", 0.08),
        Attr("strength", "Strength", "STR", 0.08),
        Attr("linkup", "Link-Up Play", "LNK", 0.08),
        Attr("long_range", "Long Range", "LNG", 0.06),
        Attr("weak_foot", "Weak Foot", "WKF", 0.04),
        Attr("penalties", "Penalties", "PEN", 0.03),
    ],
    "MID": [
        Attr("passing", "Passing", "PAS", 0.13),
        Attr("vision", "Vision", "VIS", 0.12),
        Attr("dribbling", "Dribbling", "DRI", 0.09),
        Attr("press_resistance", "Press Resistance", "PRS", 0.09),
        Attr("first_touch", "First Touch", "TCH", 0.09),
        Attr("stamina", "Stamina", "STA", 0.08),
        Attr("tackling", "Tackling", "TAC", 0.08),
        Attr("composure", "Composure", "CMP", 0.08),
        Attr("interceptions", "Interceptions", "INT", 0.07),
        Attr("work_rate", "Work Rate", "WRK", 0.07),
        Attr("long_shots", "Long Shots", "LNG", 0.06),
        Attr("set_pieces", "Set Pieces", "SET", 0.04),
    ],
    "DEF": [
        Attr("marking", "Marking", "MRK", 0.13),
        Attr("tackling", "Tackling", "TAC", 0.12),
        Attr("positioning", "Positioning", "POS", 0.12),
        Attr("interceptions", "Interceptions", "INT", 0.10),
        Attr("heading", "Heading", "HEA", 0.10),
        Attr("strength", "Strength", "STR", 0.09),
        Attr("pace", "Pace", "PAC", 0.09),
        Attr("composure", "Composure", "CMP", 0.07),
        Attr("passing", "Passing", "PAS", 0.06),
        Attr("leadership", "Leadership", "LDR", 0.05),
        Attr("stamina", "Stamina", "STA", 0.04),
        Attr("aggression", "Aggression", "AGG", 0.03),
    ],
    "GK": [
        Attr("reflexes", "Reflexes", "REF", 0.15),
        Attr("handling", "Handling", "HAN", 0.13),
        Attr("positioning", "Positioning", "POS", 0.12),
        Attr("one_on_ones", "One-on-Ones", "1v1", 0.11),
        Attr("agility", "Agility", "AGI", 0.09),
        Attr("aerial_command", "Aerial Command", "AER", 0.09),
        Attr("concentration", "Concentration", "CON", 0.08),
        Attr("distribution", "Distribution", "DIS", 0.07),
        Attr("composure", "Composure", "CMP", 0.06),
        Attr("communication", "Communication", "COM", 0.05),
        Attr("sweeping", "Sweeping", "SWP", 0.03),
        Attr("penalty_saving", "Penalty Saving", "PEN", 0.02),
    ],
}

N_CRITERIA = 12
N_SPINS = N_CRITERIA + 1  # the spare spin

# Sanity: n criteria per position, weights normalised, no duplicate keys.
for _pos, _attrs in ATTRIBUTES.items():
    assert len(_attrs) == N_CRITERIA, f"{_pos} must have exactly {N_CRITERIA} criteria"
    assert len({a.key for a in _attrs}) == N_CRITERIA, f"{_pos} has duplicate attribute keys"
    assert abs(sum(a.weight for a in _attrs) - 1.0) < 1e-9, f"{_pos} weights must sum to 1"

ERAS = {
    "current": {
        "name": "Current Era",
        "blurb": "Premier League 2025/26 squads.",
        "icon": "⚡",
    },
    "legends": {
        "name": "All-Time Legends",
        "blurb": "Club greats of the Premier League era, every one of them 80+.",
        "icon": "\U0001f451",
    },
}

# Rarity tiers. Lower number = rarer and better.
TIERS = {
    1: {"name": "Icon", "color": "#f5d67b"},
    2: {"name": "Star", "color": "#d8dee6"},
    3: {"name": "Quality", "color": "#c98f5f"},
    4: {"name": "Squad", "color": "#6f7a86"},
}


def attr_keys(position: str) -> list[str]:
    return [a.key for a in ATTRIBUTES[position]]


def overall_from(position: str, ratings: dict[str, int]) -> int:
    """Position-weighted overall. Missing criteria count as 0."""
    total = sum(a.weight * ratings.get(a.key, 0) for a in ATTRIBUTES[position])
    return int(round(total))
