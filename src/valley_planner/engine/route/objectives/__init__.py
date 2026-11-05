"""Every goal the route can plan, one module each. See base.py for what a module provides."""

from . import bus, community_center, courtship, machines, qi, skull_cavern, sprinklers, unlocks  # noqa: F401
from .base import REGISTRY, Objective

ORDER = ("greenhouse", "seed_maker", "kitchen", "cc", "stable", "sprinklers", "house_2", "marriage", "qi",
         "deluxe_barn", "deluxe_coop", "silo", "axe_steel", "pickaxe_steel", "can_steel", "mines_bottom",
         "bus", "skull_cavern", "jars", "kegs", "house_3")  # the order they're offered in
OBJECTIVES: dict[str, Objective] = {k: REGISTRY[k] for k in ORDER}
CATALOG = {k: (o.label, o.days) for k, o in OBJECTIVES.items()}  # id -> (label, default deadline in days)


def with_needs(targets, nice=()) -> tuple[list[str], list[str]]:
    """The goals with each one's prerequisites just before it. A target's prerequisite is a target, whatever tier
    it was picked at."""
    seen: set[str] = set()

    def expand(ids) -> list[str]:
        out: list[str] = []

        def add(oid: str) -> None:
            if oid in seen:
                return
            seen.add(oid)
            for first in OBJECTIVES[oid].needs if oid in OBJECTIVES else ():
                add(first)
            out.append(oid)

        for oid in ids:
            add(oid)
        return out

    picked = expand(targets)
    return picked, expand(nice)
