"""The Sell tab: what to put in the shipping bin, what to run through a machine first, and what to hold on to.

Prices are the game's own (facts/sell.py), so every profession bonus and
the profit margin are in. Only plain produce is suggested for the bin:
crops, forage, fish, animal goods, artisan goods, gems and minerals, but
not the materials your known crafting recipes use.

What to keep back: views/keep.py's rules, in order (bundles, requests, the Museum, festivals, birthdays, the
Seed Maker, Help Wanted, gifts), each set to always, ask or off. What no rule keeps is sold or processed.
The Seed Maker keeps the lowest quality: it gives 1-3 seeds whatever goes in (rule seedmaker.output-1-3).
Machines: each machine you own takes one batch (we can't see which are
busy), when its product sells for at least 1.3x the raw goods.

Worth getting: for whatever's left raw (or whatever your own machines manage), we also check every machine
in the game's data, owned or not. One you don't have at all, that would pay better than what you're doing
now, is a hint — with its crafting recipe's materials and how it's learned (engine/unlocks), the same chain
the Route tab prices.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ..engine.unlocks import Unlocks
from ..facts.machines import Input
from ..facts.sell import item_sell_price, sell_price
from . import keep as keep_rules
from .farm import Farm

PRODUCE = {-75: "Vegetable", -79: "Fruit", -80: "Flower", -81: "Forage", -4: "Fish", -5: "Egg", -6: "Milk",
           -18: "Animal product", -26: "Artisan good", -27: "Syrup", -2: "Gem", -12: "Mineral", -14: "Meat",
           -20: "Trash", -23: "Shellfish"}
GROWN = {-75, -79, -80, -4, -5, -6, -18, -26, -14, -23}  # never treated as a crafting material
QUALITY_WORD = {0: "", 1: "silver", 2: "gold", 4: "iridium"}
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


def view(farm: Farm, rules: dict[str, str] | None = None, declined: frozenset[str] = frozenset()) -> dict:
    """`rules`: {rule id: mode} for views/keep.py's rules; `declined`: the ids of Today's questions you said no to."""
    s, w = farm.save, farm.when
    objects = farm.data.asset("Data/Objects")
    by_id: dict[str, list[_Stack]] = defaultdict(list)
    for it in s.items:
        if it.qualified_id and not it.big:
            by_id[it.qualified_id].append(_Stack(it, it.stack))
    crafting_inputs = set()
    for name, raw in farm.data.asset("Data/CraftingRecipes").items():
        if name in s.crafting_recipes:
            parts = raw.split("/")[0].split()
            crafting_inputs |= {f"(O){parts[i]}" for i in range(0, len(parts) - 1, 2)}

    def produce(qid: str, it) -> bool:
        if it.price is None and not objects.get(qid[3:]):
            return False
        cat = it.category if it.category is not None else (objects.get(qid[3:]) or {}).get("Category")
        if qid in crafting_inputs and cat not in GROWN:
            return False
        return cat in PRODUCE or (it.type == "Arch" and qid[3:] in s.museum)

    # Keep: each rule in order claims from what the ones above it left (views/keep.py)
    sellable = {qid for qid, st in by_id.items() if produce(qid, st[0].it)}
    mode = keep_rules.modes(rules)
    keep: dict[tuple[str, int, str], int] = defaultdict(int)
    kept_by: dict[str, dict[str, int]] = {r.id: {"count": 0, "value": 0} for r in keep_rules.RULES}
    owned = {_machine_id(farm, name): n for name, n in s.machines.items()}
    seed_jobs = []
    for rule in keep_rules.RULES:
        if mode[rule.id] == keep_rules.OFF:
            continue
        for c in rule.claims(farm, sellable):
            if c.ask and c.ask in declined:
                continue
            for q, k in _take(by_id.get(c.item, []), c.count, c.min_quality):
                keep[(c.item, q, c.why)] += k
                kept_by[rule.id]["count"] += k
                it = next(x.it for x in by_id[c.item] if x.it.quality == q)
                kept_by[rule.id]["value"] += k * item_sell_price(it, farm.farmer, profit_margin=s.profit_margin)
                if rule.id == "seeds" and owned.get(SEED_MAKER) and "you have no" in c.why:
                    seed = c.why.rsplit("you have no ", 1)[1]
                    seed_jobs.append({"name": farm.name(c.item), "count": 1, "machine": "Seed Maker",
                                      "product": f"1-3 {seed}", "each_raw": 0, "each_product": 0, "gain": 0,
                                      "seeds": True})

    # Process, then sell
    capacity = dict(owned)
    spare = {qid: sum(x.left for x in st) for qid, st in by_id.items()}  # what's left after the holds
    spare_snapshot = dict(spare)  # for the "worth getting" hints, below, unaffected by what gets processed
    sell: dict[tuple[str, int], dict] = {}
    process: dict[tuple[str, str], dict] = {}
    materials: dict[str, int] = defaultdict(int)
    used: dict[tuple[str, int], int] = defaultdict(int)  # put through a machine, by item and quality
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
            mids = [mid for mid, cap in capacity.items() if cap > 0 and mid != SEED_MAKER]
            best = _best_output(farm, qid, it, n, w, mids, spare, objects)
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
                used[(qid, it.quality)] += use
                n -= use
            if not n:
                continue
            cat = it.category if it.category is not None else (objects.get(qid[3:]) or {}).get("Category")
            row = sell.setdefault((qid, it.quality), {"name": farm.name(qid) if not it.preserve else it.name,
                                                      "quality": QUALITY_WORD.get(it.quality, ""), "count": 0,
                                                      "each": each, "kind": PRODUCE.get(cat, "Artifact"),
                                                      "where": set(), "id": qid, "category": it.category,
                                                      "q": it.quality})
            row["count"] += n
            row["where"].add(farm.where_label(it.where, it.chest))
    sell_rows = sorted(({**r, "total": r["count"] * r["each"], "where": sorted(r["where"])} for r in sell.values()),
                       key=lambda r: -r["total"])
    proc_rows = sorted(({**r, "gain": int((r.pop("net_each") - r["each_raw"]) * r["count"])}
                        for r in process.values()), key=lambda r: -r["gain"]) + seed_jobs
    keep_rows = [{"name": farm.name(qid), "quality": QUALITY_WORD.get(q, ""), "count": n, "why": why}
                 for (qid, q, why), n in sorted(keep.items(), key=lambda kv: (kv[0][2], kv[0][0]))]
    hint_rows = _hints(farm, by_id, spare_snapshot, owned, objects, produce)
    items = []  # everything you hold that could be sold: what happens to it, and which rule decided
    for qid, stacks in by_id.items():
        if qid not in sellable:
            continue
        for q in sorted({x.it.quality for x in stacks}):
            have = sum(x.it.stack for x in stacks if x.it.quality == q)
            whys = [(why, n) for (i, qq, why), n in keep.items() if i == qid and qq == q]
            sold = sell.get((qid, q), {})
            items.append({"name": farm.name(qid), "quality": QUALITY_WORD.get(q, ""), "have": have,
                          "keep": sum(n for _, n in whys), "why": [{"count": n, "why": why} for why, n in whys],
                          "machine": used.get((qid, q), 0), "sell": sold.get("count", 0),
                          "gold": sold.get("count", 0) * sold.get("each", 0), "icon": farm.icon(qid)})
    items.sort(key=lambda r: (-r["gold"], r["name"], r["quality"]))
    return {"total": sum(r["total"] for r in sell_rows), "count": sum(r["count"] for r in sell_rows),
            "sell": sell_rows, "process": proc_rows, "process_gain": sum(r["gain"] for r in proc_rows),
            "keep": keep_rows, "materials": sorted(materials.items(), key=lambda kv: -kv[1]),
            "rules": [{"id": r.id, "label": r.label, "mode": mode[r.id], "modes": list(r.modes), **kept_by[r.id]}
                      for r in keep_rules.RULES],
            "items": items,
            "hints": hint_rows}


def _best_output(farm: Farm, qid: str, it, n: int, w, mids: list[str], spare: dict[str, int], objects: dict):
    """The best of `mids` for `n` of `it`, if its product beats selling it raw by PROCESS_GAIN (mid, per-input
    gold, the Output, its sell price), else None."""
    s = farm.save
    each = item_sell_price(it, farm.farmer, profit_margin=s.profit_margin)
    best = None
    for mid in mids:
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
    return best


def _hints(farm: Farm, by_id: dict, spare: dict[str, int], owned: dict[str, int], objects: dict, produce) -> list[dict]:
    """A machine you own none of that would pay better, for whatever's left after holding and processing with
    what you have, with how to get it (engine.unlocks: the recipe, then the machine's own materials)."""
    all_mids = [m for m in farm.data.asset("Data/Machines") if m != SEED_MAKER]
    unlocks = Unlocks(farm)
    out: dict[str, dict] = {}
    for qid, stacks in by_id.items():
        n = spare.get(qid, 0)
        if not n:
            continue
        sample = min(stacks, key=lambda st: st.it.quality).it
        if not produce(qid, sample):
            continue
        each = item_sell_price(sample, farm.farmer, profit_margin=farm.save.profit_margin)
        owned_best = _best_output(farm, qid, sample, n, farm.when, [m for m in owned if m != SEED_MAKER], spare,
                                  objects)
        any_best = _best_output(farm, qid, sample, n, farm.when, all_mids, spare, objects)
        if not any_best or owned.get(any_best[0], 0) > 0:
            continue
        mid, per_input, output, _prod = any_best
        current = owned_best[1] if owned_best else each
        if per_input <= current:
            continue
        gain_each = int(per_input - current)
        steps = [{"label": u.label, "gold": u.gold, "how": u.how,
                 "materials": [f"{c} {_material_name(farm, m)}" for m, c in u.materials]}
                for u in unlocks.chain(f"machine:{mid}")]
        out[qid] = {"name": farm.name(qid), "machine": _machine_name(farm, mid), "product": output.name,
                   "gain_each": gain_each, "count": n, "gain_total": gain_each * n, "steps": steps}
    return sorted(out.values(), key=lambda r: -r["gain_total"])


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


def _material_name(farm: Farm, qid: str) -> str:
    """A crafting material by id: a plain object id ("388"), or a big craftable it already qualifies ("(BC)13",
    a Furnace, for the Heavy Furnace's own recipe)."""
    return _machine_name(farm, qid) if qid.startswith("(BC)") else farm.name(f"(O){qid}")


def default(farm: Farm, declined: frozenset[str] = frozenset(), rules: dict[str, str] | None = None) -> dict:
    """The view for these answers and rule settings, worked out once per save: the day plan asks several times."""
    cache = farm.__dict__.setdefault("_sold", {})
    key = (frozenset(declined), tuple(sorted(keep_rules.modes(rules).items())))
    if key not in cache:
        cache[key] = view(farm, rules, declined=key[0])
    return cache[key]
