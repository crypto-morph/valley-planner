"""Shop hours: doors from maps, keepers from schedules, and the closures — small fake data, plus the real game."""

import pytest

from valley_planner.discover import find_game
from valley_planner.facts.conditions import When
from valley_planner.facts.hours import SHOPS, Hours

SHOP = {s.id: s for s in SHOPS}


def door(x, y, target, open_, close, *extra):
    return {"Action": " ".join(map(str, ["LockedDoorWarp", 1, 1, target, open_, close, *extra]))}


class Data:
    def __init__(self, schedules, festivals=None):
        town = {"Buildings": {"Width": 1, "Height": 1, "Properties": {}, "Tiles": {
            "1,1": door(1, 1, "SeedShop", 900, 2100), "2,1": door(2, 1, "Hospital", 900, 1500),
            "3,1": door(3, 1, "JojaMart", 900, 2300)}}}
        empty = {"Id": "", "Properties": {}, "Layers": {}}
        self.tables = {
            "Maps/Town": {"Id": "Town", "Properties": {}, "Layers": town},
            "Maps/Mountain": empty, "Maps/Forest": empty, "Maps/Desert": empty,
            "Maps/Beach": {"Id": "Beach", "Properties": {}, "Layers": {"Buildings": {"Width": 1, "Height": 1,
                           "Properties": {}, "Tiles": {"1,1": door(1, 1, "FishShop", 900, 1700)}}}},
            "Data/Festivals/FestivalDates": {k: v for k, v in (festivals or {}).items()},
            "Data/Characters": {"Pierre": {"Home": [{"Location": "SeedShop", "Tile": {"X": 20, "Y": 5}}]},
                                "Harvey": {"Home": [{"Location": "HarveyRoom", "Tile": {"X": 1, "Y": 1}}]},
                                "Willy": {"Home": [{"Location": "FishShop", "Tile": {"X": 5, "Y": 4}}]}},
            "Data/PassiveFestivals": {},
            **{f"Data/Festivals/{k}": {"conditions": h} for k, (_, h) in (festivals or {}).items()},
            **{f"Characters/schedules/{k}": v for k, v in schedules.items()},
        }
        self.tables["Data/Festivals/FestivalDates"] = {k: n for k, (n, _) in (festivals or {}).items()}

    def asset(self, name):
        return self.tables[name]

    def has(self, name):
        return name in self.tables

    def text(self, v):
        return v


PIERRE = {"spring": "700 SeedShop 10 20 0/830 SeedShop 4 17 2/1700 SeedShop 11 20 2"}


def test_door_and_keeper_overlap():
    h = Hours(Data({"Pierre": PIERRE}))
    assert h.day(SHOP["SeedShop"], When("spring", 2, 1, 2)).open == [(900, 1700)]  # door 9, till until 5


def test_pierre_wednesdays_and_festivals():
    h = Hours(Data({"Pierre": PIERRE}, {"spring13": ("Egg Festival", "Town/900 1400"),
                                        "spring28": ("Late Party", "Town/2200 2400")}))
    wed = h.day(SHOP["SeedShop"], When("spring", 3, 1, 3))
    assert not wed.open and "Wednesday" in wed.closed_why
    assert h.day(SHOP["SeedShop"], When("spring", 3, 1, 3, events_seen={"191393"})).open == [(900, 1700)]
    assert h.day(SHOP["SeedShop"], When("spring", 3, 1, 3), town_key=True).open == [(830, 1700)]
    assert "Egg Festival" in h.day(SHOP["SeedShop"], When("spring", 13, 1, 13)).closed_why
    late = h.day(SHOP["SeedShop"], When("spring", 28, 1, 28))  # an evening festival keeps you out of its map
    assert not late.open and "no way into Pelican Town until 10:00 PM" in late.closed_why


def test_willy_letter_and_away_days():
    willy = {"spring": "610 Beach 38 36 2/850 FishShop 5 4 2/1700 Beach 25 36 2", "Sat": "610 Forest 91 40 2"}
    h = Hours(Data({"Willy": willy}))
    assert h.day(SHOP["FishShop"], When("spring", 1, 1, 1)).open == [(900, 1700)]
    assert h.day(SHOP["FishShop"], When("spring", 1, 1, 1, mail={"willyHours"})).open == [(850, 1700)]
    sat = h.day(SHOP["FishShop"], When("spring", 6, 1, 6))
    assert not sat.open and "Willy" in sat.closed_why


def test_anyone_at_the_clinic_desk_and_joja():
    h = Hours(Data({"Harvey": {"spring": "700 HarveyRoom 21 7 0/830 Hospital 6 15 2/1200 Town 10 64 2"},
                    "Pierre": PIERRE}))
    assert h.day(SHOP["Hospital"], When("spring", 1, 1, 1)).open == [(900, 1200)]
    assert h.day(SHOP["Joja"], When("spring", 1, 1, 1)).open == [(900, 2300)]  # no keeper needed
    assert h.day(SHOP["Joja"], When("spring", 1, 1, 1, events_seen={"191393"})).closed_why


GAME = find_game()


@pytest.mark.game
@pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")
def test_real_week_of_shops():
    """The well-known weekly pattern, from the game's own maps and schedules (Fall Year 1, CC not restored)."""
    from valley_planner.gamedata import GameData
    h = Hours(GameData(GAME))

    def hours(shop, day):
        return h.day(SHOP[shop], When("fall", day, 1, 56 + day)).open

    assert hours("SeedShop", 8) == [(900, 1700)] and hours("SeedShop", 10) == []  # Monday; Wednesday shut
    assert hours("AnimalShop", 8) == [] and hours("AnimalShop", 9) == [] and hours("AnimalShop", 10) == [(900, 1600)]
    assert hours("Carpenter", 9) == [] and hours("Carpenter", 8) == [(900, 1700)]  # Robin's Tuesday off
    assert hours("Blacksmith", 8) == [(900, 1600)] and hours("Saloon", 8) == [(1200, 2400)]
    assert hours("FishShop", 13) == [] and hours("Hospital", 13) == []  # Saturdays
    assert hours("AdventureShop", 8) == [(1400, 2600)]
