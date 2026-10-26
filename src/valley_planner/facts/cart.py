"""The Traveling Cart's stock on any day, worked out from the save the way the game rolls it (1.6.15).

When the cart is out: the Forest on days where day-of-month % 7 % 5 == 0
(Fridays and Sundays), plus the Night Market and Desert Festival days from
Data/PassiveFestivals (when their condition holds). All three open the same
"Traveler" shop, so a day's stock is the same wherever it's opened.

What it sells (ShopBuilder.GetShopStock, in our words): one random number
generator per day, seeded from (days played, game id / 2), is shared by the
whole shop. The Data/Shops "Traveler" entries are taken in order:
- An entry whose condition fails is skipped without touching the generator
  (SYNCED_RANDOM conditions roll their own, separately seeded generators).
- RANDOM_ITEMS <type> <min> <max>: every item of that type, in data order,
  gets one Next() as its sort key; a stable sort by key gives the shuffle.
  Then, in that order, items are kept if: not excluded from random sale,
  a numeric id within min..max, a price above 0 (@requirePrice), not
  already offered (AvoidRepeat), and passing the entry's PerItemCondition;
  the first MaxItems are taken.
- An entry with RandomItemId picks one with Next(count).
- Then for each item, in order: the shop's price modifiers, the entry's
  price modifiers, then its stock modifiers. Every modifier with a random
  amount rolls Next(count) for it first, then checks its condition (RANDOM
  conditions roll NextDouble on the same generator). "Stack" mode applies
  each in turn; "Maximum"/"Minimum" keep the largest/smallest result.
- Base price: the entry's Price, or else (UseObjectDataPrice) the object's
  raw Price field, or else the item's sell price (furniture: its data price).
  The Traveler shop applies no profit margin.
The Year-1 Red Cabbage Seeds entry needs VisitsUntilY1Guarantee to be 0: the
save holds today's value; it drops by one on each later Forest cart day and
Night Market day while it is 0 or more.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from functools import cached_property

from .conditions import When, check, date_of, split
from .items import FIXED_SALE_PRICE
from .rng import NetRandom, day_save_random

SHOP = "Traveler"
GUARANTEE_FIELD = "VisitsUntilY1Guarantee"


@dataclass(frozen=True)
class CartItem:
    item: str  # qualified id: (O)266, (F)1234…
    name: str
    price: int
    stock: int
    entry: str  # the Data/Shops entry Id it came from
    sure: bool = True  # False when an earlier entry's condition couldn't be decided and it rolls the generator


@dataclass(frozen=True)
class CartDay:
    days_played: int
    season: str
    day: int
    year: int
    place: str  # Forest / NightMarket / DesertFestival
    items: tuple[CartItem, ...]

    @property
    def label(self) -> str:
        return f"{self.season.capitalize()} {self.day}, Year {self.year}"


def _forest_day(day: int) -> bool:
    return day % 7 % 5 == 0


def _apply(value: float, modifiers, mode: str, rng: NetRandom) -> float:
    """Utility.ApplyQuantityModifiers."""
    if not modifiers:
        return value
    best = None
    for m in modifiers:
        amount = m.get("Amount") or 0.0
        if m.get("RandomAmount"):
            amount = rng.choose(m["RandomAmount"])
        if not _modifier_condition(m.get("Condition"), rng):
            continue
        result = _modify(best if (best is not None and mode not in ("Maximum", "Minimum")) else value,
                         m.get("Modification"), amount)
        if mode == "Maximum":
            best = result if best is None or result > best else best
        elif mode == "Minimum":
            best = result if best is None or result < best else best
        else:
            best = result
    return value if best is None else best


def _modify(value: float, how: str, amount: float) -> float:
    return {"Add": value + amount, "Subtract": value - amount, "Multiply": value * amount,
            "Divide": value / amount if amount else value, "Set": amount}.get(how, value)


def _modifier_condition(condition: str | None, rng: NetRandom) -> bool:
    """The queries the cart's modifiers use; anything else is an error, not a guess."""
    if not condition:
        return True
    for tokens in split(condition):
        key = tokens[0].lstrip("!").upper()
        if key != "RANDOM" or len(tokens) < 2 or any(t.startswith("@") for t in tokens[2:]):
            raise ValueError(f"cart modifier condition not supported: {condition}")
        result = rng.next_double() < float(tokens[1])
        if result == tokens[0].startswith("!"):
            return False
    return True


