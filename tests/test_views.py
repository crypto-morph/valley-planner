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
    for url in ("/api/crops", "/api/calendar?days=7", "/api/hours", "/api/cart?days=7", "/api/cart/search?q=seed", "/"):
        assert client.get(url).status_code == 200, url
    crops = client.get("/api/crops").json()
    assert {"countdown", "mine"} <= set(crops)
