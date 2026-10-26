"""Save reading: a hand-written save laid out like a 1.6 one, plus real saves when there are some."""

import pytest

from valley_planner.discover import find_game, find_saves_root, list_saves
from valley_planner.save import read_save, rusty_key

XSI = 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'


def obj(item_id, name, *, stack=1, quality=0, price=50, category=-75, xtype="Object", extra=""):
    return (f'<Item xsi:type="{xtype}"><name>{name}</name><itemId>{item_id}</itemId><stack>{stack}</stack>'
            f"<quality>{quality}</quality><price>{price}</price><category>{category}</category>"
            f"<type>Basic</type><bigCraftable>false</bigCraftable>{extra}</Item>")


def big(item_id, name):
    return (f'<Object><name>{name}</name><itemId>{item_id}</itemId><bigCraftable>true</bigCraftable></Object>')


def placed(obj_xml, x=1, y=1):
    return f"<item><key><Vector2><X>{x}</X><Y>{y}</Y></Vector2></key><value>{obj_xml}</value></item>"


def crop(seed, harvest, *, phases=(1, 1, 1, 1, 99999), phase=1, day=0, forage=False):
    days = "".join(f"<int>{p}</int>" for p in phases)
    return (f"<crop><phaseDays>{days}</phaseDays><currentPhase>{phase}</currentPhase>"
            f"<indexOfHarvest>{harvest}</indexOfHarvest><dayOfCurrentPhase>{day}</dayOfCurrentPhase>"
            f"<fullGrown>false</fullGrown><dead>false</dead><forageCrop>{str(forage).lower()}</forageCrop>"
            f"<seedIndex>{seed}</seedIndex></crop>")


SAVE = f"""<?xml version="1.0"?>
<SaveGame {XSI}>
 <player>
  <name>Morph</name><farmName>Test</farmName><money>1234</money><totalMoneyEarned>9000</totalMoneyEarned>
  <items>{obj("24", "Parsnip", stack=5, quality=2, price=35)}
   <Item xsi:type="Axe"><name>Copper Axe</name><upgradeLevel>1</upgradeLevel></Item>
   <Item xsi:type="FishingRod"><name>Advanced Iridium Rod</name><upgradeLevel>4</upgradeLevel></Item>
   <Item xsi:nil="true" /></items>
  <toolBeingUpgraded xsi:type="Axe"><name>Steel Axe</name><upgradeLevel>2</upgradeLevel></toolBeingUpgraded>
  <mailReceived><string>ccVault</string><string>HasRustyKey</string></mailReceived>
  <mailbox><string>landslideDone</string></mailbox>
  <eventsSeen><string>191393</string><string>festival_spring13</string></eventsSeen>
  <professions><int>1</int></professions>
  <farmingLevel>5</farmingLevel><fishingLevel>3</fishingLevel>
  <maxStamina>304</maxStamina><maxItems>24</maxItems><houseUpgradeLevel>1</houseUpgradeLevel>
  <stats><daysPlayed>41</daysPlayed></stats>
 </player>
 <locations>
  <GameLocation xsi:type="Farm"><name>Farm</name><piecesOfHay>120</piecesOfHay>
   <objects>{placed('<Object xsi:type="Chest"><name>Chest</name><items>' + obj("180", "Egg", price=50, category=-5) + "</items></Object>")}
            {placed(big("12", "Keg"), 2, 2)}</objects>
   <terrainFeatures>
    <item><key><Vector2><X>5</X><Y>6</Y></Vector2></key><value><TerrainFeature xsi:type="HoeDirt"><state>0</state>
      <Tile><X>5</X><Y>6</Y></Tile><fertilizer>(O)368</fertilizer>{crop("481", "258", phase=2, day=1)}</TerrainFeature></value></item>
    <item><key><Vector2><X>7</X><Y>6</Y></Vector2></key><value><TerrainFeature xsi:type="HoeDirt"><state>1</state>
      <Tile><X>7</X><Y>6</Y></Tile>{crop("", "", forage=True)}</TerrainFeature></value></item>
   </terrainFeatures>
   <buildings><Building><buildingType>Coop</buildingType><daysUntilUpgrade>2</daysUntilUpgrade>
     <upgradeName>Big Coop</upgradeName><indoors xsi:type="AnimalHouse"><name>Coop</name>
     <objects>{placed('<Object xsi:type="Chest"><name>Chest</name><items>' + obj("442", "Duck Egg") + "</items></Object>")}</objects>
     </indoors></Building></buildings>
  </GameLocation>
  <GameLocation xsi:type="FarmHouse"><name>FarmHouse</name>
   <fridge><items>{obj("348", "Blueberry Wine", price=150, category=-26, xtype="ColoredObject",
                       extra="<preserve>Wine</preserve><preservedParentSheetIndex>258</preservedParentSheetIndex>")}</items></fridge>
   <objects>{placed('<Object xsi:type="IndoorPot"><name>Garden Pot</name><hoeDirt><state>1</state>'
                    + crop("472", "24") + "</hoeDirt></Object>")}</objects>
  </GameLocation>
  <GameLocation><name>Cellar</name><objects>{placed(big("163", "Cask"))}</objects></GameLocation>
  <GameLocation xsi:type="CommunityCenter"><name>CommunityCenter</name>
   <areasComplete><boolean>false</boolean><boolean>false</boolean><boolean>false</boolean><boolean>false</boolean>
    <boolean>false</boolean><boolean>false</boolean></areasComplete></GameLocation>
  <GameLocation xsi:type="LibraryMuseum"><name>ArchaeologyHouse</name>
   <museumPieces><item><key><Vector2><X>1</X><Y>1</Y></Vector2></key><value><string>96</string></value></item></museumPieces>
  </GameLocation>
 </locations>
 <currentSeason>summer</currentSeason><dayOfMonth>13</dayOfMonth><year>1</year><dailyLuck>0.05</dailyLuck>
 <uniqueIDForThisGame>123456</uniqueIDForThisGame><isRaining>true</isRaining>
 <worldStateIDs><string>beachBridgeFixed</string></worldStateIDs>
 <locationWeather>
  <item><key><string>Default</string></key><value><LocationWeather><weatherForTomorrow><string>Wind</string></weatherForTomorrow>
   <weather><string>GreenRain</string></weather><isGreenRain><boolean>true</boolean></isGreenRain></LocationWeather></value></item>
 </locationWeather>
 <globalInventories><item><key><string>JunimoChests</string></key><value><ArrayOfItem>{obj("24", "Parsnip")}</ArrayOfItem></value></item></globalInventories>
 <availableSpecialOrders>
  <SpecialOrder><questKey>Willy</questKey><orderType></orderType><rewards xsi:type="MoneyReward"><amount><int>1000</int></amount><multiplier><float>1.5</float></multiplier></rewards></SpecialOrder>
  <SpecialOrder><questKey>QiArtisan</questKey><orderType>QiChallenge</orderType></SpecialOrder>
 </availableSpecialOrders>
 <visitsUntilY1Guarantee>3</visitsUntilY1Guarantee>
 <gameVersion>1.6.15</gameVersion>
</SaveGame>
"""


