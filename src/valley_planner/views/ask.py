"""Ask: type an item, a villager or a fish and get one card with everything the planner knows about it."""

from __future__ import annotations

from ..facts.fish import FARM_TYPES
from ..facts.help_wanted import raw_pool
from ..facts.machines import Input
from ..facts.schedules import Situation, time_label
from ..facts.sell import sell_price
from ..facts.sources import _shop_label
from .farm import Farm, date_label

MAX_RESULTS = 8
QUALITIES = ((0, ""), (1, "silver"), (2, "gold"), (4, "iridium"))
CART_DAYS = 112


def search(farm: Farm, q: str) -> dict:
    """Matches for `q`: villagers first, then items (names starting with it before names containing it)."""
    needle = q.strip().lower()
    if len(needle) < 2:
        return {"query": q, "results": []}
    results = []
    for name, c in farm.data.asset("Data/Characters").items():
        shown = farm.data.text(c.get("DisplayName")) or name
        if c.get("BirthSeason") and needle in shown.lower():
            results.append({"kind": "villager", "id": name, "name": shown})
    items = []
    seen = set()
    for oid, info in farm.items.objects.items():
        if info.display.lower() in seen or info.category == -999 or not info.display:
            continue
        name = info.display.lower()
        if needle in name:
            seen.add(name)
            items.append((not name.startswith(needle), len(name), {"kind": "item", "id": f"(O){oid}",
                                                                  "name": info.display}))
    results += [r for *_, r in sorted(items, key=lambda t: t[:2])]
    return {"query": q, "results": results[:MAX_RESULTS]}


def item(farm: Farm, qid: str) -> dict:
    s, w = farm.save, farm.when
    oid = qid.removeprefix("(O)")
    info = farm.items.get(oid)
    if info is None:
        return {"kind": "item", "id": qid, "name": qid, "missing": True}
    card: dict = {"kind": "item", "id": qid, "name": info.display, "category": info.category, "type": info.type,
                  "held": farm.held().get(qid, 0)}
    card["sells"] = [{"quality": word, "each": sell_price(info.price, q, farm.farmer, qid, info.name, info.category,
                                                          info.type, profit_margin=s.profit_margin)}
                     for q, word in QUALITIES] if info.price else []

    today, other = [], []
    for o in farm.shops.offers(w, profit_margin=s.profit_margin, item=qid):
        row = {"shop": _shop_label(o.shop), "price": o.price, "trade": farm.name(o.trade_item) if o.trade_item else "",
               "trade_amount": o.trade_amount, "sure": o.available is True}
        (today if o.available is not False else other).append({**row, "when": o.condition})
    card["shops_today"], card["shops_other"] = today, other[:6]
    card["cart"] = [{"date": d.label, "price": i.price, "sure": i.sure}
                    for d in farm.cart.days(w, count_days=CART_DAYS, guarantee=s.cart_guarantee)
                    for i in d.items if i.item == qid][:5]

    crop = farm.crops.by_harvest.get(oid)
    if crop:
        card["grows"] = {"seed": farm.name(f"(O){crop.seed}"), "seasons": list(crop.seasons), "days": crop.grow,
                         "regrow": crop.regrow or None}
    as_seed = farm.crops.get(oid)
    if as_seed:
        card["plant"] = {"crop": farm.name(f"(O){as_seed.harvest}"), "seasons": list(as_seed.seasons),
                         "days": as_seed.grow, "regrow": as_seed.regrow or None}
    fish = farm.fish.by_id.get(oid)
    if fish:
        card["fish"] = _fish(farm, fish)

    made = []
    for mid in farm.data.asset("Data/Machines"):
        out = farm.machines.output(mid, Input(qid, 99), w, professions=set(s.professions))
        if out and out.item:
            o = farm.data.asset("Data/Objects").get(out.item.removeprefix("(O)")) or {}
            made.append({"machine": _bc_name(farm, mid), "product": out.name, "uses": out.uses,
                         "sells": sell_price(out.price, out.quality, farm.farmer, out.item, out.name,
                                             o.get("Category"), profit_margin=s.profit_margin, preserve=out.preserve),
                         "minutes": out.minutes, "days": out.days, "owned": s.machines.get(_bc_raw(farm, mid), 0)})
    card["machines"] = made

    if farm.gifts.giftable(qid):
        villagers = [n for n, c in farm.data.asset("Data/Characters").items() if c.get("BirthSeason")]
        tastes = {v: farm.gifts.taste(v, qid) for v in villagers}
        card["gifts"] = {t: [v for v, x in tastes.items() if x == t] for t in ("love", "like", "dislike", "hate")}
    card["bundles"] = [{"bundle": f.bundle.display, "room": f.bundle.room, "count": f.ingredient.stack,
                        "quality": f.ingredient.quality, "open": farm.bundles.notes_shown(f.bundle.area)}
                       for f in farm.bundles.fits(qid, info.category, 4, shown_only=False)]
    card["help_wanted"] = oid in raw_pool(w.season, w.day, w.year, mine_lowest=w.mine_lowest,
                                          vault="ccVault" in s.mail, crafting=set(s.crafting_recipes))
    card["museum"] = info.type in ("Arch", "Minerals") and ("donated" if oid in s.museum else "not donated")
    return card


