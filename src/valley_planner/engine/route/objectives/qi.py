"""Mr. Qi's notes, ending in the Club Card."""

from __future__ import annotations

from dataclasses import replace

from ...cc import Slot
from ..model import Req
from .base import objective

QI_STEPS = (  # mail flag set when done, the item, how many, where it goes
    ("TH_Tunnel", "787", 1, "the safe in the tunnel left of the bus stop"),
    ("TH_Railroad", "394", 1, "the box on the train platform"),
    ("TH_MayorFridge", "284", 10, "Mayor Lewis's fridge"),
    ("TH_SandDragon", "768", 1, "the sand dragon's skull in the Desert"),
)
QI_DONE = "TH_LumberPile"  # the Club Card, from the lumber pile beside your house


def _named(req: Req, label: str) -> Req:
    return replace(req, label=label, fallback=_named(req.fallback, label) if req.fallback else None)


def _after(req: Req, first: list) -> Req:
    return replace(req, chain=first + req.chain, fallback=_after(req.fallback, first) if req.fallback else None)


@objective("qi", "Mr. Qi's notes (the Club Card)", 112, done=lambda r: QI_DONE in r.farm.save.mail)
def qi(r) -> tuple[list[Req], int, list[str]]:
    """Mr. Qi's notes, each step after the last (GameLocation.performAction, ManorHouse): what each still
    needs, got the cheapest way; the Desert step also needs the bus. The last note sends you to the lumber
    pile by your house, which holds the Club Card."""
    mail, reqs, notes = r.farm.save.mail, [], []
    step = next((i for i, (flag, *_rest) in enumerate(QI_STEPS) if flag not in mail), len(QI_STEPS))
    if step == 0:
        notes.append("it starts with a Battery Pack in the safe in the tunnel left of the bus stop")
    for flag, oid, count, where in QI_STEPS[step:]:
        qid, name = f"(O){oid}", r.farm.name(f"(O){oid}")
        have = r.held.get(qid, 0) >= count
        ways = [] if have else r.planner.ways(qid, count=count)
        slot = Slot("Mr. Qi", "", qid, name, count, 0, have, ways)
        plural = name if count == 1 or name.endswith("s") else f"{name}s"
        label = f"{f'{count} {plural}' if count > 1 else name} (Mr. Qi: {where})"
        if have:
            r.info.append(f"You have {count if count > 1 else 'the'} {name} for {where}")
            req = Req(label, r.today, r.end, [], 0, "forage", season=f"take it to {where}")
        else:
            req = r.slot_req(slot)
            if req is None:
                continue
            if req.latest == 0:  # nothing the route can plan: say what stands in the way
                why = sorted({b for w in ways for b in w.blocked})
                luck = [f"{w.source.label} ({w.odds:.0%} by the year's end)" for w in ways if w.odds]
                r.misses.append((label, "; ".join(why) + (f"; or by luck: {', '.join(luck)}" if luck else "")
                                    or "no way to get it this year"))
                continue
            req = _named(req, label)
        if flag == "TH_SandDragon":  # in the Desert: the bus first
            desert = r.planner.unlocks.chain("place:Desert")
            req = _after(req, desert)
        reqs.append(req)
    return reqs, 0, notes
