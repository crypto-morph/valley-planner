"""Courtship rules: friendship pace, heart caps and the rain the Old Mariner needs."""

from valley_planner.facts import romance


def test_rain_chance():
    assert romance.rain_chance(3) == 0.183  # spring
    assert romance.rain_chance(29) == 0  # summer 1
    assert abs(romance.rain_chance(28 + 10) - 0.15) < 1e-9  # summer 10: 12% + 0.3% x 10
    assert romance.rain_chance(85) == 0  # winter
    assert romance.rain_by(85) == 113 + romance.rain_by(1) - 1  # from winter, nothing until spring
    assert romance.rain_by(1) == 8  # 1 - 0.817^8 = 80%


def test_points_pace():
    # from zero: 20 a day, 80 on the first two days of each week
    assert romance.points_day(0, 300, 1, birthday=None) == 7
    # the cap holds a dateable villager at 2,249 until the Bouquet
    assert romance.points_day(2200, 2500, 1, birthday=None, cap=romance.CAP_FRIEND) is None
    # a birthday gift counts 8 times
    assert romance.points_day(0, 640, 1, birthday=3) == 3
