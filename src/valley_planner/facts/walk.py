"""Walking the valley: can you get there, how far is it, and how to say the way in words (1.6.15).

The maps say which tiles block (xnb/tbin.py) and where their exits lead (the map's Warp property). Searching across
them gives the shortest walk between any two outdoor tiles. Debris on the farm and villagers aren't counted.

Speed: 5 pixels a tick is about 33 tiles in 10 game minutes. NEW_PLAYER_PACE stretches that, because a person stops,
looks and takes corners (a planning choice, from watching the first days of a real game).
"""

from __future__ import annotations

from collections import deque
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
CHUNK = 8  # tiles: small wiggles in a route aren't worth saying
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

    def reach(self, start: Node) -> dict[Node, Node | None]:
        """Every tile you can walk to from `start`, each pointing back along the shortest way."""
        prev: dict[Node, Node | None] = {start: None}
        q = deque([start])
        while q:
            c = q.popleft()
            loc, x, y = c
            onward = [(loc, x + dx, y + dy) for dx, dy in EDGE]
            if c in self.exits:
                onward.append(self.exits[c])
            for n in onward:
                if n not in prev and n[0] in self.grids and self.open(n):
                    prev[n] = c
                    q.append(n)
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

    def minutes(self, path: list[Node]) -> int:
        return round((len(path) - 1) * MINUTES_PER_TILE * self.pace)

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
                out.append((f"{words}, then " if words else "") + f"out the {_edge(path[j], self.grids)} edge "
                           f"to {place(path[j + 1][0])}")
            elif words:
                out.append(words)
            i = j + 1
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


def _legs(tiles: list[tuple[int, int]]) -> list[tuple[str, int]]:
    """A tile route as compass legs, ignoring wiggles."""
    legs: list[tuple[str, int]] = []
    for a, b in zip(tiles[::CHUNK], [*tiles[CHUNK::CHUNK], tiles[-1]], strict=False):
        dx, dy = b[0] - a[0], b[1] - a[1]
        for d, n in ((("east" if dx > 0 else "west"), abs(dx)), (("south" if dy > 0 else "north"), abs(dy))):
            if n and legs and legs[-1][0] == d:
                legs[-1] = (d, legs[-1][1] + n)
            elif n:
                legs.append((d, n))
    kept: list[tuple[str, int]] = []
    for d, n in legs:  # dropping a wiggle can leave two legs the same way
        if n < 3:
            continue
        if kept and kept[-1][0] == d:
            kept[-1] = (d, kept[-1][1] + n)
        else:
            kept.append((d, n))
    return kept


def _edge(node: Node, grids: dict) -> str:
    w, h, _ = grids[node[0]]
    gaps = {"north": node[2], "south": h - 1 - node[2], "west": node[1], "east": w - 1 - node[1]}
    return min(gaps, key=gaps.get)
