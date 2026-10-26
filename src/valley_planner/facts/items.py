"""Items from the game's own data: names, prices, categories, edibility.

Prices follow StardewValley.Object.salePrice: an object's base price is twice
its Data/Objects price, times (1 + 0.25 x quality), rounded down; six early
resources (Wood, Stone, Coal and the ores) have their own Year-1 and later
prices; only seeds and saplings scale with the farm's profit-margin setting.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

# Object.salePrice: these sell for a fixed amount, cheaper in Year 1
FIXED_SALE_PRICE = {"388": (10, 50), "390": (20, 100), "382": (120, 250), "378": (80, 160), "380": (150, 250),
                    "384": (350, 750)}  # id -> (year 1, later)
SEED_CATEGORY = -74
TEA_SAPLING = "251"


@dataclass(frozen=True)
class ItemInfo:
    id: str  # unqualified object id
    name: str  # internal name (stable, English)
    display: str  # resolved display name
    price: int
    category: int
    type: str
    edibility: int
    tags: tuple[str, ...]


class Items:
    def __init__(self, data):
        self.data = data

    @cached_property
    def objects(self) -> dict[str, ItemInfo]:
        out = {}
        for oid, o in self.data.asset("Data/Objects").items():
            out[oid] = ItemInfo(
                id=oid, name=o.get("Name") or oid, display=self.data.text(o.get("DisplayName")) or o.get("Name") or oid,
                price=int(o.get("Price") or 0), category=int(o.get("Category") or 0), type=o.get("Type") or "",
                edibility=int(o.get("Edibility") if o.get("Edibility") is not None else -300),
                tags=tuple(o.get("ContextTags") or ()))
        return out

    @cached_property
    def by_name(self) -> dict[str, str]:
        """Internal or display name -> id (the first id wins when two items share a name)."""
        out: dict[str, str] = {}
        for oid, info in sorted(self.objects.items(), key=lambda kv: (not kv[0].isdigit(), kv[0].zfill(6))):
            out.setdefault(info.name, oid)
            out.setdefault(info.display, oid)
        return out

    @cached_property
    def saplings(self) -> set[str]:
        """Object.isSapling: the Tea Sapling, wild tree seeds and fruit tree saplings."""
        wild = {(t.get("SeedItemId") or "").removeprefix("(O)") for t in self.data.asset("Data/WildTrees").values()}
        return {TEA_SAPLING} | set(self.data.asset("Data/FruitTrees")) | (wild - {""})

    def get(self, item_id: str) -> ItemInfo | None:
        return self.objects.get(item_id.removeprefix("(O)"))

    def name(self, item_id: str) -> str:
        info = self.get(item_id)
        return info.display if info else item_id

    def applies_profit_margin(self, item_id: str) -> bool:
        info = self.get(item_id)
        return bool(info and (info.category == SEED_CATEGORY or info.id in self.saplings))

    def sale_price(self, item_id: str, quality: int = 0, *, year: int = 1, profit_margin: float = 1.0,
                   ignore_profit_margin: bool = False) -> int:
        """What a shop charges as an item's standard price (Object.salePrice)."""
        oid = item_id.removeprefix("(O)")
        if oid in FIXED_SALE_PRICE:
            return FIXED_SALE_PRICE[oid][0 if year <= 1 else 1]
        info = self.get(oid)
        if info is None:
            return 0
        price = int(info.price * 2 * (1 + quality * 0.25))
        if not ignore_profit_margin and self.applies_profit_margin(oid):
            price = int(max(1.0, price * profit_margin))
        return price
