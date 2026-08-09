"""The daily challenge: one shared set of spins, one attempt, one leaderboard.

Everyone in the world faces the same thirteen players in the same order on the
same day, so the only variable is what you do with them. That is the entire
appeal -- your 87 means something because the person you're comparing it to had
exactly your cards.

Position and era rotate with the date too, so a keeper day plays nothing like a
legends-striker day.

Identity is an anonymous token the browser generates and keeps. That is enough to
stop somebody accidentally playing twice and nowhere near enough to stop somebody
determined; without accounts, nothing would be. The leaderboard is for fun.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone

from .data.attributes import ATTRIBUTES, ERAS, POSITIONS

POSITION_ORDER = ["ST", "MID", "DEF", "GK"]
ERA_ORDER = ["current", "legends"]

# Day 1. Only used to give the share text a number people can compare.
LAUNCH = date(2026, 8, 9)

# A square per criterion, scored by how much that single choice cost you in
# overall -- not by the raw rating gap. Missing a 95 in a slot worth 3% is a
# rounding error; missing an 88 in a slot worth 15% is the whole game. The
# squares therefore sum to the regret shown on screen, which is the point.
# Overall is displayed as an integer, so a choice that cost less than half a
# point could not have changed the number on the card -- that is green. Above
# about a point and a half it visibly cost you, which is a blank square.
GREEN_LOSS = 0.5
YELLOW_LOSS = 1.5
GREEN, YELLOW, BLANK = "\U0001f7e9", "\U0001f7e8", "\u2b1c"


def day_number(day: str) -> int:
    return (date.fromisoformat(day) - LAUNCH).days + 1


def result_grid(position: str, board: dict, best_picks: dict) -> str:
    """Wordle-style squares: how close each pick was to the perfect one.

    Conveys how well you played without revealing which players came up, so it
    can be posted before someone else has had their go.
    """
    squares = []
    for attribute in ATTRIBUTES[position]:
        mine = board.get(attribute.key) or 0
        best = best_picks.get(attribute.key, {}).get("value", mine)
        loss = attribute.weight * max(0, best - mine)
        squares.append(GREEN if loss < GREEN_LOSS else YELLOW if loss < YELLOW_LOSS else BLANK)
    return "".join(squares)


def share_text(
    *,
    day: str,
    position_name: str,
    era_name: str,
    overall: int,
    grade: str,
    grid: str,
    optimum: int,
    streak: int,
) -> str:
    lines = [
        f"\u26bd Build A Baller \u2014 Day {day_number(day)}",
        f"{position_name} \u00b7 {era_name} \u00b7 {overall} OVR ({grade})",
        grid,
    ]
    if optimum > overall:
        lines.append(f"Perfect play was {optimum}. I left {optimum - overall} on the table.")
    else:
        lines.append("Perfect card. Nothing left on the table.")
    if streak > 1:
        lines.append(f"\U0001f525 {streak} day streak")
    lines += ["", "build-a-baller.vercel.app"]
    return "\n".join(lines)


def today() -> str:
    """The current challenge date. UTC, so the reset is the same moment for all."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def seconds_until_reset() -> int:
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((tomorrow - now).total_seconds())


def config(day: str | None = None) -> dict:
    """Deterministic setup for a given date. Same everywhere, forever."""
    day = day or today()
    digest = hashlib.sha256(f"build-a-baller:{day}".encode()).hexdigest()
    seed = int(digest[:12], 16) % (2**31)
    position = POSITION_ORDER[int(digest[12:16], 16) % len(POSITION_ORDER)]
    era = ERA_ORDER[int(digest[16:20], 16) % len(ERA_ORDER)]
    return {
        "date": day,
        "seed": seed,
        "position": position,
        "position_name": POSITIONS[position]["name"],
        "era": era,
        "era_name": ERAS[era]["name"],
        "resets_in": seconds_until_reset(),
    }


def previous_day(day: str) -> str:
    parsed = date.fromisoformat(day)
    return (parsed - timedelta(days=1)).isoformat()


def streak_from_dates(dates: list[str], reference: str | None = None) -> int:
    """Consecutive days played, counting back from today (or yesterday).

    Yesterday still counts as an unbroken streak, because a streak that dies at
    midnight before you have had a chance to play punishes time zones rather than
    absence.
    """
    if not dates:
        return 0
    played = set(dates)
    reference = reference or today()
    cursor = reference if reference in played else previous_day(reference)
    streak = 0
    while cursor in played:
        streak += 1
        cursor = previous_day(cursor)
    return streak
