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
from .farm import Farm

TOOLS_FOR = {"mine": ("Pickaxe", "Rusty Sword", "Steel Smallsword", "Wooden Blade"), "fish": ("Bamboo Pole",)}
FREE_SLOTS = {"mine": 3, "fish": 3}
SHOP_STOPS = {"SeedShop": "pierre", "Blacksmith": "clint", "FishShop": "willy"}
STOP_NAMES = {"cc": "Community Center", "museum": "the Museum", "clint": "Clint's", "pierre": "Pierre's",
              "willy": "Willy's"}
WHO_STOP = {"Willy": "willy", "Clint": "clint", "Pierre": "pierre"}
HOME_PLACES = ("Farm", "FarmHouse", "Cellar", "Greenhouse", "Coop", "Barn", "Shed", "Junimo")
STOP_CHESTS = {"cc": "CommunityCenter chest", "mines": "Mine chest"}  # chests a stop already stands beside
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


def build(farm: Farm, plan: list[dict], spouse: str = "") -> dict:
    s = farm.save
    order = [p["id"] for p in plan]
    stops: dict[str, dict] = {}

    def stop(key: str, name: str) -> dict:
        return stops.setdefault(key, {"stop": name, "first": "", "items": [], "there": [], "gold": 0})

    def known(key: str) -> bool:
        return key in order

    taken: set[str] = set()  # one slot each
    at_stops = {STOP_CHESTS[k] for k in STOP_CHESTS if known(k)}
    stranded: dict[str, list[str]] = {}
    spare = []
    for r in sell.default(farm)["sell"]:
        stacks = [i for i in s.items if i.qualified_id == r["id"] and i.quality == r["q"]]
        here = sum(i.stack for i in stacks if is_home(i.where) or i.where in at_stops)
        for i in stacks:
            if not (is_home(i.where) or i.where in at_stops):
                stranded.setdefault(i.where.removesuffix(" chest"), []).append(f"{i.stack} {i.name}")
        if here:
            spare.append({**r, "count": here})

    if known("cc"):
        in_cc = {i.name for i in s.items if i.where == STOP_CHESTS["cc"]}
        for room in errands.community_center(farm)["rooms"]:
            for i in room["items"]:
                if not i["open"]:
                    continue
                label = f"{i['count']} {i['name']}" if i["count"] > 1 else i["name"]
                entry = stop("cc", STOP_NAMES["cc"])
                if i["name"] in in_cc:
                    entry["there"].append(label)
                else:
                    entry["items"].append(label)
                    taken.add(i["name"])
    if known("museum"):
        for t in errands.gunther(farm)["take"]:
            stop("museum", STOP_NAMES["museum"])["items"].append(t["name"])
            taken.add(t["name"])
    if known("clint"):
        for g in errands.clint(farm)["geodes"]:
            stop("clint", STOP_NAMES["clint"])["items"].append(f"{g['held']} {g['name']}")
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
            pick = _gift(farm, b["who"], spare)
            if pick:
                row, _taste = pick
                stop(f"talk:{b['who']}", b["who"])["items"].append(f"{row['name']}, a birthday gift")
                taken.add(row["name"])
                row["count"] -= 1

    buyers = Buyers(farm.data)
    ship: list[dict] = []
    sales: list[tuple[int, str, str]] = []  # gold, stop, item
    for r in spare:
        if not r["count"]:
            continue
        gold = r["count"] * r["each"]
        label = f"{r['count']} {r['name']}" if r["count"] > 1 else r["name"]
        key = next((SHOP_STOPS[b] for b in buyers.of(r.get("category")) if SHOP_STOPS.get(b) in order), None)
        if key:
            sales.append((gold, key, label))
        else:
            ship.append({"name": label, "gold": gold})

    keep = {t for p in plan for t in TOOLS_FOR.get(p["kind"], ())}
    bag = [i for i in s.items if i.where == "Backpack"]
    tool_names = [i.name for i in bag if i.name in keep]
    leave = [i.name for i in bag if i.name not in keep and i.name not in taken]
    free = max((FREE_SLOTS.get(p["kind"], 0) for p in plan), default=0)
    room = s.max_items - free - len(tool_names) - len(taken)
    sales.sort(reverse=True)
    for gold, _key, label in sales[max(0, room):]:
        ship.append({"name": label, "gold": gold, "no_room": True})
    for gold, key, label in sales[:max(0, room)]:
        entry = stop(key, STOP_NAMES[key])
        entry["items"].append(label)
        entry["gold"] += gold
    rank = {key: order.index(key) for key in stops if key in order}
    for key in stops:
        if key.startswith("give:"):
            rank[key] = len(order)
    ordered = sorted(stops.items(), key=lambda kv: rank.get(kv[0], len(order)))
    return {"leave": leave, "tools": tool_names, "stops": [v for _k, v in ordered if v["items"] or v["there"]],
            "left_behind": [{"place": farm.place(k), "items": v} for k, v in stranded.items()],
            "ship": ship, "ship_gold": sum(x["gold"] for x in ship), "dropped": [x["name"] for x in ship
                                                                                 if x.get("no_room")],
            "slots": {"used": len(tool_names) + len(taken) + min(max(0, room), len(sales)), "max": s.max_items,
                      "free_on_purpose": free}}


__all__ = ["SHOPS", "build"]
