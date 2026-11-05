"""The route's results as the page shows them: the tech tree, and the coming week's agenda."""

from __future__ import annotations

import re

from .model import Outcome

AGENDA_DAYS = 7
SOON, NOW = 14, 7  # days to spare: up to NOW is this week's, up to SOON is soon


def _urgency(slack: int | None) -> str:
    if slack is None:
        return "plenty"
    return "now" if slack <= NOW else "soon" if slack <= SOON else "plenty"


def _tree(farm, outcomes: list[Outcome], today: int, end: int) -> dict:
    """The route as a tech tree: a lane per goal, weekly columns from today, and in each lane rows of cards, each
    row one thing the goal needs with its steps left to right (chop, build, buy, then the item). A card that
    serves more than one goal says which."""
    n_cols = max(1, (end - today) // 7 + 1)

    def col(d):
        return min(n_cols - 1, max(0, (d - today) // 7))

    columns = [{"label": _week_label(farm, today + 7 * i, min(end, today + 7 * i + 6)), "gold": 0}
               for i in range(n_cols)]
    names = {o.id: o.label for o in outcomes}
    # who else uses what a step brings: unlocks planned "earlier", and whole requirements shared
    users: dict[str, list[dict]] = {}
    shared_by: dict[str, list[dict]] = {}
    for o in outcomes:
        for st in o.steps:
            if st.shared:
                shared_by.setdefault(st.label, []).append({"goal": o.label, "why": st.label})
                continue
            for n in st.needs:
                if n["state"] == "earlier":
                    users.setdefault(n["key"], []).append({"goal": o.label, "why": st.label})
    synergy: dict[str, dict] = {}
    lanes = []
    for o in outcomes:
        steps = []
        for st in o.steps:
            own = {"goal": o.label, "why": st.label}
            item = st.label.split(" (")[0]
            if st.shared:
                steps.append([{"col": col(st.ready), "tag": "SHARED", "title": item, "urgency": "shared",
                               "detail": f"planned under {names.get(st.shared, st.shared)}", "gold": 0,
                               "helps": [], "waits": []}])
                continue
            urgency = "daily" if st.how.startswith("talk to") else _urgency(
                None if st.last is None else st.last - today)
            cards: list[dict] = []
            new = [n for n in st.needs if n["state"] == "new"]
            hard = any(m.endswith(" Hardwood") for n in new for m in n["materials"])
            if st.chop_days:
                cards.append({"col": col(min(st.chop_days)), "tag": "CHOP",
                              "title": f"{'Wood and Hardwood' if hard else 'Wood'}, {len(st.chop_days)} days",
                              "detail": _span(farm, st.chop_days)})
            if st.mine_days:
                cards.append({"col": col(min(st.mine_days)), "tag": "MINE",
                              "title": f"The Mines, {len(st.mine_days)} days", "detail": _span(farm, st.mine_days)})
            for n in new:
                cost = ", ".join(([f"{n['gold']:,}g"] if n["gold"] else []) + n["materials"])
                verb = _verb(n)
                helps = [own] + users.get(n["key"], [])
                cards.append({"col": col(n["on"] if n["on"] is not None else st.day), "tag": verb,
                              "title": _thing(n["label"]).removeprefix("a ").removeprefix("the ")[:1].upper()
                              + _thing(n["label"]).removeprefix("a ").removeprefix("the ")[1:],
                              "detail": "; ".join(x for x in (cost, f"ready {n['ready']}" if n["ready"] else "") if x),
                              "gold": n["gold"], "helps": helps if len(helps) > 1 else []})
                if len(helps) > 1:
                    synergy.setdefault(n["key"], {"what": _thing(n["label"]), "goals": helps})
            if not new and st.gold:
                cards.append({"col": col(st.day), "tag": "BUY", "title": item, "detail": f"{st.gold:,}g",
                              "gold": st.gold})
            if st.how or not new:
                helps = [own] + shared_by.get(st.label, [])
                tag = "FARM CAVE" if "from the fruit bats" in st.label or "from the mushroom" in st.label \
                    else _tag(st.how)
                cards.append({"col": col(st.act or st.ready), "tag": tag, "title": item, "final": True,
                              "detail": f"{st.how} · {farm.label(st.act or st.ready)}" if st.how
                              else farm.label(st.ready), "helps": helps if len(helps) > 1 else []})
                if len(helps) > 1:
                    synergy.setdefault(st.label, {"what": item, "goals": helps})
            waits = [f"waits for {n['label']}" + (f", ready {n['ready']}" if n["ready"] else "")
                     for n in st.needs if n["state"] == "earlier"]
            merged: dict[int, dict] = {}
            for c in cards:  # one card per week: steps in the same week read as one
                m = merged.get(c["col"])
                if m is None:
                    merged[c["col"]] = {"gold": 0, "helps": [], "waits": [], **c, "urgency": urgency}
                elif m["tag"] == "CHOP":  # chopping first, then what the Wood is for, the same week
                    chopped = f"after chopping {m['title'].replace(', ', ' for ')} ({m['detail']})"
                    merged[c["col"]] = {"gold": 0, "helps": [], "waits": [], **c, "urgency": urgency,
                                        "tag": f"CHOP, THEN {c['tag']}",
                                        "detail": "; ".join(x for x in (chopped, c["detail"]) if x)}
                else:
                    if not c.get("final"):
                        m["tag"] = m["tag"] if m["tag"] == c["tag"] else f"{m['tag']} + {c['tag']}"
                        m["title"] += f", {c['title']}"
                    m["detail"] = "; ".join(x for x in (m["detail"], c["detail"]) if x)
                    m["gold"] += c.get("gold", 0)
                    m["helps"] = m["helps"] or c.get("helps", [])
            row = [merged[k] for k in sorted(merged)]
            if row and waits:
                row[-1]["waits"] = waits
            steps.append(row)
            for c in row:
                columns[c["col"]]["gold"] += c["gold"]
        rows: list[list[dict]] = []
        spans: list[list[tuple[int, int]]] = []
        for cards in steps:  # pack: a row takes the next thing whose weeks don't overlap it
            lo, hi = cards[0]["col"], cards[-1]["col"]
            for i, taken in enumerate(spans):
                if all(hi < a or lo > b for a, b in taken):
                    rows[i] += cards
                    taken.append((lo, hi))
                    break
            else:
                rows.append(list(cards))
                spans.append([(lo, hi)])
        for row in rows:
            row.sort(key=lambda c: c["col"])
        lanes.append({"id": o.id, "rows": rows})
    for lane in lanes:
        for row in lane["rows"]:
            for c in row:
                c["helps"] = _by_goal(c["helps"])
                c.pop("final", None)
    for x in synergy.values():
        x["goals"] = _by_goal(x["goals"])
    return {"columns": columns, "lanes": lanes,
            "synergy": [x for x in synergy.values() if len(x["goals"]) > 1]}


def _by_goal(helps: list[dict]) -> list[dict]:
    """[{goal, why}] -> [{goal, why: 'a, b'}], one per goal, in order."""
    out: dict[str, list[str]] = {}
    for h in helps:
        whys = out.setdefault(h["goal"], [])
        why = h["why"].split(" (")[0]
        if why not in whys:
            whys.append(why)
    return [{"goal": g, "why": ", ".join(w)} for g, w in out.items()] if len(out) > 1 else []


def _verb(n: dict) -> str:
    key = n["key"]
    if key.startswith(("building:", "kitchen", "house:")) or n["label"].startswith("repair"):
        return "BUILD"
    if key.startswith("tool:"):
        return "UPGRADE"
    if key.startswith("recipe:"):
        return "RECIPE"
    if key.startswith("craft:"):
        return "CRAFT"
    if key.startswith("tap:"):
        return "TAP"
    return "BUY" if n["gold"] or n["label"].startswith("buy") else "GET"


def _week_label(farm, a: int, b: int) -> str:
    la, lb = farm.label(a).split(", Year")[0], farm.label(b).split(", Year")[0]
    if la.split()[0] == lb.split()[0]:
        return f"{la}–{lb.split()[1]}"
    return f"{la} – {lb}"


def _tag(how: str) -> str:
    for word, tag in (("fish", "FISH"), ("forage", "FORAGE"), ("hoeing", "DIG"), ("cooking", "COOK"),
                      ("talk", "EVERY DAY"), ("Mariner", "BUY"), ("tree", "PICK"), ("three days", "WEDDING"),
                      ("give", "GIVE"), ("Goat", "PRODUCE"), ("Duck", "PRODUCE"), ("Cow", "PRODUCE"),
                      ("Chicken", "PRODUCE"), ("Rabbit", "PRODUCE"), ("Pig", "PRODUCE"), ("Sheep", "PRODUCE")):
        if word in how:
            return tag
    return "GET" if how else "DONE"


def _agenda(farm, outcomes: list[Outcome], today: int, res) -> list[dict]:
    """The route's next week as things to do on the day, each saying which goal it serves."""
    out: list[dict] = []
    end = today + AGENDA_DAYS

    def add(d, kind, text, why, goal, gold=0, shop=""):
        if today <= d < end:
            out.append({"n": d, "day": farm.label(d), "kind": kind, "text": text, "why": why, "goal": goal,
                        "gold": gold, "shop": shop})

    saving = None
    for o in outcomes:
        for st in o.steps:
            if st.shared:
                continue
            new = [n for n in st.needs if n["state"] == "new"]
            first = _thing(new[0]["label"]) if new else st.label
            hard = any(m.endswith(" Hardwood") for n in new for m in n["materials"])
            for d in st.chop_days:
                why = f"for {first}" if _bare(first) == _bare(st.label) else f"for {first}, for {st.label}"
                add(d, "chop", "Chop Hardwood (Secret Woods) and Wood" if hard else "Chop Wood all day", why, o.label)
            for d in st.mine_days:
                add(d, "mine", "Go down the Mines", f"deeper floors for {st.label}", o.label)
            for n in new:
                cost = ", ".join(([f"{n['gold']:,}g"] if n["gold"] else []) + n["materials"])
                text = n["label"][0].upper() + n["label"][1:] + (f": {cost}" if cost else "")
                if not n["gold"] and not n["materials"] and n["label"].startswith(("Robin finishes", "Clint finishes")):
                    continue  # already paid for: nothing to do but wait
                add(n["on"], "buy", text, f"for {st.label}", o.label, n["gold"], _shop_for(n))
                if n["gold"] and today <= n["on"] < today + 2 * AGENDA_DAYS and saving is None \
                        and farm.save.money < n["gold"]:
                    saving = (n, st, o)
            if not new and st.gold:
                add(st.day, "buy", f"Buy {st.label}: {st.gold:,}g", "", o.label, st.gold)
            if st.act:
                add(st.act, "fish", st.how[0].upper() + st.how[1:] if st.how else "Fish", f"for {st.label}", o.label)
            elif st.how and not new and not st.gold:
                add(st.ready, "get", f"Get {st.label.split(' (')[0]}: {st.how}", f"for {st.label}", o.label)
    for o in outcomes:  # courting: every day until the proposal
        if o.id == "marriage" and o.status != "done":
            who = next((st.label.removeprefix("10 hearts with ") for st in o.steps
                        if st.label.startswith("10 hearts with ")), None)
            if who:
                add(today, "people", f"Talk to {who}; a gift on two days each week",
                    "friendship toward the Bouquet and the Mermaid's Pendant", o.label)
    if saving:
        n, st, o = saving
        out.append({"n": today, "day": farm.label(today), "kind": "save",
                    "text": f"Save up {n['gold']:,}g for {_thing(n['label'])} "
                            f"by {farm.label(n['on'])}",
                    "why": f"you have {farm.save.money:,}g; it's for {st.label}", "goal": o.label, "gold": n["gold"]})
    out.sort(key=lambda a: (a["n"], a["kind"] != "save"))
    return out


def _shop_for(n: dict) -> str:
    """Where a step is bought or ordered: a shop id from the hours list, or "" for anywhere."""
    key = n["key"]
    if key.startswith(("building:", "kitchen", "house:")):
        return "Carpenter"
    if key.startswith("animal:"):
        return "AnimalShop"
    if key.startswith("tool:"):
        return "Blacksmith"
    if key == "bouquet" or "from Pierre" in n["label"]:
        return "SeedShop"
    for shop, words in (("Saloon", "the Saloon"), ("FishShop", "Willy"), ("SeedShop", "Pierre"),
                        ("Carpenter", "Robin"), ("AnimalShop", "Marnie"), ("Blacksmith", "Clint")):
        if words in (n.get("how") or ""):
            return shop
    return ""


def _bare(label: str) -> str:
    """'the Stable' and 'a Stable' alike."""
    return re.sub(r"^(a|an|the) ", "", label.lower())


def _thing(label: str) -> str:
    """'build a Big Barn' -> 'a Big Barn'."""
    for verb in ("build ", "buy ", "upgrade "):
        label = label.removeprefix(verb)
    return label


def _span(farm, days: list[int]) -> str:
    """'Fall 22 – Fall 25' for a run of days, or the first and last of scattered ones."""
    if not days:
        return ""
    days = sorted(days)
    return farm.label(days[0]) if len(days) == 1 else f"{farm.label(days[0])} – {farm.label(days[-1])}"


def _season(d: int) -> int:
    return (d - 1) // 28
