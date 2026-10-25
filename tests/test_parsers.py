"""Pure parser / schedule tests."""

from datetime import date, time

import pytest

from custom_components.prix_energie.parsers import (
    ParseError,
    classify_trve_resource,
    parse_prvg_html,
    parse_trve_csv,
)
from custom_components.prix_energie.schedule import (
    ScheduleError,
    in_schedule,
    parse_schedule,
    state_is_off_peak,
)

from .fixtures import PRVG_HTML, TRVE_BASE_CSV, TRVE_HPHC_CSV


def test_trve_base():
    f = parse_trve_csv(TRVE_BASE_CSV)
    assert f.option == "base"
    row, current = f.in_effect(6, date(2026, 10, 25))
    assert current and row.base == 0.194 and row.subscription == 191.52
    row, _ = f.in_effect(6, date(2025, 9, 1))
    assert row.base == 0.1952
    assert f.in_effect(36, date(2026, 10, 25)) is None
    assert f.powers() == [6, 9]


def test_trve_hphc():
    f = parse_trve_csv(TRVE_HPHC_CSV)
    assert f.option == "hphc"
    row, _ = f.in_effect(6, date(2026, 10, 25))
    assert (row.hp, row.hc, row.subscription) == (0.2068, 0.162, 201.48)


def test_trve_bad():
    with pytest.raises(ParseError):
        parse_trve_csv("a;b;c\n1;2;3\n")


def test_classify():
    assert classify_trve_resource("Option Base") == "base"
    assert classify_trve_resource("Option HPHC") == "hphc"
    assert classify_trve_resource("Heures pleines / Heures creuses") == "hphc"
    assert classify_trve_resource("Option Tempo") is None


def test_prvg_picks_current_month():
    grid = parse_prvg_html(PRVG_HTML, date(2026, 10, 25))
    assert grid.period == date(2026, 10, 1)
    assert grid.for_profile("cooking") == (149.8, 0.188)
    assert grid.for_profile("heating") == (357.1, 0.155)
    nov = parse_prvg_html(PRVG_HTML, date(2026, 11, 2))
    assert nov.for_profile("heating") == (360.79, 0.1576)


def test_prvg_only_future_grid():
    html = PRVG_HTML.split("<h2>Prix repère pour le mois de novembre")[0].replace("octobre", "novembre")
    grid = parse_prvg_html(html + "</body></html>", date(2026, 10, 25))
    assert grid.period == date(2026, 11, 1)


def test_schedule():
    ranges = parse_schedule("22:00-06:00, 12h30-14h30")
    assert in_schedule(ranges, time(23, 0))
    assert in_schedule(ranges, time(5, 59))
    assert not in_schedule(ranges, time(6, 0))
    assert in_schedule(ranges, time(13, 0))
    assert not in_schedule(ranges, time(15, 0))
    with pytest.raises(ScheduleError):
        parse_schedule("22h")


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("HC..", True),
        ("HP..", False),
        ("on", True),
        ("off", False),
        ("HEURE CREUSE", True),
        ("HEURE PLEINE", False),
        ("unavailable", None),
    ],
)
def test_state_off_peak(state, expected):
    assert state_is_off_peak(state) is expected
