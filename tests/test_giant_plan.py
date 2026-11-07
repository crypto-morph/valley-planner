"""Choosing where to sow a block so it turns giant, and the words and checks around a square."""

from types import SimpleNamespace

from valley_planner.facts import giant_plan
from valley_planner.facts.harvest import giant_roll
from valley_planner.views import picking

GID = 453557957
CHANCE = 0.009999999776482582


def _field(x0=10, y0=10, w=20, h=12):
    return {(x, y) for x in range(x0, x0 + w) for y in range(y0, y0 + h)}


def test_candidates_skip_crops_and_things_but_not_weeds():
    hoed = _field(0, 0, 6, 6)
    objects = {(0, 0): "Chest", (4, 4): "Weeds"}
    crops = {(3, 0)}
    tops = set(giant_plan.candidates(hoed, objects, crops, lambda t: True, reach=0))
    assert (0, 0) not in tops  # a Chest in the square
    assert (1, 0) not in tops  # the crop at (3, 0)
    assert (3, 3) in tops  # Weeds are cleared in a swing
    assert (0, 3) in tops


def test_find_picks_a_winning_night_after_the_crop_ripens():
    hoed = _field()
    tops = giant_plan.candidates(hoed, {}, set(), lambda t: True, reach=0)
    sow_days, grow, last = [29, 30, 31], 12, 56
    spots = giant_plan.find(tops, key="Melon", chance=CHANCE, game_id=GID, sow_days=sow_days, grow=grow,
                            last_day=last, hoed=hoed, objects={}, guarded=lambda t: True, limit=5)
    assert spots
    for s in spots:
        assert giant_roll(*s.tile, s.fires_day, GID, "Melon", CHANCE)
        assert s.ripe_day == s.sow_day + grow <= s.fires_day <= last
        assert s.sow_day in sow_days and 0 <= s.wait <= giant_plan.MAX_WAIT
        # no earlier night from the first possible ripening wins for this square
        assert not any(giant_roll(*s.tile, n, GID, "Melon", CHANCE) for n in range(sow_days[0] + grow, s.fires_day))
    days = [s.fires_day for s in spots]
    assert days == sorted(days)
    squares = [set(s.square) for s in spots]
    assert all(not a & b for i, a in enumerate(squares) for b in squares[i + 1:])


def test_find_gives_nothing_when_the_crop_cannot_ripen_in_season():
    spots = giant_plan.find([(0, 0)], key="Melon", chance=CHANCE, game_id=GID, sow_days=[50], grow=12,
                            last_day=56, hoed=set(), objects={}, guarded=lambda t: True)
    assert spots == []


def _farm(objects, crops=(), hoed=(), wet=False):
    save = SimpleNamespace(farm_objects=dict(objects), crops=list(crops), hoed=set(hoed), wet=wet)
    return SimpleNamespace(save=save)


def test_landmarks_name_the_chest_in_a_row_and_the_front_door():
    row = {(64 + i, 18): "Chest" for i in range(4)}
    assert picking._landmark(_farm(row), (61, 21)) == "3 south and 3 west of the west end of your row of 4 Chests"
    assert picking._landmark(_farm(row), (66, 20)) == "2 south of Chest 3 from the west in your row of 4"
    house = {(59 + x, 12 + y): "Farmhouse" for x in range(9) for y in range(5)}
    assert picking._landmark(_farm(house), (62, 20)) == "4 south and 2 west of your front door"


def test_watering_counts_rain_and_sprinklers():
    assert picking._watered(_farm({}, wet=True), (5, 5)) == "the rain waters it today"
    assert picking._watered(_farm({(5, 4): "Sprinkler"}), (5, 5)) == "your Sprinkler waters it"
    assert picking._watered(_farm({(4, 4): "Sprinkler"}), (5, 5)) == ""  # a plain Sprinkler doesn't reach corners
    assert picking._watered(_farm({(4, 4): "Quality Sprinkler"}), (5, 5)) == "your Quality Sprinkler waters it"


def test_picture_marks_the_top_left_and_what_to_sow():
    crop = SimpleNamespace(location="Farm", tile=(11, 10), forage=False)
    farm = _farm({(9, 9): "Scarecrow"}, crops=[crop], hoed={(10, 10), (11, 10), (12, 10), (12, 11)})
    rows = picking._picture(farm, (10, 10), missing=[(12, 11), (10, 11), (10, 10)])
    text = "\n".join(rows)
    assert text.count("1") == 1 and "X" in text
    assert rows[2][3:6] == "1GG"  # the square's top row: the top-left, then tiles that aren't missing
    assert rows[3][3:6] == "HGS"  # bare ground to hoe, then dirt to sow