class FakeData:
    """Just the tables read_save looks things up in."""

    tables = {
        "Data/Objects": {"176": {"Name": "Egg"}, "180": {"Name": "Egg"}, "24": {"Name": "Parsnip"}},
        "Data/Crops": {"481": {"RegrowDays": 4, "HarvestItemId": "258"}, "472": {"RegrowDays": -1, "HarvestItemId": "24"}},
        "Data/Machines": {"(BC)12": {}, "(BC)163": {}},
        "Data/FruitTrees": {},
        "Data/BigCraftables": {"12": {"Name": "Keg"}, "163": {"Name": "Cask"}},
    }

    def asset(self, name):
        return self.tables[name]


@pytest.fixture
def save(tmp_path):
    p = tmp_path / "Test_1"
    p.write_text(SAVE, encoding="utf-8")
    return read_save(p, FakeData())


def test_basics(save):
    assert (save.farmer, save.season, save.day, save.days_played, save.money) == ("Morph", "summer", 13, 41, 1234)
    assert save.max_stamina == 304 and save.max_items == 24 and save.game_version == "1.6.15"


def test_every_container_and_coloured_objects(save):
    where = {(i.name, i.where) for i in save.items}
    assert ("Blueberry Wine", "FarmHouse fridge") in where
    assert ("Duck Egg", "Coop chest") in where  # a chest inside a building is labelled by the building
    assert ("Parsnip", "Junimo chest") in where
    wine = next(i for i in save.items if i.name == "Blueberry Wine")
    assert (wine.id, wine.price, wine.category, wine.preserve, wine.preserved_id) == ("348", 150, -26, "Wine", "258")


def test_shared_names_kept_apart(save):
    assert "Egg (Brown)" in save.totals()  # item 180, not the white Egg


def test_weather_from_the_farm(save):
    assert (save.weather, save.weather_tomorrow, save.wet) == ("green rain", "wind", True)


def test_mail_unread_counts_and_rusty_key(save):
    assert save.has_mail("landslideDone") and not save.has_mail("landslideDone", unread_ok=False)
    assert rusty_key(save) and "beachBridgeFixed" in save.world_state
    assert "festival_spring13" in save.events_seen  # event ids are strings in 1.6


def test_tools(save):
    assert save.axe_level == 1  # the Steel Axe is still at Clint's
    assert save.rod_level == 4  # Advanced Iridium Rod


def test_crops_regrow_pot_and_forage(save):
    blueberry = next(c for c in save.crops if c.harvest_id == "258")
    assert (blueberry.regrows, blueberry.tile, blueberry.days_left, blueberry.watered) == (True, (5, 6), 1, False)
    assert blueberry.fertilizer == "(O)368" and blueberry.grown == 3  # phases 1+1 done, 1 day into the third
    pot = next(c for c in save.crops if c.in_pot)
    assert pot.harvest_id == "24" and pot.regrows is False and pot.location == "FarmHouse"
    assert any(c.forage and c.regrows is False for c in save.crops)


def test_machines_buildings_and_cellar(save):
    assert save.machines == {"Keg": 1}  # the cellar's casks don't count before the third house upgrade
    assert save.buildings["Big Coop"] == 1  # Robin is finishing the upgrade
    assert save.hay == 120


def test_special_orders_and_rooms(save):
    assert [o["money"] for o in save.special_orders_board] == [1500]
    assert [o["key"] for o in save.qi_orders_board] == ["QiArtisan"]
    assert save.room_complete("Vault") and not save.room_complete("Pantry")  # ccVault mail: either route
    assert save.museum == {"96"} and save.cart_guarantee == 3
    assert save.daily_luck == 0.05


REAL = find_saves_root()


@pytest.mark.game
@pytest.mark.skipif(REAL is None or find_game() is None, reason="no saves or no game here")
def test_real_saves_read():
    from valley_planner.gamedata import GameData

    data = GameData(find_game())
    for path in list_saves(REAL)[:5]:
        s = read_save(path, data)
        assert s.season in ("spring", "summer", "fall", "winter") and 1 <= s.day <= 28
        assert all(c.regrows is not None for c in s.crops)
