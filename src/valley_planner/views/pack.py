"""The pack list: what to leave, what to take, and which stop each thing is for.

It starts from this morning's backpack and its size, and the day's stops in order. What you can carry is what's in
your bag or stored at home; a chest at a stop already has its things there, so they take no slot; anything in a chest
the route doesn't pass is listed as left behind, not planned with. Bundle items go to the Community
Center, new finds to the Museum, geodes to Clint, requests to whoever asked, a gift to whoever you're courting, and
spares (by the Sell tab's own keep rules) to the first shop on the route that buys them. Anything that can't be sold
on the way, or doesn't fit, goes in the shipping bin. Tools stay only if a stop needs them. If the bag still can't
take it all, the cheapest sales drop out first. Days that pick things up keep slots free.
"""

from __future__ import annotations

from ..facts.buyers import SHOPS, Buyers
from . import errands, quests, sell
from . import keep as keep_rules
from .farm import Farm

TOOLS_FOR = {"mine": ("Pickaxe", "Rusty Sword", "Steel Smallsword", "Wooden Blade"), "fish": ("Bamboo Pole",)}
FREE_SLOTS = {"mine": 3, "fish": 3}
SHOP_STOPS = {"SeedShop": "pierre", "Blacksmith": "clint", "FishShop": "willy"}
STOP_NAMES = {"cc": "Community Center", "museum": "the Museum", "clint": "Clint's", "pierre": "Pierre's",
              "willy": "Willy's"}
PURPOSE = {"cc": "hand in at the Community Center", "museum": "donate at the Museum", "clint": "crack at Clint's"}
WHO_STOP = {"Willy": "willy", "Clint": "clint", "Pierre": "pierre"}
HOME_PLACES = ("Farm", "FarmHouse", "Cellar", "Greenhouse", "Coop", "Barn", "Shed", "Junimo")
# chests a stop already stands beside
STOP_CHESTS = {"cc": "CommunityCenter chest", "mines": "Mine chest", "cc_mines": "Mine chest"}
GIFT_LIMIT = 400  # gold: dearer things are a choice for you, not an automatic gift


def is_home(where: str) -> bool:
    """Your bag, or storage on the farm: what you can load up from before leaving."""
    return where == "Backpack" or where.split()[0] in HOME_PLACES


def _gift(farm: Farm, who: str, spare: list[dict]) -> dict | None:
    """The cheapest spare they'd like most."""
    ranked = []
    for r in spare:
        taste = farm.gifts.taste(who, r["id"]) if farm.gifts.giftable(r["id"]) else ""
        if taste in ("love", "like") and r["each"] < GIFT_LIMIT and r["count"]:
            ranked.append((taste != "love", r["each"], r, taste))
    return min(ranked, key=lambda x: x[:2])[2:] if ranked else None


QUALITY_WORDS = {1: "silver", 2: "gold", 4: "iridium"}


