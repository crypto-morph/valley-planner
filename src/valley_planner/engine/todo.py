"""The To-do list: today's tasks from the plan, each with a check the next morning's save can answer.

A task is kept with the day's list (in your own data folder) so that when
the next day's save appears it can be marked done or missed. Checks:
- gift: friendship with the villager went up;
- water: the crops that were dry this morning grew overnight;
- harvest: the tiles that were ready are no longer ready;
- pet: each animal's friendship went up (petting adds 15);
- get: you hold at least N of an item, or a bundle slot was filled with it;
- build / buy / upgrade / flag: the building, animal, tool level or world
  flag (the beach bridge) is there;
- plant: more of that crop is in the ground.
Anything a check can't tell is left for you to tick.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..views.farm import Farm
from .unlocks import Unlocks


def data_root(env: dict | None = None, platform: str | None = None) -> Path:
    """Where the planner keeps your day lists (never the game's folders)."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if env.get("VALLEY_PLANNER_DATA"):
        return Path(env["VALLEY_PLANNER_DATA"])
    if platform == "win32":
        return Path(env.get("LOCALAPPDATA") or Path.home() / "AppData/Local") / "ValleyPlanner" / "days"
    if platform == "darwin":
        return Path.home() / "Library/Application Support/ValleyPlanner/days"
    return Path(env.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "valley-planner" / "days"


@dataclass
class Task:
    id: str
    title: str
    why: str = ""
    group: str = "farm"  # farm / people / cc / shopping
    check: dict = field(default_factory=dict)


def _ready_tiles(save) -> list:
    return [[c.location, list(c.tile)] for c in save.crops if c.ready and c.tile and not c.forage]


def _dry_tiles(save) -> list:
    return [[c.location, list(c.tile)] for c in save.crops
            if c.tile and not c.ready and not c.dead and not c.watered and not c.forage]


def tasks(farm: Farm) -> list[Task]:
    from . import cc
    s, w = farm.save, farm.when
    out: list[Task] = []
    held = farm.held()
    for e in farm.calendar.day(w, today_days_played=w.days_played):
        if e.kind == "birthday" and e.who:
            loved = [q for q in held if farm.gifts.giftable(q) and farm.gifts.taste(e.who, q) == "love"]
            gift = farm.name(loved[0]) if loved else "something they like"
            out.append(Task(f"gift:{e.who}", f"Give {e.who} {gift} for their birthday", "gifts count 8x today",
                            "people", {"type": "gift", "npc": e.who, "points": s.friends[e.who].points
                                       if e.who in s.friends else 0}))
    ready = _ready_tiles(s)
    if ready:
        out.append(Task("harvest", f"Harvest the {len(ready)} ready crops", "", "farm",
                        {"type": "harvest", "tiles": ready}))
    dry = _dry_tiles(s)
    if dry and not s.wet:
        out.append(Task("water", f"Water {len(dry)} crops", "dry crops don't grow tonight", "farm",
                        {"type": "water", "tiles": dry}))
    if s.animals:
        out.append(Task("pet", f"Pet your {len(s.animals)} animals", "friendship, happiness and better produce",
                        "farm", {"type": "pet", "animals": {d["id"]: d["friendship"] for d in s.animals}}))
    plan = cc.plan(farm)
    unlocks = Unlocks(farm)
    for u in plan["unlocks"]:
        mats_ok = all(held.get(f"(O){m['id']}", 0) >= m["count"] for m in u["materials"])
        ready = all(unlocks.get(a).done for a in unlocks.get(u["key"]).after)  # nothing before it is still to do
        if ready and u["gold"] <= s.money and mats_ok and not u["how"] and u["key"] != "place:Woods":
            out.append(Task(f"unlock:{u['key']}", u["label"][:1].upper() + u["label"][1:],
                            f"opens {', '.join(u['slots'])} for the Community Center", "cc", _unlock_check(u["key"])))
    for slot in plan["slots"]:
        b = slot["best"]
        if slot["status"] != "ok" or not b or b["earliest"] != plan["today"]:
            continue
        if b["kind"] in ("fish", "forage", "shop", "dig"):
            out.append(Task(f"get:{slot['item']}", f"Get {slot['count']} {slot['name']}: {b['label']}",
                            f"the {slot['bundle']} bundle", "cc",
                            {"type": "get", "item": slot["item"], "count": slot["count"],
                             "had": held.get(slot["item"], 0)}))
        if b["kind"] == "crop" and b["last_start"]:
            out.append(Task(f"plant:{slot['item']}", f"Plant {b['label'][5:]} by {b['last_start']}",
                            f"{slot['name']} for the {slot['bundle']} bundle", "shopping",
                            {"type": "plant", "harvest": slot["item"][3:],
                             "had": sum(1 for c in s.crops if c.harvest_id == slot["item"][3:])}))
    return out


def _unlock_check(key: str) -> dict:
    kind, _, what = key.partition(":")
    if kind == "building":
        return {"type": "build", "building": what}
    if kind == "animal":
        return {"type": "buy", "animal": what}
    if kind == "tool":
        return {"type": "upgrade", "tool": what.split("@")[0], "level": int(what.split("@")[1])}
    if kind == "place" and what == "BeachTidePools":
        return {"type": "flag", "flag": "beachBridgeFixed"}
    if kind == "kitchen":
        return {"type": "kitchen"}
    return {}


def check(task: dict, prev, nxt) -> bool | None:
    """Did it happen? From the morning save the list was made from and the next day's."""
    c = task.get("check") or {}
    t = c.get("type")
    if t == "gift":
        f = nxt.friends.get(c["npc"])
        return bool(f and f.points > c["points"])
    if t in ("harvest", "water"):
        tiles = {(loc, tuple(xy)) for loc, xy in c["tiles"]}
        now = {(cr.location, cr.tile): cr for cr in nxt.crops if cr.tile}
        before = {(cr.location, cr.tile): cr for cr in prev.crops if cr.tile} if prev else {}
        if t == "harvest":  # a ready crop still ready the next morning wasn't picked
            return all(not (k in now and now[k].ready) for k in tiles)
        grew = [k for k in tiles if k in now and k in before
                and now[k].grown is not None and before[k].grown is not None]
        return all(now[k].grown > before[k].grown or now[k].ready for k in grew) if grew else None
    if t == "pet":
        now = {d["id"]: d["friendship"] for d in nxt.animals}
        # petting adds 15; not petting loses up to 10 overnight
        return all(now.get(a, 0) > before for a, before in c["animals"].items() if a in now)
    if t == "get":
        oid = c["item"].removeprefix("(O)")
        have = sum(it.stack for it in nxt.items if it.qualified_id == c["item"])
        return have >= c["count"] or have > c.get("had", 0) or nxt.shipped.get(oid, 0) > (prev.shipped.get(oid, 0)
                                                                                            if prev else 0)
    if t == "build":
        return bool(nxt.buildings.get(c["building"]))
    if t == "buy":
        return any(d["type"] == c["animal"] for d in nxt.animals)
    if t == "upgrade":
        return getattr(nxt, "axe_level", 0) >= c["level"] if c["tool"] == "Axe" else None
    if t == "flag":
        return c["flag"] in getattr(nxt, "flags", set())
    if t == "kitchen":
        return nxt.house_upgrade >= 1
    if t == "plant":
        return sum(1 for cr in nxt.crops if cr.harvest_id == c["harvest"]) > c["had"]
    return None


class DayLog:
    """Each day's list, one JSON file per save and day: <data>/<save>/<days played>.json."""

    def __init__(self, save_name: str, root: Path | None = None):
        self.dir = (root or data_root()) / save_name

    def path(self, day: int) -> Path:
        return self.dir / f"{day}.json"

    def load(self, day: int) -> dict | None:
        p = self.path(day)
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def store(self, day: int, label: str, items: list[Task], ticks: dict | None = None) -> dict:
        old = self.load(day) or {}
        rec = {"day": day, "label": label, "tasks": [asdict(t) for t in items],
               "ticks": {**old.get("ticks", {}), **(ticks or {})}}
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path(day).with_suffix(".tmp")
        tmp.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path(day))
        return rec

    def tick(self, day: int, task_id: str, done: bool) -> dict | None:
        rec = self.load(day)
        if rec is None:
            return None
        rec["ticks"][task_id] = done
        self.path(day).write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        return rec

    def earlier(self, day: int) -> int | None:
        days = sorted(int(p.stem) for p in self.dir.glob("*.json") if p.stem.isdigit() and int(p.stem) < day) \
            if self.dir.is_dir() else []
        return days[-1] if days else None


def today(farm: Farm, log: DayLog) -> dict:
    """Today's list (kept, so tomorrow can check it) and yesterday's checked against this save."""
    day = farm.save.days_played
    items = tasks(farm)
    rec = log.store(day, farm.label(day), items)
    review = None
    prev_day = log.earlier(day)
    if prev_day is not None:
        old = log.load(prev_day)
        prev = farm.yesterday if prev_day == day - 1 else None
        results = []
        for t in old.get("tasks", []):
            auto = check(t, prev, farm.save)
            ticked = old.get("ticks", {}).get(t["id"])
            results.append({"id": t["id"], "title": t["title"], "done": auto, "ticked": ticked})
        review = {"label": old.get("label"), "items": results,
                  "done": sum(1 for r in results if r["done"] or r["ticked"]), "total": len(results)}
    return {"date": rec["label"], "tasks": rec["tasks"], "ticks": rec["ticks"], "yesterday": review}
