"""Where Sprinklers go: the interlocking pattern that waters every crop tile once and wastes nothing.

A Sprinkler waters the four tiles beside it, not its own. Sprinklers on the lattice (x + 2y + c) mod 5 = 0, or its
mirror, cover every other tile exactly once: 4 crops a Sprinkler, 80% of the ground planted, and no paths needed
because crops can be walked through. There are 5 offsets in each mirror, so a real field is matched by trying all
10 against the dirt that's already hoed.

A Quality Sprinkler waters the 8 tiles around it. Half the lattice, the points with one value of (3x + y) mod 10
(mirrored, 3y + x), can be swapped for Quality Sprinklers: their 3x3 squares water the same crops, with nothing
moved and the other half of the Sprinklers free. On a real field the edges can still need a few old ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CROSS = ((1, 0), (-1, 0), (0, 1), (0, -1))
RING = tuple((dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)
SCARECROW_REACH = 9  # Distance < 9, from the game's crow check
SCARECROW_NAMES = ("Scarecrow", "Rarecrow", "Deluxe Scarecrow")


@dataclass
class Layout:
    mirror: bool
    offset: int
    sprinklers: list[tuple[int, int]]
    crops: set[tuple[int, int]]
    quality: list[tuple[int, int]] = field(default_factory=list)  # the ones to swap
    keep: list[tuple[int, int]] = field(default_factory=list)  # old ones the Quality ones can't replace


def _on(tile: tuple[int, int], mirror: bool, offset: int) -> bool:
    x, y = tile
    return ((y + 2 * x) if mirror else (x + 2 * y)) % 5 == offset


def _fit(hoed: set, free, box: tuple[int, int, int, int], want: int, mirror: bool, offset: int) -> Layout:
    """The Sprinklers on this lattice that water the most of the dirt you have, until `want` crops are watered."""
    x0, y0, x1, y1 = box
    points = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)
              if _on((x, y), mirror, offset) and free((x, y))]
    arms = {p: {(p[0] + dx, p[1] + dy) for dx, dy in CROSS} for p in points}
    arms = {p: {t for t in a if free(t) and t not in arms} for p, a in arms.items()}
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    points.sort(key=lambda p: (-len(arms[p] & hoed), -len(arms[p]), abs(p[0] - cx) + abs(p[1] - cy)))
    chosen, crops = [], set()
    for p in points:
        if len(crops) >= want:
            break
        chosen.append(p)
        crops |= arms[p]
    return Layout(mirror, offset, chosen, crops)


def _upgrade(layout: Layout) -> None:
    """Which Sprinklers become Quality Sprinklers, and which old ones the edges still need."""
    best: tuple[int, list, list] | None = None
    for r in range(10):
        q = [p for p in layout.sprinklers
             if ((3 * p[1] + p[0]) if layout.mirror else (3 * p[0] + p[1])) % 10 == r]
        wet = {(p[0] + dx, p[1] + dy) for p in q for dx, dy in RING} & layout.crops
        dry = layout.crops - wet
        keep = [p for p in layout.sprinklers if p not in q
                and any((p[0] + dx, p[1] + dy) in dry for dx, dy in CROSS)]
        if q and (best is None or len(q) + len(keep) < best[0]):
            best = (len(q) + len(keep), q, keep)
    if best:
        layout.quality, layout.keep = best[1], best[2]


def plan(hoed: set, objects: dict, want: int, open_tile) -> Layout | None:
    """The best lattice for `want` crops: fewest Sprinklers, then the most dirt already hoed. `open_tile`: the map."""
    if not hoed:
        return None
    pad = 2
    box = (min(x for x, _ in hoed) - pad, min(y for _, y in hoed) - pad,
           max(x for x, _ in hoed) + pad, max(y for _, y in hoed) + pad)

    def free(t):
        return t not in objects and open_tile(t)

    fits = [_fit(hoed, free, box, want, m, c) for m in (False, True) for c in range(5)]
    best = min(fits, key=lambda f: (len(f.crops) < want, len(f.sprinklers), -len(f.crops & hoed)))
    _upgrade(best)
    return best


def scarecrows(objects: dict) -> list[tuple[int, int]]:
    return [t for t, name in objects.items() if name in SCARECROW_NAMES]


def _near(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 < SCARECROW_REACH


def unguarded(crops: set, guards: list) -> set:
    return {c for c in crops if not any(_near(c, g) for g in guards)}


def next_scarecrow(crops: set, guards: list) -> tuple[int, int] | None:
    """The crop tile where one more Scarecrow protects the most; of equals, the one nearest the middle of the
    crops it's for, so it isn't squeezed against the Scarecrow you have."""
    open_crops = unguarded(crops, guards)
    if not open_crops:
        return None
    mx = sum(x for x, _ in open_crops) / len(open_crops)
    my = sum(y for _, y in open_crops) / len(open_crops)
    return max(crops, key=lambda t: (sum(_near(t, c) for c in open_crops), -((t[0] - mx) ** 2 + (t[1] - my) ** 2),
                                     t))


SPRINKLER_RADIUS = {"Sprinkler": 0, "Quality Sprinkler": 1, "Iridium Sprinkler": 2}  # rules sprinkler.basic-4 etc.


def sprinkler_tiles(objects: dict[tuple[int, int], str]) -> set[tuple[int, int]]:
    """The tiles the placed Sprinklers water ({tile: object name}): a Sprinkler its 4 neighbours, a Quality one the
    3x3 around it, an Iridium one the 5x5 (never its own tile). Pressure Nozzles aren't read from the save yet."""
    out: set[tuple[int, int]] = set()
    for (x, y), name in objects.items():
        r = SPRINKLER_RADIUS.get(name)
        if r == 0:
            out |= {(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)}
        elif r:
            out |= {(x + i, y + j) for i in range(-r, r + 1) for j in range(-r, r + 1) if i or j}
    return out
