"""What to cook for profit: each recipe's dish against what its ingredients are worth.

From the game's data at runtime: Data/CookingRecipes ("ingredients/unused/output/how it's learned/name": an
ingredient is an item id and count, or a negative category such as -5 any egg, -6 any milk, -4 any fish), the
dish's sale price (shipping bin or Pierre, the same price), and today's shop prices. Cooking takes any quality, so
each dish is costed with the cheapest units you hold, at what they'd sell for instead (what cooking gives up):
the first dish uses the cheapest, the last the dearest, so a recipe can pay for a few and then stop. An
ingredient you don't hold is costed at the cheapest shop price today, or marked as not for sale. Cooking takes
ingredients from your backpack and fridge, so items in chests have to be moved first.
"""

from __future__ import annotations

from ..engine.unlocks import Unlocks
from ..facts.sell import item_sell_price, sell_price
from .farm import REGULAR_SEED_SHOPS, Farm

QUALITIES = (0, 1, 2, 4)  # normal, silver, gold, iridium
NO_QUALITY = {-25, -7}  # cooking ingredients bought in shops (flour, sugar, oil...) and dishes: always normal
CATEGORIES = {-4: "any fish", -5: "any egg", -6: "any milk", -7: "any cooking item", -75: "any vegetable",
              -79: "any fruit", -81: "any forage", -2: "any mineral"}


def view(farm: Farm) -> dict:
    s = farm.save
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

    # every unit you hold, at what it would sell for (its own quality): cooking takes any quality, so you'd use
    # the cheapest first
    units: dict[str, list[tuple[int, str]]] = {}
    for it in s.items:
        if it.qualified_id.startswith("(O)") and not it.preserve:
            o = objects.get(it.id) or {}
            v = item_sell_price(it, farm.farmer, profit_margin=s.profit_margin, data_price=int(o.get("Price") or 0))
            units.setdefault(it.id, []).extend([(v, it.id)] * min(it.stack, 999))

    def stock(iid: str) -> list[tuple[int, str]]:  # (value, item id), cheapest first
        if iid.lstrip("-").isdigit() and int(iid) < 0:
            cat = int(iid)
            out = [u for oid, us in units.items() if (objects.get(oid) or {}).get("Category") == cat for u in us]
        else:
            out = list(units.get(iid, []))
        return sorted(out)

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
        ingredients, can, sure, stocks = [], 10 ** 6, True, []
        for i in range(0, len(parts) - 1, 2):
            iid, need = parts[i], int(parts[i + 1])
            have_units = stock(iid)
            category = iid.lstrip("-").isdigit() and int(iid) < 0
            price = None if category else buy.get(iid, (None, ""))[0]
            if category:
                label = CATEGORIES.get(int(iid), "any of a kind") + (
                    f" ({farm.name('(O)' + have_units[0][1])})" if have_units else "")
            else:
                label = farm.name(f"(O){iid}")
            if not have_units and price is None:
                sure = False
            can = min(can, len(have_units) // need)
            stocks.append((need, have_units, price))
            ingredients.append({"name": label, "need": need, "have": len(have_units),
                                "each": have_units[0][0] if have_units else price, "buy": price})
        can = can if can < 10 ** 6 else 0
        # dish by dish, each using the cheapest units left: the first is the best deal, the last the worst
        gains = []
        if sure:
            for k in range(max(1, can)):
                cost_k = 0
                for need, have_units, price in stocks:
                    take = have_units[k * need:(k + 1) * need]
                    cost_k += sum(v for v, _ in take) + (need - len(take)) * (price or 0)
                gains.append(each * made - cost_k)
        cost = each * made - gains[0] if gains else None
        by_quality = _by_quality(farm, objects, parts, buy, each * made, set(units))
        learn = unlocks.get(f"recipe:{name}")
        profit = gains[0] if gains else None
        wanted = [f"the {bundles[f'(O){dish}']} bundle"] if f"(O){dish}" in bundles else []
        wanted += [f"the quest {quests[f'(O){dish}']}"] if f"(O){dish}" in quests else []
        rows.append({"name": farm.name(f"(O){dish}"), "recipe": name, "known": name in s.cooking_recipes,
                     "wanted": wanted,
                     "learn": "" if name in s.cooking_recipes else (learn.how or "") + (
                         f" ({learn.gold:,}g)" if learn.gold else ""),
                     "sells": each * made, "cost": cost, "profit": profit,
                     "by_quality": by_quality, "worst": gains[can - 1] if can > 1 else profit,
                     "worth": sum(1 for g in gains[:can] if g > 0),
                     "gain_all": sum(g for g in gains[:can] if g > 0), "can": can, "ingredients": ingredients})
    rows.sort(key=lambda r: (not r["known"], -(r["profit"] or -10 ** 6) * max(1, r["can"]) if r["can"] else 0,
                             -(r["profit"] if r["profit"] is not None else -10 ** 6)))
    cook_now = [r for r in rows if r["known"] and r["can"] and ((r["profit"] or 0) > 0 or r["wanted"])]
    return {"kitchen": kitchen, "kitchen_days": getattr(s, "house_upgrade_days", 0) if not kitchen else 0,
            "now": cook_now, "known": [r for r in rows if r["known"] and r not in cook_now],
            "learn": sorted([r for r in rows if not r["known"] and (r["profit"] or 0) > 0],
                            key=lambda r: -(r["profit"] or 0))[:15],
            "total": sum(r["gain_all"] for r in cook_now),
            "losers": sum(1 for r in rows if r["known"] and r["profit"] is not None and r["profit"] < 0)}


def _by_quality(farm: Farm, objects: dict, parts: list[str], buy: dict, sells: int,
                held: set[str]) -> dict[int, int | None]:
    """The dish's gain if its ingredients are all of one quality (what each would sell for instead). An 'any of'
    ingredient takes the cheapest item of its kind; flour, sugar, oil and the like have no quality, and one you'd
    have to buy is costed at its shop price."""
    out: dict[int, int | None] = {}
    for q in QUALITIES:
        cost = 0
        for i in range(0, len(parts) - 1, 2):
            iid, need = parts[i], int(parts[i + 1])
            if iid.lstrip("-").isdigit() and int(iid) < 0:
                kind = [k for k, o in objects.items() if o.get("Category") == int(iid) and int(o.get("Price") or 0) > 0]
                if not kind:
                    cost = None
                    break
                iid = min(kind, key=lambda k: int(objects[k].get("Price") or 0))
            o = objects.get(iid) or {}
            if o.get("Category") in NO_QUALITY:  # held: what it'd sell for; else what it costs to buy
                unit = None if iid in held else buy.get(iid, (None,))[0]
                unit = unit if unit is not None else sell_price(int(o.get("Price") or 0), 0, farm.farmer, f"(O){iid}",
                                                                o.get("Name") or "", o.get("Category"),
                                                                profit_margin=farm.save.profit_margin)
            else:
                unit = sell_price(int(o.get("Price") or 0), q, farm.farmer, f"(O){iid}", o.get("Name") or "",
                                  o.get("Category"), profit_margin=farm.save.profit_margin)
            cost += unit * need
        out[q] = None if cost is None else sells - cost
    return out
