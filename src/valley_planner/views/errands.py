"""Errands: what to take to whom, from what you hold right now.

- Gunther (the museum): every artifact and mineral you hold that hasn't
  been donated, your donation count, and the closest museum rewards
  (Data/MuseumRewards: counts of donated items by tag).
- Clint: geodes to crack (25g each) and the tool upgrades you can afford
  now (gold and 5 bars, one level at a time, and only while he isn't
  already working on one).
- The Community Center: what the bundle plan has set aside from what you
  hold, by room and bundle, and the Vault bundles your money covers.
- Birthdays: the next week's birthdays and the loved gifts you hold.
"""

from __future__ import annotations

from collections import defaultdict

from ..engine.unlocks import TOOL_BARS, TOOL_PRICES
from ..facts.bundles import VAULT
from ..facts.machines import Input
from .farm import Farm

GEODE_PRICE = 25
TOOL_TIERS = ("", "Copper", "Steel", "Gold", "Iridium")
TOOL_NAMES = {"Axe": "Axe", "Pickaxe": "Pickaxe", "Hoe": "Hoe", "WateringCan": "Watering Can", "Pan": "Pan"}
QUALITY = {0: "", 1: "silver", 2: "gold", 4: "iridium"}


def gunther(farm: Farm) -> dict:
    s, objects = farm.save, farm.data.asset("Data/Objects")
    held = farm.held()
    take = []
    for qid, n in sorted(held.items(), key=lambda kv: farm.name(kv[0])):
        oid = qid.removeprefix("(O)")
        t = (objects.get(oid) or {}).get("Type")
        if qid.startswith("(O)") and t in ("Arch", "Minerals") and oid not in s.museum:
            take.append({"name": farm.name(qid), "kind": "artifact" if t == "Arch" else "mineral", "held": n,
                         "where": farm.where_held(qid)})
    donated_tags: dict[str, int] = defaultdict(int)
    for oid in s.museum:
        for tag in farm.machines.tags(Input(f"(O){oid}")):
            donated_tags[tag] += 1
    rewards = []
    for rid, r in farm.data.asset("Data/MuseumRewards").items():
        need = [(x["Tag"].lower(), x["Count"]) for x in r.get("TargetContextTags") or []]
        left = sum(max(0, n - donated_tags.get(tag, 0)) for tag, n in need)
        if left:
            reward = r.get("RewardItemId") or ""
            rewards.append({"id": rid, "left": left, "reward": farm.name(reward) if reward.startswith("(O)") else
                            _reward_name(farm, reward), "needs": [f"{n} × {_tag_label(farm, t)}" for t, n in need]})
    rewards.sort(key=lambda r: r["left"])
    return {"title": "Take to Gunther", "donated": len(s.museum), "take": take, "next_rewards": rewards[:4]}


def clint(farm: Farm) -> dict:
    s = farm.save
    held = farm.held()
    objects = farm.data.asset("Data/Objects")
    geodes = [{"name": farm.name(q), "held": n, "cost": n * GEODE_PRICE, "where": farm.where_held(q)}
              for q, n in held.items()
              if q.startswith("(O)") and (objects.get(q[3:]) or {}).get("GeodeDropsDefaultItems")
              or (q.startswith("(O)") and (objects.get(q[3:]) or {}).get("GeodeDrops"))]
    upgrades = []
    for tool, level in s.tool_levels.items():
        nxt = level + 1
        if level < 0 or nxt not in TOOL_PRICES:
            continue
        bars = held.get(f"(O){TOOL_BARS[nxt]}", 0)
        price = TOOL_PRICES[nxt]
        upgrades.append({"tool": f"{TOOL_TIERS[nxt]} {TOOL_NAMES.get(tool, tool)}", "gold": price,
                         "bars": f"5 {farm.name('(O)' + TOOL_BARS[nxt])}", "have_bars": bars,
                         "can": s.money >= price and bars >= 5 and not s.tool_at_clint})
    upgrades.sort(key=lambda u: (not u["can"], u["gold"]))
    busy = f"Clint is already working on your {TOOL_NAMES.get(s.tool_at_clint, s.tool_at_clint)}" \
        if s.tool_at_clint else ""
    return {"title": "Take to Clint", "geodes": geodes, "upgrades": upgrades, "busy": busy, "money": s.money}


def community_center(farm: Farm) -> dict:
    s = farm.save
    plan = farm.bundles.plan(s.items)
    rooms: dict[str, list] = defaultdict(list)
    for (bkey, _), parts in plan.reserved.items():
        b = farm.bundles.by_key[bkey]
        for qid, q, n in parts:
            rooms[b.room].append({"bundle": b.display, "name": farm.name(qid), "count": n,
                                  "where": farm.where_held(qid),
                                  "quality": QUALITY.get(q, ""), "open": farm.bundles.notes_shown(b.area)})
    vault = [{"bundle": b.display, "gold": b.gold} for b in farm.bundles.in_area(VAULT) if not b.done]
    payable = [v for v in vault if v["gold"] <= s.money]
    return {"title": "Take to the Community Center", "rooms": [{"room": r, "items": items}
                                                                  for r, items in rooms.items()],
            "vault": vault, "vault_payable": payable, "money": s.money}


