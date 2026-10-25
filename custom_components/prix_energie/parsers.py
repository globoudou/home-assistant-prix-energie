"""Pure parsing helpers (no Home Assistant import, unit-testable).

* CRE regulated electricity tariffs (TRVE) CSV files from data.gouv.fr
* CRE monthly gas reference price (PRVG) HTML table
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser

MONTHS_FR = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}
_MONTH_RE = re.compile(r"\b(" + "|".join(MONTHS_FR) + r")\s+(20\d\d)\b", re.IGNORECASE)
_NUMBER_RE = re.compile(r"-?\d+(?:[   ]\d{3})*(?:[.,]\d+)?")


class ParseError(Exception):
    """Raised when a source cannot be understood."""


def strip_accents(value: str) -> str:
    """Return an upper/lower-case agnostic, accent-free string."""
    norm = unicodedata.normalize("NFKD", value)
    return "".join(c for c in norm if not unicodedata.combining(c))


def parse_number(value: str | None) -> float | None:
    """Parse a French formatted number ("0,1952", "1 234,5 €")."""
    if value is None:
        return None
    match = _NUMBER_RE.search(value.replace(" ", " "))
    if not match:
        return None
    raw = match.group(0)
    raw = re.sub(r"[   ]", "", raw).replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def parse_date(value: str | None) -> date | None:
    """Parse dd/mm/yyyy or yyyy-mm-dd (time part ignored)."""
    if not value:
        return None
    value = value.strip()[:10]
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------
# TRVE CSV
# --------------------------------------------------------------------------


@dataclass
class TrveRow:
    """One line of a TRVE history file, TTC values."""

    start: date
    end: date | None
    power_kva: int
    subscription: float | None
    base: float | None = None
    hp: float | None = None
    hc: float | None = None


@dataclass
class TrveFile:
    """Parsed TRVE file."""

    option: str  # "base" | "hphc"
    rows: list[TrveRow] = field(default_factory=list)

    def powers(self) -> list[int]:
        """Return the subscribed powers available in the file."""
        return sorted({row.power_kva for row in self.rows})

    def in_effect(self, power_kva: int, today: date) -> tuple[TrveRow, bool] | None:
        """Return (row, is_current) for the given power.

        is_current is False when no row covers ``today`` and the most recent one
        is returned as a best effort.
        """
        rows = [r for r in self.rows if r.power_kva == power_kva]
        if not rows:
            return None
        current = [r for r in rows if r.start <= today and (r.end is None or r.end >= today)]
        if current:
            return max(current, key=lambda r: r.start), True
        past = [r for r in rows if r.start <= today]
        if past:
            return max(past, key=lambda r: r.start), False
        return min(rows, key=lambda r: r.start), False


def _tokens(header: str) -> set[str]:
    clean = strip_accents(header).upper()
    return set(re.split(r"[^A-Z0-9]+", clean)) - {""}


def parse_trve_csv(text: str) -> TrveFile:
    """Parse a CRE TRVE CSV (Base or HP/HC) into a :class:`TrveFile`."""
    text = text.lstrip("﻿")
    first_line = text.splitlines()[0] if text else ""
    delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration as err:
        raise ParseError("empty CSV") from err

    tokens = [_tokens(h) for h in header]

    def find(*required: str, exclude: tuple[str, ...] = ()) -> int | None:
        for idx, tok in enumerate(tokens):
            if all(r in tok for r in required) and not any(e in tok for e in exclude):
                return idx
        return None

    i_start = find("DEBUT")
    i_end = find("FIN")
    i_power = find("SOUSCRITE")
    if i_power is None:
        i_power = find("PUISSANCE")
    i_fixed = find("FIXE", "TTC")
    i_hc = find("HC", "TTC")
    i_hp = find("HP", "TTC")
    i_base = find("VARIABLE", "TTC", exclude=("HC", "HP"))

    if None in (i_start, i_power, i_fixed):
        raise ParseError(f"unrecognised TRVE header: {header}")
    if i_hc is not None and i_hp is not None:
        option = "hphc"
    elif i_base is not None:
        option = "base"
    else:
        raise ParseError(f"no variable price column in header: {header}")

    result = TrveFile(option=option)

    def cell(row: list[str], idx: int | None) -> str | None:
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    for row in reader:
        if not row or not any(c.strip() for c in row):
            continue
        start = parse_date(cell(row, i_start))
        power = parse_number(cell(row, i_power))
        if start is None or power is None:
            continue
        item = TrveRow(
            start=start,
            end=parse_date(cell(row, i_end)),
            power_kva=int(power),
            subscription=parse_number(cell(row, i_fixed)),
        )
        if option == "base":
            item.base = parse_number(cell(row, i_base))
            if item.base is None:
                continue
        else:
            item.hp = parse_number(cell(row, i_hp))
            item.hc = parse_number(cell(row, i_hc))
            if item.hp is None or item.hc is None:
                continue
        result.rows.append(item)

    if not result.rows:
        raise ParseError("TRVE CSV contains no usable row")
    return result


def classify_trve_resource(title: str, url: str = "") -> str | None:
    """Guess which option a data.gouv.fr resource holds from its title."""
    text = strip_accents(f"{title} {url}").lower()
    if "tempo" in text or "ejp" in text:
        return None
    if re.search(r"hp\s*/?\s*hc|hc\s*/?\s*hp|heures? creuses|hphc|hchp", text):
        return "hphc"
    if "base" in text:
        return "base"
    return None


# --------------------------------------------------------------------------
# PRVG HTML page
# --------------------------------------------------------------------------


@dataclass
class GasGrid:
    """Gas reference price grid (TTC)."""

    period: date | None  # first day of the month the grid applies to
    cooking_subscription: float | None
    cooking_kwh: float | None
    heating_subscription: float | None
    heating_kwh: float | None

    def for_profile(self, profile: str) -> tuple[float, float]:
        """Return (subscription €/year, €/kWh) TTC for a profile."""
        if profile == "heating":
            sub, kwh = self.heating_subscription, self.heating_kwh
        else:
            sub, kwh = self.cooking_subscription, self.cooking_kwh
        if sub is None or kwh is None:
            raise ParseError(f"profile {profile} missing from grid")
        return sub, kwh


class _TableCollector(HTMLParser):
    """Collect tables (as rows of cell texts) with the text that precedes them."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[tuple[str, list[list[str]]]] = []
        self._text_before: list[str] = []
        self._depth = 0
        self._rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._colspan = 1

    def handle_starttag(self, tag, attrs):  # noqa: D102
        if tag == "table":
            self._depth += 1
            if self._depth == 1:
                self._rows = []
        elif self._depth and tag == "tr":
            self._row = []
        elif self._depth and tag in ("td", "th"):
            self._cell = []
            span = dict(attrs).get("colspan") or "1"
            self._colspan = int(span) if span.isdigit() else 1
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):  # noqa: D102
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            text = re.sub(r"\s+", " ", "".join(self._cell)).strip()
            self._row.extend([text] * self._colspan)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self._rows.append(self._row)
            self._row = None
        elif tag == "table" and self._depth:
            self._depth -= 1
            if self._depth == 0:
                context = " ".join(self._text_before[-60:])
                self.tables.append((context, self._rows))
                self._text_before.append(" ")

    def handle_data(self, data):  # noqa: D102
        if self._cell is not None:
            self._cell.append(data)
        elif not self._depth:
            stripped = data.strip()
            if stripped:
                self._text_before.append(stripped)


