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


def fish_data():
    return Data(**{
        "Data/Fish": {"143": "Catfish/75/mixed/12/72/600 2400/spring fall/rainy/x/4/.4/.1/0/false",
                      "148": "Eel/70/smooth/12/80/1600 2600/spring fall/rainy/x/4/.3/.1/0/false",
                      "700": "Albacore/60/mixed/20/40/600 1100 1800 2600/fall winter/both/x/3/.3/.4/0/false",
                      "715": "Lobster/trap/.05/x/ocean/2/20/false"},
        "Data/Locations": {
            "Town": {"Fish": [{"ItemId": "(O)143", "Season": "Spring"}, {"ItemId": "(O)143", "Season": "Fall"}]},
            "Woods": {"Fish": [{"ItemId": "(O)143"}]},  # no season: all year, whatever Data/Fish says
            "Beach": {"Fish": [{"ItemId": "(O)700", "Condition": "LOCATION_SEASON Here fall winter"},
                               {"Id": "Eel_Area", "ItemId": "(O)148", "CanBeInherited": False}]},
            "Farm_Beach": {"Fish": [{"ItemId": "LOCATION_FISH Beach BOBBER_X BOBBER_Y WATER_DEPTH"}]},
            "Default": {"Fish": [{"ItemId": "(O)143"}]},
        }})


def test_fish_seasons_come_from_the_location():
    from valley_planner.facts.fish import Fish

    fish = Fish(fish_data())
    catfish = fish.by_name("Catfish")
    summer = [s.location for s in fish.open_spots(catfish, When("summer", 1, 1, 1))]
    assert summer == ["Woods"]  # the river only lists spring and fall; the Woods entry has no season
    albacore = fish.by_name("Albacore")
    assert [s.location for s in fish.open_spots(albacore, When("fall", 1, 1, 1))] == ["Beach"]
    assert fish.open_spots(albacore, When("spring", 1, 1, 1)) == []  # LOCATION_SEASON


def test_fish_inheritance_and_farm_type():
    from valley_planner.facts.fish import Fish

    beach_farm = Fish(fish_data(), farm_type=6)
    assert "Farm" in [s.location for s in beach_farm.by_name("Albacore").spots]  # borrowed from the Beach
    assert "Farm" not in [s.location for s in beach_farm.by_name("Eel").spots]  # not inheritable
    standard = Fish(fish_data(), farm_type=0)
    assert "Farm" not in [s.location for s in standard.by_name("Albacore").spots]  # other farm types' ponds don't count


def test_fish_times_weather_and_traps():
    from valley_planner.facts.fish import Fish

    fish = Fish(fish_data())
    albacore = fish.by_name("Albacore")
    spot = albacore.spots[0]
    assert albacore.bites(spot, season="fall", time=1900, wet=False) is True  # the second window
    assert albacore.bites(spot, season="fall", time=1200, wet=False) is False
    assert albacore.bites(spot, season="fall", time=1100, wet=False) is False  # end is exclusive
    catfish = fish.by_name("Catfish")
    woods = next(s for s in catfish.spots if s.location == "Woods")
    assert catfish.bites(woods, season="winter", time=1000, wet=False) is False  # rainy fish: snow is dry
    assert catfish.bites(woods, season="winter", time=1000, wet=True) is True
    lobster = fish.by_name("Lobster")
    assert lobster.trap and lobster.water == "ocean" and lobster.spots == []


def gift_data():
    objects = {
        "24": {"Name": "Parsnip", "Category": -75, "Price": 35, "Edibility": 10},
        "92": {"Name": "Sap", "Category": -81, "Price": 2, "Edibility": -1},
        "330": {"Name": "Clay", "Category": -16, "Price": 20, "Edibility": -300},
        "388": {"Name": "Wood", "Category": -16, "Price": 2, "Edibility": -300},
        "96": {"Name": "Dwarf Scroll I", "Category": 0, "Price": 1, "Type": "Arch"},
        "Raisins": {"Name": "Raisins", "Category": 0, "Price": 600, "Edibility": 50},
        "102": {"Name": "Book", "Category": 0, "Price": 50, "Edibility": -300, "ContextTags": ["book_item"]},
        "206": {"Name": "Pizza", "Category": -7, "Price": 300, "Edibility": 60},
    }
    tastes = {
        "Universal_Love": "Raisins", "Universal_Like": "-7", "Universal_Neutral": "", "Universal_Dislike": "",
        "Universal_Hate": "92",
        "Harvey": "//x/ /x/206/x/ /x/ /x/",  # dislikes Pizza by item, beating the universal Cooking like
        "Penny": "/book_item/x/-75/x/ /x/ /x/ /x/",  # loves anything tagged book_item, likes vegetables
        "Abigail": "/-7/x/ /x/ /x/ /x/ /x/",  # loves Cooking — but Pizza is named universally? no: category, not item
    }
    return Data(**{"Data/Objects": objects, "Data/NPCGiftTastes": tastes})


def test_gift_taste_resolution():
    from valley_planner.facts.gifts import Gifts

    g = Gifts(gift_data())
    assert g.taste("Abigail", "Raisins") == "love"  # universal item
    assert g.taste("Abigail", "92") == "hate"  # universal item (Sap)
    assert g.taste("Abigail", "388") == "dislike"  # neutral and worth under 20g
    assert g.taste("Abigail", "330") == "neutral"  # worth 20g
    assert g.taste("Abigail", "96") == "dislike" and g.taste("Penny", "96") == "like"  # artifacts
    assert g.taste("Harvey", "206") == "dislike"  # his own item list beats the universal category like
    assert g.taste("Abigail", "206") == "love"  # her own category beats the universal category
    assert g.taste("Penny", "102") == "love"  # her own context tag
    assert g.taste("Penny", "24") == "like"  # her own category
    assert g.taste("Penny", "StardropTea") == "love"


def test_giftable_flag():
    from valley_planner.facts.gifts import Gifts

    data = gift_data()
    data.tables["Data/Objects"]["999"] = {"Name": "Quest item", "Category": 0, "Price": 0, "CanBeGivenAsGift": False}
    g = Gifts(data)
    assert g.giftable("24") and not g.giftable("999") and not g.giftable("nope")
