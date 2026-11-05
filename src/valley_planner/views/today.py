"""Today's plan: a timed list you can just follow, or recalculate from wherever you've got to.

It's limited by the three things that run out: the clock, your energy and what's reachable. Must-dos come first
(watering, then planting), then the stops worth the walk, best value for the minutes first. What doesn't fit is
listed with the reason. Recalculate with the time, energy and place you're at, and ticked stops left out.

Energy at the start of a game (planning choices, from the first days of a real game): hoeing or watering a tile
costs 2; a tile takes a person about 1.6 minutes. FINISH: no planned stop starts after this.

The person you're courting is a stop with a time window, from their schedule. Spare energy at the end goes on
whichever of fishing or chopping you ask for, suggested rather than timed to the minute.
"""

from __future__ import annotations

import json

from ..facts import bubbles, geodes, help_wanted, skills
from ..facts.fish import Fish
from ..facts.garbage import CANS
from ..facts.schedules import Situation
from ..facts.walk import FARMHOUSE_DOOR, NEW_PLAYER_PACE, OUTDOORS
from .farm import Farm

TILE_ENERGY = 2
TILE_MINUTES = 1.6
RESERVE = 10  # energy never spent, so you don't pass out
START = 6 * 60 + 10
FINISH = 20 * 60
QUEST_VALUE = 500
SWEETHEART_VALUE = 400
CAST_ENERGY, CAST_MINUTES = 9, 20  # fishing: an average cast and catch, from a real game's first days
TREE_ENERGY, TREE_MINUTES, TREE_WOOD = 30, 15, 17  # a tree and its stump
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


def _stops(farm: Farm, held: dict[str, int]) -> list[dict]:
    s = farm.save
    out = []
    for f in s.forage:
        why, value = _forage_why(farm, f.item, held)
        out.append({"id": f"forage:{f.location}:{f.tile[0]}:{f.tile[1]}", "kind": "forage",
                    "title": f"Pick up {f.name}", "why": why, "at": (f.location, *f.tile), "minutes": 1,
                    "value": value})
    fest = farm.hours.festivals
    today = (farm.when.season, farm.when.day) in fest or (farm.when.season, farm.when.day + 1) in fest
    quest = help_wanted.quest_today(s, farm.data, festival=today)
    if quest and quest["kind"] == "delivery" and held.get(f"(O){quest['item']}"):  # only if you can fill it
        qid = f"(O){quest['item']}"
        gold = 3 * _price(farm, qid)
        out.append({"id": "quest", "kind": "quest", "title": f"Help Wanted: {farm.name(qid)} for {quest['who']}",
                    "why": f"{gold}g and 150 friendship; take it from the board outside Pierre's first",
                    "at": ("Town", 42, 58), "minutes": 1, "value": QUEST_VALUE})
    marks = {m.name.removeprefix("Garbage:"): m for m in farm.walker.landmarks["Town"]}
    for can in farm.bins.day(s, farm.when):
        if can.loot and can.loot.item and _price(farm, can.loot.item) >= GOOD_BIN and can.can in marks:
            m = marks[can.can]
            out.append({"id": f"bin:{can.can}", "kind": "bin", "title": f"Bin at {CANS[can.can]}: {can.loot.label}",
                        "why": "check nobody's close by first", "at": ("Town", m.x, m.y), "minutes": 1,
                        "value": _price(farm, can.loot.item) * can.loot.stack})
    return out


