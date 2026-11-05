"""Machines to craft: Preserves Jars, and Kegs with the Oak Resin they need."""

from __future__ import annotations

import math

from ...unlocks import Unlock
from ..model import OAK_RESIN, TAPPER, Req
from .base import objective

MACHINE_GOALS = {"jars": ("15", "Preserves Jars"), "kegs": ("12", "Kegs")}  # objective -> (big craftable, plural)


def crafted(r, bc: str, n: int, plural: str) -> list[Unlock]:
    """The recipe (if it isn't known) and crafting n of a machine."""
    m = r.planner.unlocks.get(f"machine:(BC){bc}")
    recipe = [u for k in m.after for u in r.planner.unlocks.chain(k)]
    return recipe + [Unlock(f"craft:{bc}", f"craft {n} {plural}", 0, [(x, k * n) for x, k in m.materials],
                            after=[u.key for u in recipe])]


def tap_days(r, item: str) -> int | None:
    """Days a Tapper takes to give `item` on the wild tree that gives it (Data/WildTrees)."""
    for t in r.farm.data.asset("Data/WildTrees").values():
        for tap in t.get("TapItems") or []:
            if (tap.get("ItemId") or "").removeprefix("(O)") == item and not tap.get("Condition"):
                return int(tap.get("DaysUntilReady") or 0)
    return None


def machine_reqs(r, oid: str) -> tuple[list[Req], int, list[str]]:
    """Craft the machines still missing; Kegs need an Oak Resin each, from Tappers on oak trees first."""
    bc, plural = MACHINE_GOALS[oid]
    n = getattr(r.s, oid) - r.machines(bc)
    reqs, chain = [], []
    if oid == "kegs":
        resin = max(0, n - r.held.get(f"(O){OAK_RESIN}", 0))
        days = tap_days(r, OAK_RESIN)
        if resin and days:
            taps = max(1, min(r.s.tappers, resin))
            have = r.held.get(f"(BC){TAPPER}", 0)
            chain = crafted(r, TAPPER, taps - have, "Tappers") if taps > have else []
            rounds = math.ceil(resin / taps)
            chain.append(Unlock("tap:oak", f"tap {taps} oak trees for {resin} Oak Resin", 0, [], days * rounds,
                                [u.key for u in chain[-1:]],
                                how=f"a Tapper on a grown oak gives one Oak Resin every {days} days"))
            reqs.append(Req(f"{resin} Oak Resin", r.today, r.end, list(chain), sum(u.days for u in chain)))
            r.info.append(f"{resin} Oak Resin from {taps} Tappers takes {rounds * days} days "
                             f"({rounds} round{'s' if rounds > 1 else ''}); more Tappers (a setting) shorten it")
            placed = r.farm.save.machines.get("Tapper", 0)
            if placed:
                r.info.append(f"Your {placed} placed Tapper{'s' if placed > 1 else ''} aren't counted: one "
                                 f"moved onto an oak saves crafting one")
    chain += crafted(r, bc, n, plural)
    if any(m == "382" for u in chain for m, _ in u.materials):
        r.info.append("Coal is priced at Clint's; mining it or a Charcoal Kiln saves gold but costs days")
    reqs.append(Req(f"{n} {plural}", r.today, r.end, chain, sum(u.days for u in chain)))
    return reqs, 0, []


def _enough(oid: str):
    return lambda r: r.machines(MACHINE_GOALS[oid][0]) >= getattr(r.s, oid)


objective("jars", "Preserves Jars", 112, done=_enough("jars"))(lambda r: machine_reqs(r, "jars"))
objective("kegs", "Kegs", 112, done=_enough("kegs"))(lambda r: machine_reqs(r, "kegs"))
