"""Off-peak (heures creuses) helpers — pure Python, unit-testable."""

from __future__ import annotations

import re
from datetime import time

_RANGE_RE = re.compile(r"^\s*(\d{1,2})[:hH](\d{2})\s*-\s*(\d{1,2})[:hH](\d{2})\s*$")

HC_STATES = {"on", "true", "1", "hc", "heures creuses", "heure creuse", "offpeak", "off_peak"}


class ScheduleError(ValueError):
    """Invalid off-peak schedule."""


def parse_schedule(value: str) -> list[tuple[int, int]]:
    """Parse "22:00-06:00, 12h30-14h30" into [(start_min, end_min), ...]."""
    ranges: list[tuple[int, int]] = []
    for part in re.split(r"[;,]", value or ""):
        if not part.strip():
            continue
        match = _RANGE_RE.match(part)
        if not match:
            raise ScheduleError(part.strip())
        h1, m1, h2, m2 = (int(g) for g in match.groups())
        if h1 > 24 or h2 > 24 or m1 > 59 or m2 > 59:
            raise ScheduleError(part.strip())
        start, end = (h1 * 60 + m1) % 1440, (h2 * 60 + m2) % 1440
        if start == end:
            raise ScheduleError(part.strip())
        ranges.append((start, end))
    if not ranges:
        raise ScheduleError("empty")
    return ranges


def in_schedule(ranges: list[tuple[int, int]], now: time) -> bool:
    """Return True when ``now`` falls in one of the ranges (end excluded)."""
    minute = now.hour * 60 + now.minute
    for start, end in ranges:
        if start < end:
            if start <= minute < end:
                return True
        elif minute >= start or minute < end:  # wraps around midnight
            return True
    return False


def state_is_off_peak(state: str | None) -> bool | None:
    """Interpret an entity state (teleinfo PTEC/LTARF, binary sensor...)."""
    if state is None:
        return None
    low = state.strip().lower()
    if low in ("unknown", "unavailable", ""):
        return None
    if low in HC_STATES or low.startswith("hc") or "creuse" in low:
        return True
    return False
