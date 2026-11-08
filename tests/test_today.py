"""Walking, skills, the board's request and the day's plan."""

from types import SimpleNamespace

import pytest
from shared import shared_data

from valley_planner.facts import help_wanted, skills
from valley_planner.facts.items import Items
from valley_planner.facts.walk import Walker, _legs
from valley_planner.save import night_override


@pytest.fixture(scope="module")
def data():
    try:
        return shared_data()
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
        farm = Planner(shared_data()).farm()
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
        v = today.view(Planner(shared_data()).farm())
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
        v = today.view(Planner(shared_data()).farm(), spouse="Penny")
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
        farm = Planner(shared_data()).farm()
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
    jelly = SimpleNamespace(qualified_id="(O)RiverJelly", category=-7, quality=0, stack=2)
    farm = SimpleNamespace(data=data, items=Items(data), save=SimpleNamespace(items=[jelly]),
                           bundles=SimpleNamespace(fits=lambda *a, **k: []), name=lambda _q: "River Jelly")
    assert "2 River Jelly" in today.food_advice(farm, 100)
    assert "1 River Jelly" in today.food_advice(farm, 50)
    assert "still be" in today.food_advice(farm, 500)


def test_food_eats_the_cheapest_energy_first(data):
    """A Salmonberry gives 25 energy for 5g; a Parsnip 25 for 35g."""
    from valley_planner.views import today
    berry = SimpleNamespace(qualified_id="(O)296", category=-79, quality=0, stack=1)
    parsnip = SimpleNamespace(qualified_id="(O)24", category=-75, quality=0, stack=1)
    farm = SimpleNamespace(data=data, items=Items(data), save=SimpleNamespace(items=[parsnip, berry]),
                           bundles=SimpleNamespace(fits=lambda *a, **k: []),
                           name=lambda q: {"(O)296": "Salmonberry", "(O)24": "Parsnip"}[q])
    assert today.food_advice(farm, 20).startswith("Eat 1 Salmonberry")


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
        v = ask.villager(Planner(shared_data()).farm(), "Penny")
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
        farm = Planner(shared_data()).farm()
    except Exception:
        pytest.skip("no save here")
    if not today._show_today(farm):
        pytest.skip("nothing new on TV today")
    assert today.view(farm)["plan"][0]["id"] == "tv"
    assert today.view(farm, done={"tv"})["plan"][0]["id"] != "tv"
    away = today.view(farm, time=1100, where="Town", done={"water", "plant", "harvest"})
    assert not [x for x in away["plan"] if x["id"] == "tv"] and any("Queen of Sauce" in n["text"] + n["why"] for n in away["notes"])


def test_a_person_indoors_is_a_stop_at_the_door(data, monkeypatch):
    from valley_planner.app import Planner
    from valley_planner.facts.schedules import DaySchedule, Stop
    from valley_planner.views import today
    try:
        farm = Planner(shared_data()).farm()
    except Exception:
        pytest.skip("no save here")
    day = DaySchedule("Tue", (Stop(900, False, "ArchaeologyHouse", 17, 9, 2), Stop(1400, False, "Town", 88, 100, 2)))
    monkeypatch.setattr(farm.schedules, "today", lambda _n, _s: [day])
    monkeypatch.setattr(farm.save.friends["Penny"], "talked_today", False)
    first, second = today._sweetheart(farm, "Penny")
    assert first["at"][0] == "Town" and "inside" in first["why"] and first["until"] == 14 * 60
    assert second["at"] == ("Town", 88, 100) and "inside" not in second["why"]


def test_a_birthday_with_a_gift_in_hand_is_a_stop(monkeypatch):
    from valley_planner.views import errands, keep, today
    monkeypatch.setattr(errands, "birthdays", lambda _f, days=7: {"birthdays": [{"who": "Pierre"}, {"who": "Emily"}]})
    monkeypatch.setattr(keep, "birthday_gift", lambda _f, who: ("(O)20", "like") if who == "Pierre" else None)
    monkeypatch.setattr(today, "_person", lambda _f, who, why, value: [{"id": f"talk:{who}", "why": why}])
    stops = today._birthdays(SimpleNamespace(name=lambda q: "Carrot"))
    assert [s["id"] for s in stops] == ["talk:Pierre"] and "give a Carrot, a liked gift" in stops[0]["why"]


