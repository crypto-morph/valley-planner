"""Today's plan: a timed list you can just follow, or recalculate from wherever you've got to.

It's limited by the three things that run out: the clock, your energy and what's reachable. Must-dos come first
(watering, then planting), then the stops worth the walk, best value for the minutes first. What doesn't fit is
listed with the reason. Recalculate with the time, energy and place you're at, and ticked stops left out.

Energy comes from the game's own sums (facts/tools.py): the can and hoe are charged as far as the job fills them, and
picking a crop stops the clock, so only the steps between crops count. FINISH: no planned stop starts after this,
which leaves an hour to get home and into bed by midnight, the last time that costs nothing tomorrow.

The person you're courting is a stop with a time window, from their schedule. Spare energy at the end goes on
whichever of fishing or chopping you ask for, suggested rather than timed to the minute.
"""

from __future__ import annotations

import json
import math
import re

from ..engine import cc
from ..engine.unlocks import BRIDGE_WOOD, KITCHEN
from ..facts import (
    artifact_spots,
    bubbles,
    comforts,
    geodes,
    help_wanted,
    mine_day,
    mine_floors,
    romance,
    skills,
    tools,
)
from ..facts.buyers import Buyers
from ..facts.fish import Fish
from ..facts.garbage import CANS
from ..facts.items import FIXED_SALE_PRICE
from ..facts.schedules import Situation
from ..facts.walk import FARMHOUSE_DOOR, NEW_PLAYER_PACE, OUTDOORS, polylines
from . import crops, errands, levels, pack, picking, quests, sell
from .farm import Farm

TILE_ENERGY = 2  # a tile hand-watered at Farming 0, for the odd job
TILE_MINUTES = 1.6
HARVEST_MINUTES = 0.3  # a crop: the clock stops while you pick, so it's the step to the next one
RESERVE = 10  # energy never spent: touching 0 halves tomorrow
START = 6 * 60 + 10
FINISH = 23 * 60
QUEST_VALUE = 500
SWEETHEART_VALUE = 400
CAST_MINUTES = 20  # fishing: an average cast and catch, from a real game's first days
TREE_MINUTES, TREE_WOOD = 15, 17  # a tree and its stump
INTRODUCTIONS_VALUE = 300  # each hello on the way to +100 with everyone you've met
BUNDLE_VALUE = 200
GOOD_BIN = 50  # gold a bin's item has to be worth to be a stop
SPARE_DETOUR = 15  # minutes: the longest walk for something no bundle needs
GEODES = ("(O)535", "(O)536", "(O)537", "(O)749")
GEODE_PRICE = 25
PIERRE_SEEDS = ("472", "473", "474", "475", "427", "477", "429", "476", "273", "479", "480", "481", "482", "483", "484",
                "485", "487", "488", "490", "491", "493", "299", "301", "302", "453", "455", "431", "425")
PACE_DAYS = 7
PACE_MIN_MINUTES = 60  # a shorter stretch says too little about pace
MIN_REPLANT = 8
BIRTHDAY_VALUE = 300
HEAVY_WATERING = 40  # crops: the point where sprinklers start to matter most
TV_MINUTES = 10
BERRIES = {"spring": "(O)296", "fall": "(O)410"}  # Salmonberry, Blackberry
SHOP_TRIP = 100  # gold of spares that makes Pierre's worth a stop on its own
FISH_TRIP = 150  # gold of fish that makes Willy's worth the walk
CART_AHEAD = 10  # days of cart visits to hold gold back for
KEEP_GOLD = 100  # never spend the last of it on seeds
MINE_DOOR = ("Mountain", 54, 5)
MINES_MINUTES = 180
MINES_MIN_ENERGY = 80  # not worth the trip below this
MINES_LEAVE = 20
KEEP = ("(O)92", "(O)771", "(O)330", "(O)390", "(O)388", "(O)709")  # Sap, Fiber, Clay, Stone, Wood, Hardwood
SELL_CATEGORIES = (-4, -81, -75, -79, -80, -2, -12, -5, -6, -7, -26, -27)  # fish, forage, crops, gems, food, artisan
PASSING = 12  # tiles: a spare this close to the route is optional extra cash, not a detour


def clock(minutes: int) -> str:
    h, m = minutes // 60, minutes % 60
    return f"{(h - 1) % 12 + 1}:{m:02d} {'AM' if h % 24 < 12 else 'PM'}"


def _minutes(game_time: int | None) -> int | None:
    return None if game_time is None else game_time // 100 * 60 + game_time % 100


def _price(farm: Farm, qid: str) -> int:
    info = farm.items.get(qid.removeprefix("(O)"))
    return info.price if info else 0


def _forage_why(farm: Farm, qid: str, held: dict[str, int]) -> tuple[str, int]:
    fits = farm.bundles.fits(qid, None, 0, shown_only=False)
    if fits and not held.get(qid):
        return f"keep it for the {fits[0].bundle.display} bundle", BUNDLE_VALUE
    return "a spare: sell or gift it", _price(farm, qid)


LOST_BOOK_VALUE = 50  # a library book: no gold, but the museum's reward track and lore


def _dig_spots(farm: Farm, held: dict[str, int]) -> list[dict]:
    """Worm tiles and seed spots you can reach today, with what digging each one gives (seeded by tile and day)."""
    try:
        spots = artifact_spots.spots(farm.save, farm.data)
    except Exception:  # noqa: BLE001 - a forecast we can't make shouldn't stop the day plan
        return []
    out = []
    for sp in spots:
        if sp.reachable is False or sp.location not in OUTDOORS:
            continue
        sure = [d for d in sp.drops if d.sure and d.id]
        if not sure:
            continue
        value, whys = 0, []
        for d in sure:
            if d.id == "(O)102":
                value += LOST_BOOK_VALUE
                whys.append("a Lost Book for the library")
                continue
            why, v = _forage_why(farm, d.id, held)
            value += v * (1 if v == BUNDLE_VALUE else d.count)
            whys.append(why if v == BUNDLE_VALUE else f"{d.count} {d.name}, about {v * d.count}g")
        names = " and ".join(f"{d.count} {d.name}" if d.count > 1 else d.name for d in sp.drops)
        kind = "worm tile" if sp.kind == "artifact" else "seed spot"
        out.append({"id": f"dig:{sp.location}:{sp.tile[0]}:{sp.tile[1]}", "kind": "forage",
                    "title": f"Hoe the {kind}: {names}" + ("" if sp.sure else " (probably)"),
                    "why": "; ".join(whys), "at": (sp.location, *sp.tile), "minutes": 1, "value": value})
    return out


def _stops(farm: Farm, held: dict[str, int], spouse: str = "") -> list[dict]:
    s = farm.save
    out = []
    for f in s.forage:
        why, value = _forage_why(farm, f.item, held)
        out.append({"id": f"forage:{f.location}:{f.tile[0]}:{f.tile[1]}", "kind": "forage",
                    "title": f"Pick up {f.name}", "why": why, "at": (f.location, *f.tile), "minutes": 1,
                    "value": value})
    out += _dig_spots(farm, held)
    fest = farm.hours.festivals
    today = (farm.when.season, farm.when.day) in fest or (farm.when.season, farm.when.day + 1) in fest
    quest = help_wanted.quest_today(s, farm.data, festival=today)
    if quest and quest["kind"] == "delivery" and held.get(f"(O){quest['item']}"):  # only if you can fill it
        qid = f"(O){quest['item']}"
        gold = 3 * _price(farm, qid)
        dear = quest["who"] == spouse
        out.append({"id": "quest", "kind": "quest", "title": f"Help Wanted: {farm.name(qid)} for {quest['who']}",
                    "why": f"{gold}g and 150 friendship"
                           f"{', nearly two gifts and outside the weekly two' if dear else ''};"
                           " take it from the board outside Pierre's first",
                    "at": ("Town", 42, 58), "minutes": 1, "value": QUEST_VALUE + (SWEETHEART_VALUE if dear else 0)})
    marks = {m.name.removeprefix("Garbage:"): m for m in farm.walker.landmarks["Town"]}
    for can in farm.bins.day(s, farm.when):
        if can.loot and can.loot.item and _price(farm, can.loot.item) >= GOOD_BIN and can.can in marks:
            m = marks[can.can]
            out.append({"id": f"bin:{can.can}", "kind": "bin", "title": f"Bin at {CANS[can.can]}: {can.loot.label}",
                        "why": "check nobody's close by first", "at": ("Town", m.x, m.y), "minutes": 1,
                        "value": _price(farm, can.loot.item) * can.loot.stack})
    return out


