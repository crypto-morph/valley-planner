"""What it all takes: everything the chosen goals need, added up, and every way to get each item.

The route (plan.py) is replayed goal by goal and each goal's requirements are kept, the ones it placed and the
ones it couldn't (the page says what it would take, this year or not). Each unlock is counted once, for the
first goal in priority order that needs it; the other goals that need it are named in `also`. The bus to the
Desert is the Vault's gold, so it's only counted as the Vault. Bars stay bars (their gold, bought as ore from
Clint, is a note), Wood and Hardwood come with the days to gather them.
"""

from __future__ import annotations

import math
import re

from ...facts import romance
from ...facts.sources import seasons_text
from ...views.sell import view as sell_view
from ..cc import YEAR, Planner, Slot, Way
from ..income import project
from ..unlocks import Unlock
from .plan import BOUGHT, HARDWOOD, QUARTZ, REFINED_QUARTZ, STONE, WOOD, Req, Router, Settings, route

DESERT = "place:Desert"
MAX_OPTIONS = 4  # a longer list keeps its first two and folds the rest of the plain ones into one line
_ORDER = {"planned": 0, "possible": 1, "luck": 2, "later": 3, "no": 4}


def _snake(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def _item_label(req_label: str) -> str:
    """'Truffle (Chef's)' -> 'Truffle'; 'the kitchen' -> 'The kitchen'."""
    return _cap(req_label.split(", from the ")[0].split(" (")[0])


def _thing(label: str) -> str:
    for verb in ("build ", "buy ", "upgrade ", "craft ", "plant "):
        label = label.removeprefix(verb)
    return label


def _way_label(w: Way) -> str:
    return _cap(w.source.label.removesuffix(" (deluxe)").removesuffix(" (random)"))


def _bare(label: str) -> str:
    return re.sub(r"^(a|an|the) ", "", label.split(" (")[0].lower())


def _detail(chain: list[Unlock], item: str = "", before: list[Unlock] = ()) -> str:
    """'Deluxe Barn, then a Pig': what a way buys or builds (the item itself left out), and what it waits for
    that's counted elsewhere."""
    steps = [_thing(u.label) for u in chain if not u.key.startswith(("floor:", "recipe:"))]
    steps = [x for x in steps if not item or not _bare(x).startswith(_bare(item))]
    steps += [f"the recipe ({u.how})" for u in chain if u.key.startswith("recipe:") and u.how]
    if steps:
        steps[0] = re.sub(r"^(a|an) ", "", steps[0])
    out = _cap(", then ".join(steps))
    after = [_thing(u.label) for u in before if not u.key.startswith(("floor:", "recipe:"))]
    if after:
        out += ("; " if out else "") + "after " + " and ".join(after)
    return _cap(out)


class _Tally:
    """Unlocks counted once across the goals, in priority order."""

    def __init__(self, router: Router, vault_counted: bool):
        self.r = router
        self.vault = vault_counted
        self.owner: dict[str, dict] = {}  # unlock key -> the item that pays for it
        self.users: dict[str, list[str]] = {}  # unlock key -> every goal that needs it, in order
        self.names: dict[str, str] = {}  # goal id -> its label

    def also(self, chain: list[Unlock], goal: str) -> list[str]:
        """The other goals (labels) these unlocks serve."""
        ids = dict.fromkeys(g for u in chain for g in self.users.get(u.key, ()) if g != goal)
        return [self.names.get(g, g) for g in ids]

    def chain(self, req: Req) -> list[Unlock]:
        chain = [u for u in req.chain if not u.done]
        if any(m == HARDWOOD for u in chain for m, _ in u.materials):  # stumps need a Steel Axe
            axe = [u for u in self.r.planner.unlocks.chain("tool:Axe@2") if not u.done]
            keys = {u.key for u in axe}
            chain = axe + [u for u in chain if u.key not in keys]
        return chain

    def split(self, chain: list[Unlock], item: dict | None) -> tuple[list[Unlock], list[Unlock]]:
        """(the unlocks this item pays for, the ones another item already does)."""
        own = [u for u in chain if self.owner.get(u.key, item) is item]
        return own, [u for u in chain if u not in own]

    def add(self, item: dict, goal: str, chain: list[Unlock]) -> None:
        for u in chain:
            users = self.users.setdefault(u.key, [])
            if goal not in users:
                users.append(goal)
            first = self.owner.get(u.key)
            if first is not None:
                if first["goal"] != goal and goal not in first["also"]:
                    first["also"].append(goal)
                continue
            self.owner[u.key] = item
            if u.key == DESERT and self.vault:
                continue  # the bus is the Vault's gold
            if u.gold:
                item["amounts"]["gold"] = item["amounts"].get("gold", 0) + u.gold
            for m, n in u.materials:
                if not m.startswith("-"):
                    item["amounts"][m] = item["amounts"].get(m, 0) + n


def _record(r: Router) -> dict[str, tuple]:
    """Keep what each goal asks for as the route places it: (requirements, gold paid, misses)."""
    asked: dict[str, tuple] = {}
    ask = r.requirements

    def requirements(oid: str):
        out = ask(oid)
        asked[oid] = (out[0], out[1], list(r.misses))
        return out

    r.requirements = requirements
    return asked


def _courtship_rest(r: Router, reqs: list[Req], misses: list[tuple[str, str]]) -> list[Req]:
    """What marriage still takes after the route stopped short: the Bouquet and the Mermaid's Pendant."""
    name = r.sweetheart()
    if not name:
        return []
    have = {q.label for q in reqs}
    objects = r.farm.data.asset("Data/Objects")
    out = []
    status = r.farm.save.friends[name].status if name in r.farm.save.friends else ""
    if status != "Dating" and not any(x.startswith("a Bouquet") for x in have):
        price = 2 * int((objects.get(romance.BOUQUET) or {}).get("Price") or 0)
        out.append(Req(f"a Bouquet for {name}", r.end, r.end, [Unlock("bouquet", "buy a Bouquet from Pierre", price)],
                       0))
    if "the Mermaid's Pendant" not in have:
        price = 2 * int((objects.get(romance.PENDANT) or {}).get("Price") or 0)
        u = r.planner.unlocks
        chain = u.chain("kitchen") + u.chain("place:BeachTidePools") + \
            [Unlock("pendant", "buy the Mermaid's Pendant from the Old Mariner", price)]
        out.append(Req("the Mermaid's Pendant", r.end, r.end, chain, 0, "social",
                       season="on a rainy day, from the Old Mariner past the beach bridge"))
    return out


def _slots(r: Router) -> dict[str, Slot]:
    return {f"{s.name} ({s.bundle})": s for _k, _n, slots in r.planner.bundle_slots() for s in slots if not s.have}


def needs(farm, targets: list[str], nice: list[str] = (), *, settings: Settings | None = None,
          cave: str = "best") -> dict:
    """Everything these goals take, added up, with what each part is for and every way to get each item."""
    settings = settings or Settings()
    plan = route(farm, targets, nice, settings=settings, cave=cave)
    r = Router(farm, settings=settings, cave=plan["cave"])
    asked = _record(r)
    outs = [r.objective(o, "target") for o in targets] + [r.objective(o, "nice") for o in nice]
    status = {o["id"]: o["status"] for o in plan["objectives"]}
    held = farm.held()
    slots = _slots(r)
    tally = _Tally(r, vault_counted=any(asked.get(o.id, ((), 0))[1] for o in outs))
    tally.names = {o.id: o.label for o in outs}
    items: list[dict] = []  # each: goal, label, how, amounts, also, this_year
    mine: dict[str, dict] = {}  # requirement -> its item (the first goal's)
    fish: set[str] = set()
    floor = 0
    for o in outs:
        if o.id not in asked:
            continue  # done already
        reqs, paid, misses = asked[o.id]
        if o.id == "marriage" and misses:
            reqs = list(reqs) + _courtship_rest(r, reqs, misses)
        placed = {st.label for st in o.steps}
        for q in reqs:
            chain = tally.chain(q)
            slot = slots.get(q.label.split(", from the ")[0])
            it = {"goal": o.id, "label": _item_label(q.label), "how": "", "amounts": {}, "also": [],
                  "this_year": q.label in placed}
            own, _ = tally.split(chain, it)
            it["how"] = q.season if q.activity == "social" else _detail(own, it["label"])
            if slot and not own and "from the " not in q.label:
                it["how"] = _cap(q.season)
            tally.add(it, o.id, chain)
            mine.setdefault(q.label, it)
            items.append(it)
            if q.activity == "fish":
                fish.add(q.season)
            floor = max([floor] + [int(u.key[6:]) for u in chain if u.key.startswith("floor:")])
        if paid:
            bus = [_item_label(q.label) for q in reqs if any(u.key == DESERT for u in q.chain)]
            items.append({"goal": o.id, "label": "The Vault", "how": "also brings the bus" + (
                f": {', '.join(bus)}" if bus else ""), "amounts": {"gold": paid}, "also": [],
                "this_year": r.vault_day is not None})
    goals = [{"id": o.id, "label": o.label, "tier": o.tier, "status": status.get(o.id, o.status)} for o in outs]
    names = {o.id: o.label for o in outs}
    resources = _resources(farm, r, items, held, names)
    by = {x["id"]: x for x in resources}
    rq = by.get("refined_quartz")
    quartz = max(0, (rq["short"] if rq else 0) - held.get(f"(O){QUARTZ}", 0))
    mining = math.ceil(quartz / r.s.quartz_per_day) if quartz else 0
    if rq and mining:
        rq["days"], rq["days_label"] = mining, "days in the Mines for the Quartz"
    if floor > farm.when.mine_lowest:
        mining += math.ceil((floor - farm.when.mine_lowest) / r.s.floors_per_day)
    days = {"chop": by["wood"]["days"] or 0, "stumps": by["hardwood"]["days"] or 0, "mine": mining,
            "fish": len(fish), "left": r.end - r.today + 1}
    return {"today": farm.label(r.today), "end": farm.label(r.end), "days_left": r.end - r.today + 1,
            "goals": goals, "resources": resources, "days": days,
            "choices": _choices(farm, r, outs, slots, asked, tally, mine)}


def _resources(farm, r: Router, items: list[dict], held: dict[str, int], names: dict[str, str]) -> list[dict]:
    order = ["gold", WOOD, STONE, HARDWOOD] + [m for it in items for m in it["amounts"]]
    keys = list(dict.fromkeys(order))
    out = []
    for k in keys:
        rows: dict[str, dict] = {}
        for it in items:
            n = it["amounts"].get(k, 0)
            if not n:
                continue
            g = rows.setdefault(it["goal"], {"goal": it["goal"], "label": names[it["goal"]], "amount": 0,
                                             "items": [], "also": []})
            g["amount"] += n
            also = [names[x] for x in it["also"]]
            g["items"].append({"label": it["label"], "how": it["how"], "amount": n, "also": also,
                               "this_year": it["this_year"]})
            g["also"] += [x for x in also if x not in g["also"]]
        for g in rows.values():
            g["items"].sort(key=lambda x: -x["amount"])
        breakdown = sorted(rows.values(), key=lambda g: -g["amount"])
        total = sum(g["amount"] for g in breakdown)
        if k == "gold":
            name, have, unit = "Gold", farm.save.money, "g"
        else:
            name, have, unit = farm.name(f"(O){k}"), held.get(f"(O){k}", 0), ""
            if not total and k not in (WOOD, STONE, HARDWOOD):
                continue  # Wood, Stone and Hardwood are listed even at nothing; other materials when needed
        res = {"id": "gold" if k == "gold" else _snake(name), "label": name, "unit": unit, "total": total,
               "have": have, "expected": None, "short": max(0, total - have), "note": "", "extra": "",
               "days": None, "days_label": "", "breakdown": breakdown, "_key": k,
               "group": "bars" if k != "gold" and (name.endswith(" Bar") or k == REFINED_QUARTZ) else "",
               "short_label": name.removesuffix(" Bar")}
        if k == WOOD:
            res["days"] = math.ceil(res["short"] / r.s.wood_per_day)
            res["days_label"] = f"chopping days at {r.s.wood_per_day} a day"
        elif k == HARDWOOD:
            res["days"] = math.ceil(res["short"] / r.s.hardwood_per_day)
            res["days_label"] = "days at the Secret Woods stumps"
        elif k == STONE:
            res["note"] = "picked up while mining and clearing"
        elif k in BOUGHT and res["short"]:
            res["note"] = f"about {BOUGHT[k] * res['short']:,}g as ore and coal from Clint"
        elif k == REFINED_QUARTZ and res["short"]:
            res["note"] = f"{res['short']} Quartz and {res['short']} Coal through a Furnace"
        out.append(res)
    gold = out[0]
    end = r.end
    pace = project(farm, end, sell_now=sell_view(farm)["total"])
    gold["expected"] = pace["counted"]
    gold["short"] = max(0, gold["total"] - gold["have"] - gold["expected"])
    gold["note"] = "from " + ", ".join(s["label"] for s in pace["streams"] if s["gold"]) if pace["streams"] else ""
    bars = [x for x in out if x["_key"] in BOUGHT or x["_key"] == REFINED_QUARTZ]
    bar_gold = sum((BOUGHT[x["_key"]] if x["_key"] in BOUGHT else BOUGHT["382"]) * x["short"] for x in bars)
    if bar_gold:
        uses = list(dict.fromkeys(i["label"] for x in bars for g in x["breakdown"] for i in g["items"]))
        uses = [u if not u.startswith("The ") else "the " + u[4:] for u in uses]
        what = " and ".join([", ".join(uses[:-1]), uses[-1]] if len(uses) > 1 else uses)
        gold["extra"] = f"Bars for {what} add about {round(bar_gold, -2):,}g if you buy the ore from Clint"
    for x in out:
        x.pop("_key")
    return out


def _choices(farm, r: Router, outs, slots: dict[str, Slot], asked: dict[str, tuple], tally: _Tally,
             mine: dict[str, dict]) -> list[dict]:
    """Items a goal needs that can be got more than one way: every way, the route's one ticked."""
    later = Planner(farm, r.end + YEAR)  # what next year allows
    seen: set[str] = set()
    out = []
    for o in outs:
        placed = {st.label: st for st in o.steps}
        why = dict(o.misses)
        for q in asked.get(o.id, ((),))[0]:
            key = q.label.split(", from the ")[0]
            slot = slots.get(key)
            if slot is None or key in seen:
                continue
            seen.add(key)
            cave = "from the " in q.label
            if len(slot.ways) + (1 if cave else 0) < 2:
                continue
            step = placed.get(q.label)
            opts = []
            if cave:
                who = "fruit bats" if r.cave == "bats" else "mushroom boxes"
                opts.append({"label": f"Your {who}", "detail": "in the farm cave", "gold": 0,
                             "state": "planned" if step else "no",
                             "tag": "✓ PLANNED · FREE" if step else "✕ NOT THIS YEAR",
                             "when": f"likely by {farm.label(q.earliest)}", "odds": None, "planned": bool(step),
                             "also": [], "pick": "cave"})
            same = [w for w in slot.ways if not cave and w.source.label == q.season]
            route_way = next((w for w in same if (w.earliest or 1, w.latest_start or 0) == (q.earliest, q.latest)),
                             same[0] if same else None)
            for w in slot.ways:
                ours = w is route_way
                opts.append(_option(farm, r, later, slot, w, ours, step, why.get(q.label, ""), tally,
                                    mine.get(q.label), o.id))
            opts.sort(key=lambda x: _ORDER[x["state"]])
            out.append({"item": slot.name, "where": f"{slot.bundle} bundle", "goal": o.id, "options": _fold(opts),
                        "picked": r.s.picks.get(slot.name, "")})
    return out


def _option(farm, r: Router, later: Planner, slot: Slot, w: Way, mine: bool, step, miss: str, tally: _Tally,
            item: dict | None, goal: str) -> dict:
    """One way to get an item; its gold is what it would add on top of what the other goals already pay for."""
    chain = r.chain(w)
    own, before = tally.split(chain, item)
    gold = sum(u.gold for u in own if u.key != DESERT)
    detail = _detail(own, before=before)
    if not detail:
        s = seasons_text(w.source)
        detail = "" if s == "any season" else s
    opt = {"label": _way_label(w), "detail": detail, "gold": gold, "state": "possible", "tag": "",
           "when": "", "odds": round(w.odds, 3) if w.odds is not None else None,
           "planned": mine and (step is not None or w.odds is not None), "also": tally.also(chain, goal),
           "pick": w.source.label}
    if mine and step is not None:
        opt.update(state="planned", tag="✓ PLANNED · FREE" if not chain else "✓ PLANNED",
                   when=f"from {farm.label(step.act or step.ready)}")
        return opt
    if w.odds is not None:
        return {**opt, "state": "luck", "tag": f"✓ PLANNED · LUCK {w.odds:.0%}" if mine else f"LUCK · {w.odds:.0%}",
                "when": f"if it turns up by {farm.label(r.end)}; watch it Fridays and Sundays"
                if w.source.kind == "cart" else f"by {farm.label(r.end)}"}
    if mine:  # the route's way, but it couldn't be placed
        late = "too late" in miss or "not in time" in miss
        return {**opt, "state": "no", "tag": "✕ TOO LATE THIS YEAR" if late else "✕ NOT THIS YEAR", "when": miss}
    if w.source.kind == "monster":
        return {**opt, "tag": "MONSTER", "when": "; ".join(w.blocked) + "; not on your route"}
    if w.earliest is not None:
        problems = r.cost(chain)[3]
        if problems:
            return {**opt, "state": "no", "tag": "✕ NOT THIS YEAR", "when": "needs " + "; ".join(problems)}
        return {**opt, "when": f"from {farm.label(w.earliest)}"}
    nxt = later.way(w.source, slot.item)
    if nxt.earliest is not None and nxt.earliest > r.end:
        year = (nxt.earliest - 1) // YEAR + 1
        if w.source.days:
            season = ("Spring", "Summer", "Fall", "Winter")[(nxt.earliest - 1) // 28 % 4]
            tag = f"YEAR {year} · {season} {w.source.days[0]}–{w.source.days[1]}".upper()
        else:
            tag = f"YEAR {year} · FROM {farm.label(nxt.earliest).split(', Year')[0]}".upper()
        return {**opt, "state": "later", "tag": tag,
                "when": "; ".join(f"needs {b}" for b in nxt.blocked) or f"from {farm.label(nxt.earliest)}"}
    return {**opt, "state": "no", "tag": "✕ NOT THIS YEAR", "when": "; ".join(w.blocked) or "not this year"}


def _fold(opts: list[dict]) -> list[dict]:
    """A long list keeps its first two; the other plain ways fold into one line."""
    if len(opts) <= MAX_OPTIONS:
        return opts
    keep, rest = opts[:2], opts[2:]
    fold = [x for x in rest if x["state"] == "possible"]
    if len(fold) < 2:
        return opts
    places = [x["label"].split(" at ", 1)[1] for x in fold if " at " in x["label"]]
    what = f"{len(fold)} more places: {', '.join(places)}" if len(places) == len(fold) else \
        f"{len(fold)} more ways: {', '.join(x['label'] for x in fold)}"
    more = {"label": what, "detail": "", "gold": min(x["gold"] for x in fold), "state": "possible", "tag": "",
            "when": "", "odds": None, "more": True, "planned": False,
            "also": list(dict.fromkeys(g for x in fold for g in x["also"]))}
    return keep + [more] + [x for x in rest if x not in fold]
