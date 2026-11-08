"""Walking the valley: can you get there, how far is it, and how to say the way in words (1.6.15).

The maps say which tiles block (xnb/tbin.py) and where their exits lead (the map's Warp property). Searching across
them gives the shortest walk between any two outdoor tiles. Debris on the farm and villagers aren't counted.

Speed: 5 pixels a tick is about 33 tiles in 10 game minutes. NEW_PLAYER_PACE stretches that, because a person stops,
looks and takes corners (a planning choice, from watching the first days of a real game).

Diagonals (Farmer.getMovementSpeed): holding two directions moves both axes at once, each at 0.707 of the speed, so
a diagonal step crosses one tile across and one down in sqrt(2) times a straight step's time: slower per step,
faster than the L of two straight steps it replaces. The walk takes a diagonal only when both straight tiles beside
it are open too (no squeezing past a corner), and costs it DIAGONAL tiles.
Unsure: the farmer's box is narrower than a tile and slides along walls one axis at a time, so in play some corners
can be shaved a little more than this allows.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from functools import cached_property

FARM_MAPS = {0: "Farm", 1: "Farm_Fishing", 2: "Farm_Foraging", 3: "Farm_Mining", 4: "Farm_Combat",
             5: "Farm_FourCorners", 6: "Farm_Island", 7: "Farm_Ranching"}
OUTDOORS = ("Farm", "Backwoods", "BusStop", "Mountain", "Town", "Forest", "Beach")
FARMHOUSE_DOOR = (64, 16)
MINUTES_PER_TILE = 10 / 33
NEW_PLAYER_PACE = 1.5
TIDE_POOLS_X = 58  # the Beach east of its broken bridge
EDGE = {(0, -1): "north", (0, 1): "south", (-1, 0): "west", (1, 0): "east"}
DIAGONALS = ((-1, -1), (1, -1), (-1, 1), (1, 1))
DIAGONAL = math.sqrt(2)  # a diagonal step, in straight steps' time (0.707 a tick on each axis)
CHUNK = 8  # tiles: small wiggles in a route aren't worth saying
SLANT = 2.414  # tan(67.5°): a stretch this close to 45° is said as a diagonal
Node = tuple[str, int, int]


@dataclass(frozen=True)
class Landmark:
    name: str
    x: int
    y: int


class Walker:
    def __init__(self, data, farm_type: int = 0, *, bridge_fixed: bool = False):
        self.data = data
        self.farm_map = FARM_MAPS.get(farm_type, "Farm")
        self.bridge_fixed = bridge_fixed
        self.pace = NEW_PLAYER_PACE  # how much slower than a straight run this player walks

    def _asset(self, name: str) -> dict:
        return self.data.asset(f"Maps/{self.farm_map if name == 'Farm' else name}")

    @cached_property
    def grids(self) -> dict[str, tuple[int, int, set[tuple[int, int]]]]:
        out = {}
        for name in OUTDOORS:
            m = self._asset(name)
            back = m["Layers"]["Back"]
            blocked = {tuple(int(v) for v in t.split(",")) for t in m["Blocked"]}
            out[name] = (back["Width"], back["Height"], blocked)
        return out

    @cached_property
    def exits(self) -> dict[Node, Node]:
        """A tile you stand on -> where stepping off it puts you."""
        out: dict[Node, Node] = {}
        for name in OUTDOORS:
            w, h, _ = self.grids[name]
            parts = str(self._asset(name)["Properties"].get("Warp") or "").split()
            for i in range(0, len(parts) - 4, 5):
                x, y, to, tx, ty = parts[i:i + 5]
                if to not in OUTDOORS:
                    continue
                out[(name, min(w - 1, max(0, int(x))), min(h - 1, max(0, int(y))))] = (to, int(tx), int(ty))
        return out

    def open(self, node: Node) -> bool:
        loc, x, y = node
        w, h, blocked = self.grids[loc]
        if not (0 <= x < w and 0 <= y < h) or (x, y) in blocked:
            return False
        return not (loc == "Beach" and x >= TIDE_POOLS_X and not self.bridge_fixed)

    @cached_property
    def _free(self) -> set[Node]:
        """Every open tile, for the search to look up quickly."""
        return {(loc, x, y) for loc, (w, h, _) in self.grids.items() for x in range(w) for y in range(h)
                if self.open((loc, x, y))}

    def reach(self, start: Node) -> dict[Node, Node | None]:
        """Every tile you can walk to from `start`, each pointing back along the quickest way (diagonals allowed)."""
        free, exits = self._free, self.exits
        prev: dict[Node, Node | None] = {start: None}
        best: dict[Node, float] = {start: 0.0}
        done: set[Node] = set()
        heap: list[tuple[float, int, Node]] = [(0.0, 0, start)]
        tick = 0  # first come, first kept among equal costs
        while heap:
            d, _, c = heapq.heappop(heap)
            if c in done:
                continue
            done.add(c)
            loc, x, y = c
            onward = [((loc, x + dx, y + dy), 1.0) for dx, dy in EDGE]
            onward += [((loc, x + dx, y + dy), DIAGONAL) for dx, dy in DIAGONALS
                       if (loc, x + dx, y) in free and (loc, x, y + dy) in free]
            if c in exits:
                onward.append((exits[c], 1.0))
            for n, step in onward:
                nd = d + step
                if n in free and n not in done and nd < best.get(n, math.inf) - 1e-9:
                    best[n] = nd
                    prev[n] = c
                    tick += 1
                    heapq.heappush(heap, (nd, tick, n))
        return prev

    @staticmethod
    def path(prev: dict[Node, Node | None], to: Node) -> list[Node] | None:
        """The way to `to`, or to a tile touching it (forage sits on a tile you walk up to)."""
        loc, x, y = to
        ends = [to] + [(loc, x + dx, y + dy) for dx, dy in EDGE]
        end = next((e for e in ends if e in prev), None)
        if end is None:
            return None
        out = [end]
        while prev[out[-1]] is not None:
            out.append(prev[out[-1]])
        return out[::-1]

    @staticmethod
    def tiles(path: list[Node]) -> float:
        """How long the walk is, in straight steps: a diagonal step counts DIAGONAL."""
        return sum(DIAGONAL if a[0] == b[0] and abs(a[1] - b[1]) == 1 and abs(a[2] - b[2]) == 1 else 1.0
                   for a, b in zip(path, path[1:], strict=False))

    def minutes(self, path: list[Node]) -> int:
        return round(self.tiles(path) * MINUTES_PER_TILE * self.pace)

    @cached_property
    def landmarks(self) -> dict[str, list[Landmark]]:
        """Doors and garbage cans, by the map they're on (name = the place the door opens, or Garbage:<id>)."""
        out: dict[str, list[Landmark]] = {}
        for name in OUTDOORS:
            marks = out.setdefault(name, [])
            for layer in self._asset(name)["Layers"].values():
                for key, props in layer["Tiles"].items():
                    action = str(props.get("Action") or "").split()
                    x, y = (int(v) for v in key.split(","))
                    if len(action) > 3 and action[0] == "LockedDoorWarp":
                        marks.append(Landmark(action[3], x, y))
                    elif action[:1] == ["WarpCommunityCenter"]:
                        marks.append(Landmark("CommunityCenter", x, y))
                    elif action[:1] == ["Garbage"] and len(action) > 1:
                        marks.append(Landmark(f"Garbage:{action[1]}", x, y))
        return out

    def directions(self, path: list[Node], place=lambda n: n) -> list[str]:
        """The walk in words: compass legs on each map, and which edge to leave by."""
        out: list[str] = []
        i = 0
        while i < len(path):
            j = i
            while j + 1 < len(path) and path[j + 1][0] == path[i][0]:
                j += 1
            legs = _legs([(n[1], n[2]) for n in path[i:j + 1]])
            leaving = j + 1 < len(path)
            words = ", then ".join(f"{d} {n}" for d, n in legs)
            if leaving:
                w, h, _ = self.grids[path[j][0]]
                x, y = path[j][1], path[j][2]
                if min(x, y, w - 1 - x, h - 1 - y) > 1:  # a way out inside the map (the Bus Stop's to Town)
                    back = path[max(i, j - 3)]
                    out.append((f"{words}, then " if words else "") + f"on {_heading(x - back[1], y - back[2])} "
                               f"into {place(path[j + 1][0])}")
                else:
                    out.append((f"{words}, then " if words else "") + f"out the {_edge(path[j], self.grids)} edge "
                               f"to {place(path[j + 1][0])}")
            elif words:
                out.append(words)
            i = j + 1
        return out

    def steps(self, path: list[Node], place=lambda n: n) -> list[dict]:
        """The walk as satnav steps, one instruction each (static/satnav.js): a compass leg ("walk"), the edge you
        leave a map by ("exit"), and the door you go in at when the walk ends at one ("door"). Each is
        {kind, loc, from: [x, y], to: [x, y], heading, tiles, minutes, points (turning tiles, for drawing), text};
        an exit also has `onto`, the next map. The legs and their tile counts are the ones `directions` says."""
        out: list[dict] = []
        i = 0
        while i < len(path):
            j = i
            while j + 1 < len(path) and path[j + 1][0] == path[i][0]:
                j += 1
            loc = path[i][0]
            seg = [(n[1], n[2]) for n in path[i:j + 1]]
            last, spans = 0, _spans(seg)
            for k, (d, n, a, b) in enumerate(spans):
                part = path[i + a:i + b + 1]
                out.append({"kind": "walk", "loc": loc, "from": list(seg[a]), "to": list(seg[b]), "heading": d,
                            "tiles": n, "minutes": self.minutes(part), "points": polylines(part)[0]["points"],
                            "text": f"{'Turn' if k else 'Head'} {d} for {n} tile{'s' if n != 1 else ''}"})
                last = b
            if not spans and j + 1 == len(path) and len(seg) > 1:  # a hop too short for a leg: still one step
                (ax, ay), (bx, by) = seg[0], seg[-1]
                d, n = _heading(bx - ax, by - ay), max(abs(bx - ax), abs(by - ay))
                out.append({"kind": "walk", "loc": loc, "from": [ax, ay], "to": [bx, by], "heading": d, "tiles": n,
                            "minutes": self.minutes(path[i:j + 1]), "points": polylines(path[i:j + 1])[0]["points"],
                            "text": f"Step {d} {n} tile{'s' if n != 1 else ''}"})
            if j + 1 < len(path):
                edge, onto = _edge(path[j], self.grids), path[j + 1][0]
                part = path[i + last:j + 1]
                (fx, fy), (tx, ty) = seg[last], seg[-1]
                w, h, _ = self.grids[loc]
                text = f"Leave by the {edge} edge to {place(onto)}"
                if min(tx, ty, w - 1 - tx, h - 1 - ty) > 1:  # a way out inside the map (the Bus Stop's to Town)
                    (ax, ay) = seg[max(0, len(seg) - 4)]
                    edge = _heading(tx - ax, ty - ay)
                    text = f"Go on {edge} into {place(onto)}"
                out.append({"kind": "exit", "loc": loc, "from": [fx, fy], "to": [tx, ty], "heading": edge,
                            "tiles": max(abs(tx - fx), abs(ty - fy)), "minutes": self.minutes(part),
                            "points": polylines(part)[0]["points"], "onto": onto, "text": text})
            i = j + 1
        if path:
            loc, x, y = path[-1]
            doors = [m for m in self.landmarks.get(loc, []) if not m.name.startswith("Garbage:")
                     and abs(m.x - x) <= 1 and -2 <= m.y - y <= -1]  # a door just above where the walk ends
            if doors:
                m = min(doors, key=lambda k: abs(k.x - x) + abs(k.y - y))
                out.append({"kind": "door", "loc": loc, "from": [x, y], "to": [m.x, m.y],
                            "heading": _heading(m.x - x, m.y - y), "tiles": 0, "minutes": 0,
                            "points": [[x, y], [m.x, m.y]], "door": m.name,
                            "text": f"Go in at {place(m.name)}"})
        return out

    def near(self, loc: str, tile: tuple[int, int], place=lambda n: n) -> str:
        """The closest door, in words."""
        marks = [m for m in self.landmarks.get(loc, []) if not m.name.startswith("Garbage:")]
        if not marks:
            return ""
        m = min(marks, key=lambda k: abs(k.x - tile[0]) + abs(k.y - tile[1]))
        dx, dy = tile[0] - m.x, tile[1] - m.y
        if abs(dx) + abs(dy) > 30:
            return ""
        bits = [f"{abs(dy)} {'south' if dy > 0 else 'north'}" if abs(dy) > 1 else "",
                f"{abs(dx)} {'east' if dx > 0 else 'west'}" if abs(dx) > 1 else ""]
        where = " and ".join(b for b in bits if b)
        return f"{where} of {place(m.name)}'s door" if where else f"at {place(m.name)}'s door"


