"""Sprinklers for the whole field: basic first, because iron and copper are in reach and gold isn't."""

from __future__ import annotations

import math

from ...unlocks import Unlock
from ..model import REFINED_QUARTZ, Req
from .base import objective

SPRINKLER = "621"
SPRINKLER_TILES = 8  # a Quality Sprinkler waters the eight tiles around it
BASIC = "599"
BASIC_TILES = 4  # a Sprinkler waters the four tiles beside it


def wanted(r) -> int:
    return math.ceil(r.s.tiles / SPRINKLER_TILES)


def _done(r) -> bool:
    return r.held.get(f"(O){SPRINKLER}", 0) >= wanted(r)


def wanted_basic(r) -> int:
    return math.ceil(r.s.tiles / BASIC_TILES)


def _basic_done(r) -> bool:
    return r.held.get(f"(O){BASIC}", 0) + r.farm.save.sprinklers.get("Sprinkler", 0) >= wanted_basic(r)


@objective("sprinklers_basic", "Sprinklers for the field", 28, done=_basic_done)
def sprinklers_basic(r):
    s = r.farm.save
    n = wanted_basic(r) - r.farm.held().get(f"(O){BASIC}", 0) - s.sprinklers.get("Sprinkler", 0)
    recipe = r.planner.unlocks.chain("recipe:Sprinkler")
    craft = Unlock("craft:sprinklers_basic", f"craft {n} Sprinklers", 0, [("334", n), ("335", n)],
                   after=[u.key for u in recipe])
    r.info.append("Bars are priced as ore bought from Clint (Year 1); iron from the Mines costs days, not gold")
    return [Req(f"{n} Sprinklers", r.today, r.end, recipe + [craft], 0)], 0, []


@objective("sprinklers", "Quality Sprinklers for the field", 112, done=_done)
def sprinklers(r):
    n = wanted(r) - r.farm.held().get(f"(O){SPRINKLER}", 0)
    recipe = r.planner.unlocks.chain("recipe:Quality Sprinkler")
    craft = Unlock("craft:sprinklers", f"craft {n} Quality Sprinklers", 0,
                   [("335", n), ("336", n), (REFINED_QUARTZ, n)],
                   after=[u.key for u in recipe])
    r.info.append("Bars are priced as ore bought from Clint (Year 1); mining your own saves gold "
                  "but costs days")
    return [Req(f"{n} Quality Sprinklers", r.today, r.end, recipe + [craft], 0)], 0, []
