"""The Mines pace target, and what the player has to travel with."""

from types import SimpleNamespace

import pytest
from shared import shared_data

from valley_planner.engine.route.pace import Pace
from valley_planner.facts.conditions import When
from valley_planner.facts.travel import Travel


def fresh_farm():
    """A new farm from the installed game; skipped where there isn't one, like CI."""
    from valley_planner.discover import find_game
    from valley_planner.engine.route.start import new_farm
    game = find_game()
    if game is None:
        pytest.skip("no game here")
    return new_farm(shared_data())


def at(floor, day):
    return SimpleNamespace(mine_lowest=floor, days_played=day)


def test_pace_stays_on_target_until_there_is_something_to_go_on():
    assert Pace.of(at(0, 60), 10).floors_per_week == 10  # hasn't started
    assert Pace.of(at(30, 12), 10).floors_per_week == 10  # one week isn't enough
    assert Pace.of(at(120, 90), 10).floors_per_week == 10  # finished
    assert "10 Mines floors a week" in Pace.of(at(0, 1), 10).note


def test_pace_moves_halfway_towards_what_the_save_shows():
    fast = Pace.of(at(60, 33), 10)  # 15 a week
    assert fast.observed == 15 and fast.floors_per_week == 12
    assert "15 a week your save shows" in fast.note
    assert Pace.of(at(10, 33), 10).floors_per_week == 6  # 2.5 a week, halfway
    assert Pace.of(at(5, 110), 6).floors_per_week == 5  # never below the floor
    assert Pace.of(at(119, 19), 30).floors_per_week == 40  # nor above the ceiling


def test_a_faster_pace_needs_fewer_trips_and_they_stay_a_week_apart():
    from valley_planner.engine.route.plan import Router, Settings
    farm = fresh_farm()
    days = Router(farm).mining_days(120, 112)
    assert len(days) == 12 and all(b - a >= 2 for a, b in zip(days, days[1:], strict=False))
    assert len({(d - 1) // 7 for d in days}) == 12
    assert len(Router(farm, settings=Settings(floors_per_week=20)).mining_days(120, 112)) == 6
    assert Router(farm).mining_days(120, 40) is None  # twelve weeks won't fit by then


DESTINATIONS = [
    {"Id": "Mines", "TargetLocation": "Mine", "TargetTile": {"X": 13, "Y": 9},
     "Condition": "PLAYER_HAS_MAIL Any landslideDone"},
    {"Id": "Town", "TargetLocation": "Town", "TargetTile": {"X": 105, "Y": 80}},
    {"Id": "Quarry", "TargetLocation": "Mountain", "TargetTile": {"X": 124, "Y": 12},
     "Condition": "PLAYER_HAS_MAIL Host ccCraftsRoom Received"}]


class Data:
    tables = {"Data/Minecarts": {"Default": {"UnlockCondition": "PLAYER_HAS_MAIL Host ccBoilerRoom Received",
                                             "Destinations": DESTINATIONS}},
              "Data/CraftingRecipes": {"Warp Totem: Beach": "709 1 393 2 771 10/Field/690/false/s Foraging 6/",
                                       "Warp Totem: Desert": "709 2 88 1 386 4/Field/261/false/null/"}}

    def asset(self, name):
        return self.tables[name]


def test_minecarts_open_with_the_boiler_room_and_each_stop_has_its_condition():
    t = Travel(Data())
    assert t.minecarts(When("spring", 1, 1, 1)) == []
    w = When("spring", 1, 1, 1, mail={"ccBoilerRoom"})
    assert [s.id for s in t.minecarts(w)] == ["Town"]
    w.mail |= {"landslideDone", "ccCraftsRoom"}
    assert [s.id for s in t.minecarts(w)] == ["Mines", "Town", "Quarry"]
    assert t.minecarts(w)[2].tile == (124, 12)


def test_totems_read_their_recipes():
    t = Travel(Data())
    beach = t.totem("690", known={"Warp Totem: Beach"}, held={"(O)690": 2})
    assert beach.skill == ("Foraging", 6) and beach.known and beach.held == 2
    assert beach.materials == (("709", 1), ("393", 2), ("771", 10)) and beach.tile == (20, 4)
    desert = t.totem("261", known=set(), held={})
    assert desert.skill is None and not desert.known  # only from the Desert Trader


def test_a_goal_brings_in_what_it_depends_on():
    from valley_planner.engine.route.objectives import with_needs
    assert with_needs(["skull_cavern"]) == (["mines_bottom", "bus", "skull_cavern"], [])
    assert with_needs(["skull_cavern"], ["bus", "silo"]) == (["mines_bottom", "bus", "skull_cavern"], ["silo"])
    assert with_needs(["bus", "skull_cavern"]) == (["bus", "mines_bottom", "skull_cavern"], [])


def test_a_goal_waits_for_the_goals_it_depends_on():
    from valley_planner.engine.route.plan import Settings, route
    farm = fresh_farm()
    objs = {o["id"]: o for o in route(farm, ["skull_cavern"], [], cave="bats")["objectives"]}
    assert all(o["status"] == "ok" for o in objs.values()) and len(objs) == 3
    assert objs["skull_cavern"]["steps"][0]["ready"] == objs["mines_bottom"]["finish"]  # the key is the last to come
    slow = route(farm, ["skull_cavern"], [], cave="bats", settings=Settings(floors_per_week=5))["objectives"]
    last = {o["id"]: o for o in slow}
    assert last["mines_bottom"]["status"] == "impossible" and last["skull_cavern"]["status"] == "impossible"
    assert any("comes first" in p for p in last["skull_cavern"]["problems"])