def _spans(tiles: list[tuple[int, int]]) -> list[tuple[str, int, int, int]]:
    """A tile route as compass legs (diagonals too), ignoring wiggles: (direction, tiles, first index, last index).
    The legs run end to end over the whole route: a dropped wiggle's tiles join a leg beside it."""
    legs: list[list] = []
    for ia, ib in zip(range(0, len(tiles), CHUNK), [*range(CHUNK, len(tiles), CHUNK), len(tiles) - 1], strict=False):
        (ax, ay), (bx, by) = tiles[ia], tiles[ib]
        dx, dy = bx - ax, by - ay
        ns, ew = ("south" if dy > 0 else "north"), ("east" if dx > 0 else "west")
        if not dx and not dy:
            continue
        if min(abs(dx), abs(dy)) * SLANT >= max(abs(dx), abs(dy)):  # about as far across as down: a diagonal leg
            d = ns + ew
        else:
            d = ew if abs(dx) > abs(dy) else ns
        n = max(abs(dx), abs(dy))
        if legs and legs[-1][0] == d:
            legs[-1][1] += n
            legs[-1][3] = ib
        else:
            legs.append([d, n, ia, ib])
    kept: list[list] = []
    for d, n, a, b in legs:  # dropping a wiggle can leave two legs the same way
        if n < 3:
            continue
        if kept and kept[-1][0] == d:
            kept[-1][1] += n
            kept[-1][3] = b
        else:
            kept.append([d, n, a, b])
    for k, leg in enumerate(kept):
        leg[2] = kept[k - 1][3] if k else 0
    if kept:
        kept[-1][3] = len(tiles) - 1
    return [(d, n, a, b) for d, n, a, b in kept]