def _building_door(farm: Farm, location: str) -> tuple | None:
    """The outdoor tile outside a building, so someone indoors can still be a stop."""
    for place in OUTDOORS:
        door = _door(farm, place, location)
        if door:
            return door
    return None


def _person(farm: Farm, name: str, why: str, value: int) -> list[dict]:
    """A stop for each stretch of their day, indoors or out, so the plan catches whichever fits."""
    s = farm.save
    f = s.friends.get(name)
    if name not in farm.data.asset("Data/Characters") or (f is not None and f.talked_today):
        return []
    days = farm.schedules.today(name, Situation(farm.when, hearts=f.hearts if f else 0, raining=s.wet))
    if len(days) != 1:  # a coin-flip day: nowhere certain to send you
        return []
    stops = days[0].stops
    out = []
    for a, b in zip(stops, [*stops[1:], None], strict=False):
        at = (a.location, a.x, a.y) if a.location in OUTDOORS else _building_door(farm, a.location)
        if not at:
            continue
        indoors = "" if a.location in OUTDOORS else f"inside {farm.place(a.location)}, "
        begin, end = _minutes(a.time), _minutes(b.time) if b else FINISH
        out.append({"id": f"talk:{name}", "kind": "talk", "title": f"Talk to {name}",
                    "why": f"{indoors}there until {clock(end)}; {why}", "minutes": 2, "at": at, "value": value,
                    "from": begin, "until": end})
    return out


def _sweetheart(farm: Farm, name: str) -> list[dict]:
    """A daily talk, unless they're at the cap a Bouquet lifts: then talking adds nothing and skipping costs
    nothing, since nobody you could date loses points at 8 hearts."""
    f = farm.save.friends.get(name)
    if f and f.status not in ("Dating", "Engaged", "Married") and f.points >= romance.CAP_FRIEND:
        return []
    return _person(farm, name, "a daily talk keeps the hearts moving", SWEETHEART_VALUE)


LUAU_DAY = 11  # Summer 11


def luau_note(farm: Farm) -> str:
    """The Luau soup pays every townsperson you've met, so keep one good thing for it (Event.governorTaste)."""
    s = farm.save
    if s.season != "summer" or s.day > LUAU_DAY:
        return ""
    objects = farm.data.asset("Data/Objects")
    best = None
    for it in s.items:
        o = objects.get(it.qualified_id.removeprefix("(O)")) if it.qualified_id.startswith("(O)") else None
        if not o or it.category == -7 or int(o.get("Edibility") or -300) == -300:
            continue
        price, edible = int(o.get("Price") or 0), int(o.get("Edibility") or 0)
        if (it.quality >= 2 and price >= 160) or (it.quality == 1 and price >= 300 and edible > 10):
            score = 120
        elif edible >= 20 or price >= 100 or (it.quality >= 1 and price >= 70):
            score = 60
        else:
            continue
        if not best or (score, price) > best[:2]:
            best = (score, price, farm.name(it.qualified_id), it.quality)
    if not best:
        return ("The Luau on Summer 11: keep a gold crop worth 160g or more for the soup, for +120 with everyone in"
                " town.")
    quality = {1: "silver ", 2: "gold ", 4: "iridium "}.get(best[3], "")
    return f"Keep your {quality}{best[2]} for the Luau soup on Summer 11: +{best[0]} with everyone in town."


def _birthdays(farm: Farm, spouse: str = "") -> list[dict]:
    """Anyone with a birthday today, if you hold something they'd like: a gift counts 8 times."""
    out = []
    for b in errands.birthdays(farm, days=0)["birthdays"]:
        gift = (b["loved"] or b["liked"] or [""])[0]
        if b["who"] != spouse and gift:
            out += _person(farm, b["who"], f"it's their birthday, and {gift} counts 8 times", BIRTHDAY_VALUE)
    return out


def wood_wanted(farm: Farm) -> int:
    """The Wood the big jobs still want: open bundles, the Beach bridge and the kitchen."""
    s = farm.save
    wood = sum(i.stack for b in farm.bundles.all for i in b.open_ingredients if i.item == "(O)388")
    wood += 0 if "beachBridgeFixed" in s.flags else BRIDGE_WOOD
    return wood + (0 if s.house_upgrade >= 1 else dict(KITCHEN[1])["388"])


def wood_note(farm: Farm, trees: int) -> dict | None:
    """Energy to spare buys Wood for nothing; with none left, Robin's is the cheap way, above all in Year 1.
    What the Wood is for, with dates, comes from the goals route when the note is opened (wood_uses)."""
    short = wood_wanted(farm) - farm.held().get("(O)388", 0)
    if short <= 0:
        return None
    s = farm.save
    price = FIXED_SALE_PRICE["388"][0 if s.year == 1 else 1]
    per_tree = tools.tree(s.tool_levels.get("Axe", 0), s.skills.get("foraging", 0))
    chop = (f"A tree and its stump give about {TREE_WOOD} Wood for about {round(per_tree)} energy and "
            f"{TREE_MINUTES} minutes, so the {short} would take about {math.ceil(short / TREE_WOOD)} trees. ")
    buy = (f"Robin sells Wood at {price}g each" + (" this year (it's 50g from Year 2)" if s.year == 1 else "")
           + f": the {short} would cost {short * price:,}g.")
    if not trees:
        return {"text": f"{short} Wood short for the bundles, bridge and kitchen, and no energy left to chop: "
                        f"buy it from Robin at {price}g.",
                "why": chop + buy, "lazy": "wood", "trees": trees}
    rest = short - trees * TREE_WOOD
    return {"text": f"{short} Wood short for the bundles, bridge and kitchen: chop your {trees} spare trees today "
                    "and replant a seed where each stood.",
            "why": chop + (f"That leaves {rest}. " if rest > 0 else "") + buy, "lazy": "wood", "trees": trees}


def wood_uses(route: dict) -> list[dict]:
    """The goals route's jobs that take Wood, soonest first: {what, wood, by, on (days played), goal}."""
    out, seen = [], set()
    for o in route.get("objectives", []):
        for step in o.get("steps", []):
            for need in step.get("needs", []):
                wood = next((int(m.split()[0]) for m in need.get("materials", []) if m.endswith(" Wood")), 0)
                if wood and need["key"] not in seen and need.get("state") == "new":
                    seen.add(need["key"])
                    out.append({"what": need["label"], "wood": wood, "by": need.get("ready", ""),
                                "on": need.get("on") or 0, "goal": o.get("label", "")})
    return sorted(out, key=lambda x: x["on"])


WOOD_SOON, WOOD_URGENT = 7, 2  # days before the next Wood job when the note turns amber, then red


