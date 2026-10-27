"""What the Mines give, floor by floor (floors 1-120; MineShaft, 1.6.15).

In our words:
- Areas: floors 1-10 and 30-39 are the first area (the game counts 30-39 with it), 11-29 the second, 40-79
  the frozen floors, 80-120 the lava floors. Every tenth floor has no rocks or monsters; every fifth has no
  ore, gem or forage nodes; floor 1 has no monsters.
- Ores: copper nodes on 2-39 (and copper in ore clumps everywhere), iron nodes on 41-79, gold nodes on
  81-119 (loose iron ore from rocks from 20, loose gold from 60). No iridium in the regular Mines.
- Geodes from rocks: Geode 1-39, Frozen Geode 41-79, Magma Geode 81-119, Omni Geode from 21.
- Minerals on the ground: Quartz anywhere, Earth Crystal 2-39, Frozen Tear 41-79, Fire Quartz 81-119.
  Gem nodes: Amethyst and Topaz from 2; Aquamarine and Jade from 40, Ruby and Emerald from 80 (any floor
  once you've reached the bottom); Diamond nodes from 51; Prismatic Shard from mystic stones on 101+.
- Monsters' drops: Slime from slimes (2-29, 41-79, 81-119; none on 31-39), Bat Wing from bats (31-39,
  41-79, 81-119), Solar Essence from ghosts (51-79) and metal heads / squid kids (81-119), Void Essence
  from shadow brutes and shamans (81-119), Bug Meat from bugs, grubs and flies (2-39).
- Mushrooms on the ground: Red 21-39 and 81-119, Purple 81-119.
- The elevator offers every fifth floor down to the deepest reached; floor 120's chest holds the Skull Key.
"""

from __future__ import annotations

# item id -> (first floor, last floor, how): the shallowest range that gives it
FLOORS: dict[str, tuple[int, int, str]] = {
    "378": (2, 120, "copper nodes and ore"), "380": (20, 119, "iron ore (nodes from floor 41)"),
    "384": (60, 119, "gold ore (nodes from floor 81)"),
    "382": (2, 120, "coal from rocks and monsters"),
    "535": (1, 39, "geodes from rocks"), "536": (41, 79, "frozen geodes from rocks"),
    "537": (81, 119, "magma geodes from rocks"), "749": (21, 120, "omni geodes from rocks"),
    "80": (2, 120, "quartz on the ground"), "86": (2, 39, "earth crystals on the ground"),
    "84": (41, 79, "frozen tears on the ground"), "82": (81, 119, "fire quartz on the ground"),
    "66": (2, 120, "amethyst nodes"), "68": (2, 120, "topaz nodes"),
    "62": (40, 120, "aquamarine nodes"), "70": (40, 120, "jade nodes"),
    "64": (80, 120, "ruby nodes"), "60": (80, 120, "emerald nodes"),
    "72": (51, 120, "diamond nodes"), "74": (101, 120, "mystic stones (rare)"),
    "766": (2, 29, "slimes"), "767": (31, 39, "bats"), "768": (51, 79, "ghosts"),
    "769": (81, 119, "shadow brutes and shamans"), "684": (2, 39, "bugs"),
    "420": (21, 39, "red mushrooms on the ground"), "422": (81, 119, "purple mushrooms on the ground"),
}
ELEVATOR_STEP = 5
BOTTOM = 120


def floor_for(item: str) -> int | None:
    """The shallowest floor that gives this item, or None if the Mines don't."""
    row = FLOORS.get(item.removeprefix("(O)"))
    return row[0] if row else None