def _sweetheart(farm: Farm, name: str) -> list[dict]:
    """Where they stand between walks: a stop for each stretch of today, so the plan catches whichever fits."""
    s = farm.save
    f = s.friends.get(name)
    if f is None and name not in farm.data.asset("Data/Characters"):
        return []
    if f is not None and f.talked_today:
        return []
    days = farm.schedules.today(name, Situation(farm.when, hearts=f.hearts if f else 0, raining=s.wet))
    if len(days) != 1:  # a coin-flip day: nowhere certain to send you
        return []
    stops = days[0].stops
    out = []
    for a, b in zip(stops, [*stops[1:], None], strict=False):
        if a.location not in OUTDOORS:
            continue
        begin, end = _minutes(a.time), _minutes(b.time) if b else FINISH
        out.append({"id": f"talk:{name}", "kind": "talk", "title": f"Talk to {name}",
                    "why": f"there until {clock(end)}; a daily talk keeps the hearts moving", "minutes": 2,
                    "at": (a.location, a.x, a.y), "value": SWEETHEART_VALUE, "from": begin, "until": end})
    return out


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
    for d in farm.cart.days(farm.when, count_days=CART_AHEAD, guarantee=s.cart_guarantee):
        for i in d.items:
            if i.sure and i.item not in wanted and farm.bundles.fits(i.item, None, 0, shown_only=False):
                if not farm.held().get(i.item):
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
    """A trip down the Mines, if the day has the energy for one."""
    s = farm.save
    if "landslideDone" not in s.mail and s.days_played < 5:
        return []
    if power < MINES_MIN_ENERGY or s.deepest_mine_level >= 120:
        return []
    floor = s.deepest_mine_level
    goal = (floor // 5 + 1) * 5
    return [{"id": "mines", "kind": "mine", "title": f"The Mines: reach floor {goal} (you're on {floor})",
             "why": f"leave at about {MINES_LEAVE} energy", "at": MINE_DOOR, "minutes": MINES_MINUTES,
             "value": BUNDLE_VALUE, "energy_to": MINES_LEAVE}]


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
    return {"place": farm.place(best), "fish": spots[best], "bubbles": _bubble_words(farm, best)}


def _bubble_words(farm: Farm, location: str) -> list[str]:
    s = farm.save
    spells = bubbles.forecast(farm.data, location, s.days_played, int(s.unique_id), legacy=s.legacy_random)
    return [f"{clock(_minutes(x.start))} to {clock(_minutes(min(x.end, 2400)))}"
            + (f", {farm.walker.near(location, x.tile, farm.place)}" if farm.walker.near(location, x.tile, farm.place)
               else "") for x in spells if 700 <= x.start < 2000]


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
    if not ripe or shop.get("closed"):
        return []
    return [{"id": "pierre", "kind": "shop", "title": "Pierre's: sell the harvest, buy seeds",
             "why": "he pays on the spot, so you can replant today", "at": ("Town", 43, 57), "minutes": 5,
             "value": QUEST_VALUE, "from": 9 * 60, "until": 17 * 60}]


def _board_note(farm: Farm) -> str:
    s = farm.save
    quest = help_wanted.quest_today(s, farm.data)
    if quest is None:
        return "No Help Wanted request today."
    if quest["kind"] == "delivery":
        qid = f"(O){quest['item']}"
        have = "you have one" if farm.held().get(qid) else "you don't have one"
        return f"Help Wanted: {farm.name(qid)} for {quest['who']}, {3 * _price(farm, qid)}g ({have})."
    return f"Help Wanted: a {quest['kind']} request."


def view(farm: Farm, *, time: int | None = None, energy: int | None = None, where: str | None = None,
         done: set[str] = frozenset(), spouse: str = "", pace: float | None = None) -> dict:
    s = farm.save
    walker = farm.walker
    walker.pace = pace or NEW_PLAYER_PACE
    held = farm.held()
    now = _minutes(time) if time is not None else START
    power = energy if energy is not None else s.stamina
    pos = (where, *_anchor(walker, where)) if where and where != "Farm" else ("Farm", *FARMHOUSE_DOOR)
    plan: list[dict] = []
    left: list[dict] = []
    walked: list[tuple] = []  # every tile the plan's walks cross

    def farm_job(job_id: str, title: str, tiles: int, cost: int, minutes: float, why: str) -> None:
        nonlocal now, power
        if job_id in done or not tiles:
            return
        afford = min(tiles, max(0, power - RESERVE) // cost) if cost else tiles
        fits = min(afford, max(0, (FINISH - now)) // max(1, int(minutes)))
        if fits:
            power -= fits * cost
            plan.append({"id": job_id, "time": clock(now), "kind": "farm", "title": f"{title} {fits}", "why": why,
                         "way": [], "energy_after": power})
            now += round(fits * minutes)
        if fits < tiles:
            left.append({"title": f"{title} {tiles - fits}", "why": "not enough energy or time left today"})

    wet = s.wet
    thirsty = 0 if wet else sum(1 for c in s.crops if c.location == "Farm" and not c.watered and not c.ready)
    seeds = sum(i.stack for i in s.items if i.type == "Seeds" and i.category == -74)
    home_first = pos[0] != "Farm" and ((thirsty and "water" not in done) or (seeds and "plant" not in done))
    if home_first:  # the farm jobs still come first: walk back for them
        way = walker.path(walker.reach(pos), ("Farm", *FARMHOUSE_DOOR))
        if way:
            now += walker.minutes(way)
            plan.append({"id": "home", "time": clock(now), "kind": "farm", "title": "Back to the farm",
                         "why": "the crops come first", "way": walker.directions(way, farm.place),
                         "energy_after": power})
            pos = ("Farm", *FARMHOUSE_DOOR)
    ripe = sum(1 for c in s.crops if c.location == "Farm" and c.ready and not c.forage and c.harvest_id)
    farm_job("harvest", "Harvest", ripe, 0, 1, "keep what the bundles need, sell the rest")
    farm_job("water", "Water", thirsty, TILE_ENERGY, TILE_MINUTES, "they won't grow tonight otherwise")
    farm_job("plant", "Hoe and plant", seeds, TILE_ENERGY if wet else 2 * TILE_ENERGY,
             TILE_MINUTES * (1 if wet else 2), "the rain waters them" if wet else "hoe, plant, water")

    place = lambda n: farm.place(n)  # noqa: E731
    stops = [x for x in _stops(farm, held) + _wizard(farm) + _pierre(farm, ripe) + _clint(farm, held)
             + _mines(farm, power) + (_sweetheart(farm, spouse) if spouse else []) if x["id"] not in done]
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
                      "too far for what it's worth today", "at": x["at"], "value": x["value"],
                      "spare": x["kind"] == "forage"} for x in seen.values()]
            break
        path = walker.path(prev, best["at"])
        walked += path
        now = max(now + walker.minutes(path), best.get("from", 0))
        arrived = now
        tile = (best["at"][1], best["at"][2])
        plan.append({"id": best["id"], "time": clock(now), "at": arrived, "kind": best["kind"],
                     "title": best["title"],
                     "why": best["why"], "way": walker.directions(path, place),
                     "near": walker.near(best["at"][0], tile, place), "place": place(best["at"][0]),
                     "energy_after": power})
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
    walked += home or []
    passing = []
    for x in [y for y in left if y.get("spare")]:
        loc, tx, ty = x["at"]
        gap = min((abs(a[1] - tx) + abs(a[2] - ty) for a in walked if a[0] == loc), default=PASSING + 1)
        if gap <= PASSING:
            passing.append({"title": x["title"].removeprefix("Pick up "), "gold": x["value"],
                            "near": walker.near(loc, (tx, ty), farm.place), "place": farm.place(loc)})
    left = [{k: x[k] for k in ("title", "why")} for x in left if x["title"].removeprefix("Pick up ") not in
            {p["title"] for p in passing}]
    spare = max(0, power - RESERVE)
    hours = max(0, FINISH - now)
    casts = min(spare // CAST_ENERGY, hours // CAST_MINUTES)
    trees = min(spare // TREE_ENERGY, hours // TREE_MINUTES)
    extra = []
    if casts >= 3:
        extra.append(f"fish about {casts} times")
    if trees:
        extra.append(f"chop about {trees} trees for {trees * TREE_WOOD} Wood")
    return {"plan": plan, "left": left, "notes": [_board_note(farm)], "spare": extra, "passing": passing,
            "bring": bring_list(farm, spouse), "fishing": _fishing(farm), "geodes": geode_forecast(farm, held),
            "pace": round(walker.pace / NEW_PLAYER_PACE, 2),
            "energy": {"now": s.stamina, "max": s.max_stamina, "planned_left": power},
            "home": clock(now + walker.minutes(home)) if home else "",
            "skills": [{"name": k.name, "level": k.level, "xp": k.xp, "next": k.next_xp, "to_go": k.to_go,
                        "share": round(k.share, 3), "ways": list(k.ways)} for k in skills.progress(s.experience)],
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
