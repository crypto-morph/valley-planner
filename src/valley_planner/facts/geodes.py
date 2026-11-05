"""What a geode holds before you crack it (Utility.getTreasureFromGeode, GeodeMenu, 1.6.15).

In our words: the count of geodes cracked goes up first, then a generator seeded with that count, the game id / 2
and the farmer's id / 2 skips forward twice (Next(1, 10) draws each), so the result hangs on how many you've cracked,
not when. A one-in-ten roll follows (Qi Beans if that order is running). Geodes with default items flip a coin to use
their mineral list (Data/Objects GeodeDrops, in Precedence order; a chance of 1 draws nothing, and the first that
passes wins). Otherwise it's a stack or a gem: 1, 3 or 5 (10% 10, 1% 20), then a coin: stone, clay or the geode's
gem; or ore by geode type, the rarer ores behind Mines depth.
"""

from __future__ import annotations

from dataclasses import dataclass

from .rng import NetRandom, _i32, random_seed

GEODES = ("535", "536", "537", "749")


@dataclass(frozen=True)
class Crack:
    item: str  # qualified id
    stack: int = 1


def _trunc_half(n: int) -> int:
    return int(n / 2) if abs(n) < 2**31 else n // 2


def crack(data, geode: str, count: int, game_id: int, farmer_id: int, *, deepest: int = 0, legacy: bool = False,
          artifact_found: bool = True) -> Crack:
    """The geode cracked when the running total becomes `count` (1 for your first). An artifact before your first
    real one comes out as 5 Stone (GeodeMenu)."""
    got = _roll(data, geode, count, game_id, farmer_id, deepest, legacy)
    kind = (data.asset("Data/Objects").get(got.item.removeprefix("(O)")) or {}).get("Type")
    return Crack("(O)390", 5) if kind == "Arch" and not artifact_found else got


def _roll(data, geode: str, count: int, game_id: int, farmer_id: int, deepest: int, legacy: bool) -> Crack:
    pid = _trunc_half(_i32(farmer_id))
    r = NetRandom(random_seed(count, game_id // 2, pid, legacy=legacy))
    for _ in range(2):
        for _ in range(r.next(1, 10)):
            r.next_double()
    r.next_double()  # Qi Beans
    info = data.asset("Data/Objects")[geode]
    drops = info.get("GeodeDrops") or []
    if drops and (not info.get("GeodeDropsDefaultItems") or r.next_double() < 0.5):
        for drop in sorted(drops, key=lambda d: d.get("Precedence") or 0):
            chance = drop.get("Chance", 1.0)
            if chance < 1.0 and not r.next_double() < chance:
                continue
            cond = drop.get("Condition") or ""
            if cond.startswith("PLAYER_STAT Current GeodesCracked") and count < int(cond.split()[-1]):
                continue
            pick = r.choose(drop["RandomItemId"]) if drop.get("RandomItemId") else drop.get("ItemId")
            return Crack(pick)
    size = r.next(3) * 2 + 1
    if r.next_double() < 0.1:
        size = 10
    if r.next_double() < 0.01:
        size = 20
    if r.next_double() < 0.5:
        n = r.next(4)
        if n < 2:
            return Crack("(O)390", size)
        if n == 2:
            return Crack("(O)330")
        gem = {"749": 82 + r.next(3) * 2 if geode == "749" else 0, "535": 86, "536": 84}.get(geode, 82)
        return Crack(f"(O){gem}")
    if geode == "535":
        n = r.next(3)
        return Crack("(O)378" if n == 0 or (n == 1 and deepest <= 25) else "(O)380" if n == 1 else "(O)382", size)
    if geode == "536":
        n = r.next(4)
        ore = {0: "378", 1: "380", 2: "382", 3: "384" if deepest > 75 else "380"}[n]
        return Crack(f"(O){ore}", size)
    n = r.next(5)
    if n == 4:
        return Crack("(O)386", size // 2 + 1)
    return Crack(f"(O){('378', '380', '382', '384')[n]}", size)
