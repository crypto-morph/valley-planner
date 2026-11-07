"""Skill levels: how far along each one is, and what the next level takes in plain actions (1.6.15).

XP for a level (Farmer.getBaseExperienceForLevel): 100, 380, 770, 1300, 2150, 3300, 4800, 6900, 10000, 15000.
What pays it, from the game's gainExperience calls:
- Farming: a crop gives 16 x ln(0.018 x price + 1), so a Parsnip 8; petting or milking an animal 5.
- Fishing: 3 x (quality + 1) + difficulty / 3 for a catch, so a Sunfish about 13; a crab pot pull 5.
- Foraging: 7 for picked forage, 14 for a felled tree, 2 for its stump.
- Mining: 1 for a stone outdoors and nothing in the Mines; ore pays (copper 5, iron 12).
- Combat: what the monster's data gives (a Green Slime 3, a Bug 1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

LEVELS = (100, 380, 770, 1300, 2150, 3300, 4800, 6900, 10000, 15000)
ACTIONS = {  # skill -> what earns it: (the action, its XP)
    "farming": (("harvest a Parsnip", 8), ("pet an animal", 5)),
    "fishing": (("catch a Sunfish-type fish", 13), ("pull a crab pot", 5)),
    "foraging": (("pick up forage", 7), ("fell a tree", 14)),
    "mining": (("mine copper ore", 5), ("mine iron ore", 12)),
    "combat": (("kill a Green Slime", 3), ("kill a Bug", 1)),
}


UNLOCKS = {  # what a level brings, the things worth planning around (Data/CraftingRecipes)
    "farming": {2: "Sprinkler, Mayonnaise Machine", 3: "Bee House, Speed-Gro", 4: "Preserves Jar",
                6: "Quality Sprinkler, Cheese Press", 7: "Loom", 8: "Keg, Oil Maker",
                9: "Seed Maker, Iridium Sprinkler"},
    "fishing": {2: "Bait", 3: "Crab Pot", 4: "Recycling Machine, Worm Bin", 6: "Iridium Rod, Trap Bobber"},
    "foraging": {2: "Charcoal Kiln", 4: "Tapper", 6: "Lightning Rod", 9: "Rain Totem"},
    "mining": {2: "Staircase", 4: "Transmute (Fe)", 6: "Bomb", 7: "Transmute (Au)", 9: "Crystalarium"},
    "combat": {},
}
PICKS = {  # the profession worth choosing, if the path allows it; the level-up screen comes at bedtime, unannounced
    ("farming", 5): "Tiller", ("farming", 10): "Artisan", ("mining", 5): "Miner", ("mining", 10): "Blacksmith",
    ("fishing", 5): "Fisher", ("fishing", 10): "Angler", ("foraging", 5): "Forester", ("foraging", 10): "Lumberjack",
    ("combat", 5): "Fighter", ("combat", 10): "Defender",
}
RAISES_PRICES = {"Tiller", "Artisan", "Blacksmith", "Fisher", "Angler"}  # hold the bin back that night


def harvest_xp(price: int) -> int:
    """Crop.harvest: once per harvest, however many drop."""
    return round(16 * math.log(0.018 * price + 1))


def level_of(xp: int) -> int:
    return sum(1 for n in LEVELS if xp >= n)


@dataclass(frozen=True)
class Skill:
    name: str
    level: int
    xp: int
    next_xp: int | None  # XP that reaches the next level; None at 10
    ways: tuple[str, ...]

    @property
    def to_go(self) -> int:
        return max(0, self.next_xp - self.xp) if self.next_xp else 0

    @property
    def share(self) -> float:
        """How far through this level."""
        if self.next_xp is None:
            return 1.0
        base = LEVELS[self.level - 1] if self.level else 0
        return (self.xp - base) / (self.next_xp - base)


def progress(xp: dict[str, int]) -> list[Skill]:
    out = []
    for name, actions in ACTIONS.items():
        have = xp.get(name, 0)
        level = sum(1 for n in LEVELS if have >= n)
        goal = LEVELS[level] if level < len(LEVELS) else None
        left = max(0, goal - have) if goal else 0
        ways = tuple(f"{action} {-(-left // each)} more time{'s' if -(-left // each) != 1 else ''}"
                     for action, each in actions) if goal else ()
        out.append(Skill(name, level, have, goal, ways))
    return out