def _month_in(text: str) -> date | None:
    matches = _MONTH_RE.findall(strip_accents(text).lower())
    if not matches:
        return None
    month, year = matches[-1]
    return date(int(year), MONTHS_FR[month], 1)


def _grid_from_table(rows: list[list[str]]) -> GasGrid | None:
    sub_row = kwh_row = None
    header_rows: list[list[str]] = []
    for row in rows:
        label = strip_accents(row[0]).lower() if row else ""
        if sub_row is None and label.startswith("abonnement"):
            sub_row = row
        elif kwh_row is None and "kwh" in label and "moyen" in label:
            kwh_row = row
        elif sub_row is None and kwh_row is None:
            header_rows.append(row)
    if kwh_row is None:
        # Some layouts only have a single "Prix du kWh" row.
        for row in rows:
            label = strip_accents(row[0]).lower() if row else ""
            if "kwh" in label and "fourchette" not in label:
                kwh_row = row
                break
    if sub_row is None or kwh_row is None:
        return None

    width = max(len(sub_row), len(kwh_row)) - 1
    # Work out which value column is (profile, tax) from the header rows.
    profiles: list[str | None] = [None] * width
    taxes: list[str | None] = [None] * width
    for hrow in header_rows:
        cells = hrow[1:] if len(hrow) == width + 1 else hrow[-width:]
        for idx, cell in enumerate(cells[:width]):
            low = strip_accents(cell).lower()
            if "cuisson" in low or "eau chaude" in low or "b0" in low:
                profiles[idx] = "cooking"
            elif "chauffage" in low or "b1" in low:
                profiles[idx] = "heating"
            if re.search(r"\bttc\b", low):
                taxes[idx] = "ttc"
            elif re.search(r"\bht\b", low):
                taxes[idx] = "ht"
    if width == 4 and not any(profiles):
        profiles = ["cooking", "cooking", "heating", "heating"]
    if width == 4 and not any(taxes):
        taxes = ["ht", "ttc", "ht", "ttc"]
    if width == 2 and not any(profiles):
        profiles = ["cooking", "heating"]
        taxes = ["ttc", "ttc"]

    values: dict[str, dict[str, float | None]] = {
        "cooking": {"sub": None, "kwh": None},
        "heating": {"sub": None, "kwh": None},
    }
    for idx in range(width):
        if profiles[idx] is None or taxes[idx] not in ("ttc", None):
            continue
        if taxes[idx] is None and width != 2:
            continue
        prof = profiles[idx]
        if idx + 1 < len(sub_row):
            values[prof]["sub"] = parse_number(sub_row[idx + 1])
        if idx + 1 < len(kwh_row):
            values[prof]["kwh"] = parse_number(kwh_row[idx + 1])

    grid = GasGrid(
        period=None,
        cooking_subscription=values["cooking"]["sub"],
        cooking_kwh=values["cooking"]["kwh"],
        heating_subscription=values["heating"]["sub"],
        heating_kwh=values["heating"]["kwh"],
    )
    # kWh values sometimes published in €/MWh: normalise.
    for attr in ("cooking_kwh", "heating_kwh"):
        val = getattr(grid, attr)
        if val is not None and val > 5:
            setattr(grid, attr, val / 1000)
    if grid.cooking_kwh is None and grid.heating_kwh is None:
        return None
    return grid


def parse_prvg_html(html: str, today: date) -> GasGrid:
    """Extract the gas reference price grid that applies to ``today``."""
    collector = _TableCollector()
    collector.feed(html)
    grids: list[GasGrid] = []
    for context, rows in collector.tables:
        grid = _grid_from_table(rows)
        if grid is None:
            continue
        grid.period = _month_in(context)
        grids.append(grid)
    if not grids:
        raise ParseError("no gas reference price table found")

    month = date(today.year, today.month, 1)
    dated = [g for g in grids if g.period is not None]
    exact = [g for g in dated if g.period == month]
    if exact:
        return exact[0]
    past = [g for g in dated if g.period <= month]
    if past:
        return max(past, key=lambda g: g.period)
    undated = [g for g in grids if g.period is None]
    if undated:
        return undated[0]
    # Only future grids are published (published ahead of time): use the
    # earliest one rather than nothing.
    return min(dated, key=lambda g: g.period)
