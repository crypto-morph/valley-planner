"""Overnight farm events: the roll chain, where a meteorite or statue lands, and what stops it."""

import pytest
from shared import shared_data

from valley_planner.facts import night_events as ne

MUGGLETON = 452013745  # a meteorite came down on night 16 at (50, 21)
MCCLARKIES = 452453427  # Pantry done; meteorites on nights 107 (40, 37) and 134 (42, 60)
PANTRY_DONE = frozenset({"ccPantry", "raccoonTreeFallen", "sawQiPlane"})
WIDTH, HEIGHT = 80, 65  # the Standard farm


@pytest.fixture(scope="module")
def data():
    try:
        return shared_data()
    except RuntimeError:
        pytest.skip("no game here")


def test_meteorites_seen_in_saves():
    assert ne.pick(16, MUGGLETON) == "meteorite"
    assert ne.meteor_tile(MUGGLETON, 16, WIDTH, HEIGHT) == (50, 21)
    for night, tile in ((107, (40, 37)), (134, (42, 60))):
        assert ne.pick(night, MCCLARKIES, mail=PANTRY_DONE) == "meteorite"
        assert ne.meteor_tile(MCCLARKIES, night, WIDTH, HEIGHT) == tile


def test_pantry_draw_shifts_the_chain():
    """With the Pantry done one more number is drawn first, so Muggleton's meteorite night moves."""
    assert ne.pick(16, MUGGLETON, mail=PANTRY_DONE) != "meteorite"
    assert ne.pick(107, MCCLARKIES, mail=frozenset({"sawQiPlane"})) != "meteorite"


def test_fixed_nights_come_first():
    assert ne.pick(31, MUGGLETON) == "earthquake"
    assert ne.pick(16, MUGGLETON, wedding=True) == "wedding"
    assert ne.pick(51, MUGGLETON) == "qi plane"
    assert ne.pick(51, MUGGLETON, mail=frozenset({"sawQiPlane"})) != "qi plane"
    assert ne.pick(16, MUGGLETON, mail_tomorrow={"ccPantry%&NL&%"}) == "world change"


def test_no_meteorite_early_or_capsule_in_year_one():
    found = {ne.pick(n, MUGGLETON) for n in range(1, 113)}
    assert "capsule" not in found
    assert all(ne.pick(n, g) != "meteorite" for g in (MUGGLETON, MCCLARKIES) for n in range(1, 6))


def test_statue_tiles_are_inside_the_margin():
    tiles = ne.statue_tiles(MUGGLETON, 40, WIDTH, HEIGHT)
    assert len(tiles) == ne.TRIES
    assert all(5 <= x < WIDTH - 4 and 5 <= y < HEIGHT - 4 for x, y in tiles)


def _state(**kw) -> ne.FarmState:
    return ne.FarmState(WIDTH, HEIGHT, walls=kw.pop("walls", set()), water=kw.pop("water", set()), **kw)


def test_meteor_needs_its_three_by_three_clear():
    tile = (50, 21)
    assert ne.meteor_blockers(None, None, tile, _state()) == []
    # the row above and the column to the right count too
    assert ne.meteor_blockers(None, None, tile, _state(objects={(52, 20): "Stone"})) == [((52, 20), "Stone")]
    assert ne.meteor_blockers(None, None, tile, _state(walls={(50, 20)})) == [((50, 20), "the map")]
    # trees and crops don't stop it (they're cleared), water only in its own two rows
    assert ne.meteor_blockers(None, None, tile, _state(solid={(50, 21): "a tree"}, water={(51, 20)})) == []
    assert ne.meteor_blockers(None, None, tile, _state(water={(52, 22)})) == [((52, 22), "water")]
    barn = ne.Building("Barn", 49, 22, 7, 4)
    assert {why for _t, why in ne.meteor_blockers(None, None, tile, _state(buildings=[barn]))} == {"Barn"}


def test_blocked_meteor_is_a_quiet_night():
    walls = ne._meteor(16, MUGGLETON, _state(walls={(51, 21)}), False)
    assert (walls.kind, walls.tile, walls.lands, walls.sure) == ("meteorite", (50, 21), False, True)
    junk = ne._meteor(16, MUGGLETON, _state(objects={(51, 21): "Weeds"}), False)
    assert (junk.lands, junk.sure) == (False, False)  # clear the weeds and it lands


def test_statue_takes_the_first_free_tile():
    first, second = ne.statue_tiles(MUGGLETON, 40, WIDTH, HEIGHT)[:2]
    assert ne._statue("owl", 40, MUGGLETON, _state(), False).tile == first
    behind_rock = ne._statue("owl", 40, MUGGLETON, _state(objects={first: "Stone"}), False)
    assert (behind_rock.tile, behind_rock.sure) == (second, False)
    behind_wall = ne._statue("owl", 40, MUGGLETON, _state(walls={first}), False)
    assert (behind_wall.tile, behind_wall.sure) == (second, True)


def test_fairy_picks_a_growing_crop_or_nothing():
    crops = [((10, 10), "Parsnip"), ((10, 11), "Parsnip"), ((12, 5), "Potato")]
    night = ne._fairy(40, MUGGLETON, _state(growing=crops), False, False)
    assert night.tile in [t for t, _ in crops] and not night.sure
    assert not ne._fairy(40, MUGGLETON, _state(growing=crops), True, False).lands
    assert not ne._fairy(40, MUGGLETON, _state(), False, False).lands


def test_witch_needs_a_coop_with_room():
    full = ne.Building("Big Coop", 10, 10, 6, 3, animals=8, room=8)
    assert not ne._witch(40, MUGGLETON, _state(buildings=[full]), False, False).lands


def test_standard_map_size(data):
    state = ne.map_state(data, 0)
    assert (state.width, state.height) == (WIDTH, HEIGHT)
    assert ne.meteor_blockers(None, None, (50, 21), state) == []  # Muggleton's landed there


def test_nights_from_the_newest_save(data):
    from valley_planner.app import Planner
    try:
        save = Planner(data).farm().save
    except Exception:
        pytest.skip("no save here")
    out = ne.nights(save, data, count=28)
    assert [n.days_played for n in out] == list(range(save.days_played + 1, save.days_played + 29))
    if save.days_played < 31 <= save.days_played + 28 and not save.spouse:
        assert next(n for n in out if n.days_played == 31).kind == "earthquake"
