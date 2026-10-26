"""What each shop sells and for how much, from Data/Shops, priced the way the game prices it.

StardewValley.Internal.ShopBuilder (GetShopStock, GetBasePrice), in our words:
1. Base price: the entry's Price, or else the item's standard price
   (Object.salePrice, without the profit margin). Trade-item entries cost
   no gold.
2. Times the farm's profit margin when the entry, else the shop, else the
   item says profit margins apply (for objects: only seeds and saplings).
3. Times 1.5 when Pierre's Missing Stock List lets him sell a seed out of
   season (the entry fails only on its season, and the list is unlocked).
4. The shop's PriceModifiers, unless the entry ignores them; then the
   entry's own. Each modifier counts only if its condition holds.
5. Rounded down.
Entries whose ItemId is a query (random items, flavoured goods…) aren't plain
offers and are left out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .conditions import SEASON_KEYS, When, check
from .items import Items

PLAIN_ID = re.compile(r"^\((O|BC|F|W|H|S|P|B|T|WP|FL|TR)\)[\w .'-]+$")
MISSING_STOCK_MAIL = "PierreStocklist"


@dataclass(frozen=True)
class Offer:
    shop: str
    item: str  # qualified id
    price: int  # in gold; 0 if paid with a trade item
    trade_item: str | None
    trade_amount: int
    condition: str
    available: bool | None  # on the given day: True / False / None (can't tell)
    out_of_season: bool  # via Pierre's Missing Stock List (at 1.5x)
    recipe: bool = False  # the entry sells the recipe for this item, not the item


def _modify(value: float, modifiers, mode: str | None, when: When) -> float:
    """Utility.ApplyQuantityModifiers: Stack applies each in turn; Minimum/Maximum keep the extreme."""
    if not modifiers:
        return value
    result = None
    for m in modifiers:
        holds = check(m.get("Condition"), when)
        if not holds:  # False, or can't tell: leave it out
            continue
        amount = float(m.get("Amount") or 0)
        op = (m.get("Modification") or "Multiply").lower()
        base = value if mode in ("Minimum", "Maximum") else (value if result is None else result)
        applied = {"add": base + amount, "subtract": base - amount, "multiply": base * amount,
                   "divide": base / amount if amount else base, "set": amount}.get(op, base)
        if mode == "Minimum":
            result = applied if result is None else min(result, applied)
        elif mode == "Maximum":
            result = applied if result is None else max(result, applied)
        else:
            result = applied
    return value if result is None else result


class Shops:
    def __init__(self, data, items: Items | None = None):
        self.data = data
        self.items = items or Items(data)

    def offers(self, when: When, *, profit_margin: float = 1.0, item: str | None = None) -> list[Offer]:
        """Every plain offer in every shop, checked against `when`. `item`: one qualified id only."""
        out = []
        missing_stock = when.has_or_will_get_mail(MISSING_STOCK_MAIL)
        for shop_id, shop in self.data.asset("Data/Shops").items():
            for entry in shop.get("Items") or []:
                qid = (entry.get("ItemId") or "").strip()
                if not PLAIN_ID.match(qid) or (item and qid != item):
                    continue
                cond = entry.get("Condition") or ""
                available = check(cond, when)
                out_of_season = False
                if available is False and shop_id == "SeedShop" and missing_stock:
                    if check(cond, when, ignore=SEASON_KEYS):
                        available, out_of_season = True, True
                out.append(Offer(
                    shop=shop_id, item=qid,
                    price=self.price(shop, entry, qid, when, profit_margin=profit_margin, out_of_season=out_of_season),
                    trade_item=entry.get("TradeItemId"), trade_amount=int(entry.get("TradeItemAmount") or 1),
                    condition=cond, available=available, out_of_season=out_of_season,
                    recipe=bool(entry.get("IsRecipe"))))
        return out

    def price(self, shop: dict, entry: dict, qid: str, when: When, *, profit_margin: float = 1.0,
              out_of_season: bool = False) -> int:
        base = float(entry["Price"]) if (entry.get("Price") if entry.get("Price") is not None else -1) >= 0 else -1.0
        is_object = qid.startswith("(O)")
        oid = qid[3:] if is_object else ""
        if base < 0:
            if entry.get("TradeItemId"):
                base = 0.0
            elif is_object and entry.get("UseObjectDataPrice"):
                info = self.items.get(oid)
                base = float(info.price if info else 0)
            elif is_object:
                base = float(self.items.sale_price(oid, year=when.year, ignore_profit_margin=True))
            else:
                base = 0.0  # non-object items without a price aren't modelled
        margin = entry.get("ApplyProfitMargins")
        if margin is None:
            margin = shop.get("ApplyProfitMargins")
        if margin is None:
            margin = is_object and self.items.applies_profit_margin(oid)
        if margin:
            base *= profit_margin
        if out_of_season:
            base *= 1.5
        if not entry.get("IgnoreShopPriceModifiers"):
            base = _modify(base, shop.get("PriceModifiers"), shop.get("PriceModifierMode"), when)
        base = _modify(base, entry.get("PriceModifiers"), entry.get("PriceModifierMode"), when)
        return int(base)
