"""What the shipping bin (or a shop) pays for an item (Object.sellToStorePrice, 1.6.15).

In our words: the item's own price × (1 + quality × 0.25), cut to a whole
number; times the best multiplier among the farmers it counts for (one
farmer: every bonus that applies, multiplied together); Cranberry Seeds sell
for half; then times the farm's profit-margin setting, at least 1 if
positive; cut to a whole number. Tackle sells by wear instead.

Bonuses (per farmer):
- Rancher (0) ×1.2: eggs, milk, -18 animal goods, and anything whose name
  has mayonnaise, cheese, cloth or wool in it.
- Tiller (1) ×1.1: vegetables, flowers, and fruit that wasn't found as forage.
- Artisan (4) ×1.4: artisan goods (-26).
- Fisher (6) ×1.25, or ×1.5 with Angler (8): fish, and smoked fish.
- Tapper (15) ×1.25: syrups (-27).  Blacksmith (20) ×1.5: metal bars.
- Gemologist (23) ×1.3: gems and minerals.
- Bear's Knowledge (event 2120303) ×3: Salmonberry, Blackberry.
- Spring Onion Mastery (event 3910979) ×5: Spring Onion.
- The artifact book (Book_Artifact) ×3: artifacts.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

BARS = {"(O)334", "(O)335", "(O)336", "(O)337", "(O)910"}
CRANBERRY_SEEDS = "(O)493"
TACKLE, MAX_TACKLE_USES = -22, 20
RANCHER_WORDS = ("mayonnaise", "cheese", "cloth", "wool")


def f32(x: float) -> float:
    """Round to a 32-bit float, as the game's float arithmetic does after every step."""
    return struct.unpack("<f", struct.pack("<f", x))[0]


@dataclass
class Farmer:
    professions: set[int] = field(default_factory=set)
    events_seen: set[str] = field(default_factory=set)
    stats: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_save(cls, save) -> Farmer:
        return cls(set(save.professions), set(save.events_seen), dict(getattr(save, "stats", {}) or {}))


def multiplier(f: Farmer, qid: str, name: str, category: int | None, type_: str = "", *, spawned: bool = False,
               preserve: str | None = None) -> float:
    lowered, p, m = name.lower(), f.professions, 1.0
    factors = []
    if 0 in p and (any(w in lowered for w in RANCHER_WORDS) or category in (-5, -6, -18)):
        factors.append(1.2)
    if 1 in p and (category in (-75, -80) or (category == -79 and not spawned)):
        factors.append(1.1)
    if 4 in p and category == -26:
        factors.append(1.4)
    if 6 in p and (category == -4 or preserve == "SmokedFish"):
        factors.append(1.5 if 8 in p else 1.25)
    if 15 in p and category == -27:
        factors.append(1.25)
    if 20 in p and qid in BARS:
        factors.append(1.5)
    if 23 in p and category in (-2, -12):
        factors.append(1.3)
    if "2120303" in f.events_seen and qid in ("(O)296", "(O)410"):
        factors.append(3)
    if "3910979" in f.events_seen and qid == "(O)399":
        factors.append(5)
    if f.stats.get("Book_Artifact") and type_ == "Arch":
        factors.append(3)
    for x in factors:
        m = f32(m * f32(x))
    return m


def sell_price(price: int, quality: int, f: Farmer, qid: str, name: str, category: int | None, type_: str = "", *,
               profit_margin: float = 1.0, spawned: bool = False, preserve: str | None = None, uses: int = 0) -> int:
    """One item's sale price. `price` is the item's own price (artisan goods carry theirs)."""
    q = f32(1 + f32(quality * 0.25))
    if category == TACKLE:
        return int(f32(f32(price * q) * f32((MAX_TACKLE_USES - uses) / MAX_TACKLE_USES)))
    value = float(int(f32(price * q)))
    value = f32(value * multiplier(f, qid, name, category, type_, spawned=spawned, preserve=preserve))
    if qid == CRANBERRY_SEEDS:
        value = f32(value / 2)
    if value > 0:
        value = max(1.0, f32(value * f32(profit_margin)))
    return int(value)


def item_sell_price(it, f: Farmer, *, profit_margin: float = 1.0, data_price: int | None = None) -> int:
    """For a save Item (its own price if the save has it, else the data price)."""
    price = it.price if it.price is not None else (data_price or 0)
    return sell_price(price, it.quality, f, it.qualified_id, it.name, it.category, it.type,
                      profit_margin=profit_margin, spawned=it.spawned, preserve=it.preserve or None, uses=it.uses)
