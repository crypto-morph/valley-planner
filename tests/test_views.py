"""Views: the crop countdown's season rules, and the web app end to end on a real install."""

import pytest

from valley_planner.discover import find_game, find_saves_root
from valley_planner.views.crops import _denied_outdoors, _location_season, _run_end, _season_day


def test_season_runs_and_places():
    assert _run_end(("spring",), "spring") == 28
    assert _run_end(("summer", "fall"), "summer") == 56  # corn carries on into fall
    assert _run_end(("spring", "summer", "fall", "winter"), "fall") is None  # never dies of the season
    assert _season_day("summer", 30) == ("fall", 2)
    assert _location_season("Greenhouse", "winter") is None
    assert _location_season("IslandWest", "winter") == "summer" and _location_season("Farm", "fall") == "fall"
    cactus = {"PlantableLocationRules": [{"Result": "Deny", "PlantedIn": "Any",
                                          "Condition": "LOCATION_IS_OUTDOORS Here, !LOCATION_CONTEXT Here Island"}]}
    ancient = {"PlantableLocationRules": [{"Result": "Deny", "PlantedIn": "GardenPot", "Condition": None}]}
    assert _denied_outdoors(cactus) and not _denied_outdoors(ancient)


GAME, SAVES = find_game(), find_saves_root()


@pytest.mark.game
@pytest.mark.skipif(GAME is None or SAVES is None, reason="needs the game and a save")
def test_app_end_to_end():
    from fastapi.testclient import TestClient

    from valley_planner.app import create_app
    client = TestClient(create_app())
    meta = client.get("/api/meta").json()
    assert meta["game_version"] and meta["save"]
    for url in ("/api/crops", "/api/calendar?days=7", "/api/hours", "/api/cart?days=7", "/api/cart/search?q=seed", "/api/sell", "/api/sell?liked=true&seeds=false", "/api/ask?q=mar", "/api/ask/item/(O)266", "/api/ask/item/(O)142", "/api/ask/villager/Abigail", "/api/morning", "/api/plan", "/api/route/objectives", "/api/errand/gunther", "/api/errand/clint", "/api/errand/cc", "/api/errand/birthdays", "/"):
        assert client.get(url).status_code == 200, url
    crops = client.get("/api/crops").json()
    assert {"countdown", "mine"} <= set(crops)


def test_help_wanted_pool_and_holds():
    from types import SimpleNamespace

    from valley_planner.facts.help_wanted import possible_crops, raw_pool
    from valley_planner.views.sell import _Stack, _take
    fall = raw_pool("fall", 10, 1)
    assert {"404", "142", "272", "270"} <= fall and "62" not in fall and "334" not in fall
    assert "270" not in raw_pool("fall", 3, 1)  # first week: only the early crops
    assert {"62", "64", "334"} <= raw_pool("fall", 10, 1, mine_lowest=90, crafting={"Furnace"})
    assert possible_crops("winter", False, 2, True) == [] and "266" in possible_crops("summer", True, 2, False)
    stacks = [_Stack(SimpleNamespace(quality=2), 3), _Stack(SimpleNamespace(quality=0), 2)]
    assert _take(stacks, 3) == [(0, 2), (2, 1)]  # the lowest quality goes first; the best stays to sell
    assert _take(stacks, 5, min_q=2) == [(2, 2)]


def test_place_and_shop_names():
    from valley_planner.facts.places import Places
    from valley_planner.facts.sources import _shop_label

    class Data:
        def asset(self, name):
            return {"AnimalShop": {"DisplayName": "Marnie's Ranch"}, "Farm_Standard": {"DisplayName": "[Token]"}}

        def text(self, v):
            return v

    p = Places(Data(), "McClarkies")
    assert p.name("AnimalShop") == "Marnie's Ranch"
    assert p.name("Farm") == p.name("Farm_Standard") == "McClarkies Farm"
    assert p.name("UndergroundMine") == "the Mines" and p.name("SomeNewPlace") == "Some New Place"
    assert _shop_label("SeedShop") == "Pierre's"
    assert _shop_label("Festival_EggFestival_Pierre") == "Pierre at the Egg Festival"
    assert _shop_label("DesertFestival_Jas") == "Jas at the Desert Festival"
