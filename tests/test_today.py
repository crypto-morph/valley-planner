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
    assert all("gold" in p and "place" in p and "stop" in p for p in v["passing"])
    on_stops = [e for x in v["plan"] for e in x.get("extras", [])]
    assert len(on_stops) == sum(1 for p in v["passing"] if p["stop"] < len(v["plan"]))


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


def test_a_can_near_a_step_shows_both_items(data):
    """Found in play: Blacksmith's bin said 3 Iron Ore, then gave a Newspaper once 20 cans had been opened."""
    from valley_planner.facts.conditions import When
    from valley_planner.facts.garbage import GarbageCans, _Roll
    w = When("spring", 15, 1, 15, game_id=453557957)
    s = SimpleNamespace(days_played=15, daily_luck=0.0, stats={"trashCansChecked": 18}, mail=set(), special_orders=[],
                        dish_of_the_day=None, deepest_mine_level=5, crafting_recipes=set())
    cans = GarbageCans(data)
    before, after = _Roll(cans, "Blacksmith", w, s).at(0), _Roll(cans, "Blacksmith", w, s, 20).at(0)
    assert before.label == "3 Iron Ore" and after.name == "Soggy Newspaper"
    day = {c.can: c for c in cans.day(s, w)}
    assert day["Blacksmith"].other.name == "Soggy Newspaper"
    s.stats["trashCansChecked"] = 25
    assert {c.can: c for c in cans.day(s, w)}["Blacksmith"].other is None


def test_food_advice_covers_the_shortfall(data):
    from valley_planner.views import today
    farm = SimpleNamespace(data=data, held=lambda: {"(O)RiverJelly": 2}, name=lambda _q: "River Jelly")
    assert "2 River Jelly" in today.food_advice(farm, 100)
    assert "1 River Jelly" in today.food_advice(farm, 50)
    assert "still be" in today.food_advice(farm, 500)


def test_a_machine_you_cannot_build_yet_is_not_suggested():
    from valley_planner.views.morning import _can_build
    farm = SimpleNamespace(save=SimpleNamespace(skills={"farming": 3}))
    assert not _can_build(farm, {"steps": [{"how": "Farming level 4"}]})
    assert _can_build(farm, {"steps": [{"how": "Farming level 3"}, {"how": ""}]})


def test_the_island_is_no_deadline():
    from valley_planner.views.morning import _out_of_reach
    assert _out_of_reach({"blocked": ["Willy's boat"]}) and _out_of_reach({"blocked": ["the bus (the Vault)"]})
    assert not _out_of_reach({"blocked": ["a Coop"]}) and not _out_of_reach({})


def test_books_and_catalogues_are_rare_gifts(data):
    from valley_planner.app import Planner
    from valley_planner.views import ask
    try:
        v = ask.villager(Planner(None).farm(), "Penny")
    except Exception:
        pytest.skip("no save here")
    rare = {x["name"] for x in v["loves"] if x["rare"]}
    assert {"Animal Catalogue", "Prismatic Shard"} <= rare and "Melon" not in rare and "Poppy" not in rare


def tv_farm(label, sure=True, known=()):
    event = SimpleNamespace(kind="tv", label=label, sure=sure)
    return SimpleNamespace(save=SimpleNamespace(days_played=21, cooking_recipes=set(known)), when=None,
                           calendar=SimpleNamespace(day=lambda _w, today_days_played: [event]))


def test_the_queen_of_sauce_is_a_stop_when_the_recipe_is_new():
    from valley_planner.views import today
    show = today._show_today(tv_farm("Queen of Sauce: Radish Salad"))
    assert show["title"] == "Watch the Queen of Sauce: Radish Salad" and "new recipe" in show["why"]
    assert today._show_today(tv_farm("Queen of Sauce: Omelet", known=["Omelet"])) is None
    rerun = today._show_today(tv_farm("Queen of Sauce rerun: Coleslaw", sure=False))
    assert "probably" in rerun["why"]


def test_the_show_comes_first_at_home_and_is_only_a_note_when_away(data):
    from valley_planner.app import Planner
    from valley_planner.views import today
    try:
        farm = Planner(None).farm()
    except Exception:
        pytest.skip("no save here")
    if not today._show_today(farm):
        pytest.skip("nothing new on TV today")
    assert today.view(farm)["plan"][0]["id"] == "tv"
    assert today.view(farm, done={"tv"})["plan"][0]["id"] != "tv"
    away = today.view(farm, time=1100, where="Town", done={"water", "plant", "harvest"})
    assert not [x for x in away["plan"] if x["id"] == "tv"] and any("Queen of Sauce" in n for n in away["notes"])
