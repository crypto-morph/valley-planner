"""The Sell tab: what to put in the shipping bin, what to run through a machine first, and what to hold on to.

Prices are the game's own (facts/sell.py), so every profession bonus and
the profit margin are in. Only plain produce is suggested for the bin:
crops, forage, fish, animal goods, artisan goods, gems and minerals, but
not the materials your known crafting recipes use.

Always held: what the bundle plan has set aside, items an open request
asks for, the first copy of anything the museum hasn't had, and a loved
gift for each birthday in the next week.
Held unless you switch it off: gifts a villager loves (2 per villager who
loves it, up to 4) or likes (1), one of anything a Help Wanted request can
ask for this season (they pay 3x), and one of each crop you hold no seeds
for (a Seed Maker turns it into seeds).
Machines: each machine you own takes one batch (we can't see which are
busy), when its product sells for at least 1.3x the raw goods.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ..facts.help_wanted import raw_pool
from ..facts.machines import Input
from ..facts.sell import item_sell_price, sell_price
from .farm import Farm

PRODUCE = {-75: "Vegetable", -79: "Fruit", -80: "Flower", -81: "Forage", -4: "Fish", -5: "Egg", -6: "Milk",
           -18: "Animal product", -26: "Artisan good", -27: "Syrup", -2: "Gem", -12: "Mineral", -14: "Meat",
           -20: "Trash", -23: "Shellfish"}
GROWN = {-75, -79, -80, -4, -5, -6, -18, -26, -14, -23}  # never treated as a crafting material
QUALITY_WORD = {0: "", 1: "silver", 2: "gold", 4: "iridium"}
FILTERS = {
    "loved": "Gifts a villager loves (2 for each who loves it, up to 4)",
    "liked": "Gifts a villager likes (1)",
    "help_wanted": "Things a Help Wanted request can ask for this season, which pays 3x (1)",
    "seeds": "One of every crop you hold no seeds for, for the Seed Maker (1)",
}
DEFAULT_FILTERS = {"loved": True, "liked": False, "help_wanted": True, "seeds": True}
PROCESS_GAIN = 1.3
SEED_MAKER = "(BC)25"


@dataclass
class _Stack:
    it: object
    left: int


def _take(stacks: list[_Stack], n: int, min_q: int = 0) -> list[tuple[int, int]]:
    """Set aside n from the lowest qualities that still qualify, so the best stays free to sell."""
    got = []
    for s in sorted((s for s in stacks if s.it.quality >= min_q), key=lambda s: s.it.quality):
        k = min(n, s.left)
        if k:
            s.left -= k
            n -= k
            got.append((s.it.quality, k))
        if not n:
            break
    return got


def view(farm: Farm, filters: dict[str, bool] | None = None) -> dict:
    s, w = farm.save, farm.when
    on = {**DEFAULT_FILTERS, **(filters or {})}
    objects = farm.data.asset("Data/Objects")
    by_id: dict[str, list[_Stack]] = defaultdict(list)
    for it in s.items:
        if it.qualified_id and not it.big:
            by_id[it.qualified_id].append(_Stack(it, it.stack))
    keep: dict[tuple[str, int, str], int] = defaultdict(int)

    def hold(qid: str, n: int, why: str, min_q: int = 0) -> None:
        for q, k in _take(by_id.get(qid, []), n, min_q):
            keep[(qid, q, why)] += k

    # Always held
    plan = farm.bundles.plan(s.items)
    for (bkey, _), parts in plan.reserved.items():
        b = farm.bundles.by_key[bkey]
        for qid, q, n in parts:
            hold(qid, n, f"{b.display} bundle", q)
    for q in s.quests:
        if q.get("item_id") and not q.get("completed"):
            hold(f"(O){q['item_id']}", q.get("count") or 1, f"{q.get('target') or 'a'} request: {q.get('title')}")
    for qid in by_id:
        t = (objects.get(qid[3:]) or {}).get("Type")
        if t in ("Arch", "Minerals") and qid[3:] not in s.museum:
            hold(qid, 1, "the museum (not donated yet)")
    villagers = [n for n, c in farm.data.asset("Data/Characters").items() if c.get("BirthSeason")]
    for dp in range(w.days_played, w.days_played + 8):
        day = w.on(dp)
        for npc in farm.calendar.birthdays(day):
            loved = [qid for qid, st in by_id.items() if any(x.left for x in st)
                     and farm.gifts.giftable(qid) and farm.gifts.taste(npc, qid) == "love"]
            if loved:
                cheapest = min(loved, key=lambda qid: int((objects.get(qid[3:]) or {}).get("Price") or 0))
                when = "today" if dp == w.days_played else farm.label(dp).rsplit(",", 1)[0]
                hold(cheapest, 1, f"{npc}'s birthday ({when})")

    # Held unless switched off
    crafting_inputs = set()
    for name, raw in farm.data.asset("Data/CraftingRecipes").items():
        if name in s.crafting_recipes:
            parts = raw.split("/")[0].split()
            crafting_inputs |= {f"(O){parts[i]}" for i in range(0, len(parts) - 1, 2)}
    help_ids = raw_pool(w.season, w.day, w.year, mine_lowest=w.mine_lowest, vault="ccVault" in s.mail,
                        crafting=set(s.crafting_recipes))
    seed_of = {f"(O){c.harvest}": f"(O){seed}" for seed, c in farm.crops.by_seed.items()
               if c.harvest and objects.get(seed, {}).get("Category") == -74}
    held = farm.held()
    owned = {_machine_id(farm, name): n for name, n in s.machines.items()}
    seed_maker = bool(owned.get(SEED_MAKER))
    impact = {k: {"count": 0, "value": 0} for k in FILTERS}
    seed_jobs = []

    def produce(qid: str, it) -> bool:
        if it.price is None and not objects.get(qid[3:]):
            return False
        cat = it.category if it.category is not None else (objects.get(qid[3:]) or {}).get("Category")
        if qid in crafting_inputs and cat not in GROWN:
            return False
        return cat in PRODUCE or (it.type == "Arch" and qid[3:] in s.museum)

    for qid, stacks in by_id.items():
        sample = stacks[0].it
        if not produce(qid, sample) or not any(x.left for x in stacks):
            continue
        holds: dict[str, tuple[int, str]] = {}
        if farm.gifts.giftable(qid):
            loves = [v for v in villagers if farm.gifts.taste(v, qid) == "love"]
            likes = [v for v in villagers if farm.gifts.taste(v, qid) == "like"]
            if loves:
                holds["loved"] = (min(4, 2 * len(loves)), "loved by " + ", ".join(loves[:4]))
            if likes:
                holds["liked"] = (1, "liked by " + ", ".join(likes[:3]) + ("…" if len(likes) > 3 else ""))
        if qid[3:] in help_ids:
            holds["help_wanted"] = (1, "a Help Wanted request could ask for it (3x the price)")
        seed = seed_of.get(qid)
        if seed and not held.get(seed):
            holds["seeds"] = (1, f"you have no {farm.name(seed)}: " + (
                "put one in your Seed Maker" if seed_maker else "keep one until you have a Seed Maker"))
        spare = sum(x.left for x in stacks)
        cheapest = min(stacks, key=lambda x: x.it.quality).it
        for k, (n, _) in holds.items():
            impact[k]["count"] += min(n, spare)
            impact[k]["value"] += min(n, spare) * item_sell_price(cheapest, farm.farmer, profit_margin=s.profit_margin)
        active = [(n, why) for k, (n, why) in holds.items() if on.get(k)]
        if not active:
            continue
        if seed_maker and on["seeds"] and "seeds" in holds:
            seed_jobs.append({"name": farm.name(qid), "count": 1, "machine": "Seed Maker",
                              "product": f"1-3 {farm.name(seed)}", "each_raw": 0, "each_product": 0, "gain": 0,
                              "seeds": True})
        n = max(active)[0]
        for q, k in _take(stacks, n):
            keep[(qid, q, "; ".join(why for _, why in active))] += k

    # Process, then sell
    capacity = dict(owned)
    spare = {qid: sum(x.left for x in st) for qid, st in by_id.items()}  # what's left after the holds
    sell: dict[tuple[str, int], dict] = {}
    process: dict[tuple[str, str], dict] = {}
    materials: dict[str, int] = defaultdict(int)
    for qid, stacks in by_id.items():
        for st in sorted(stacks, key=lambda x: -(x.it.price or 0)):
            it, n = st.it, st.left
            if not n:
                continue
            if not produce(qid, it):
                if qid in crafting_inputs or it.category in (-15, -16):
                    materials[farm.name(qid)] += n
                continue
            each = item_sell_price(it, farm.farmer, profit_margin=s.profit_margin)
            best = None
            for mid, cap in capacity.items():
                if cap <= 0 or mid == SEED_MAKER:
                    continue
                out = farm.machines.output(mid, Input(qid, n, it.quality, it.preserve or None, it.preserved_id or None),
                                           w, professions=set(s.professions))
                if not out or not out.item or out.uses > n:
                    continue
                if any(spare.get(a, 0) < k for a, k in out.also):
                    continue  # you don't hold what else it burns (coal)
                o = objects.get(out.item.removeprefix("(O)")) or {}
                prod = sell_price(out.price, out.quality, farm.farmer, out.item, out.name, o.get("Category"),
                                  o.get("Type") or "", profit_margin=s.profit_margin, preserve=out.preserve)
                burnt = sum(k * _value(farm, a) for a, k in out.also)
                per_input = (prod * out.stack[0] - burnt) / out.uses
                if per_input >= each * PROCESS_GAIN and (best is None or per_input > best[1]):
                    best = (mid, per_input, out, prod)
            if best:
                mid, per_input, out, prod = best
                use = min(n, capacity[mid] * out.uses)
                loads = -(-use // out.uses)
                capacity[mid] -= loads
                for a, k in out.also:
                    spare[a] = spare.get(a, 0) - k * loads
                row = process.setdefault((qid, mid), {"name": farm.name(qid), "machine": _machine_name(farm, mid),
                                                      "product": out.name, "count": 0, "each_raw": each,
                                                      "each_product": prod, "net_each": per_input,
                                                      "burns": ", ".join(f"{k} {farm.name(a)}" for a, k in out.also),
                                                      "minutes": out.minutes, "days": out.days})
                row["count"] += use
                n -= use
            if not n:
                continue
            cat = it.category if it.category is not None else (objects.get(qid[3:]) or {}).get("Category")
            row = sell.setdefault((qid, it.quality), {"name": farm.name(qid) if not it.preserve else it.name,
                                                      "quality": QUALITY_WORD.get(it.quality, ""), "count": 0,
                                                      "each": each, "kind": PRODUCE.get(cat, "Artifact"),
                                                      "where": set()})
            row["count"] += n
            row["where"].add(farm.where_label(it.where, it.chest))
    sell_rows = sorted(({**r, "total": r["count"] * r["each"], "where": sorted(r["where"])} for r in sell.values()),
                       key=lambda r: -r["total"])
    proc_rows = sorted(({**r, "gain": int((r.pop("net_each") - r["each_raw"]) * r["count"])}
                        for r in process.values()), key=lambda r: -r["gain"]) + seed_jobs
    keep_rows = [{"name": farm.name(qid), "quality": QUALITY_WORD.get(q, ""), "count": n, "why": why}
                 for (qid, q, why), n in sorted(keep.items(), key=lambda kv: (kv[0][2], kv[0][0]))]
    return {"total": sum(r["total"] for r in sell_rows), "count": sum(r["count"] for r in sell_rows),
            "sell": sell_rows, "process": proc_rows, "process_gain": sum(r["gain"] for r in proc_rows),
            "keep": keep_rows, "materials": sorted(materials.items(), key=lambda kv: -kv[1]),
            "filters": [{"id": k, "label": label, "on": bool(on[k]), **impact[k]} for k, label in FILTERS.items()]}


def _value(farm: Farm, qid: str) -> int:
    o = farm.data.asset("Data/Objects").get(qid.removeprefix("(O)")) or {}
    return sell_price(int(o.get("Price") or 0), 0, farm.farmer, qid, o.get("Name") or "", o.get("Category"),
                      profit_margin=farm.save.profit_margin)


def _machine_id(farm: Farm, name: str) -> str:
    for bid, b in farm.data.asset("Data/BigCraftables").items():
        if b.get("Name") == name:
            return f"(BC){bid}"
    return name


def _machine_name(farm: Farm, mid: str) -> str:
    b = farm.data.asset("Data/BigCraftables").get(mid.removeprefix("(BC)")) or {}
    return farm.data.text(b.get("DisplayName")) or b.get("Name") or mid
