"""The Forge's Prismatic Shard roll: what fits each tool, the seeded pick, and the sequence."""

from pathlib import Path
from types import SimpleNamespace

from valley_planner.facts.forge import Tool, available, forge_cost, next_enchantments, roll, sequence, tools_in_save
from valley_planner.facts.rng import NetRandom, random_seed

GAME_ID, FARMER = 452453427, -6034567812345678901


def test_what_fits_each_tool():
    assert available(Tool("MeleeWeapon", item_id="8")) == ["Artful", "Bug Killer", "Vampiric", "Crusader", "Haymaker"]
    assert available(Tool("MeleeWeapon", item_id="47")) == []  # scythe
    assert available(Tool("Hoe", upgrade_level=3)) == ["Generous", "Archaeologist", "Efficient", "Swift"]
    assert available(Tool("Hoe", upgrade_level=4))[0] == "Expansive"
    assert available(Tool("WateringCan")) == ["Bottomless", "Efficient"]
    assert available(Tool("Pan", upgrade_level=4)) == ["Expansive", "Generous", "Archaeologist", "Fisher"]
    assert available(Tool("FishingRod")) == ["Master", "Auto-Hook", "Preserving", "Efficient"]
    assert available(Tool("MilkPail")) == available(Tool("Slingshot")) == []


def test_current_and_previous_are_dropped_while_more_than_one_is_left():
    can = Tool("WateringCan", enchantments=("EfficientToolEnchantment",), previous=("Efficient", "Bottomless"))
    assert available(can) == ["Bottomless"]  # one left: previous names stop being dropped
    axe = Tool("Axe", enchantments=("SwiftToolEnchantment",), previous=("Swift", "Powerful"))
    assert available(axe) == ["Shaving", "Efficient"]


def test_roll_is_seeded_by_times_enchanted_game_and_farmer():
    tool = Tool("Pickaxe")
    pick = NetRandom(random_seed(7, GAME_ID, float(FARMER))).next(3)
    assert roll(7, GAME_ID, FARMER, tool) == ["Powerful", "Efficient", "Swift"][pick]


def test_sequence_replaces_and_remembers():
    seq = sequence(0, GAME_ID, FARMER, Tool("Axe"), 4)
    assert [r.times_enchanted for r in seq] == [0, 1, 2, 3] and [r.sure for r in seq] == [True, False, False, False]
    for a, b in zip(seq, seq[1:], strict=False):
        assert b.enchantment != a.enchantment and a.enchantment not in b.options
    save = SimpleNamespace(stats={"timesEnchanted": 2}, unique_id=str(GAME_ID), farmer_id=FARMER, legacy_random=False)
    assert next_enchantments(save, None, Tool("Axe"), 1)[0].enchantment == roll(2, GAME_ID, FARMER, Tool("Axe"))


def test_costs():
    sword = Tool("MeleeWeapon", item_id="8", forge_levels=1)
    assert forge_cost(sword, "(O)74") == 20 and forge_cost(sword, "(O)64") == 15 and forge_cost(sword, "(O)72") == 10
    assert forge_cost(Tool("MeleeWeapon", item_id="8", forge_levels=3), "(O)64") is None
    assert forge_cost(Tool("MilkPail"), "(O)74") is None and forge_cost(Tool("Hoe"), "(O)64") is None


SAVE = """<?xml version="1.0"?>
<SaveGame xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><player><items>
<Item xsi:type="Axe"><name>Iridium Axe</name><itemId>IridiumAxe</itemId><upgradeLevel>4</upgradeLevel>
<enchantments xsi:type="SwiftToolEnchantment"><level>1</level></enchantments>
<previousEnchantments>Swift</previousEnchantments><previousEnchantments>Powerful</previousEnchantments></Item>
<Item xsi:type="MeleeWeapon"><name>Lava Katana</name><itemId>9</itemId>
<enchantments xsi:type="RubyEnchantment"><level>2</level></enchantments>
<enchantments xsi:type="DiamondEnchantment"><level>1</level></enchantments></Item>
</items></player></SaveGame>"""


def test_tools_read_from_the_save(tmp_path: Path):
    p = tmp_path / "Farm_1"
    p.write_text(SAVE, encoding="utf-8")
    axe, katana = tools_in_save(SimpleNamespace(path=p))
    assert (axe.kind, axe.upgrade_level, axe.enchantment, axe.previous) == ("Axe", 4, "Swift", ("Swift", "Powerful"))
    assert (katana.item_id, katana.forge_levels, katana.enchantment) == ("9", 2, None)