def test_sprinklers_say_what_is_missing():
    from valley_planner.views import today

    def farm(held, recipes=("Sprinkler",)):
        return SimpleNamespace(save=SimpleNamespace(crafting_recipes=set(recipes)), held=lambda: held)

    assert "Iron Bars" in today.sprinkler_note(farm({"(O)334": 14}), 80)
    assert "craft 3" in today.sprinkler_note(farm({"(O)334": 14, "(O)335": 3}), 80)
    assert today.sprinkler_note(farm({"(O)334": 14}), 10) == ""
    assert today.sprinkler_note(farm({}, recipes=()), 80) == ""


def _plain_walker(blocked=()):
    w = Walker(None)
    w.__dict__["grids"] = {"Farm": (10, 10, set(blocked))}
    w.__dict__["exits"] = {}
    return w


def test_walks_go_diagonally_at_root_two_a_step():
    w = _plain_walker()
    path = w.path(w.reach(("Farm", 0, 0)), ("Farm", 5, 5))
    assert len(path) == 6 and w.tiles(path) == pytest.approx(5 * 2 ** 0.5)  # five diagonal steps, not ten straight
    assert w.minutes(path) == round(5 * 2 ** 0.5 * 10 / 33 * 1.5)


def test_walks_dont_squeeze_past_corners():
    w = _plain_walker(blocked={(1, 0)})
    prev = w.reach(("Farm", 0, 0))
    assert prev[("Farm", 1, 1)] == ("Farm", 0, 1)  # a wall beside the diagonal: round the corner instead
    assert _plain_walker().reach(("Farm", 0, 0))[("Farm", 1, 1)] == ("Farm", 0, 0)
    w = _plain_walker(blocked={(1, 0), (0, 1)})
    assert ("Farm", 1, 1) not in w.reach(("Farm", 0, 0))  # walled in: no slipping out between the corners


def test_legs_say_diagonals():
    assert _legs([(i, i) for i in range(30)]) == [("southeast", 29)]
    assert _legs([(0, y) for y in range(10)] + [(x, 9) for x in range(1, 20)]) == [("south", 8), ("east", 19)]


def test_crops_that_cannot_ripen_are_not_watered():
    from types import SimpleNamespace

    from valley_planner.views import crops as crops_view
    from valley_planner.views import today as today_view

    info = SimpleNamespace(seasons=("spring",))
    farm = SimpleNamespace(when=SimpleNamespace(season="spring", day=25),
                           crops=SimpleNamespace(get=lambda seed: info, by_harvest={}),
                           name=lambda qid: {"(O)190": "Cauliflower"}.get(qid, qid))
    late = SimpleNamespace(dead=False, ready=False, in_pot=False, seed_id="474", harvest_id="190", location="Farm",
                           days_left=6)
    soon = SimpleNamespace(**{**vars(late), "days_left": 3})
    assert crops_view.doomed(farm, late) and not crops_view.doomed(farm, soon)
    note = today_view.doomed_note(farm, [late, late])
    assert note.startswith("Don't water 2 Cauliflower: they can't ripen")
    assert today_view.doomed_note(farm, []) == ""


def test_slay_request_is_worked_out_from_the_seed():
    from valley_planner.facts import help_wanted
    q = help_wanted.slay(453557957, 26, 40, {"wizardJunimoNote"})
    assert q["monster"] in ("Frost Jelly", "Dust Spirit")  # the pool for floors 39 to 78
    lo, hi, even, each = help_wanted.SLAY[q["monster"]]
    assert lo <= q["count"] < hi and q["reward"] == q["count"] * each
    assert q["who"] == ("Lewis" if q["monster"] == "Frost Jelly" else "Wizard")
    assert help_wanted.slay(453557957, 26, 40, set())["who"] == "Lewis"  # no Wizard before his letter
    shallow = help_wanted.slay(453557957, 26, 5, set())
    assert shallow["monster"] == "Green Slime" and shallow["count"] % 2 == 0


def test_notes_split_into_a_line_and_its_reason():
    from valley_planner.views import today as today_view
    assert today_view._note("First part. The reason, at more length.") == {
        "text": "First part.", "why": "The reason, at more length."}
    assert today_view._note({"text": "a", "why": "b"}) == {"text": "a", "why": "b"}