def wood_plan(farm: Farm, uses: list[dict], trees: int = 0) -> dict | None:
    """The Wood note from the goals' own dates: only the next job you can't cover yet, how long you have, and
    what to do about it. Calm until a week before; the full schedule, with a running total, goes in `rows`."""
    s = farm.save
    held = farm.held().get("(O)388", 0)
    today = s.days_played
    price = FIXED_SALE_PRICE["388"][0 if s.year == 1 else 1]
    need, rows, nxt = 0, [], None
    for u in uses:
        need += u["wood"]
        row = {**u, "date": farm.label(u["on"]).rsplit(",", 1)[0] if u["on"] else u["by"], "total": need,
               "covered": need <= held}
        rows.append(row)
        if nxt is None and need > held:
            nxt = row
    if nxt is None:
        return None
    short, days = nxt["total"] - held, max(0, nxt["on"] - today)
    level = "urgent" if days <= WOOD_URGENT else "soon" if days <= WOOD_SOON else "later"
    when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
    job = re.sub(r"^(build|craft|repair) ", "", nxt["what"])
    what = f"{job} ({nxt['date']}, {when})"
    per_tree = tools.tree(s.tool_levels.get("Axe", 0), s.skills.get("foraging", 0))
    if level == "later":
        text = f"Wood: next needed for {what}. You're {short} short; plenty of time."
        act = (f"Chop trees on days with energy to spare (about {TREE_WOOD} Wood a tree for {round(per_tree)} "
               f"energy), or buy the rest from Robin nearer the time: {short} costs {short * price:,}g.")
    else:
        do = (f"chop your {trees} spare trees today" + (f" and buy the other {short - trees * TREE_WOOD} from "
              f"Robin ({(short - trees * TREE_WOOD) * price:,}g)" if short > trees * TREE_WOOD else "")
              if trees else f"buy it from Robin ({short * price:,}g)")
        text = f"Wood: {short} more for {what}: {do}."
        act = (f"Chopping costs about {round(per_tree)} energy a tree for about {TREE_WOOD} Wood. Robin's shop is in "
               "the Mountains, north of Town.")
    cheap = (f" Wood is cheap this year at {price}g (50g from Year 2), so buying is fine when energy is "
             "better spent on crops." if s.year == 1 else "")
    return {"text": text, "why": act + cheap, "level": level, "rows": rows, "held": held}


def doomed_note(farm: Farm, lost: list) -> str:
    """Crops that die at the season's end before they ripen: watering them is wasted energy."""
    if not lost:
        return ""
    names: dict[str, int] = {}
    for c in lost:
        name = farm.name(f"(O){c.harvest_id}")
        names[name] = names.get(name, 0) + 1
    words = " and ".join(f"{n} {name}" for name, n in names.items())
    return (f"Don't water {words}: {'it' if len(lost) == 1 else 'they'} can't ripen before the season ends, so "
            "the can's energy is wasted. Pull them up and sow something quicker, or leave them.")


def sprinkler_note(farm: Farm, watering: int) -> str:
    """Watering is the biggest daily cost, so say what stands between you and sprinklers."""
    s, held = farm.save, farm.held()
    if watering < HEAVY_WATERING or "Sprinkler" not in s.crafting_recipes:
        return ""
    copper, iron = held.get("(O)334", 0), held.get("(O)335", 0)
    can = min(copper, iron)
    if can:
        return f"You can craft {can} Sprinklers now: each saves about 8 energy a day."
    missing = "Iron Bars" if not iron else "Copper Bars"
    return f"{missing} are all that's stopping Sprinklers. Each saves about 8 energy a day."


def geode_forecast(farm: Farm, held: dict[str, int]) -> list[dict]:
    """The next few cracks, for each kind of geode you hold: the result hangs on the running count alone."""
    s = farm.save
    cracked = s.stats.get("geodesCracked", 0)
    kinds = [g for g in geodes.GEODES if held.get(f"(O){g}")]
    out = []
    for offset in range(sum(held.get(f"(O){g}", 0) for g in kinds)):
        count = cracked + offset + 1
        each = []
        for g in kinds:
            got = geodes.crack(farm.data, g, count, int(s.unique_id), s.farmer_id, deepest=s.deepest_mine_level,
                               legacy=s.legacy_random, artifact_found="artifactFound" in s.mail)
            each.append({"geode": farm.name(f"(O){g}"), "item": farm.name(got.item), "stack": got.stack})
        out.append({"crack": count, "gives": each})
    return out


def cart_budget(farm: Farm) -> int:
    """Gold to hold back for the coming cart visits' bundle items, each counted once."""
    s, wanted = farm.save, {}
    slots = {x["item"]: x for x in cc.plan(farm)["slots"] if x["status"] != "have"}
    for d in farm.cart.days(farm.when, count_days=CART_AHEAD, guarantee=s.cart_guarantee):
        for i in d.items:
            if i.sure and i.item in slots and i.item not in wanted and not farm.held().get(i.item) \
                    and cc.cart_only(slots[i.item], i.stock):
                wanted[i.item] = i.price
    return sum(wanted.values())


