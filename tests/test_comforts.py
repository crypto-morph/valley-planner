"""The spa, the horse, heaters and truffles."""

import pytest

from valley_planner.facts import comforts as c
from valley_planner.facts.walk import MINUTES_PER_TILE, NEW_PLAYER_PACE


def test_the_spa_fills_about_six_a_minute():
    assert c.SPA_FIRST_TICKS == 51 and c.SPA_EVERY_TICKS == 7 and c.SPA_ENERGY_PER_MINUTE == 6.25
    assert c.spa_minutes(270, 270) == 0 and c.spa_minutes(300, 270) == 0
    assert c.spa_minutes(269, 270) == 2  # the first point waits 800 ms: 816 ms is over a game minute
    assert c.spa_minutes(0, 270) == 45  # 51 + 7 * 269 ticks of 16 ms, 700 ms a minute
    assert c.spa_minutes(0, 508) > c.spa_minutes(0, 270)
    assert not c.spa_open(30) and c.spa_open(31)


def test_the_horse_runs_nearly_twice_as_fast():
    assert c.horse_speed_ratio() == pytest.approx(1.92)
    assert c.horse_speed_ratio(carrot=True, book=True) == pytest.approx(2.1)
    saved = c.horse_minutes_saved(100, pace=1.0)
    assert saved == pytest.approx(100 * MINUTES_PER_TILE * (1 - 1 / 1.92))  # about 14.5 minutes a hundred tiles
    assert c.horse_minutes_saved(100) == pytest.approx(saved * NEW_PLAYER_PACE)
    assert c.horse_minutes_saved(0) == 0


def test_heaters_only_keep_happy_animals_happy():
    assert c.evening_checks(1700) == 0 and c.evening_checks(1800) == 1 and c.evening_checks(2200) == 25
    assert c.winter_evening(200, 5, heater=True, checks=5) == 225
    assert c.winter_evening(200, 5, heater=False, checks=20) == 150  # stops once it's down to 150
    assert c.winter_evening(140, 5, heater=True, checks=20) == 140  # a heater doesn't lift unhappy animals
    assert c.winter_evening(250, 7, heater=True, checks=3) == 255


def test_truffles():
    assert c.truffle_minutes_between_digs() == pytest.approx(80000 / 700)
    assert c.truffle_can_dig(outdoors=True, raining=False, season="fall")
    assert not c.truffle_can_dig(outdoors=True, raining=True, season="fall")
    assert not c.truffle_can_dig(outdoors=True, raining=False, season="winter")
    assert not c.truffle_can_dig(outdoors=False, raining=False, season="spring")
    assert c.truffles_expected(0) == 1 and c.truffles_expected(1000) == pytest.approx(3)
    assert c.truffles_expected(1000, minutes_out=120) == pytest.approx(120 / (80000 / 700))


@pytest.fixture(scope="module")
def data():
    from valley_planner.app import Planner
    try:
        return Planner(None).data
    except RuntimeError:
        pytest.skip("no game here")


def test_the_stable_from_the_game(data):
    s = c.stable(data)
    assert (s.gold, s.days, s.builder) == (10000, 2, "Robin")
    assert dict(s.materials) == {"(O)709": 100, "(O)335": 5}  # Hardwood, Iron Bars
