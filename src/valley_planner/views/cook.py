"""What to cook for profit: each recipe's dish against what its ingredients are worth.

From the game's data at runtime: Data/CookingRecipes ("ingredients/unused/output/how it's learned/name": an
ingredient is an item id and count, or a negative category such as -5 any egg, -6 any milk, -4 any fish), the
dish's sale price (shipping bin or Pierre, the same price), and today's shop prices. An ingredient you hold is
costed at what you'd get for selling it instead (what cooking gives up); one you don't is costed at the cheapest
shop price today, or marked as not for sale. Cooking takes ingredients from your backpack and fridge, so items
in chests have to be moved first.
"""

from __future__ import annotations

from ..engine.unlocks import Unlocks
from ..facts.sell import sell_price
from .farm import REGULAR_SEED_SHOPS, Farm

CATEGORIES = {-4: "any fish", -5: "any egg", -6: "any milk", -7: "any cooking item", -75: "any vegetable",
              -79: "any fruit", -81: "any forage", -2: "any mineral"}


def view(farm: Farm) -> dict:
    s, held = farm.save, farm.held()
    objects = farm.data.asset("Data/Objects") or {}
    unlocks = Unlocks(farm)

    def value(oid: str) -> int:  # what one sells for, normal quality
        o = objects.get(oid) or {}
        return sell_price(int(o.get("Price") or 0), 0, farm.farmer, f"(O){oid}", o.get("Name") or "", o.get("Category"),
                          profit_margin=s.profit_margin)

    buy: dict[str, tuple[int, str]] = {}
    for o in farm.shops.offers(farm.when, profit_margin=s.profit_margin):
        oid = o.item.removeprefix("(O)")
        if o.item.startswith("(O)") and o.price and not o.recipe and o.available is not False \
                and (o.shop in REGULAR_SEED_SHOPS or o.shop in ("Saloon", "FishShop", "AnimalShop")):
            if oid not in buy or o.price < buy[oid][0]:
                buy[oid] = (o.price, o.shop)

    def held_of(cat: int) -> list[tuple[str, int]]:  # held items of a category, cheapest first
        items = [(q[3:], n) for q, n in held.items() if q.startswith("(O)")
                 and (objects.get(q[3:]) or {}).get("Category") == cat]
        return sorted(items, key=lambda x: value(x[0]))

    kitchen = s.house_upgrade >= 1
    from ..engine import cc
    bundles = {x["item"]: x["bundle"] for x in cc.plan(farm)["slots"] if x["status"] != "have"}
    quests = {f"(O){q['item_id']}": q["title"] for q in s.quests if q["item_id"] and not q["completed"]}
    rows = []
    for name, raw in (farm.data.asset("Data/CookingRecipes") or {}).items():
        f = raw.split("/")
        parts, out = f[0].split(), f[2].split()
        dish = out[0]
        made = int(out[1]) if len(out) > 1 else 1
        each = value(dish)
        ingredients, cost, can, sure = [], 0, 10 ** 6, True
        for i in range(0, len(parts) - 1, 2):
            iid, need = parts[i], int(parts[i + 1])
            if iid.lstrip("-").isdigit() and int(iid) < 0:
                options = held_of(int(iid))
                have = sum(n for _, n in options)
                unit = value(options[0][0]) if options else None
                label = CATEGORIES.get(int(iid), "any of a kind") + (f" ({farm.name('(O)' + options[0][0])})"
                                                                     if options else "")
                price = None
            else:
                have = held.get(f"(O){iid}", 0)
                price, shop = buy.get(iid, (None, ""))
                unit = value(iid) if have else price
                label = farm.name(f"(O){iid}")
            if unit is None:
                sure = False
            else:
                cost += unit * need
            can = min(can, have // need)
            ingredients.append({"name": label, "need": need, "have": have, "each": unit,
                                "buy": price if price is not None else None})
        learn = unlocks.get(f"recipe:{name}")
        profit = each * made - cost if sure else None
        wanted = [f"the {bundles[f'(O){dish}']} bundle"] if f"(O){dish}" in bundles else []
        wanted += [f"the quest {quests[f'(O){dish}']}"] if f"(O){dish}" in quests else []
        rows.append({"name": farm.name(f"(O){dish}"), "recipe": name, "known": name in s.cooking_recipes,
                     "wanted": wanted,
                     "learn": "" if name in s.cooking_recipes else (learn.how or "") + (
                         f" ({learn.gold:,}g)" if learn.gold else ""),
                     "sells": each * made, "cost": cost if sure else None, "profit": profit,
                     "can": can if can < 10 ** 6 else 0, "ingredients": ingredients})
    rows.sort(key=lambda r: (not r["known"], -(r["profit"] or -10 ** 6) * max(1, r["can"]) if r["can"] else 0,
                             -(r["profit"] if r["profit"] is not None else -10 ** 6)))
    cook_now = [r for r in rows if r["known"] and r["can"] and ((r["profit"] or 0) > 0 or r["wanted"])]
    return {"kitchen": kitchen, "kitchen_days": getattr(s, "house_upgrade_days", 0) if not kitchen else 0,
            "now": cook_now, "known": [r for r in rows if r["known"] and r not in cook_now],
            "learn": sorted([r for r in rows if not r["known"] and (r["profit"] or 0) > 0],
                            key=lambda r: -(r["profit"] or 0))[:15],
            "total": sum(r["profit"] * r["can"] for r in cook_now if (r["profit"] or 0) > 0),
            "losers": sum(1 for r in rows if r["known"] and r["profit"] is not None and r["profit"] < 0)}
