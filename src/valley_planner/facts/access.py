"""Which places you can get to, and what opens the ones you can't yet (1.6.15).

In our words, from the game's own checks:
- The Desert: the host has the ccVault flag (the bus is fixed).
- The Secret Woods: the hollow log needs an axe upgraded twice (Steel).
- The Sewers: the grate opens with the Rusty Key (or once opened).
- The Mines: open from day 5 (the landslide is cleared).
- The Railroad: from Summer 3, Year 1 for you (DaysPlayed 31); villagers
  use it from day 32.
- The Beach's tide pools (east of the broken bridge): once the bridge is
  repaired (300 Wood).
- Ginger Island: Willy's boat, once repaired (willyBoatFixed).
- The Mutant Bug Lair and the Witch's Swamp: behind quests (the Dark
  Talisman, then Goblin Problem), shown as not open yet.
"""

from __future__ import annotations

from .conditions import When, location_accessible

RAILROAD_DAY = 31
MINES_DAY = 5


def place_open(location: str, w: When) -> tuple[bool, str]:
    """(open now, what opens it)."""
    if location in ("Desert", "SandyHouse", "SkullCave"):
        return location_accessible("Desert", w), "the bus (the Vault bundles, or Joja)"
    if location == "Woods":
        return w.axe_level >= 2, "a Steel Axe for the log"
    if location == "Sewer":
        return "HasRustyKey" in w.mail or "OpenedSewer" in w.mail, "the Rusty Key (60 museum donations)"
    if location == "UndergroundMine":
        return "landslideDone" in w.mail or w.days_played >= MINES_DAY, "the landslide clearing (Spring 5)"
    if location == "Railroad":
        return w.days_played >= RAILROAD_DAY, "Summer 3, Year 1"
    if location == "BeachTidePools":
        return "beachBridgeFixed" in w.flags, "repairing the beach bridge (300 Wood)"
    if location.startswith("Island"):
        return "willyBoatFixed" in w.mail, "Willy's boat"
    if location == "BugLand":
        return False, "the Dark Talisman quest"
    if location == "WitchSwamp":
        return False, "the Witch's Swamp quests"
    return True, ""
