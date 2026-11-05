"""The quick ways around the valley: the minecarts and the warp totems (1.6.15).

Minecarts (Data/Minecarts): the network opens when the host has ccBoilerRoom, and each stop may have its own
condition (the Mines needs the landslide cleared, the Quarry the Crafts Room). They're free.

Warp totems (Object.totemWarpForReal): using one spends it and puts you on a fixed tile; the Farm's tile depends on
the farm map, so it's left out here. Totems are made from recipes learned at Foraging levels (Data/CraftingRecipes)
or bought (Data/Shops): the Casino sells the Farm one for 1,000 Qi Coins, the Desert Trader the Desert one and its
recipe, Island Trader and Volcano shops the others.

This says what the player has to travel with; how much time a trip saves belongs to the day's route.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from .conditions import When, check, split

NETWORK = "Default"
TOTEMS = {  # item id -> (recipe, where it puts you, the tile)
    "688": ("Warp Totem: Farm", "Farm", None),
    "689": ("Warp Totem: Mountains", "Mountain", (31, 20)),
    "690": ("Warp Totem: Beach", "Beach", (20, 4)),
    "261": ("Warp Totem: Desert", "Desert", (35, 43)),
    "886": ("Warp Totem: Island", "IslandSouth", (11, 11)),
}


@dataclass(frozen=True)
class Stop:
    id: str
    location: str
    tile: tuple[int, int]


@dataclass(frozen=True)
class Totem:
    item: str  # qualified id
    name: str
    location: str
    tile: tuple[int, int] | None
    materials: tuple[tuple[str, int], ...]  # one craft's
    skill: tuple[str, int] | None  # the level that teaches the recipe; None if it's only got from a shop
    known: bool  # the recipe is known
    held: int


class Travel:
    def __init__(self, data):
        self.data = data

    @cached_property
    def network(self) -> dict:
        return self.data.asset("Data/Minecarts")[NETWORK]

    @cached_property
    def recipes(self) -> dict:
        return self.data.asset("Data/CraftingRecipes")

    def minecarts(self, when: When) -> list[Stop]:
        """The stops running for this farm: none until the Boiler Room is done."""
        if check(self.network.get("UnlockCondition"), when) is not True:
            return []
        return [Stop(d["Id"], d["TargetLocation"], (d["TargetTile"]["X"], d["TargetTile"]["Y"]))
                for d in self.network["Destinations"] if check(d.get("Condition"), when) is True]

    def totem(self, item: str, *, known: set[str], held: dict[str, int]) -> Totem:
        name, location, tile = TOTEMS[item]
        fields = self.recipes[name].split("/")
        parts = fields[0].split()
        materials = tuple((parts[i], int(parts[i + 1])) for i in range(0, len(parts) - 1, 2))
        learn = split(fields[4]) if len(fields) > 4 else []
        skill = (learn[0][1], int(learn[0][2])) if learn and learn[0][0] == "s" else None
        return Totem(f"(O){item}", name, location, tile, materials, skill, name in known, held.get(f"(O){item}", 0))

    def totems(self, save, held: dict[str, int]) -> list[Totem]:
        return [self.totem(i, known=save.crafting_recipes, held=held) for i in TOTEMS]
