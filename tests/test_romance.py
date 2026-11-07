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


def test_a_birthday_week_holds_three_gifts():
    """Fall 2 (day 58) is a Tuesday: Sunday's and Monday's gifts, then the birthday's on top."""
    from valley_planner.facts import romance
    # from Sunday Fall 7 (day 63) nothing special: two gifts a week, so 20 x 7 + 2 x 80 = 300 a week
    assert romance.points_day(0, 300, 63, birthday=None, cap=10**6) == 69
    # the week of Fall 2 (Sunday day 56): 80 + 80 + 640 by the Tuesday, plus 3 talks
    assert romance.points_day(0, 860, 56, birthday=58, cap=10**6) == 58


def test_heart_event_keys_read_as_conditions():
    from valley_planner.facts.heart_events import _parse
    e = _parse("Forest", "181928/f Penny 2000/t 900 1600/w sunny", "Penny")
    assert (e.hearts, e.start, e.end, e.weather, e.present) == (8, 900, 1600, "sunny", False)
    assert _parse("Trailer", "35/f Penny 1000/p Penny", "Penny").present
    assert _parse("Town", "99/f Haley 500", "Penny") is None