def _per_item(condition: str | None, obj: dict) -> bool:
    """PerItemCondition queries about the item (Target)."""
    if not condition:
        return True
    category = int(obj.get("Category") or 0)
    for tokens in split(condition):
        key = tokens[0].lstrip("!").upper()
        args = tokens[2:] if len(tokens) > 1 and tokens[1] in ("Target", "Input") else tokens[1:]
        if key == "ITEM_HAS_EXPLICIT_OBJECT_CATEGORY":
            result = category < 0
        elif key == "ITEM_CATEGORY":
            result = str(category) in args if args else category != 0
        elif key == "ITEM_OBJECT_TYPE":
            result = (obj.get("Type") or "") in args
        else:
            raise ValueError(f"cart per-item condition not supported: {condition}")
        if result == tokens[0].startswith("!"):
            return False
    return True


class Cart:
    def __init__(self, data):
        self.data = data

    @cached_property
    def shop(self) -> dict:
        return self.data.asset("Data/Shops")[SHOP]

    @cached_property
    def objects(self) -> dict:
        return self.data.asset("Data/Objects")

    @cached_property
    def furniture(self) -> dict[str, list[str]]:
        return {k: v.split("/") for k, v in self.data.asset("Data/Furniture").items()}

    @cached_property
    def big_craftables(self) -> dict:
        return self.data.asset("Data/BigCraftables")

    def _name(self, qid: str) -> str:
        kind, _, iid = qid[1:].partition(")")
        if kind == "O" and iid in self.objects:
            o = self.objects[iid]
            return self.data.text(o.get("DisplayName")) or o.get("Name") or iid
        if kind == "BC" and iid in self.big_craftables:
            b = self.big_craftables[iid]
            return self.data.text(b.get("DisplayName")) or b.get("Name") or iid
        if kind == "F" and iid in self.furniture:
            f = self.furniture[iid]
            return self.data.text(f[7]) if len(f) > 7 and f[7] else f[0]
        return qid

    def _pool(self, kind: str, year: int) -> list[tuple[str, dict | list, bool, int]]:
        """(id, data, excluded from random sale, sell price) for every item of a type, in data order."""
        if kind == "O":
            out = []
            for oid, o in self.objects.items():
                if oid in FIXED_SALE_PRICE:
                    price = FIXED_SALE_PRICE[oid][0 if year <= 1 else 1]
                else:
                    price = int(int(o.get("Price") or 0) * 2)
                out.append((oid, o, bool(o.get("ExcludeFromRandomSale")), price))
            return out
        if kind == "F":
            return [(fid, f, len(f) > 10 and f[10].strip().lower() == "true",
                     int(f[5]) if len(f) > 5 and f[5].lstrip("-").isdigit() else 0)
                    for fid, f in self.furniture.items()]
        raise ValueError(f"cart RANDOM_ITEMS type not supported: {kind}")

    def _random_items(self, query: str, entry: dict, rng: NetRandom, year: int, seen: set[str]) -> list[str]:
        parts = query.split()
        kind = parts[1].strip("()")
        lo, hi = -(2**31), 2**31 - 1
        if len(parts) > 2 and parts[2].lstrip("-").isdigit():
            lo = int(parts[2])
            if len(parts) > 3 and parts[3].lstrip("-").isdigit():
                hi = int(parts[3])
        ranged = (lo, hi) != (-(2**31), 2**31 - 1)
        flags = {p.lower() for p in parts[2:] if p.startswith("@")}
        pool = self._pool(kind, year)
        keyed = sorted(((rng.next(), i) for i in range(len(pool))), key=lambda k: k[0])
        out: list[str] = []
        limit = entry.get("MaxItems")
        for _, i in keyed:
            iid, raw, excluded, price = pool[i]
            if "@israndomsale" in flags and excluded:
                continue
            if ranged and (not iid.lstrip("-").isdigit() or not lo <= int(iid) <= hi):
                continue
            if "@requireprice" in flags and price <= 0:
                continue
            qid = f"({kind}){iid}"
            if entry.get("AvoidRepeat") and (qid in seen or qid in out):
                continue
            if kind == "O" and not _per_item(entry.get("PerItemCondition"), raw):
                continue
            out.append(qid)
            if limit is not None and len(out) >= limit:
                break
        return out

    def _base_price(self, entry: dict, qid: str, year: int) -> float:
        if (entry.get("Price") if entry.get("Price") is not None else -1) >= 0:
            return entry["Price"]
        if entry.get("TradeItemId"):
            return 0
        kind, _, iid = qid[1:].partition(")")
        if kind == "O":
            o = self.objects[iid]
            if entry.get("UseObjectDataPrice"):
                return int(o.get("Price") or 0)
            return FIXED_SALE_PRICE[iid][0 if year <= 1 else 1] if iid in FIXED_SALE_PRICE \
                else int(o.get("Price") or 0) * 2
        if kind == "F":
            f = self.furniture.get(iid) or []
            return int(f[5]) if len(f) > 5 and f[5].lstrip("-").isdigit() else 0
        raise ValueError(f"cart price for {qid} not supported")

    def stock(self, when: When) -> tuple[CartItem, ...]:
        """What the Traveler shop sells on `when` (whether or not the cart is out that day).
        An entry whose condition we can't decide is taken as absent; if it would have rolled the
        generator, everything after it is marked not sure."""
        rng = day_save_random(when.days_played, when.game_id, legacy=when.legacy_random)
        seen: set[str] = set()
        sure = True
        out: list[CartItem] = []
        for entry in self.shop.get("Items") or []:
            ok = check(entry.get("Condition"), when)
            if ok is False:
                continue
            if ok is None:
                probe = copy.deepcopy(rng)
                self._entry(entry, probe, when.year, set(seen))
                sure = sure and probe.draws == rng.draws
                continue
            for qid, price, stock in self._entry(entry, rng, when.year, seen):
                out.append(CartItem(qid, self._name(qid), price, stock, entry.get("Id") or qid, sure))
        return tuple(out)

    def _entry(self, entry: dict, rng: NetRandom, year: int, seen: set[str]) -> list[tuple[str, int, int]]:
        """One shop entry's (item, price, stock), rolling `rng` as the game does."""
        shop = self.shop
        item_id = entry.get("ItemId") or ""
        if entry.get("RandomItemId"):
            picks = [rng.choose(entry["RandomItemId"])]
        elif item_id.startswith("RANDOM_ITEMS"):
            picks = self._random_items(item_id, entry, rng, year, seen)
        elif item_id.startswith("("):
            picks = [item_id]
        else:
            raise ValueError(f"cart item query not supported: {item_id}")
        out = []
        for qid in picks:
            price = self._base_price(entry, qid, year)
            if not entry.get("IgnoreShopPriceModifiers"):
                price = _apply(price, shop.get("PriceModifiers"), shop.get("PriceModifierMode"), rng)
            price = _apply(price, entry.get("PriceModifiers"), entry.get("PriceModifierMode"), rng)
            stock = entry.get("AvailableStock", -1)
            if not entry.get("IsRecipe"):
                stock = int(_apply(stock, entry.get("AvailableStockModifiers"), entry.get("AvailableStockModifierMode"),
                                   rng))
            if entry.get("AvoidRepeat") and qid in seen:
                continue
            seen.add(qid)
            out.append((qid, int(price), stock if stock >= 0 else 2**31 - 1))
        return out

    def _festival_days(self, when: When) -> dict[tuple[str, int], str]:
        out = {}
        for fid in ("NightMarket", "DesertFestival"):
            fest = self.data.asset("Data/PassiveFestivals").get(fid)
            if not fest:
                continue
            season = (fest.get("Season") or "").lower()
            for d in range(fest["StartDay"], fest["EndDay"] + 1):
                out[(season, d)] = fid
        return out

    def days(self, when: When, *, count_days: int = 112, guarantee: int = -1):
        """Cart days from `when` (today included) for `count_days`, with their stock.
        `guarantee`: the save's VisitsUntilY1Guarantee (today's value)."""
        festivals = self._festival_days(when)
        g = guarantee
        for dp in range(when.days_played, when.days_played + count_days):
            season, day, year = date_of(dp)
            today = dp == when.days_played
            fest = festivals.get((season, day))
            forest = _forest_day(day)
            if not today and g >= 0 and (forest or fest == "NightMarket"):
                g -= 1
            w = when.on(dp, world_fields={**when.world_fields, GUARANTEE_FIELD: g})
            places = (["Forest"] if forest else []) + ([fest] if fest else [])
            if fest:
                cond = self.data.asset("Data/PassiveFestivals")[fest].get("Condition")
                if check(cond, w) is False:
                    places.remove(fest)
            if places:
                yield CartDay(dp, season, day, year, places[0] if len(places) == 1 else " & ".join(places),
                              self.stock(w))

    def find(self, when: When, item_ids: set[str], **kw) -> list[tuple[CartDay, CartItem]]:
        """Each upcoming cart day that sells any of these (qualified) items."""
        return [(d, i) for d in self.days(when, **kw) for i in d.items if i.item in item_ids]
