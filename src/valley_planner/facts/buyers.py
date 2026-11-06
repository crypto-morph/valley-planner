"""Who buys what (Data/Shops SalableItemTags, 1.6.15).

A shop buys an item when one of its tags matches the item's category tag, so Pierre takes crops and forage, Willy
fish, Clint gems and metal, Robin Wood and Stone, Marlon monster loot. The shipping bin takes the lot, overnight.
"""

from __future__ import annotations

from functools import cached_property

SHOPS = {"SeedShop": "Pierre's", "FishShop": "Willy's", "Blacksmith": "Clint's", "AnimalShop": "Marnie's",
         "Carpenter": "Robin's", "AdventureShop": "the Adventurer's Guild"}
CATEGORY_TAGS = {
    -2: "gem", -4: "fish", -5: "egg", -6: "milk", -7: "cooking", -8: "crafting", -12: "minerals", -14: "meat",
    -15: "metal_resources", -16: "building_resources", -17: "sell_at_pierres", -18: "sell_at_pierres_and_marnies",
    -19: "fertilizer", -21: "bait", -22: "tackle", -23: "sell_at_fish_shop", -25: "ingredients", -26: "artisan_goods",
    -28: "monster_loot", -74: "seeds", -75: "vegetable", -79: "fruits", -80: "flowers", -81: "greens",
}


class Buyers:
    def __init__(self, data):
        self.data = data

    @cached_property
    def tags(self) -> dict[str, set[str]]:
        shops = self.data.asset("Data/Shops")
        return {sid: set(shops[sid].get("SalableItemTags") or []) for sid in SHOPS if sid in shops}

    def of(self, category: int | None) -> list[str]:
        """The shops that buy this category, best known first."""
        tag = f"category_{CATEGORY_TAGS.get(category, '')}"
        return [sid for sid in SHOPS if tag in self.tags.get(sid, ())]