def seed_advice(farm: Farm, money: int, tiles: int) -> list[dict]:
    """What to buy with `money` for `tiles`: the best gold a tile a day that still ripens this season, then the next
    best for what's left."""
    s = farm.save
    left = 28 - s.day
    objects = farm.data.asset("Data/Objects")
    options = []
    for seed, c in farm.crops.by_seed.items():
        sold = (objects.get(c.harvest) or {}).get("Price") if hasattr(c, "harvest") else None
        if sold is None or s.season not in c.seasons or c.grow > left or seed not in PIERRE_SEEDS:
            continue
        cost = 2 * int((objects.get(seed) or {}).get("Price") or 0)
        rounds = max(1, left // c.grow)
        options.append(((int(sold) - cost) * rounds / left, cost, seed, objects[c.harvest]["Name"]))
    out = []
    purse, room = money - KEEP_GOLD - min(money // 2, cart_budget(farm)), tiles
    for _rate, cost, _seed, name in sorted(options, reverse=True):
        n = min(room, purse // cost) if cost else 0
        if n > 0:
            out.append({"name": name, "count": n, "gold": n * cost})
            purse -= n * cost
            room -= n
    return out


def _clint(farm: Farm, held: dict[str, int]) -> list[dict]:
    """Geodes waiting to be cracked, if there's the gold for it."""
    n = sum(held.get(g, 0) for g in GEODES)
    shop = next((x for x in farm.hours_today() if x["id"] == "Blacksmith"), {})
    door = next((m for m in farm.walker.landmarks["Town"] if m.name == "Blacksmith"), None)
    if not n or shop.get("closed") or door is None or farm.save.money < GEODE_PRICE:
        return []
    return [{"id": "clint", "kind": "shop", "title": f"Clint: crack {n} geode{'s' if n != 1 else ''}",
             "why": f"{GEODE_PRICE}g each; keep anything new for the Museum", "at": ("Town", door.x, door.y + 1),
             "minutes": 5, "value": BUNDLE_VALUE, "from": 9 * 60, "until": 16 * 60}]


def _mines(farm: Farm, power: int) -> list[dict]:
    """A trip down the Mines, if the day has the energy for one, with what today's luck and floors hold."""
    s, w = farm.save, farm.when
    if "landslideDone" not in s.mail and s.days_played < 5:
        return []
    if power < MINES_MIN_ENERGY or s.deepest_mine_level >= 120:
        return []
    floor = s.deepest_mine_level
    goal = (floor // 5 + 1) * 5
    iron = floor >= mine_day.IRON_FROM - 1 and farm.held().get("(O)335", 0) < 20
    lines = [mine_day.luck_words(s.daily_luck)]
    dark = mine_day.dark_floors(w.days_played, w.game_id, range(floor // 5 * 5 + 1, goal + 10),
                                legacy=w.legacy_random)
    if dark:
        lines.append(f"today's dark floors carry extra ore: {', '.join(map(str, dark[:6]))}")
    kw = dict(reached_bottom=s.deepest_mine_level >= 120,
              quarry_open="ccCraftsRoom" in s.mail and "VisitedQuarryMine" in s.mail, legacy=w.legacy_random)
    busy = mine_floors.infested_ahead(w.days_played, w.game_id, floor, goal - floor, **kw)
    if busy:
        words = {"monsters": "monsters", "slimes": "slimes", "dinos": "dinosaurs"}
        lines.append("full of monsters today, with no ladder until every one is dead: " + ", ".join(
            f"floor {k.floor} ({words.get(k.infested, k.infested)})" for k in busy)
            + ". Bring food, or stop above it")
    carts = mine_day.full_carts(s.mine_carts, floor)
    if carts:
        lines.append(f"{len(carts) * mine_day.CART_COAL} free Coal in the minecarts on floor "
                     f"{' and '.join(map(str, carts))}")
    lines.append(f"leave at about {MINES_LEAVE} energy")
    title = f"The Mines: floors {floor + 1} to {goal}" + (", for Iron Ore" if iron else f" (you're on {floor})")
    return [{"id": "mines", "kind": "mine", "title": title, "why": "; ".join(lines), "at": MINE_DOOR,
             "minutes": MINES_MINUTES, "value": BUNDLE_VALUE, "energy_to": MINES_LEAVE}]


def _introductions(farm: Farm) -> list[dict]:
    """The Introductions quest: the last hello adds 100 with everyone you've met."""
    for q in farm.save.quests:
        if q["type"] == "SocializeQuest" and not q["completed"] and q.get("greet"):
            left = q["greet"]
            why = (f"{len(left)} to go for Introductions, which ends with +100 friendship with everyone you've met")
            return [x for name in left for x in _person(farm, name, why, INTRODUCTIONS_VALUE)]
    return []


def bring_list(farm: Farm, spouse: str = "") -> list[dict]:
    """What's worth taking out of the Chest: spares to sell (bundles keep one of each) and a gift."""
    s = farm.save
    counts: dict[str, int] = {}
    names: dict[str, tuple[str, int, str | None]] = {}
    for it in s.items:
        if it.where == "Backpack" or not it.qualified_id:
            continue
        counts[it.qualified_id] = counts.get(it.qualified_id, 0) + it.stack
        names[it.qualified_id] = (it.name, it.quality, it.category)
    out = []
    for qid, n in counts.items():
        name, quality, category = names[qid]
        if farm.bundles.fits(qid, category, quality, shown_only=False):
            n -= 1
        if qid in GEODES:
            out.append({"name": name, "count": counts[qid], "why": "for Clint"})
        elif spouse and n > 0 and farm.gifts.giftable(qid) and farm.gifts.taste(spouse, qid) in ("love", "like"):
            out.append({"name": name, "count": 1, "why": f"a gift {spouse} {farm.gifts.taste(spouse, qid)}s"})
            n -= 1
        price = _price(farm, qid)
        if n > 0 and price and category in SELL_CATEGORIES and qid not in KEEP:
            out.append({"name": name, "count": n, "why": f"sell, about {price * n}g"})
    return out


def _fishing(farm: Farm) -> dict | None:
    """Where the fish the bundles still want are biting today, with its bubbles."""
    s, w = farm.save, farm.when
    fish = Fish(farm.data, s.farm_type)
    held = farm.held()
    wanted: dict[str, list[str]] = {}
    for b in farm.bundles.all:
        if b.done:
            continue
        for ing in b.open_ingredients:
            info = fish.by_id.get((ing.item or "").removeprefix("(O)"))
            if not info or held.get(ing.item):
                continue
            for spot in fish.open_spots(info, w):
                if info.bites(spot, season=s.season, wet=s.wet) is not False:
                    wanted.setdefault(spot.location, []).append(farm.name(ing.item))
    spots = {k: sorted(set(v)) for k, v in wanted.items() if k in bubbles.MAPS}
    if not spots:
        return None
    best = max(spots, key=lambda k: len(spots[k]))
    spells = bubbles.spells(farm.data, best, farm.sky)
    return {"place": farm.place(best), "fish": spots[best], "bubbles": _bubble_words(farm, best),
            "location": best, "spots": [list(x.tile) for x in spells if 700 <= x.start < 2000]}


def _head(farm: Farm) -> dict:
    """The day at a glance, cheap enough to show before anything else has loaded."""
    from .morning import WEATHER, WEEKDAYS, luck_words
    s = farm.save
    return {"date": farm.label(s.days_played), "weekday": WEEKDAYS[(s.days_played - 1) % 7],
            "weather": WEATHER.get(s.weather, s.weather),
            "tomorrow": WEATHER.get(s.weather_tomorrow, s.weather_tomorrow),
            "mood": luck_words(s.daily_luck)[0], "money": s.money}


def _show_today(farm: Farm) -> dict | None:
    """The Queen of Sauce, when she's teaching something you don't know: it's on the TV at home, so it comes first."""
    s = farm.save
    for e in farm.calendar.day(farm.when, today_days_played=s.days_played):
        if e.kind != "tv":
            continue
        recipe = e.label.split(": ", 1)[-1]
        if recipe not in s.cooking_recipes:
            sure = "" if e.sure else "probably "
            return {"title": f"Watch the Queen of Sauce: {recipe}",
                    "why": f"{sure}a new recipe, on the TV in your house"}
    return None


def _berries(farm: Farm) -> list[dict]:
    """Fruiting bushes you can shake in passing: each gives 1 + Foraging level / 4 berries."""
    s = farm.save
    item = BERRIES.get(s.season)
    if not item or not s.bushes:
        return []
    name, price = farm.name(item), _price(farm, item)
    count = 1 + s.skills.get("foraging", 0) // 4
    return [{"id": f"bush:{b.location}:{b.tile[0]}:{b.tile[1]}", "title": f"{name} bush ({count})",
             "gold": price * count, "at": (b.location, *b.tile)} for b in s.bushes if b.location in OUTDOORS]


def _all_bubbles(farm: Farm) -> list[dict]:
    out = []
    for loc in bubbles.MAPS:
        spells = bubbles.spells(farm.data, loc, farm.sky)
        out.append({"place": farm.place(loc), "spells": _bubble_words(farm, loc),
                    "spots": [{"loc": loc, "x": x.tile[0], "y": x.tile[1], "label": clock(_minutes(x.start))}
                              for x in spells if 700 <= x.start < 2000]})
    return out


def _spell_words(farm: Farm, location: str, start: int, end: int, tile: tuple[int, int]) -> str:
    near = farm.walker.near(location, tile, farm.place)
    return f"{clock(_minutes(start))} to {clock(_minutes(min(end, 2400)))}" + (f", {near}" if near else "")


def _bubble_words(farm: Farm, location: str) -> list[str]:
    spells = bubbles.spells(farm.data, location, farm.sky)
    return [_spell_words(farm, location, x.start, x.end, x.tile) + (", maybe a Fish Frenzy" if x.frenzy else "")
            for x in spells if 700 <= x.start < 2000]


def _all_pans(farm: Farm) -> list[dict]:
    """Where ore shimmers in the water for the pan today, on the maps you can reach; nothing before the Fish Tank."""
    from ..facts.access import place_open
    day = farm.sky
    if not day.fish_tank:
        return []
    out = []
    for loc in bubbles.PAN_MAPS:
        if not place_open(loc, farm.when)[0]:
            continue
        spots = [x for x in bubbles.pan_spots(farm.data, loc, day) if 600 <= x.start < 2400]
        if spots:
            out.append({"place": farm.place(loc), "loc": loc,
                        "spells": [_spell_words(farm, loc, x.start, x.end, x.tile) for x in spots],
                        "spots": [{"loc": loc, "x": x.tile[0], "y": x.tile[1], "label": clock(_minutes(x.start))}
                                  for x in spots]})
    return out


def pan_note(farm: Farm, pans: list[dict]) -> dict | None:
    """With a Pan in hand, the day's pan spots: ore and coal from a tool you already own, for a few swings."""
    s = farm.save
    if not pans or s.tool_levels.get("Pan", -1) < 0 or s.tool_at_clint == "Pan":
        return None
    first = [f"{g['place']} from {g['spells'][0]}" for g in pans[:3]]
    return {"text": "Ore in the water for your Pan today: " + "; ".join(first) + ".",
            "why": "Each spot shimmers until it fades by itself or someone pans it. They're forecast as if nobody "
                   "pans: once you pan one, the later spots on that map come at other times and places (other "
                   "maps keep theirs). All of today's spots are on the Map and in the Calendar."}


def _door(farm: Farm, location: str, name: str) -> tuple | None:
    """The tile you stand on to use a door."""
    door = next((m for m in farm.walker.landmarks[location] if m.name == name), None)
    return (location, door.x, door.y + 1) if door else None


def _take_words(stop: dict) -> list[str]:
    """A stop's 'take' line: what you carry there, merged by item, and what's already waiting in its chest."""
    if not stop.get("rows"):
        return stop["items"]
    carry: dict[str, int] = {}
    there: dict[str, int] = {}
    for r in stop["rows"]:
        name = r.get("name", r["label"])
        for f in r["from"]:
            book = there if f.get("there") else carry
            book[name] = book.get(name, 0) + (f.get("take") or 0)
    out = [f"{n} {k}" if n > 1 else k for k, n in carry.items() if n]
    out += [f"({n} {k} already there)" for k, n in there.items() if n]
    return out or stop["items"]


WOOD_SOON_DAYS = 28  # a Wood job this close comes before the Construction bundle, which has no deadline


def hold_back(farm: Farm, route: dict | None = None) -> dict[str, str]:
    """Bundle items worth more elsewhere for now, by name, with why. Bundles have no deadline (bar the Vault's
    gold), so they wait: Iron Bars while you're short of Sprinklers (each saves the can's energy every dry day),
    Wood while it would leave a goal's next Wood job in the coming four weeks short (the Coop…)."""
    s, held = farm.save, farm.held()
    out: dict[str, str] = {}
    if "Sprinkler" in s.crafting_recipes:
        from . import layout as layout_view
        try:
            short = layout_view.view(farm).get("short", 0)
        except Exception:  # noqa: BLE001 - without a field plan, no reason to hold back
            short = 0
        if short and held.get("(O)335", 0) <= short:
            out["Iron Bar"] = (f"keep it for a Sprinkler (you're {short} short): it saves watering energy every dry "
                               "day; the Blacksmith's bundle can wait")
    if route:
        cc_wood = sum(i["count"] for r in errands.community_center(farm)["rooms"] for i in r["items"]
                      if i["open"] and i["name"] == "Wood")
        soon = [u for u in wood_uses(route) if u["on"] <= s.days_played + WOOD_SOON_DAYS]
        need = soon[0]["wood"] if soon else 0  # the next job must still be covered after the bundle
        if cc_wood and soon and held.get("(O)388", 0) - cc_wood < need:
            job = re.sub(r"^(build|craft|repair) ", "", soon[0]["what"])
            out["Wood"] = (f"keep it for {job} ({farm.label(soon[0]['on']).rsplit(',', 1)[0]}) first: the "
                           "Construction bundle has no deadline")
    return out


def _community_center(farm: Farm, hold: dict[str, str] | None = None) -> list[dict]:
    if "canReadJunimoText" not in farm.save.mail:
        return []
    hold = hold or {}
    items = [i for r in errands.community_center(farm)["rooms"] for i in r["items"] if i["open"]
             and i["name"] not in hold]
    door = _door(farm, "Town", "CommunityCenter")
    if not items or not door:
        return []
    what = ", ".join(f"{i['count']} {i['name']} ({i['bundle']})" if i["count"] > 1 else f"{i['name']} ({i['bundle']})"
                     for i in items)
    return [{"id": "cc", "kind": "shop", "title": "Community Center", "minutes": 5, "at": door,
             "why": f"hand in {what}",
             "value": QUEST_VALUE}]


def _museum(farm: Farm) -> list[dict]:
    take = errands.gunther(farm)["take"]
    door = _door(farm, "Town", "ArchaeologyHouse")
    if not take or not door:
        return []
    return [{"id": "museum", "kind": "shop", "title": "The Museum", "minutes": 5, "at": door,
             "why": f"{len(take)} new find{'s' if len(take) != 1 else ''} to donate", "value": BUNDLE_VALUE,
             "from": 8 * 60, "until": 18 * 60}]


def _willy(farm: Farm, quest: dict | None) -> list[dict]:
    """His shop is worth the walk for a request, or a good bag of fish."""
    door = _door(farm, "Beach", "FishShop")
    for_him = quest and quest.get("who") == "Willy" and farm.held().get(f"(O){quest['item']}")
    active = any(q["deliver_to"] == "Willy" for q in quests.view(farm)["quests"])
    fish = sum(r["each"] * r["count"] for r in sell.default(farm)["sell"] if r.get("category") == -4)
    if not door or not (for_him or active or fish >= FISH_TRIP):
        return []
    return [{"id": "willy", "kind": "shop", "title": "Willy's shop", "minutes": 5, "at": door,
             "why": "hand in the request and sell your fish" if for_him or active else "sell your fish",
             "value": QUEST_VALUE if for_him or active else fish, "from": 9 * 60, "until": 17 * 60}]


def energy_warning(farm: Farm, cost: int, power: int) -> str:
    """Say so when the day's must-dos cost more than you've got, and what to eat."""
    if cost <= power - RESERVE:
        return ""
    return f"Watering costs {cost} energy and you have {power}. {food_advice(farm, cost - (power - RESERVE))}"


def night_note(farm: Farm, power: int) -> str:
    """What tonight does to tomorrow: a level-up fills you up, and 0 energy halves you."""
    s = farm.save
    up = [r for r in levels.forecast(farm) if r["day"] == s.days_played and r["sure"]]
    if up:
        r = up[0]
        return (f"You reach {r['skill'].title()} {r['level']} today, so you wake on full energy tomorrow"
                " whatever you spend or however late you sleep.")
    if power <= 0:
        return (f"At 0 energy tomorrow starts on {s.max_stamina // 2 + 1}. A Muscle Remedy (Harvey's) clears that,"
                " and so does a level-up tonight.")
    late = tools.wake(s.max_stamina, 2500, 0)
    return f"Be in bed by 12:50am: at 1:00am tomorrow starts on {late}, not {s.max_stamina}." if late else ""


def _giant_watch(farm: Farm) -> dict | None:
    try:
        return picking.watch(farm)
    except Exception:  # noqa: BLE001 - a forecast we can't make shouldn't stop the day plan
        return None


def food_advice(farm: Farm, short: int) -> str:
    """Enough food from what you hold to cover the shortfall, the least gold lost per energy first,
    and the spa when it's open: free, it only costs time."""
    text = _food_advice(farm, short)
    if short > 0 and comforts.spa_open(getattr(farm.save, "days_played", 0)):
        text += (f" Or sit still in the spa pool, up the mountain past the Railroad: about "
                 f"{math.ceil(short / comforts.SPA_ENERGY_PER_MINUTE)} game minutes for {short} energy, free.")
    return text


def _food_advice(farm: Farm, short: int) -> str:
    objects = farm.data.asset("Data/Objects")
    foods = []
    for it in farm.save.items:
        q = it.qualified_id
        o = objects.get(q.removeprefix("(O)")) if q.startswith("(O)") else None
        if not o or int(o.get("Edibility") or 0) <= 0 or farm.bundles.fits(q, it.category, it.quality,
                                                                            shown_only=False):
            continue
        energy = tools.food(int(o["Edibility"]), it.quality)
        foods += [((_price(farm, q) or 0) / energy, energy, farm.name(q))] * it.stack
    eat, gained = [], 0
    for _cost, energy, name in sorted(foods):
        if gained >= short:
            break
        eat.append((name, energy))
        gained += energy
    if not eat:
        return "You've no food, so do the crops that matter most first."
    counts = {name: sum(1 for n, _e in eat if n == name) for name, _e in eat}
    words = " and ".join(f"{k} {name}" for name, k in counts.items())
    if gained < short:
        return f"Eat {words} (+{gained}), and you'll still be {short - gained} short: do the crops that matter first."
    return f"Eat {words} (+{gained}) partway through."


def _wizard(farm: Farm) -> list[dict]:
    """The Wizard's letter means the tower is the next step: after his scene the bundles can be read and filled."""
    s = farm.save
    if "canReadJunimoText" in s.mail or not ({"wizardJunimoNote"} & (s.mail | s.mailbox)):
        return []
    return [{"id": "wizard", "kind": "story", "title": "The Wizard's tower: answer his letter",
             "why": "read the letter first; after his scene you can fill bundles", "at": ("Forest", 5, 27),
             "minutes": 15, "value": 2 * QUEST_VALUE, "from": 6 * 60, "until": 23 * 60}]


def _pierre(farm: Farm, ripe: int) -> list[dict]:
    """A harvest is only money, and replanted, once it's been to Pierre's: he pays on the spot."""
    shop = next((x for x in farm.hours_today() if x["id"] == "SeedShop"), {})
    selling = sum(r["each"] * r["count"] for r in sell.default(farm)["sell"]
                  if "SeedShop" in Buyers(farm.data).of(r.get("category")))
    if not (ripe or selling >= SHOP_TRIP) or shop.get("closed"):
        return []
    seeds = seed_list(farm)
    cost = sum(x["count"] * x["price"] for x in seeds)
    kinds = len(seeds)
    return [{"id": "pierre", "kind": "shop", "title": "Pierre's: sell the harvest" + (", buy seeds" if seeds else ""),
             "why": (f"{kinds} kind{'s' if kinds != 1 else ''} of seed, about {cost:,}g: what each is for is below"
                     if seeds else "he pays on the spot"),
             "seeds": seeds, "at": ("Town", 43, 57), "minutes": 5,
             "value": QUEST_VALUE, "from": 9 * 60, "until": 17 * 60}]


def seed_list(farm: Farm) -> list[dict]:
    """What to buy at Pierre's today, and why: the giant-crop square due now, the crops your bundles still need,
    then the best earner for the rest of your empty dirt. Only seeds he sells today."""
    from ..engine import cc
    from . import crops as crops_view
    rows = [r for r in crops_view.countdown(farm)["crops"] if r["status"] == "ok" and r["where"] == "Pierre's"
            and r.get("seed_price")]
    by_crop = {r["crop"]: r for r in rows}
    out: list[dict] = []

    def add(row: dict, count: int, why: str) -> None:
        if count > 0:
            out.append({"seed": row["seed"], "id": row["seed_id"], "count": count, "price": row["seed_price"],
                        "why": why})

    used = 0
    for plan in picking.plans(farm, limit=1):
        if plan["sow_days_played"] <= farm.when.days_played and plan["crop"] in by_crop:
            add(by_crop[plan["crop"]], 9, "the giant square")
            used += 9
    for slot in cc.plan(farm)["slots"]:
        best = slot.get("best") or {}
        if slot["status"] != "have" and best.get("kind") in ("grow", "crop") and slot["name"] in by_crop:
            # a gold-quality slot is a roll: plant three times as many (and fertilize them)
            want = slot["count"] * (3 if slot.get("quality") else 1) + 1
            add(by_crop[slot["name"]], want,
                f"{slot['bundle']} bundle" + (", gold quality: fertilize them" if slot.get("quality") else ""))
            used += want
    s = farm.save
    planted = {c.tile for c in s.crops if c.location == "Farm" and not c.dead}
    free = len({t for t in s.hoed if t not in planted and t not in s.farm_objects}) - used
    best = max(rows, key=lambda r: r["income"], default=None)
    if best and free > 0:
        add(best, free, f"the rest of your dirt: {free} tiles, the best earner")
    merged: dict[str, dict] = {}
    for x in out:  # one line a seed
        if x["seed"] in merged:
            merged[x["seed"]]["count"] += x["count"]
            merged[x["seed"]]["why"] += f", {x['why']}"
        else:
            merged[x["seed"]] = dict(x)
    held = {r["seed"]: r["held_seeds"] for r in rows}
    for x in merged.values():  # what you already hold comes off once, whatever it's for
        x["held"] = held.get(x["seed"], 0)
        x["count"] = max(0, x["count"] - x["held"])
    return [x for x in merged.values() if x["count"]]


def _note(x) -> dict:
    """A note as {text, why}: a plain sentence becomes its first sentence, with the rest as the why."""
    if isinstance(x, dict):
        return x
    head, sep, rest = x.partition(". ")
    return {"text": head + ("." if sep else ""), "why": rest.strip()}


def _board_note(farm: Farm) -> dict:
    """Today's Help Wanted request: who wants what, by when, and where to get it."""
    s = farm.save
    quest = help_wanted.quest_today(s, farm.data)
    tomorrow = farm.label(s.days_played + 1).rsplit(",", 1)[0]
    if quest is None:
        return {"text": "No Help Wanted request today.", "why": "The board outside Pierre's is empty today."}
    if quest["kind"] == "delivery":
        qid = f"(O){quest['item']}"
        have = farm.held().get(qid)
        name = farm.name(qid)
        a = "an" if name[:1].lower() in "aeiou" else "a"
        return {"text": f"Help Wanted: {quest['who']} wants {a} {name}, {3 * _price(farm, qid)}g.",
                "why": f"Take the request from the board outside Pierre's today and give {quest['who']} {a} "
                       f"{name} by the end of {tomorrow}. It pays three times its price and 150 "
                       f"friendship. " + ("You have one." if have else "You don't have one yet.")}
    taken = next((q for q in s.quests if q["daily"] and not q["completed"] and q.get("to_kill")), None)
    if quest["kind"] == "slay" and taken:
        m = taken["monster"]
        by = farm.label(s.days_played + max(0, taken["days_left"] - 1)).rsplit(",", 1)[0]
        where = help_wanted.SLAY_WHERE.get(m, "the Mines")
        return {"text": f"Help Wanted, taken: {taken['killed']} of {taken['to_kill']} {m}s killed so far.",
                "why": f"Finish by the end of {by} for {taken['reward']:,}g. {m}s live in {where}. The count only "
                       "moves when the game saves at night, so today's kills show tomorrow."}
    if quest["kind"] == "slay":
        m, n = quest["monster"], quest["count"]
        plural = m if m.endswith(("s", "Jelly", "Duggy")) and n == 1 else (m[:-1] + "ies" if m.endswith("y") and
                                                                           not m.endswith("Duggy") else m + "s")
        deep = s.deepest_mine_level
        who = "the Wizard" if quest["who"] == "Wizard" else quest["who"]
        return {"text": f"Help Wanted: {who} needs {n} {plural} killed by {tomorrow}, {quest['reward']:,}g.",
                "why": f"Take the request from the board outside Pierre's today; it lasts until the end of "
                       f"{tomorrow}. {plural} live in {quest['where']}. You've reached floor {deep}, so "
                       + ("you can get there by the elevator." if deep >= 40 or m in ("Green Slime", "Rock Crab")
                          else "they're on floors you've already reached.")
                       + " The monster is fixed by how deep anyone had been when the board is read: going deeper "
                         "first can change it."}
    words = {"fishing": "a fish to catch", "resource": "ore or stone to gather", "socialize": "people to talk to"}
    return {"text": f"Help Wanted: {words.get(quest['kind'], quest['kind'])}.",
            "why": "The details are on the board outside Pierre's; the planner doesn't forecast this kind yet."}


def view(farm: Farm, *, time: int | None = None, energy: int | None = None, where: str | None = None,
         done: set[str] = frozenset(), spouse: str = "", pace: float | None = None, route: dict | None = None) -> dict:
    s = farm.save
    walker = farm.walker
    walker.pace = pace or NEW_PLAYER_PACE
    held = farm.held()
    now = _minutes(time) if time is not None else START
    power = energy if energy is not None else s.stamina
    pos = (where, *_anchor(walker, where)) if where and where != "Farm" else ("Farm", *FARMHOUSE_DOOR)
    start = pos
    plan: list[dict] = []
    left: list[dict] = []
    legs: list[tuple[int, list]] = []  # (the stop it leads to, the tiles walked)

    def farm_job(job_id: str, title: str, tiles: int, cost: int, minutes: float, why: str) -> None:
        nonlocal now, power
        if job_id in done or not tiles:
            return
        afford = min(tiles, int(max(0, power - RESERVE) // cost)) if cost else tiles
        fits = min(afford, int(max(0, (FINISH - now)) // max(0.1, minutes)))
        if fits:
            power -= round(fits * cost)
            plan.append({"id": job_id, "time": clock(now), "at": now, "kind": "farm", "title": f"{title} {fits}",
                         "why": why, "way": [], "energy_after": power})
            now += round(fits * minutes)
        if fits < tiles:
            left.append({"title": f"{title} {tiles - fits}", "why": "not enough energy or time left today"})

    wet = s.wet
    lost = [c for c in s.crops if c.location == "Farm" and not c.watered and crops.doomed(farm, c)]
    thirsty = 0 if wet else sum(1 for c in s.crops if c.location == "Farm" and not c.watered and not c.ready
                                and not c.dead and c not in lost)
    seeds = sum(i.stack for i in s.items if i.type == "Seeds" and i.category == -74)
    home_first = pos[0] != "Farm" and ((thirsty and "water" not in done) or (seeds and "plant" not in done))
    if home_first:  # the farm jobs still come first: walk back for them
        way = walker.path(walker.reach(pos), ("Farm", *FARMHOUSE_DOOR))
        if way:
            now += walker.minutes(way)
            legs.append((len(plan), way))
            plan.append({"id": "home", "time": clock(now), "kind": "farm", "title": "Back to the farm",
                         "why": "the crops come first", "way": walker.directions(way, farm.place),
                         "energy_after": power})
            pos = ("Farm", *FARMHOUSE_DOOR)
    ripe = sum(1 for c in s.crops if c.location == "Farm" and c.ready and not c.forage and c.harvest_id)
    warning = energy_warning(farm, round(thirsty * tools.water(s.tool_levels.get("WateringCan", 0),
                                                               s.skills.get("farming", 0), thirsty)[0]),
                             power) if "water" not in done else ""
    show = _show_today(farm)
    tv_note = ""
    if show and "tv" not in done:
        if pos[0] == "Farm":  # before you leave the house
            plan.append({"id": "tv", "time": clock(now), "at": now, "kind": "farm", **show, "way": [],
                         "energy_after": power})
            now += TV_MINUTES
        else:
            tv_note = f"{show['title']} is on: {show['why']}."
    can, farming = s.tool_levels.get("WateringCan", 0), s.skills.get("farming", 0)
    water_e, water_m = tools.water(can, farming, thirsty)
    hoe_e, hoe_m = tools.hoe(s.tool_levels.get("Hoe", 0), farming, seeds)
    plant_e, plant_m = tools.water(can, farming, seeds)
    farm_job("harvest", "Harvest", ripe, 0, HARVEST_MINUTES, "keep what the bundles need, sell the rest")
    farm_job("water", "Water", thirsty, water_e, water_m, "they won't grow tonight otherwise"
             + ("; hold the can to charge it, it's cheaper a tile" if can and thirsty >= tools.TILES[1] else ""))
    farm_job("plant", "Hoe and plant", seeds, hoe_e + (0 if wet else plant_e), hoe_m + (0 if wet else plant_m),
             "the rain waters them" if wet else "hoe, plant, water"
             + ("; a charged hoe costs one swing however many tiles it digs" if s.tool_levels.get("Hoe") else ""))

    place = lambda n: farm.place(n)  # noqa: E731
    fest_today = (s.season, s.day) in farm.hours.festivals
    board = help_wanted.quest_today(s, farm.data, festival=fest_today)
    hold = hold_back(farm, route)
    stops = [x for x in _stops(farm, held, spouse) + _wizard(farm) + _community_center(farm, hold) + _pierre(farm, ripe)
             + _clint(farm, held) + _museum(farm) + _willy(farm, board) + _mines(farm, power) + _introductions(farm)
             + (_sweetheart(farm, spouse) if spouse else []) + _birthdays(farm, spouse) if x["id"] not in done]
    fest = farm.hours.festivals.get((s.season, s.day))
    if fest:  # the map is the festival's and the day ends with it: only the farm jobs and the festival itself
        stops = []
        plan.append({"id": "festival", "time": clock(max(now, _minutes(fest[1]))), "kind": "festival", "title": fest[0],
                     "why": f"at {farm.place(fest[2])}: finish the farm first, the day ends when you leave", "way": [],
                     "energy_after": power})
    prev = walker.reach(pos)
    for x in list(stops):
        if walker.path(prev, x["at"]) is None:
            stops.remove(x)  # the Desert, the tide pools: not part of today, and not worth listing one by one
    while stops:
        best, score = None, 0.0
        for x in stops:
            path = walker.path(prev, x["at"])
            cost = walker.minutes(path) + x["minutes"]
            if x["value"] < BUNDLE_VALUE and cost > SPARE_DETOUR:  # a spare is only worth picking up in passing
                continue
            arrive = now + walker.minutes(path)
            if "until" in x:
                if arrive >= x["until"]:
                    continue
                cost += max(0, x["from"] - arrive)  # waiting counts as time spent
            if now + cost <= FINISH and x["value"] / max(1, cost) > score:
                best, score = x, x["value"] / max(1, cost)
        if best is None:
            seen = {x["id"]: x for x in stops}  # one line for a stop with several time windows
            left += [{"title": x["title"], "why": "can't be there in time" if "until" in x else
                      "too far for what it's worth today", "at": x["at"], "value": x["value"], "id": x["id"],
                      "spare": x["kind"] == "forage"} for x in seen.values()]
            break
        path = walker.path(prev, best["at"])
        legs.append((len(plan), path))
        now = max(now + walker.minutes(path), best.get("from", 0))
        arrived = now
        tile = (best["at"][1], best["at"][2])
        plan.append({"id": best["id"], "time": clock(now), "at": arrived, "kind": best["kind"],
                     "title": best["title"],
                     "why": best["why"], "way": walker.directions(path, place),
                     "near": walker.near(best["at"][0], tile, place), "place": place(best["at"][0]),
                     "spot": None if best["kind"] == "farm" else list(best["at"]), "energy_after": power})
        now += best["minutes"]
        if best["id"] == "pierre":  # then home to get the seeds in
            way = walker.path(walker.reach(best["at"]), ("Farm", *FARMHOUSE_DOOR))
            cash = s.money + sum(_price(farm, f"(O){c.harvest_id}") for c in s.crops
                                 if c.location == "Farm" and c.ready and not c.forage and c.harvest_id)
            buy = seed_advice(farm, cash, ripe)
            tiles = sum(x["count"] for x in buy)
            if way and tiles >= MIN_REPLANT:  # a handful of seeds can wait for the next trip home
                plan[-1]["why"] = "buy " + ", ".join(f"{x['count']} {x['name']}" for x in buy) + " seeds"
                now += walker.minutes(way)
                cost = TILE_ENERGY * tiles
                power -= min(cost, max(0, power - RESERVE))
                legs.append((len(plan), way))
                plan.append({"id": "replant", "time": clock(now), "at": now, "kind": "farm", "title":
                             f"Home: plant and water {tiles} seeds", "why": "harvested tiles stay tilled", "way":
                             walker.directions(way, farm.place), "energy_after": power})
                now += round(tiles * TILE_MINUTES)
                pos = ("Farm", *FARMHOUSE_DOOR)
                prev = walker.reach(pos)
                stops = [x for x in stops if x["id"] != best["id"]]
                continue
        if "energy_to" in best:
            power = min(power, best["energy_to"])
            plan[-1]["energy_after"] = power
        stops = [x for x in stops if x["id"] != best["id"]]
        pos = path[-1]
        prev = walker.reach(pos)
    home = walker.path(prev, ("Farm", *FARMHOUSE_DOOR))
    if home:
        legs.append((len(plan), home))
    candidates = [{"id": x["id"], "title": x["title"].removeprefix("Pick up "), "gold": x["value"], "at": x["at"]}
                  for x in left if x.get("spare")] + _berries(farm)
    passing = []
    placed = set()
    for c in candidates:
        loc, tx, ty = c["at"]
        gaps = [(min(abs(a[1] - tx) + abs(a[2] - ty) for a in path if a[0] == loc), i, path) for i, path in legs
                if any(a[0] == loc for a in path)]
        best = min(gaps, key=lambda g: g[0], default=None)
        if best and best[0] <= PASSING:
            row = {"title": c["title"], "gold": c["gold"], "near": walker.near(loc, (tx, ty), farm.place),
                   "place": farm.place(loc), "stop": best[1], "spot": [loc, tx, ty]}
            passing.append(row)
            placed.add(c["id"])
            if best[1] < len(plan):
                plan[best[1]].setdefault("extras", []).append(row)
    left = [{k: x[k] for k in ("title", "why")} for x in left if x.get("id") not in placed]
    for i, path in legs:  # the walk as one instruction at a time, for the satnav (static/satnav.js)
        if i < len(plan):
            plan[i]["steps"] = walker.steps(path, farm.place)
    spare = max(0, power - RESERVE)
    hours = max(0, FINISH - now)
    casts = min(int(spare // tools.cast(s.skills.get("fishing", 0))), hours // CAST_MINUTES)
    trees = min(int(spare // tools.tree(s.tool_levels.get("Axe", 0), s.skills.get("foraging", 0))),
                hours // TREE_MINUTES)
    extra = []
    if casts >= 3:
        extra.append(f"fish about {casts} times")
    if trees:
        extra.append(f"chop about {trees} trees for {trees * TREE_WOOD} Wood")
    coming: dict[str, dict] = {}
    for row in levels.forecast(farm):  # soonest first, so each skill keeps its next level
        coming.setdefault(row["skill"], row)
    bag = pack.build(farm, plan, spouse, hold=hold)
    load: dict[str, dict[str, int]] = {}
    for st in bag["stops"]:  # a stop's words shouldn't promise what you won't have with you
        row = next((r for r in plan if r["id"] == st.get("key")), None)
        if row is not None and st["items"]:
            row["take"] = _take_words(st)
        for r in st.get("rows", []):
            for f in r["from"]:
                if (f["where"].endswith("farm") or f["where"] == "your backpack") and not f.get("there"):
                    chest = load.setdefault(f["where"], {})
                    name = r.get("name", r["label"])
                    chest[name] = chest.get(name, 0) + (f.get("take") or 1)
        if row is not None and st.get("short"):
            if st["key"] == "cc" and st["items"]:
                row["why"] = "hand in " + ", ".join(st["items"])
            row["why"] += "; not today: " + "; ".join(f"{x['label']} ({x['text']})" for x in st["short"])
    pans = _all_pans(farm)
    return {"head": _head(farm), "plan": plan, "left": left, "spare": extra,
            "notes": [_note(x) for x in (_board_note(farm), tv_note, doomed_note(farm, lost),
                                         sprinkler_note(farm, thirsty), wood_note(farm, trees), night_note(farm, power),
                                         luau_note(farm), pan_note(farm, pans)) if x],
            "passing": passing,
            "bring": bring_list(farm, spouse), "fishing": _fishing(farm), "geodes": geode_forecast(farm, held),
            "pace": round(walker.pace / NEW_PLAYER_PACE, 2),
            "energy": {"now": s.stamina, "max": s.max_stamina, "planned_left": power}, "warning": warning,
            "giant": _giant_watch(farm),
            "pack": bag, "held_back": [{"item": k, "why": v} for k, v in hold.items()],
            "load": [{"where": w, "items": [f"{n} {k}" if n > 1 else k for k, n in items.items()]}
                     for w, items in load.items() if w != "your backpack"],
            "bubbles": _all_bubbles(farm), "pans": pans,
            "home": clock(now + walker.minutes(home)) if home else "",
            "route": [{"stop": i, "lines": polylines(path)} for i, path in legs],
            "start": list(start), "home_steps": walker.steps(home, farm.place) if home else [],
            "skills": [{"name": k.name, "level": k.level, "xp": k.xp, "next": k.next_xp, "to_go": k.to_go,
                        "share": round(k.share, 3), "ways": list(k.ways), "coming": coming.get(k.name)}
                       for k in skills.progress(s.experience)],
            "places": ["Farm", "Town", "Forest", "Beach", "Mountain", "BusStop", "Backwoods"]}


def learned_pace(path, day: int, ratio: float | None) -> float:
    """The walking pace from this save's recalculations: each day's stated time against the plan's, the last week
    averaged. A day's own figure is replaced, not added, so pressing Recalculate twice counts once."""
    try:
        days = {int(k): v for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
    except (OSError, ValueError):
        days = {}
    if ratio is not None:
        days[day] = max(0.5, min(3.0, ratio))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(days), encoding="utf-8")
    recent = [days[d] for d in sorted(days)[-PACE_DAYS:]]
    return NEW_PLAYER_PACE * (sum(recent) / len(recent)) if recent else NEW_PLAYER_PACE


def pace_ratio(morning: dict, time: int | None, done: set[str]) -> float | None:
    """How your stated time compares with when the morning plan had you at the last stop you've ticked."""
    ticked = [x for x in morning["plan"] if x["id"] in done and "at" in x]
    if time is None or not ticked:
        return None
    planned = ticked[-1]["at"] - START
    return (_minutes(time) - START) / planned if planned >= PACE_MIN_MINUTES else None


def _anchor(walker, where: str) -> tuple[int, int]:
    """A walkable tile to stand for 'somewhere on this map': where its first exit brings you."""
    for node in walker.exits.values():
        if node[0] == where:
            return node[1], node[2]
    return 0, 0
