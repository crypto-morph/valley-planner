"""Garbage cans: the rolls against values from the game's own hash and .NET's Random, and small fake tables."""

from types import SimpleNamespace

import pytest

from valley_planner.facts.conditions import When
from valley_planner.facts.garbage import CANS, LUCKS, GarbageCans, _Roll

GAME_ID = 452453427
ITEM = {"Id": "x", "ItemId": "(O)390"}
TABLE = {"DefaultBaseChance": 0.2, "BeforeAll": [], "AfterAll": [{"Id": "Fallback", "ItemId": "(O)168"}],
         "GarbageCans": {c: {"BaseChance": -1, "Items": []} for c in CANS}}


class Data:
    def __init__(self, table=None):
        self.tables = {"Data/GarbageCans": table or TABLE,
                       "Data/Objects": {"168": {"Name": "Trash"}, "390": {"Name": "Stone"}, "378": {"Name": "Copper Ore"}},
                       "Data/SpecialOrders": {"QiBeans": {"SpecialRule": "DROP_QI_BEANS"}}}

    def asset(self, name):
        return self.tables[name]

    def has(self, name):
        return name in self.tables

    def text(self, value):
        return value


def save(**changes):
    fields = dict(days_played=135, daily_luck=0.0, stats={}, mail=set(), special_orders=[], dish_of_the_day=None,
                  deepest_mine_level=0, crafting_recipes=set())
    return SimpleNamespace(**{**fields, **changes})


def when(days_played=135, **changes):
    return When("spring", 23, 2, days_played, game_id=GAME_ID, **changes)


@pytest.mark.parametrize(("day", "can", "value"), [
    (135, "JodiAndKent", 0.11399168666172385), (135, "Evelyn", 0.005090328401462328),
    (136, "JojaMart", 0.1853876594386006), (139, "Museum", 0.6933314877996833)])
def test_the_rolls_match_the_game(day, can, value):
    """From a C# run of the game's HashUtility and System.Random with the same seed recipe."""
    assert _Roll(GarbageCans(Data()), can, when(day), save()).roll == value


def test_today_is_exact():
    days = {c.can: c for c in GarbageCans(Data()).day(save(), when())}
    assert days["Evelyn"].odds == 1 and days["Evelyn"].loot.name == "Trash"
    assert days["Museum"].odds == 0 and days["Museum"].loot is None
    assert len(days) == len(CANS)


def test_another_day_gives_the_share_of_lucks_that_fill_it():
    """Roll 0.11176: 0.2 + luck beats it from luck -0.088 up, which is 189 of the 201 lucks."""
    days = {c.can: c for c in GarbageCans(Data()).day(save(), when(139))}
    assert days["JodiAndKent"].odds == 189 / len(LUCKS) and days["JodiAndKent"].loot.name == "Trash"
    assert days["Museum"].odds == 0


def test_the_trash_book_lifts_the_base_chance_only():
    roll = _Roll(GarbageCans(Data()), "Museum", when(), save())
    roll.roll = 0.3
    assert roll.at(0) is None
    roll.read_book = True
    assert roll.at(0).name == "Trash"


def test_a_failed_roll_leaves_a_can_empty_unless_an_entry_ignores_the_base_chance():
    table = {**TABLE, "BeforeAll": [{"Id": "Rare", "ItemId": "(O)390", "IgnoreBaseChance": True,
                                     "Condition": "PLAYER_STAT Current trashCansChecked 20"}]}
    cans = GarbageCans(Data(table))
    assert _Roll(cans, "Museum", when(), save()).at(0) is None
    loot = _Roll(cans, "Museum", when(), save(stats={"trashCansChecked": 20})).at(0)
    assert loot.name == "Stone" and loot.rare


def test_an_unmet_query_skips_the_random_after_it():
    """Conditions stop at the first failure, so PLAYER_STAT below the bar leaves the can's generator untouched."""
    roll = _Roll(GarbageCans(Data()), "Evelyn", when(), save())
    rng = roll.rng.clone()
    assert not roll._holds("PLAYER_STAT Current trashCansChecked 20, RANDOM .5", rng, 0)
    assert rng.draws == roll.rng.draws
    assert isinstance(roll._holds("PLAYER_STAT Current trashCansChecked 0, RANDOM .5", rng, 0), bool)
    assert rng.draws == roll.rng.draws + 1


def test_special_order_rules_and_stacks():
    table = {**TABLE, "GarbageCans": {**TABLE["GarbageCans"], "Evelyn": {"BaseChance": -1, "Items": [
        {"Id": "Qi", "ItemId": "(O)390", "Condition": "PLAYER_SPECIAL_ORDER_RULE_ACTIVE Current DROP_QI_BEANS"},
        {"Id": "Ore", "ItemId": "(O)378", "StackModifiers": [{"Modification": "Multiply", "RandomAmount": [3.0]}]}]}}}
    cans = GarbageCans(Data(table))
    assert _Roll(cans, "Evelyn", when(), save()).at(0).label == "3 Copper Ore"
    running = [{"key": "QiBeans", "state": "InProgress"}]
    assert _Roll(cans, "Evelyn", when(), save(special_orders=running)).at(0).name == "Stone"


def test_the_dish_is_only_known_today():
    table = {**TABLE, "GarbageCans": {**TABLE["GarbageCans"], "Evelyn": {"BaseChance": -1, "Items": [
        {"Id": "Dish", "ItemId": "DISH_OF_THE_DAY"}]}}}
    s = save(dish_of_the_day=("(O)390", 2))
    assert _Roll(GarbageCans(Data(table)), "Evelyn", when(), s).at(0).name == "Stone"
    assert _Roll(GarbageCans(Data(table)), "Evelyn", when(139), s).at(0.1).name == "the day's dish"


def test_morning_bins_line():
    from valley_planner.app import Planner
    from valley_planner.views import morning
    try:
        farm = Planner(None).farm()
    except Exception:
        pytest.skip("no save here")
    assert morning._bins(farm)["kind"] == "bins"
    assert "garbage can" in morning._bins(farm)["title"].lower()