def _fish(farm: Farm, fish) -> dict:
    w = farm.when
    spots = []
    for sp in farm.fish.open_spots(fish, w, include_conditional=True):
        where = farm.place(sp.location) + (f" (floor {sp.floor})" if sp.floor else "")
        spots.append(where)
    other = sorted({s for sp in fish.spots for s in sp.seasons} - {w.season})
    return {"trap": fish.trap, "water": fish.water,
            "times": [f"{time_label(a)}–{time_label(b)}" for a, b in fish.times], "weather": fish.weather,
            "min_level": fish.min_level, "difficulty": fish.difficulty, "here_now": sorted(set(spots)),
            "other_seasons": other, "farm": FARM_TYPES.get(farm.save.farm_type, "")}


def villager(farm: Farm, name: str) -> dict:
    s, w = farm.save, farm.when
    c = farm.data.asset("Data/Characters").get(name) or {}
    f = s.friends.get(name)
    card: dict = {"kind": "villager", "id": name, "name": farm.data.text(c.get("DisplayName")) or name,
                  "birthday": date_label((c.get("BirthSeason") or "").lower(), c.get("BirthDay") or 0)
                  if c.get("BirthSeason") else "",
                  "hearts": f.hearts if f else 0, "points": f.points if f else 0,
                  "gifts_this_week": f.gifts_this_week if f else 0, "gifted_today": bool(f and f.gifts_today),
                  "talked_today": bool(f and f.talked_today), "status": f.status if f else "", "met": f is not None}
    held = farm.held()
    loves = farm.gifts.lists(name)
    card["loves"] = [{"name": farm.name(f"(O){i}"), "held": held.get(f"(O){i}", 0)} for i in loves["love"]
                     if farm.gifts.giftable(f"(O){i}")]
    card["loves"].sort(key=lambda x: (-bool(x["held"]), x["name"]))
    card["likes_held"] = sorted(farm.name(f"(O){i}") for i in loves["like"] if held.get(f"(O){i}"))[:12]
    days = farm.schedules.today(name, Situation(w, hearts=card["hearts"], raining=s.wet,
                                                married=bool(f and f.status == "Married")))
    card["today"] = [{"key": d.key, "chance": d.chance,
                      "stops": [{"time": time_label(st.time), "place": farm.place(st.location)} for st in d.stops]}
                     for d in days]
    return card


def _bc_raw(farm: Farm, mid: str) -> str:
    return (farm.data.asset("Data/BigCraftables").get(mid.removeprefix("(BC)")) or {}).get("Name") or mid


def _bc_name(farm: Farm, mid: str) -> str:
    b = farm.data.asset("Data/BigCraftables").get(mid.removeprefix("(BC)")) or {}
    return farm.data.text(b.get("DisplayName")) or b.get("Name") or mid
