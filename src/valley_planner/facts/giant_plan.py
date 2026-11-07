"""Where to sow a 3x3 block so it turns giant, chosen before the seeds go in (1.6.15).

The giant roll (facts/harvest.py giant_roll) only depends on the top-left tile, the night and the game id, so
for a crop you're about to sow we can look at every square of free ground near your field and every night after
the crop would ripen, and pick a square whose top-left wins on one of them.

In our words:
- The top-left crop rolls on each night it is fully grown (the night it ripens included) and was watered, until
  it's picked. The other 8 tiles only have to hold the same crop, at any age.
- So a block sown on day S of a crop that takes G days is ripe on S + G and can turn giant on the night into any
  day from S + G until the season ends. Waiting a few nights is fine but holds the 9 tiles.
- Only the Farm; only while the crop is in season (the first night of a new season never rolls).
Assumed: no Speed-Gro on the block unless the caller passes its grow days, and the top-left watered every day.
"""

from __future__ import annotations

from dataclasses import dataclass

from .harvest import giant_roll

CLEARABLE = {"Weeds", "Stone", "Twig"}  # cleared in a swing, so a square may cover them
REACH = 8  # how far from your dirt to look, in tiles
MAX_WAIT = 6  # nights a ripe block may wait for its roll


@dataclass(frozen=True)
class GiantSpot:
    key: str  # Data/GiantCrops entry
    tile: tuple[int, int]  # the top-left
    sow_day: int  # days played
    ripe_day: int  # days played: the morning the top-left is ripe
    fires_day: int  # days played: the morning the giant crop is there
    to_hoe: int  # tiles of the 9 that aren't dirt yet
    to_clear: int  # of those, tiles with weeds, stones or twigs on them
    unguarded: int  # tiles outside your Scarecrows' reach

    @property
    def wait(self) -> int:
        return self.fires_day - self.ripe_day

    @property
    def square(self) -> list[tuple[int, int]]:
        x, y = self.tile
        return [(x + i, y + j) for j in range(3) for i in range(3)]


def _square(x: int, y: int) -> list[tuple[int, int]]:
    return [(x + i, y + j) for j in range(3) for i in range(3)]


def candidates(hoed: set, objects: dict, crops: set, open_tile, *, reach: int = REACH) -> list[tuple[int, int]]:
    """Top-left tiles whose whole square is free ground near your dirt: no crop, nothing standing that a swing
    won't clear, and ground you can hoe."""
    near = hoed or set()
    if not near:
        return []
    xs, ys = [x for x, _ in near], [y for _, y in near]
    out = []
    for x in range(min(xs) - reach, max(xs) + reach + 1):
        for y in range(min(ys) - reach, max(ys) + reach + 1):
            sq = _square(x, y)
            if any(t in crops for t in sq):
                continue
            if any((t in objects and objects[t] not in CLEARABLE) or (t not in hoed and not open_tile(t))
                   for t in sq):
                continue
            if min(abs(tx - hx) + abs(ty - hy) for tx, ty in sq for hx, hy in near) > reach:
                continue
            out.append((x, y))
    return out


def find(tops: list[tuple[int, int]], *, key: str, chance: float, game_id: int, sow_days: list[int], grow: int,
         last_day: int, hoed: set, objects: dict, guarded, max_wait: int = MAX_WAIT, legacy: bool = False,
         limit: int = 3) -> list[GiantSpot]:
    """The best squares among `tops` for a block sown on one of `sow_days`: earliest giant first, then least
    waiting, least hoeing, and inside a Scarecrow's reach. `guarded(tile)` says a Scarecrow covers a tile."""
    sow_days = sorted(d for d in sow_days if d + grow <= last_day)
    if not sow_days:
        return []
    first, last = sow_days[0] + grow, last_day
    spots = []
    for x, y in tops:
        for night in range(first, last + 1):
            if not giant_roll(x, y, night, game_id, key, chance, legacy=legacy):
                continue
            sow = [d for d in sow_days if d + grow <= night]
            if not sow or night - (sow[-1] + grow) > max_wait:
                continue
            sq = _square(x, y)
            spots.append(GiantSpot(key, (x, y), sow[-1], sow[-1] + grow, night,
                                   to_hoe=sum(t not in hoed for t in sq),
                                   to_clear=sum(t in objects for t in sq),
                                   unguarded=sum(not guarded(t) for t in sq)))
            break  # the earliest night for this square is the one that matters
    spots.sort(key=lambda s: (s.fires_day, s.wait, s.unguarded > 0, s.to_hoe, s.to_clear, s.tile[1], s.tile[0]))
    out: list[GiantSpot] = []
    for s in spots:  # different squares, not overlapping ones
        if all(not set(s.square) & set(o.square) for o in out):
            out.append(s)
        if len(out) == limit:
            break
    return out