def birthdays(farm: Farm, days: int = 7) -> dict:
    w, held = farm.when, farm.held()
    out = []
    for dp in range(w.days_played, w.days_played + days + 1):
        day = w.on(dp)
        for npc in farm.calendar.birthdays(day):
            loved = sorted(farm.name(q) for q in held if farm.gifts.giftable(q)
                            and farm.gifts.taste(npc, q) == "love")
            liked = sorted(farm.name(q) for q in held if farm.gifts.giftable(q)
                            and farm.gifts.taste(npc, q) == "like")[:6]
            out.append({"who": npc, "date": "today" if dp == w.days_played else farm.label(dp).rsplit(",", 1)[0],
                        "loved": loved, "liked": liked})
    return {"title": "Birthday gifts", "birthdays": out}


def _tag_label(farm: Farm, tag: str) -> str:
    if tag.startswith("id_o_"):
        return farm.name(f"(O){tag[5:]}")
    return {"item_type_arch": "artifacts", "item_type_minerals": "minerals"}.get(tag, tag.replace("_", " "))


def _reward_name(farm: Farm, qid: str) -> str:
    if qid.startswith("(F)"):
        f = (farm.data.asset("Data/Furniture").get(qid[3:]) or "").split("/")
        return farm.data.text(f[7]) if len(f) > 7 and f[7] else (f[0] or qid)
    if qid.startswith("(BC)"):
        b = farm.data.asset("Data/BigCraftables").get(qid[4:]) or {}
        return farm.data.text(b.get("DisplayName")) or b.get("Name") or qid
    return qid or "a reward"


FAIR = ("fall", 16)
LEAD_DAYS = 7  # seasonal buttons show for the week before


def grange(farm: Farm) -> dict:
    """The best nine for the Fair's grange display from everything you hold, and what to pack."""
    from ..facts.grange import Entry, best, prize, score
    from ..facts.sell import item_sell_price
    held: dict[tuple, list] = {}
    for it in farm.save.items:
        if not it.qualified_id or it.big or not it.qualified_id.startswith("(O)"):
            continue
        cat = it.category if it.category is not None else (farm.items.get(it.id).category if farm.items.get(it.id)
                                                            else None)
        e = Entry(it.qualified_id, it.name if it.preserve else farm.name(it.qualified_id), it.quality, cat,
                  item_sell_price(it, farm.farmer, profit_margin=farm.save.profit_margin))
        key = (e.item, e.quality, e.name)
        if key in held:
            held[key][1] += it.stack
            held[key][2].add(farm.where_label(it.where, it.chest))
        else:
            held[key] = [e, it.stack, {farm.where_label(it.where, it.chest)}]
    picked = best([(e, n) for e, n, _ in held.values()])
    points = score(picked)
    place, tokens = prize(points)
    where = {(e.item, e.quality, e.name): w for e, _, w in held.values()}
    rows = [{"name": e.name, "quality": QUALITY.get(e.quality, ""), "kind": e.kind or "no kind bonus",
             "price": e.price, "points": e.points,
             "pack": sorted(x for x in where[(e.item, e.quality, e.name)] if x != "your backpack")} for e in picked]
    kinds = sorted({e.kind for e in picked if e.kind})
    days = _days_until(farm, FAIR)
    return {"title": "Grange display for the Fair", "score": points, "place": place, "tokens": tokens,
            "kinds": kinds, "items": rows, "days": days,
            "short": max(0, 90 - points), "pack": sorted({w for r in rows for w in r["pack"]})}


def _days_until(farm: Farm, when: tuple[str, int]) -> int:
    w = farm.when
    seasons = ("spring", "summer", "fall", "winter")
    target = seasons.index(when[0]) * 28 + when[1]
    now = seasons.index(w.season) * 28 + w.day
    return (target - now) % 112


def seasonal(farm: Farm) -> list[dict]:
    """Errand buttons that only show for the week before their day."""
    out = []
    days = _days_until(farm, FAIR)
    if days <= LEAD_DAYS:
        out.append({"id": "grange", "label": "Grange display" + (" (today!)" if days == 0 else f" ({days} days)")})
    return out


def trees(farm: Farm) -> dict:
    """Your fruit trees and when each fruits next, and the farm cave's odds if it's fruit bats."""
    from ..facts.cave import BAT_FRUIT, BATS, MUSHROOM, MUSHROOMS, nightly
    from .crops import fruit_trees
    choice = {1: BATS, 2: MUSHROOMS}.get(farm.save.cave_choice)
    cave = []
    if choice:
        for oid in (BAT_FRUIT if choice == BATS else MUSHROOM):
            cave.append({"name": farm.name(f"(O){oid}"), "chance": round(nightly(choice, f"(O){oid}"), 3)})
        cave.sort(key=lambda c: -c["chance"])
    return {"title": "Fruit trees", "trees": fruit_trees(farm),
            "cave": cave, "cave_kind": {BATS: "fruit bats", MUSHROOMS: "mushroom boxes"}.get(choice, "")}


ERRANDS = {"trees": trees, "gunther": gunther, "clint": clint, "cc": community_center, "birthdays": birthdays,
           "grange": grange}
