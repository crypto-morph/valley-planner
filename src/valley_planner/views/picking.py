"""When to pick, and where a giant crop is coming: the harvest rolls are seeded by tile and day (facts/harvest.py).

Quality: a crop picked on a different day rolls a different quality, so one that isn't being replanted can wait
for its best day. A regrowing crop pays for waiting with a later next harvest, so that's said with it.
Giant crops: a ripe Cauliflower, Melon or Pumpkin (and the rest of Data/GiantCrops) whose roll hits that night,
with the same crop on all 9 tiles of its square, becomes a giant crop. The other 8 only need to be the same crop,
at any stage, so a near miss can be finished by sowing the gaps. Nobody has seen this in our saves yet.
"""

from __future__ import annotations

from collections import defaultdict

from ..facts import harvest, layout
from .farm import Farm

QUALITY = {0: "normal", 1: "silver", 2: "gold", 4: "iridium"}
NIGHTS = 7  # how far ahead to look for giant crops
MOST_MISSING = 5  # gaps worth sowing for one


def _day(farm: Farm, dp: int) -> str:
    return farm.label(dp).rsplit(",", 1)[0]


def waiting(farm: Farm) -> list[dict]:
    """Ripe crops that come out better on a later day, grouped by crop and best day."""
    groups: dict[tuple, dict] = defaultdict(lambda: {"count": 0})
    for a in harvest.quality_ahead(farm.save, farm.data):
        if not a.worth_waiting:
            continue
        g = groups[(a.name, a.best_day, a.best, a.today, bool(a.regrows))]
        g["count"] += 1
    out = []
    for (name, day, best, now, regrows), g in sorted(groups.items(), key=lambda kv: kv[0][1]):
        out.append({"crop": name, "count": g["count"], "day": _day(farm, day), "best": QUALITY[best],
                    "now": QUALITY[now],
                    "note": "it regrows, so waiting also pushes back the next harvest" if regrows else ""})
    return out


def _picture(farm: Farm, hit) -> list[str]:
    """The field around the square: G the giant crop's tiles you have, S sow here, H hoe and sow, P pull up the
    crop there and sow, X your Scarecrow, c other crops, o dirt."""
    x0, y0 = hit.tile
    square = {(x0 + dx, y0 + dy) for dx in range(3) for dy in range(3)}
    missing = set(hit.missing)
    crops = {c.tile for c in farm.save.crops if c.location == "Farm" and c.tile and not c.forage}
    guards = set(layout.scarecrows(farm.save.farm_objects))
    near = square | {t for t in crops | farm.save.hoed | guards if abs(t[0] - x0 - 1) <= 6 and abs(t[1] - y0 - 1) <= 4}
    xa, xb = min(x for x, _ in near), max(x for x, _ in near)
    ya, yb = min(y for _, y in near), max(y for _, y in near)

    def letter(t) -> str:
        if t in missing:
            return "P" if t in crops else "S" if t in farm.save.hoed else "H"
        if t in square:
            return "G"
        if t in guards:
            return "X"
        return "c" if t in crops else "o" if t in farm.save.hoed else "."

    return ["".join(letter((x, y)) for x in range(xa, xb + 1)) for y in range(ya, yb + 1)]


def giants(farm: Farm) -> list[dict]:
    """Giant-crop chances over the coming nights: ready squares, and near misses worth sowing for."""
    out = []
    for night in range(1, NIGHTS + 1):
        g = harvest.giant_tonight(farm.save, farm.data, night=night)
        for hit in (*g.ready, *(h for h in g.incomplete if len(h.missing) <= MOST_MISSING)):
            day = _day(farm, hit.days_played)
            if hit.complete:
                text = (f"Leave the {hit.key} in this square unpicked and watered, and it turns giant overnight"
                        f" into {day}.")
            else:
                crops = {c.tile: c for c in farm.save.crops if c.location == hit.location and c.tile}
                taken = [farm.name(f"(O){crops[t].harvest_id}") for t in hit.missing if t in crops]
                bare = sum(1 for t in hit.missing if t not in crops and t not in farm.save.hoed)
                steps = [f"sow {len(hit.missing)} {hit.key} on the marked tiles before then"]
                if taken:
                    steps.append(f"{len(taken)} of them hold {', '.join(sorted(set(taken)))} now, which you'd pull up")
                if bare:
                    steps.append(f"{bare} {'needs' if bare == 1 else 'need'} hoeing first")
                said = "; ".join(steps)
                text = (f"{said[0].upper()}{said[1:]}. Keep the top-left one watered and unpicked, and the"
                        f" square turns giant overnight into {day}.")
            out.append({"crop": hit.key, "day": day, "days_played": hit.days_played, "complete": hit.complete,
                        "sow": len(hit.missing), "text": text, "sure": hit.sure, "rows": _picture(farm, hit)})
    return out