def build(farm: Farm, plan: list[dict], spouse: str = "", hold: dict[str, str] | None = None,
          sold: dict | None = None) -> dict:
    s = farm.save
    order = [p["id"] for p in plan]
    stops: dict[str, dict] = {}

    def stop(key: str, name: str) -> dict:
        return stops.setdefault(key, {"key": key, "stop": name, "first": "", "items": [], "there": [], "gold": 0,
                                      "rows": [], "short": []})

    def reach_before(key: str) -> set[str]:
        """Chests you pass before reaching stop `key`: home and the bag always, plus chests at earlier stops."""
        before = order[:order.index(key)] if key in order else order
        return {STOP_CHESTS[k] for k in before if k in STOP_CHESTS}

    def take(key: str, name: str, count: int, label: str) -> bool:
        """Add an item to stop `key` with where each part comes from. False (and a 'short' line instead) when the
        chests you pass on the way don't hold enough, so it waits for another day."""
        entry = stop(key, STOP_NAMES.get(key, key.split(":", 1)[-1]))
        ok_places = reach_before(key) | ({STOP_CHESTS[key]} if key in STOP_CHESTS else set())  # and the one there
        parts: dict[str, list] = {}
        qid = next((it.qualified_id for it in s.items if it.name == name and it.qualified_id), "")
        for it in s.items:
            if it.name == name and (is_home(it.where) or it.where in ok_places or it.where.endswith(" chest")):
                where = farm.where_label(it.where, it.chest).replace(f"({farm.place('Farm')})", "(farm)")
                where = where.removeprefix("the ").replace(" (", ", ").removesuffix(")")
                part = parts.setdefault(where, [0, is_home(it.where) or it.where in ok_places, it.where])
                part[0] += it.stack
        usable = sum(n for n, ok, _raw in parts.values() if ok)
        rows = [{"where": w, "count": n, "on_route": ok, "raw": raw}
                for w, (n, ok, raw) in sorted(parts.items(), key=lambda kv: not kv[1][1])]
        if count and usable < count:
            after = order[order.index(key) + 1:] if key in order else []
            later = {STOP_CHESTS[k] for k in after if k in STOP_CHESTS}
            off = [r for r in rows if not r["on_route"]]
            where = "; ".join(f"{r['count']} in {r['where']}" for r in off)
            comes = any(r["raw"] in later for r in off)
            entry["short"].append({"label": label, "have": usable, "need": count,
                                   "text": f"{usable} of {count} with you" + (
                                       f"; {where} (later today)" if comes else f"; {where}" if where else "")})
            return False
        entry["items"].append(label)
        # what to take from where: the chest at the stop first, then the rest from the nearest you pass
        here = STOP_CHESTS.get(key)
        left, src = count or usable, []
        for r in sorted((r for r in rows if r["on_route"]), key=lambda r: r["raw"] != here):
            n = min(left, r["count"])
            if n:
                src.append({"where": r["where"], "count": r["count"], "take": n, "there": r["raw"] == here})
                left -= n
        purpose = PURPOSE.get(key) or (f"give to {entry['stop']}" if key.startswith(("talk:", "give:"))
                                       else entry["stop"])
        entry["rows"].append({"label": label, "name": name, "from": src, "for": purpose,
                              "icon": farm.icon(qid) if qid else None})
        return True

    def known(key: str) -> bool:
        return key in order

    taken: set[str] = set()  # one slot each
    at_stops = {STOP_CHESTS[k] for k in STOP_CHESTS if known(k)}
    stranded: dict[str, list[str]] = {}
    spare = []
    for r in (sold or sell.default(farm))["sell"]:
        stacks = [i for i in s.items if i.qualified_id == r["id"] and i.quality == r["q"]]
        here = sum(i.stack for i in stacks if is_home(i.where) or i.where in at_stops)
        for i in stacks:
            if not (is_home(i.where) or i.where in at_stops):
                stranded.setdefault(i.where.removesuffix(" chest"), []).append(f"{i.stack} {i.name}")
        if here:  # never more than the sell plan offers: the rest is held back for something
            spare.append({**r, "count": min(here, r["count"])})

    if known("cc"):
        for room in errands.community_center(farm)["rooms"]:
            for i in room["items"]:
                if not i["open"] or i["name"] in (hold or {}):
                    continue
                label = f"{i['count']} {i['name']}" if i["count"] > 1 else i["name"]
                entry = stop("cc", STOP_NAMES["cc"])
                there = sum(it.stack for it in s.items if it.name == i["name"] and it.where == STOP_CHESTS["cc"])
                if there >= i["count"]:
                    entry["there"].append(label)
                elif take("cc", i["name"], i["count"], label):
                    taken.add(i["name"])
    if known("museum"):
        for t in errands.gunther(farm)["take"]:
            if take("museum", t["name"], 1, t["name"]):
                taken.add(t["name"])
    if known("clint"):
        for g in errands.clint(farm)["geodes"]:
            if take("clint", g["name"], 0, f"{g['held']} {g['name']}"):
                taken.add(g["name"])
    for q in quests.view(farm)["quests"]:
        if q["deliver_to"] and q["item"]:
            key = WHO_STOP.get(q["deliver_to"], f"give:{q['deliver_to']}")
            stop(key, STOP_NAMES.get(key, q["deliver_to"]))["items"].append(f"{q['item']} for the request")
            taken.add(q["item"])
    if known("quest") and (board := next(p for p in plan if p["id"] == "quest")):
        name, _, rest = board["title"].removeprefix("Help Wanted: ").partition(" for ")
        key = WHO_STOP.get(rest, f"give:{rest}")
        entry = stop(key, STOP_NAMES.get(key, rest))
        entry["first"] = "Take the Help Wanted from the board first"
        entry["items"].append(f"{name} for the request")
        taken.add(name)
    friend = s.friends.get(spouse)
    if spouse and (friend is None or friend.gifts_this_week < 2) and not (friend and friend.gifts_today):
        pick = _gift(farm, spouse, spare)
        if pick:
            row, taste = pick
            stop(f"talk:{spouse}", spouse)["items"].append(f"{row['name']}, a gift {spouse} {taste}s")
            taken.add(row["name"])
            row["count"] -= 1

    for b in errands.birthdays(farm, days=0)["birthdays"]:
        if known(f"talk:{b['who']}") and b["who"] != spouse:
            pick = keep_rules.birthday_gift(farm, b["who"])  # the gift the keep rules hold back for it
            if pick and take(f"talk:{b['who']}", farm.name(pick[0]), 1, f"{farm.name(pick[0])}, a birthday gift"):
                taken.add(farm.name(pick[0]))

    buyers = Buyers(farm.data)
    selling = {p["id"] for p in plan if p.get("sells")}  # shops you sell at today; the rest goes in the bin
    ship: list[dict] = []
    sales: list[tuple[int, str, str, dict]] = []  # gold, stop, item, the row for the bin if the bag is full

    def row(r: dict, gold: int, label: str) -> dict:
        """A Shipping bin line: the words, plus the parts a table shows (item, its picture, count, price)."""
        return {"name": label, "gold": gold, "item": r["name"], "count": r["count"], "each": r["each"],
                "q": r.get("q", 0), "quality": QUALITY_WORDS.get(r.get("q", 0), ""), "icon": farm.icon(r["id"])}

    for r in spare:
        if not r["count"]:
            continue
        gold = r["count"] * r["each"]
        label = f"{r['count']} {r['name']}" if r["count"] > 1 else r["name"]
        key = next((SHOP_STOPS[b] for b in buyers.of(r.get("category")) if SHOP_STOPS.get(b) in selling), None)
        if key:
            sales.append((gold, key, label, row(r, gold, label)))
        else:
            ship.append(row(r, gold, label))

    keep = {t for p in plan for t in TOOLS_FOR.get(p["kind"], ())}
    bag = [i for i in s.items if i.where == "Backpack"]
    tool_names = [i.name for i in bag if i.name in keep]
    leave = [i.name for i in bag if i.name not in keep and i.name not in taken]
    free = max((FREE_SLOTS.get(p["kind"], 0) for p in plan), default=0)
    room = s.max_items - free - len(tool_names) - len(taken)
    sales.sort(key=lambda x: x[0], reverse=True)
    for _gold, _key, _label, line in sales[max(0, room):]:
        ship.append({**line, "no_room": True})
    for gold, key, label, line in sales[:max(0, room)]:
        entry = stop(key, STOP_NAMES[key])
        entry["items"].append(label)
        entry["gold"] += gold
        left, src = line["count"], []  # spares to sell come from your bag and the chests at home, at their quality
        for it in sorted((i for i in s.items if i.name == line["item"] and i.quality == line["q"]
                          and is_home(i.where)), key=lambda i: i.where != "Backpack"):
            n = min(left, it.stack)
            if n > 0:
                where = farm.where_label(it.where, it.chest).replace(f"({farm.place('Farm')})", "(farm)")
                src.append({"where": where.removeprefix("the ").replace(" (", ", ").removesuffix(")"),
                            "count": it.stack, "take": n, "there": False, "quality": line["quality"]})
                left -= n
        entry["rows"].append({"label": label, "name": line["item"], "icon": line["icon"], "from": src,
                              "for": f"sell at {STOP_NAMES[key]}"})
    rank = {key: order.index(key) for key in stops if key in order}
    for key in stops:
        if key.startswith("give:"):
            rank[key] = len(order)
    ordered = sorted(stops.items(), key=lambda kv: rank.get(kv[0], len(order)))
    kept = [v for _k, v in ordered if v["items"] or v["there"] or v["short"]]
    return {"leave": leave, "tools": tool_names, "stops": kept,
            "left_behind": [{"place": farm.place(k), "items": v} for k, v in stranded.items()],
            "ship": ship, "ship_gold": sum(x["gold"] for x in ship), "dropped": [x["name"] for x in ship
                                                                                 if x.get("no_room")],
            "slots": {"used": len(tool_names) + len(taken) + min(max(0, room), len(sales)), "max": s.max_items,
                      "free_on_purpose": free}}


__all__ = ["SHOPS", "build"]
