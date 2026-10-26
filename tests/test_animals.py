"""Farm animals overnight: the produce, deluxe and quality rolls replayed, and the odds."""

from valley_planner.facts.animals import Animal, Animals
from valley_planner.facts.rng import NetRandom, random_seed

CHICKEN = {"House": "Coop", "DaysToProduce": 1, "DaysToMature": 3, "HarvestType": "DropOvernight",
           "ProduceItemIds": [{"ItemId": "176"}], "DeluxeProduceItemIds": [{"ItemId": "174"}],
           "DeluxeProduceMinimumFriendship": 200, "DeluxeProduceCareDivisor": 1200.0, "HappinessDrain": 7,
           "FriendshipForFasterProduce": -1, "ProfessionForFasterProduce": -1, "ProfessionForQualityBoost": 2,
           "ProfessionForHappinessBoost": 2, "SellPrice": 800, "PurchasePrice": 400}
SHEEP = {**CHICKEN, "House": "Barn", "DaysToProduce": 3, "HarvestType": "HarvestWithTool",
         "ProduceItemIds": [{"ItemId": "440"}], "DeluxeProduceItemIds": [], "FriendshipForFasterProduce": 900,
         "ProfessionForFasterProduce": 3}


class Data:
    def asset(self, name):
        return {"Data/FarmAnimals": {"White Chicken": CHICKEN, "Sheep": SHEEP}}[name]


def by_hand(animal_id, day, friendship, happiness):
    """The game's draws for a full, happy adult, written out longhand."""
    r = NetRandom(random_seed(int(animal_id) / 2.0, day))
    assert r.next_double() < 1 and r.next_double() < happiness / 70  # fullness/200 (=1.275), then happiness/70
    item = ["176"][r.next(1)]
    if r.next_double() < happiness / 150:
        deluxe = ["174"][r.next(1)]
        if r.next_double() < (friendship + happiness * 1.5) / 1200:
            item = deluxe
        q = friendship / 1000 - (1 - happiness / 225)
        quality = 4 if q >= 0.95 and r.next_double() < q / 2 else (
            2 if r.next_double() < q / 2 else (1 if r.next_double() < q else 0))
        return item, quality
    return item, None


def test_tonight_matches_the_draws():
    a = Animals(Data())
    for animal_id in ("2630641285515244035", "12345", "987654321987"):
        chicken = Animal(animal_id, "White Chicken", friendship=500, happiness=255, age=10)
        night = a.tonight(chicken, 66)
        item, quality = by_hand(animal_id, 66, 515, 255)
        assert night.produce == item and (quality is None or night.quality == quality)
        assert night.friendship == 515


def test_babies_hunger_and_slow_producers():
    a = Animals(Data())
    assert a.tonight(Animal("1", "White Chicken", age=1), 10).produce is None  # still a baby tomorrow
    hungry = a.tonight(Animal("1", "White Chicken", friendship=300, age=10), 10, fed=False, petted=False)
    assert hungry.produce is None and hungry.friendship == 300 - 9 - 20
    sheep = Animal("7", "Sheep", friendship=950, happiness=255, age=10, days_since_lay=0)
    assert a.tonight(sheep, 20).produce is None  # 1 day of 3 (2 with 900+ friendship)
    sheep.days_since_lay = 1
    assert a.tonight(sheep, 20).produce == "440"
    sheep.days_since_lay, sheep.friendship = 0, 950
    assert a.tonight(sheep, 20, professions={3}).produce == "440"  # Shepherd: every night at 900+


def test_odds_and_price():
    a = Animals(Data())
    hen = Animal("1", "White Chicken", friendship=500, happiness=255, age=10)
    o = a.odds(hen)
    assert o["produce"] == 1.0 and 0.7 < o["deluxe"] < 0.8
    assert abs(o["iridium"] + o["gold"] + o["silver"] + o["normal"] - 1) < 1e-9
    assert o["iridium"] == 0 and a.odds(hen, professions={2})["iridium"] > 0  # Coopmaster reaches iridium
    assert a.sell_price(hen) == int(800 * 0.8)
