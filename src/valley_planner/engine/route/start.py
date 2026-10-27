"""A new farm on Spring 1, Year 1, as a save the rest of the planner can read.

What a new game starts with, in our words: 500g, the farmhouse and the
(broken) greenhouse, a pet bowl and shipping bin, 15 Parsnip Seeds, the
basic tools (no fishing rod until Willy's letter on Spring 2), skills at
0, the standard bundles (Data/Bundles; remixed bundles are chosen when the
farm is made, so a real save's own list wins once there is one).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from ...save import Item, Save
from ...views.farm import Farm

START_MONEY = 500
PARSNIP_SEEDS, START_SEEDS = "472", 15


def new_save(data, *, farm_name: str = "New", unique_id: str = "1") -> Save:
    return Save(
        path=Path(""), mtime=0.0, game_version=data.version, farmer="Farmer", farm=farm_name,
        season="spring", day=1, year=1, days_played=1, money=START_MONEY, total_earned=0, unique_id=unique_id,
        legacy_random=False, weather="sun", weather_tomorrow="sun", daily_luck=0.0,
        items=[Item(id=PARSNIP_SEEDS, name="Parsnip Seeds", stack=START_SEEDS, quality=0, where="Backpack",
                    price=20, category=-74, type="Seeds")],
        buildings=Counter({"Farmhouse": 1, "Greenhouse": 1, "Shipping Bin": 1, "Pet Bowl": 1}),
        skills={k: 0 for k in ("farming", "fishing", "foraging", "mining", "combat")},
        bundle_data=dict(data.asset("Data/Bundles")),
        tool_levels={"Axe": 0, "Pickaxe": 0, "Hoe": 0, "WateringCan": 0, "Pan": -1},
    )


def new_farm(data, **kw) -> Farm:
    return Farm(data, new_save(data, **kw))
