"""The Community Center plan: choosing the best way, day windows, and the sources it draws on."""

from valley_planner.engine.cc import Way, _best, _day_ok
from valley_planner.facts.access import place_open
from valley_planner.facts.conditions import When
from valley_planner.facts.sources import Source


def way(kind, earliest=None, blocked=(), odds=None, sure=True):
    return Way(Source(kind, kind), earliest, earliest, list(blocked), odds, sure)


def test_best_way_policy():
    fish, cart, goat = way("fish", 20), way("cart", odds=0.33), way("animal", 15, blocked=["a Goat"])
    assert _best([cart, fish, goat]) is fish  # a way you can use now beats luck and unlocks
    assert _best([cart, goat]) is goat  # an unlock beats unlikely luck…
    likely = way("cart", odds=0.9)
    assert _best([likely, goat]) is likely  # …but not likely luck
    maybe, sure = way("shop", 12, sure=False), way("fish", 14)
    assert _best([maybe, sure]) is sure
    assert _best([way("monster", None, blocked=["killing x"], odds=None, sure=False), cart]) is cart


def test_day_windows():
    w = When("fall", 1, 1, 57)
    stall = Source("shop", "Festival_EggFestival_Pierre", frozenset({"spring"}), (13, 13))
    assert _day_ok(stall, 13, w) and not _day_ok(stall, 14, w) and not _day_ok(stall, 13 + 28, w)
    y2 = Source("shop", "SeedShop", frozenset({"summer"}), condition="YEAR 2")
    assert _day_ok(y2, 29, w) is False and _day_ok(y2, 112 + 29, w) is True


def test_place_gates():
    w = When("fall", 1, 1, 57)
    assert place_open("Woods", w)[0] is False and place_open("Woods", When("fall", 1, 1, 57, axe_level=2))[0]
    assert place_open("Railroad", When("summer", 2, 1, 30))[0] is False and place_open("Railroad", w)[0]
    assert place_open("BeachTidePools", w)[0] is False
    assert place_open("BeachTidePools", When("fall", 1, 1, 57, flags={"beachBridgeFixed"}))[0]
    assert place_open("Desert", When("fall", 1, 1, 57, mail={"ccVault"}))[0]


GAME_SAVES = None


def test_unlock_rules_from_data():
    from types import SimpleNamespace

    from valley_planner.engine.unlocks import Unlocks

    class Data:
        tables = {"Data/Buildings": {"Coop": {"BuildCost": 4000, "BuildDays": 3},
                                     "Big Coop": {"BuildCost": 10000, "BuildDays": 2, "BuildingToUpgrade": "Coop",
                                                  "BuildMaterials": [{"ItemId": "(O)388", "Amount": 400}]}},
                  "Data/FarmAnimals": {"Duck": {"PurchasePrice": 600, "RequiredBuilding": "Big Coop",
                                                "DaysToMature": 5, "DaysToProduce": 2}}}

        def asset(self, name):
            return self.tables[name]

    save = SimpleNamespace(buildings={"Coop": 1}, animals=[], axe_level=1, house_upgrade=0, machines={},
                           crafting_recipes=set(), cooking_recipes=set(), skills={})
    u = Unlocks(SimpleNamespace(data=Data(), save=save))
    duck = u.get("animal:Duck")
    assert (duck.gold, duck.days, duck.after) == (1200, 7, ["building:Big Coop"])
    assert [x.key for x in u.chain("animal:Duck")] == ["building:Big Coop", "animal:Duck"]  # the Coop is done
    steel = u.get("tool:Axe@2")
    assert (steel.gold, steel.materials, steel.days, steel.done) == (5000, [("335", 5)], 2, False)
    assert u.get("tool:Axe@1").done and u.get("kitchen").gold == 10000


def test_income_helpers():
    from valley_planner.engine.income import Stream, _cumulative, _season_end, afford_day
    assert _season_end(60, ("fall",)) == 84  # dies at the end of fall
    assert _season_end(40, ("summer", "fall")) == 84  # corn carries on into fall
    crops = Stream("crops", 300, {10: 100, 12: 200})
    run = _cumulative([crops], 50, 10, 20)
    assert run[0] == {"day": 10, "gold": 150} and run[-1] == {"day": 20, "gold": 350}
    assert afford_day(run, 300) == 17 and afford_day(run, 1000) is None


def test_recipe_entries_are_not_the_item():
    from valley_planner.facts.sources import Sources

    class Data:
        tables = {"Data/Shops": {"Saloon": {"Items": [{"ItemId": "(O)228", "IsRecipe": True, "Price": 300},
                                                      {"ItemId": "(O)346", "Price": -1}]}},
                  "Data/Objects": {"228": {"Name": "Maki Roll", "Price": 220, "Category": -7, "Type": "Cooking"},
                                   "346": {"Name": "Beer", "Price": 200, "Category": -26, "Type": "Basic"}}}

        def asset(self, name):
            return self.tables.get(name, {})

        def text(self, v):
            return v

    s = Sources(Data())
    assert [x.label for x in s.of("228", cart=False)] == []  # the Saloon sells the Maki Roll recipe, not the dish
    assert [x.label for x in s.of("346", cart=False)] == ["the Saloon"]
