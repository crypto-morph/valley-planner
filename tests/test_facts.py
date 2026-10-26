"""Game facts from data: conditions, item prices, shop prices, crops — small fake data, plus the real game."""

import pytest

from valley_planner.discover import find_game
from valley_planner.facts.conditions import When, check
from valley_planner.facts.crops import CropInfo, Crops, quality_odds
from valley_planner.facts.items import Items
from valley_planner.facts.shops import Shops


class Data:
    def __init__(self, **tables):
        self.tables = {"Data/WildTrees": {}, "Data/FruitTrees": {}, **tables}

    def asset(self, name):
        return self.tables[name]

    def text(self, value):
        return value


OBJECTS = {"472": {"Name": "Parsnip Seeds", "Price": 10, "Category": -74, "Type": "Seeds"},
           "479": {"Name": "Melon Seeds", "Price": 40, "Category": -74, "Type": "Seeds"},
           "24": {"Name": "Parsnip", "Price": 35, "Category": -75, "Type": "Basic", "Edibility": 10},
           "388": {"Name": "Wood", "Price": 2, "Category": -16, "Type": "Basic"}}
SHOPS = {
    "SeedShop": {"PriceModifiers": [{"Modification": "Multiply", "Amount": 2.0}], "Items": [
        {"Id": "a", "ItemId": "(O)472", "Price": -1, "IgnoreShopPriceModifiers": True, "Condition": "SEASON spring"},
        {"Id": "b", "ItemId": "(O)479", "Price": -1, "IgnoreShopPriceModifiers": True, "Condition": "SEASON summer"},
        {"Id": "c", "ItemId": "RANDOM_ITEMS (O)", "Price": 100}]},
    "Joja": {"PriceModifiers": [{"Modification": "Multiply", "Amount": 1.25, "Condition": "!PLAYER_HAS_MAIL Current JojaMember"}],
             "Items": [{"Id": "a", "ItemId": "(O)472", "Price": -1, "Condition": "SEASON spring"}]},
}


def spring5(**kw):
    return When("spring", 5, 1, 5, **kw)


def test_condition_grammar():
    w = When("summer", 7, 2, 35, mail={"ccVault"})
    assert check("SEASON spring summer, YEAR 2", w) is True
    assert check("YEAR 1 1", w) is False  # an optional maximum
    assert check("DAY_OF_WEEK Sun", w) is True  # the 7th is a Sunday; short names and numbers work
    assert check("DAY_OF_WEEK 0", w) is True and check("DAY_OF_WEEK Monday", w) is False
    assert check("!PLAYER_HAS_MAIL Current ccVault", w) is False
    assert check("SYNCED_RANDOM day x 0.5", w) is None  # a random roll: can't tell
    assert check("SYNCED_RANDOM day x 0.5, SEASON winter", w) is False  # …unless another part fails
    assert check('ANY "SEASON winter" "YEAR 2"', w) is True
    assert check("IS_COMMUNITY_CENTER_COMPLETE", w) is False


def test_sale_price_and_profit_margin():
    items = Items(Data(**{"Data/Objects": OBJECTS}))
    assert items.sale_price("24", 2) == 105  # 35 x 2 x 1.5
    assert items.sale_price("388", year=1) == 10 and items.sale_price("388", year=2) == 50  # Wood
    assert items.sale_price("472", profit_margin=0.5) == 10  # seeds follow the profit margin
    assert items.sale_price("24", profit_margin=0.5) == 70  # crops don't (when a shop sells them)


def test_shop_prices_markups_and_missing_stock():
    shops = Shops(Data(**{"Data/Objects": OBJECTS, "Data/Shops": SHOPS}))
    offers = {(o.shop, o.item): o for o in shops.offers(spring5())}
    assert offers[("SeedShop", "(O)472")].price == 20 and offers[("SeedShop", "(O)472")].available is True
    assert offers[("SeedShop", "(O)479")].available is False
    assert offers[("Joja", "(O)472")].price == 25  # non-member markup
    assert all(o.item != "RANDOM_ITEMS (O)" for o in offers.values())  # item queries aren't plain offers
    member = {(o.shop, o.item): o for o in shops.offers(spring5(mail={"JojaMember"}))}
    assert member[("Joja", "(O)472")].price == 20
    listed = {(o.shop, o.item): o for o in shops.offers(spring5(mail={"PierreStocklist"}))}
    melon = listed[("SeedShop", "(O)479")]
    assert melon.available and melon.out_of_season and melon.price == 120  # 80 x 1.5


def test_quality_odds():
    plain = quality_odds(5)
    assert round(plain[2], 4) == 0.11 and plain[4] == 0  # gold-or-better is exactly g without Deluxe
    deluxe = quality_odds(5, 3)
    assert deluxe[0] == 0  # never normal
    assert round(deluxe[4], 4) == 0.23 and round(deluxe[2], 4) == 0.3542
    assert round(sum(deluxe.values()), 9) == 1
    assert quality_odds(5, 0, max_quality=0) == {0: 1.0, 1: 0.0, 2: 0.0, 4: 0.0}  # held to the crop's range


def test_expected_stack():
    rice = CropInfo("273", "271", ("spring",), (1, 2, 2, 3), 0, False, True, True, 1, 1, 0.1, 0.1, 0, 4)
    assert rice.max_harvest(10) == 2  # floor(10 x 0.1) more
    assert round(rice.expected_stack(10), 3) == 1.611  # 1.5 + 0.1/0.9


GAME = find_game()


@pytest.mark.game
@pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")
def test_real_pierre_prices():
    from valley_planner.gamedata import GameData

    data = GameData(GAME)
    shops, crops = Shops(data), Crops(data)
    seed_shop = {o.item: o for o in shops.offers(spring5()) if o.shop == "SeedShop"}
    assert seed_shop["(O)472"].price == 20 and seed_shop["(O)474"].price == 80  # Parsnip, Cauliflower
    assert seed_shop["(O)273"].available is False  # Rice Shoot: Year 2 at Pierre's
    assert crops.get("474").grow == 12 and crops.get("481").regrow == 4


def test_season_change_survival():
    fiber = CropInfo("885", "771", ("spring", "summer", "fall", "winter"), (1, 2, 2, 2), 0, False, False, False,
                     4, 4, 0, 0, 0, 4)
    corn = CropInfo("487", "270", ("summer", "fall"), (2, 3, 3, 3, 3), 4, False, False, True, 1, 1, 0, 0, 0, 4)
    assert fiber.survives_into("spring") and fiber.survives_into("winter")  # lists all four: never dies of it
    assert corn.survives_into("fall") and not corn.survives_into("winter")
