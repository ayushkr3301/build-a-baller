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

from .data.attributes import ERAS, POSITIONS

POSITION_ORDER = ["ST", "MID", "DEF", "GK"]
ERA_ORDER = ["current", "legends"]


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