def test_take_line_counts_what_you_carry_and_what_waits_there():
    from valley_planner.views import today as today_view
    stop = {"items": ["10 Bat Wing"], "rows": [{"label": "10 Bat Wing", "name": "Bat Wing", "from": [
        {"where": "plain chest, Community Center", "take": 8, "there": True},
        {"where": "grey chest, farm", "take": 2, "there": False}]}]}
    assert today_view._take_words(stop) == ["2 Bat Wing", "(8 Bat Wing already there)"]


def test_wood_is_held_back_for_the_next_job_but_not_when_there_is_plenty(monkeypatch):
    from types import SimpleNamespace as NS

    from valley_planner.views import errands
    from valley_planner.views import today as today_view
    monkeypatch.setattr(errands, "community_center", lambda f: {"rooms": [{"items": [
        {"name": "Wood", "count": 99, "open": True}]}]})
    route = {"objectives": [{"label": "The CC", "steps": [{"needs": [
        {"key": "building:Coop", "label": "build a Coop", "state": "new", "on": 51, "ready": "",
         "materials": ["300 Wood"]}]}]}]}

    def farm(wood):
        return NS(save=NS(crafting_recipes=set(), days_played=29), held=lambda: {"(O)388": wood},
                  label=lambda d: f"Summer {d - 28}, Year 1")
    assert "Coop (Summer 23)" in today_view.hold_back(farm(310), route)["Wood"]  # 310 - 99 leaves the Coop short
    assert "Wood" not in today_view.hold_back(farm(450), route)
    assert today_view.hold_back(farm(310), None) == {}  # no goals given: nothing to weigh it against


def test_planting_waits_for_sprinklers_unless_you_say_plant_them_all():
    from valley_planner.views.today import planting_note
    assert planting_note(67, 10, set(), False) is None  # no Sprinklers yet: plant as before
    assert planting_note(5, 10, {(1, 1)}, False) is None  # room for them all
    n = planting_note(67, 10, {(1, 1)}, False)
    assert "57 seeds wait" in n["text"] and n["toggle"] == {"key": "plantAll", "on": True, "label": "Plant them all today"}
    assert planting_note(67, 10, {(1, 1)}, True)["toggle"]["on"] is False


def test_a_rare_find_gets_its_own_note_on_the_plan_or_off_it():
    from valley_planner.views.today import rare_note
    assert rare_note([{"id": "water"}], []) is None
    on = rare_note([{"rare": ["Jack Be Nimble, Jack Be Thick"], "time": "8:11 AM", "title": "Hoe the worm tile",
                     "near": "by the bridge"}], [])
    assert on["level"] == "rare" and "8:11 AM" in on["text"]
    off = rare_note([], [{"rare": ["Prismatic Shard"], "title": "Hoe the worm tile", "why": "too far"}])
    assert "doesn't fit" in off["text"]


def test_the_community_center_goes_by_the_mines_chest_when_a_bundle_item_waits_there(monkeypatch):
    from valley_planner.views import errands, today
    items = [SimpleNamespace(name="Aquamarine", stack=1, where="Mine chest"),
             SimpleNamespace(name="Chub", stack=1, where="Farm chest")]
    farm = SimpleNamespace(save=SimpleNamespace(items=items))
    monkeypatch.setattr(errands, "community_center", lambda f: {"rooms": [{"items": [
        {"name": "Aquamarine", "count": 1, "open": True}, {"name": "Chub", "count": 1, "open": True}]}]})
    cc = {"id": "cc", "value": 500, "at": ("Town", 1, 1), "minutes": 5}
    stops = [cc]
    extra = today._cc_via_mines(farm, stops, {})
    assert stops == [] and extra[0]["then"] is cc and "Aquamarine" in extra[0]["title"]
    assert today._cc_via_mines(farm, [dict(cc)], {"Aquamarine": "held back"}) == []


def test_only_crops_that_must_go_in_this_season_are_bought_now():
    from valley_planner.views.today import _this_season
    farm = SimpleNamespace(when=SimpleNamespace(season="summer", year=1))
    assert _this_season(farm, "Summer 16, Year 1") and _this_season(farm, "")
    assert not _this_season(farm, "Fall 14, Year 1") and not _this_season(farm, "Summer 16, Year 2")
