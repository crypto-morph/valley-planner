"""Goals that are one unlock: a building, a tool level, the kitchen, a Mines floor."""

from __future__ import annotations

from ..model import Req
from .base import objective

UNLOCK_GOALS = {  # objectives that are one unlock: (its key, what the route calls it)
    "stable": ("building:Stable", "the Stable", "A horse"),
    "house_2": ("house:2", "the second house upgrade", "The second house upgrade"),
    "house_3": ("house:3", "the third house upgrade (the cellar)", "The cellar (third house upgrade)"),
    "deluxe_barn": ("building:Deluxe Barn", "a Deluxe Barn", "A Deluxe Barn"),
    "deluxe_coop": ("building:Deluxe Coop", "a Deluxe Coop", "A Deluxe Coop"),
    "silo": ("building:Silo", "a Silo", "A Silo"),
    "axe_steel": ("tool:Axe@2", "a Steel Axe", "A Steel Axe (the Secret Woods)"),
    "pickaxe_steel": ("tool:Pickaxe@2", "a Steel Pickaxe", "A Steel Pickaxe"),
    "can_steel": ("tool:WateringCan@2", "a Steel Watering Can", "A Steel Watering Can"),
    "mines_bottom": ("floor:120", "Mines floor 120 (the Skull Key)", "The bottom of the Mines (Skull Key)"),
}

def _one_unlock(oid: str, key: str, label: str):
    def plan(r):
        u = r.planner.unlocks.chain(key)
        if key.startswith("floor:"):
            r.info.append(r.pace.note)
        if key.startswith("tool:"):
            r.info.append("Clint takes one tool at a time, for two days, and you're without it meanwhile")
            if "WateringCan" in key:
                r.info.append("Leave the can with Clint on a rainy day, or once sprinklers do the watering")
        return [Req(label, r.today, r.end, u, sum(x.days for x in u))], 0, []
    return plan


def _have(key: str):
    return lambda r: r.planner.unlocks.get(key).done


for _oid, (_key, _label, _title) in UNLOCK_GOALS.items():
    _done = _have(_key)
    if _oid == "mines_bottom":
        _done = (lambda d: lambda r: "HasSkullKey" in r.farm.save.mail or d(r))(_done)
    objective(_oid, _title, 112, done=_done)(_one_unlock(_oid, _key, _label))


@objective("kitchen", "The kitchen", 112, done=lambda r: r.farm.save.house_upgrade >= 1)
def kitchen(r):
    u = r.planner.unlocks.get("kitchen")
    return [Req("the kitchen", r.today, r.end, [u], u.days)], 0, []


@objective("seed_maker", "A Seed Maker", 112, done=lambda r: bool(r.farm.save.machines.get("Seed Maker")))
def seed_maker(r):
    u = r.planner.unlocks.get("machine:(BC)25")
    u.how = "Farming level 9"
    return [Req("a Seed Maker", r.today, r.end, [u], 0)], 0, []
