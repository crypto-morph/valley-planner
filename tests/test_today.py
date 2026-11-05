"""Walking, skills, the board's request and the day's plan."""

from types import SimpleNamespace

import pytest

from valley_planner.facts import help_wanted, skills
from valley_planner.facts.walk import Walker, _legs
from valley_planner.save import night_override


@pytest.fixture(scope="module")
def data():
    from valley_planner.app import Planner
    try:
        return Planner(None).data
    except RuntimeError:
        pytest.skip("no game here")


def test_bridges_are_walkable_and_water_is_not(data):
    w = Walker(data)
    assert w.open(("Forest", 79, 49)) and not w.open(("Forest", 90, 44))


def test_the_south_of_the_forest_connects_over_the_bridge(data):
    """Found in play: the wooden bridge below Marnie's reaches the Horseradish side."""
    w = Walker(data)
    prev = w.reach(("Forest", 90, 17))
    for tile in ((85, 65), (88, 82), (49, 71)):
        assert w.path(prev, ("Forest", *tile))


def test_routes_cross_maps_and_read_as_words(data):
    w = Walker(data)
    path = w.path(w.reach(("Farm", 64, 16)), ("Backwoods", 28, 11))
    assert path[0][0] == "Farm" and path[-1][0] == "Backwoods"
    words = w.directions(path, lambda n: n)
    assert "north edge to Backwoods" in words[0] and not any("then north 2" in x for x in words)


def test_tide_pools_wait_for_the_bridge(data):
    walker = Walker(data)
    assert walker.path(walker.reach(("Farm", 64, 16)), ("Beach", 71, 22)) is None


def test_legs_merge_after_dropping_wiggles():
    assert _legs([(0, y) for y in range(0, 20)]) == [("south", 19)]


def test_the_night_overrides_the_forecast():
    assert night_override(2, 2, "spring", "sun") == "rain"  # day 3 is always rain
    assert night_override(3, 3, "spring", "rain") == "sun"  # days up to 4 are sunny
    assert night_override(27, 27, "spring", "rain") == "rain"
    assert night_override(28, 28, "spring", "rain") == "sun"  # the first of a month
    assert night_override(40, 12, "summer", "sun") == "storm"


def test_skills_say_what_the_next_level_takes():
    fishing, foraging = skills.progress({"fishing": 74, "foraging": 111})[1:3]
    assert (fishing.level, fishing.to_go) == (0, 26) and fishing.ways[0].endswith("2 more times")
    assert (foraging.level, foraging.next_xp) == (1, 380)
    top = skills.progress({"mining": 15000})[3]
    assert top.level == 10 and top.next_xp is None and top.ways == ()


def test_the_boards_request_matched_the_game(data):
    """Spring 2 on the Antropic farm: the board really did ask for a Leek for Robin."""
    friend = SimpleNamespace(status="Friendly", points=0, hearts=0)
    save = SimpleNamespace(
        unique_id="453557957", days_played=2, legacy_random=False, deepest_mine_level=0, mail=set(), season="spring",
        day=2, year=1, crafting_recipes=set(), cooking_order=["Fried Egg"], cooking_recipes={"Fried Egg"},
        mailbox=set(), events_seen=set(), skills={}, house_upgrade=0, museum=[], axe_level=0, rod_level=-1,
        friends={k: friend for k in ("Lewis", "Robin", "Jas", "Penny")}, flags=set())
    assert help_wanted.quest_today(save, data) == {"kind": "delivery", "who": "Robin", "item": "20"}
    save.days_played = 3
    assert help_wanted.quest_today(save, data) is None


def test_the_plan_finds_the_person_you_are_courting_and_stops_at_low_energy(data):
    from valley_planner.app import Planner
    from valley_planner.views import today
    try:
        farm = Planner(None).farm()
    except Exception:
        pytest.skip("no save here")
    v = today.view(farm, time=900, energy=60, spouse="Penny")
    assert all(x["energy_after"] >= 0 for x in v["plan"])
    late = today.view(farm, time=2300, energy=60, spouse="Penny")
    assert not [x for x in late["plan"] if x["kind"] == "talk"]


def test_spares_near_the_route_are_offered_as_optional(data):
    from valley_planner.app import Planner
    from valley_planner.views import today
    try:
        v = today.view(Planner(None).farm())
    except Exception:
        pytest.skip("no save here")
    assert all("gold" in p and "place" in p for p in v["passing"])
    assert not {x["title"].removeprefix("Pick up ") for x in v["left"]} & {p["title"] for p in v["passing"]}


def test_bubbles_rise_in_fishable_water_near_land(data):
    from valley_planner.facts import bubbles
    m = data.asset("Maps/Mountain")
    water = {tuple(int(v) for v in t.split(",")) for t in m["Water"]}
    spells = bubbles.forecast(data, "Mountain", 4, 453557957)
    assert spells and all(s.tile in water and s.start < s.end for s in spells)
    assert bubbles.forecast(data, "Mountain", 4, 453557957) == spells  # a seeded roll: the same every time
    assert bubbles.forecast(data, "Mountain", 5, 453557957) != spells


def test_the_day_brings_bundle_keepers_out_of_the_way(data):
    from valley_planner.app import Planner
    from valley_planner.views import today
    try:
        v = today.view(Planner(None).farm(), spouse="Penny")
    except Exception:
        pytest.skip("no save here")
    assert all(x["count"] > 0 and x["why"] for x in v["bring"])


def test_geodes_hang_on_the_count_alone(data):
    from valley_planner.facts import geodes
    first = geodes.crack(data, "535", 1, 453557957, 7620022464892434704)
    assert first == geodes.crack(data, "535", 1, 453557957, 7620022464892434704)
    runs = [geodes.crack(data, "535", n, 453557957, 7620022464892434704) for n in range(1, 40)]
    assert len({x.item for x in runs}) > 3  # a mix, drawn from the geode's own list and the fallbacks
    assert all(x.stack > 0 for x in runs)


def test_pace_learns_from_the_day_and_counts_a_day_once(tmp_path):
    from valley_planner.views import today
    f = tmp_path / "p.json"
    base = today.learned_pace(f, 5, None)
    assert base == today.NEW_PLAYER_PACE
    assert today.learned_pace(f, 5, 2.0) == pytest.approx(today.NEW_PLAYER_PACE * 2)
    assert today.learned_pace(f, 5, 1.0) == pytest.approx(today.NEW_PLAYER_PACE)  # the same day, replaced
    assert today.learned_pace(f, 6, 2.0) == pytest.approx(today.NEW_PLAYER_PACE * 1.5)
    morning = {"plan": [{"id": "a", "at": today.START + 120}]}
    assert today.pace_ratio(morning, 1010, {"a"}) == pytest.approx(2.0)  # 240 minutes against 120
    assert today.pace_ratio(morning, None, {"a"}) is None


def test_a_festival_day_is_only_the_farm_and_the_festival(data):
    from valley_planner.app import Planner
    from valley_planner.views import today
    try:
        farm = Planner(None).farm()
    except Exception:
        pytest.skip("no save here")
    farm.hours.festivals[(farm.save.season, farm.save.day)] = ("A Fair", 900, "Town")
    kinds = {x["kind"] for x in today.view(farm)["plan"]}
    assert "festival" in kinds and not kinds & {"mine", "shop", "forage", "talk", "bin"}