def _legs(tiles: list[tuple[int, int]]) -> list[tuple[str, int]]:
    """A tile route as compass legs (diagonals too), ignoring wiggles."""
    return [(d, n) for d, n, _, _ in _spans(tiles)]


def _heading(dx: int, dy: int) -> str:
    """The compass way from one tile to another, to the nearest eighth."""
    ns, ew = ("south" if dy > 0 else "north" if dy < 0 else ""), ("east" if dx > 0 else "west" if dx < 0 else "")
    if ns and ew and min(abs(dx), abs(dy)) * SLANT < max(abs(dx), abs(dy)):
        return ew if abs(dx) > abs(dy) else ns
    return ns + ew or "north"


def _edge(node: Node, grids: dict) -> str:
    w, h, _ = grids[node[0]]
    gaps = {"north": node[2], "south": h - 1 - node[2], "west": node[1], "east": w - 1 - node[1]}
    return min(gaps, key=gaps.get)


def polylines(path: list[Node]) -> list[dict]:
    """A walk as one line per map, for drawing: {"loc", "points": [[x, y], ...]}, keeping only the tiles where
    the line turns (and each map's first and last tile, so its exits show)."""
    out: list[dict] = []
    for node in path:
        loc, x, y = node
        if not out or out[-1]["loc"] != loc:
            out.append({"loc": loc, "points": [[x, y]]})
            continue
        pts = out[-1]["points"]
        if len(pts) >= 2:
            (ax, ay), (bx, by) = pts[-2], pts[-1]
            sign = lambda v: (v > 0) - (v < 0)  # noqa: E731
            if (sign(bx - ax), sign(by - ay)) == (x - bx, y - by):  # the same step again: straight on
                pts[-1] = [x, y]
                continue
        pts.append([x, y])
    return out
