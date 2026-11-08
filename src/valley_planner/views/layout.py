"""The Sprinkler plan for your field: a picture you can match to the ground, and what it takes."""

from __future__ import annotations

import math

from ..facts import layout
from .farm import Farm

IRON_BAR, COPPER_BAR = "(O)335", "(O)334"
ORE_PER_BAR = 5
ROUND = 20  # field sizes offered go in these steps


def _grid(plan, hoed: set, objects: dict, extra: tuple | None, *, quality: bool) -> dict:
    """Rows of one letter a tile: S Sprinkler, Q Quality, c crop on your dirt, n crop to hoe, x something standing,
    A one more Scarecrow, X a Scarecrow, o other dirt, and . nothing."""
    tiles = {*plan.sprinklers, *plan.crops}
    x0, y0 = min(x for x, _ in tiles) - 1, min(y for _, y in tiles) - 1
    x1, y1 = max(x for x, _ in tiles) + 1, max(y for _, y in tiles) + 1
    guards = set(layout.scarecrows(objects))
    q, keep = set(plan.quality), set(plan.keep)

    def letter(t) -> str:
        if t == extra:
            return "A"
        if t in guards:
            return "X"
        if t in plan.sprinklers:
            return ("Q" if t in q else "S" if t in keep else "f") if quality else "S"
        if t in plan.crops:
            return "c" if t in hoed else "n"
        return "x" if t in objects else "o" if t in hoed else "."

    return {"rows": ["".join(letter((x, y)) for x in range(x0, x1 + 1)) for y in range(y0, y1 + 1)],
            "origin": [x0, y0]}


def view(farm: Farm, crops: int | None = None) -> dict:
    s = farm.save
    planted = sum(1 for c in s.crops if not c.forage and c.location == "Farm")
    want = crops or max(ROUND, math.ceil(planted / ROUND) * ROUND)
    plan = layout.plan(s.hoed, s.farm_objects, want, lambda t: farm.walker.open(("Farm", *t)))
    if plan is None:
        return {"ready": False, "text": "Hoe your field first, and the plan will fit itself to it."}
    held, made = farm.held(), farm.held().get("(O)599", 0) + s.sprinklers.get("Sprinkler", 0)
    short = max(0, len(plan.sprinklers) - made)
    iron, copper = max(0, short - held.get(IRON_BAR, 0)), max(0, short - held.get(COPPER_BAR, 0))
    guards = layout.scarecrows(s.farm_objects)
    open_crops = layout.unguarded(plan.crops, guards)
    extra = layout.next_scarecrow(plan.crops, guards)
    make = [f"{iron} Iron Bars ({iron * ORE_PER_BAR} Iron Ore and {iron} Coal)" if iron else "",
            f"{copper} Copper Bars" if copper else ""]
    return {"ready": True, "sprinklers": len(plan.sprinklers), "crops": len(plan.crops), "want": want,
            "to_hoe": len(plan.crops - s.hoed), "lost": len(s.hoed - plan.crops - set(plan.sprinklers)),
            "made": made, "short": short, "need": [x for x in make if x],
            "scarecrow": len(open_crops), "quality": len(plan.quality), "quality_keep": len(plan.keep),
            "freed": len(plan.sprinklers) - len(plan.quality) - len(plan.keep),
            "now": _grid(plan, s.hoed, s.farm_objects, extra, quality=False),
            "later": _grid(plan, s.hoed, s.farm_objects, extra, quality=True),
            "sizes": [40, 60, 80, 100, 120]}
