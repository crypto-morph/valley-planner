"""The Forge: which enchantment a Prismatic Shard gives a tool or weapon next, and what forging costs (1.6.15).

The Prismatic Shard roll, in our words (BaseEnchantment.GetEnchantmentFromItem):
- A fresh generator seeded from (the farmer's "timesEnchanted" stat, game id,
  the farmer's multiplayer id) picks one with Next(count) from the
  enchantments the tool can take. Nothing else goes in: not the day, not the
  tool, not luck. Taking the tool out and back, or waiting days, changes
  nothing; the forge shows the same result every time.
- The list, in the game's order: Artful, Bug Killer, Vampiric, Crusader,
  Haymaker, Powerful, Expansive, Shaving, Bottomless, Generous,
  Archaeologist, Master, Auto-Hook, Preserving, Efficient, Swift, Fisher —
  keeping those that fit the tool (below), dropping the kind it already has,
  then dropping, one by one, the names in its "previous enchantments" (the
  last two, newest first) while more than one would be left.
- What fits: melee weapons (not scythes) Artful, Bug Killer, Vampiric,
  Crusader, Haymaker; Pickaxe Powerful, Efficient, Swift; Axe Powerful,
  Shaving, Efficient, Swift; Hoe Expansive (Iridium only), Generous,
  Archaeologist, Efficient, Swift; Watering Can Expansive (Iridium only),
  Bottomless, Efficient; Fishing Rod (any) Master, Auto-Hook, Preserving,
  Efficient; Pan Expansive (Iridium only), Generous, Archaeologist, Fisher.
  Scythes, Milk Pail, Shears, Slingshots and the Return Scepter take none.
- Forging it replaces the tool's enchantment, puts the new name first in
  its previous enchantments (two kept), and adds 1 to timesEnchanted — the
  stat is the farmer's, shared by every tool, so enchanting any other tool
  moves every tool's next roll on.
- Cost: the Prismatic Shard and 20 Cinder Shards.

Weapon forging (Tool.Forge, ForgeMenu.GetForgeCost):
- A gem adds its own enchantment (Emerald speed, Aquamarine crit chance,
  Ruby damage, Amethyst knockback, Topaz defense, Jade crit power), up to 3
  forges a weapon: 10, 15, 20 Cinder Shards for the 1st, 2nd, 3rd. Sure.
- A Diamond (10 shards) fills every forge left with gems not on it yet,
  picked with the game's running random (Game1.random): not knowable ahead.
- A Dragon Tooth (10 shards) rerolls the weapon's innate enchantments, also
  with Game1.random: not knowable ahead.
- A Galaxy Soul on a Galaxy weapon (20 shards): one level of three; the
  third makes it an Infinity weapon. Sure.

Unsure:
- Not yet checked against an enchant done in the game: no save here has
  timesEnchanted or an enchanted tool. The seed and list are read straight
  from the 1.6.15 code.
- The sequence after the first roll assumes you enchant only this tool in
  between (any other Prismatic enchant moves the stat on).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace

from .rng import NetRandom, random_seed

XSI = "{http://www.w3.org/2001/XMLSchema-instance}"
STAT = "timesEnchanted"
SHARD = "(O)74"
SHARD_COST = 20  # Cinder Shards with a Prismatic Shard (or a Galaxy Soul)
SCYTHES = {"47", "53", "66"}
TOOL_KINDS = ("Axe", "Pickaxe", "Hoe", "WateringCan", "FishingRod", "Pan", "MilkPail", "Shears", "Wand",
              "Slingshot", "MeleeWeapon")
GEMS = {"(O)60": "Emerald", "(O)62": "Aquamarine", "(O)64": "Ruby", "(O)66": "Amethyst", "(O)68": "Topaz",
        "(O)70": "Jade"}


def _weapon(t: Tool) -> bool:
    return t.kind == "MeleeWeapon" and t.item_id not in SCYTHES


def _iridium(*kinds: str):
    return lambda t: t.kind in kinds and t.upgrade_level == 4


# (name as the save keeps it, class name, fits) in GetAvailableEnchantments order
ENCHANTMENTS: tuple[tuple[str, str, object], ...] = (
    ("Artful", "ArtfulEnchantment", _weapon),
    ("Bug Killer", "BugKillerEnchantment", _weapon),
    ("Vampiric", "VampiricEnchantment", _weapon),
    ("Crusader", "CrusaderEnchantment", _weapon),
    ("Haymaker", "HaymakerEnchantment", _weapon),
    ("Powerful", "PowerfulEnchantment", lambda t: t.kind in ("Pickaxe", "Axe")),
    ("Expansive", "ReachingToolEnchantment", _iridium("WateringCan", "Hoe", "Pan")),
    ("Shaving", "ShavingEnchantment", lambda t: t.kind == "Axe"),
    ("Bottomless", "BottomlessEnchantment", lambda t: t.kind == "WateringCan"),
    ("Generous", "GenerousEnchantment", lambda t: t.kind in ("Hoe", "Pan")),
    ("Archaeologist", "ArchaeologistEnchantment", lambda t: t.kind in ("Hoe", "Pan")),
    ("Master", "MasterEnchantment", lambda t: t.kind == "FishingRod"),
    ("Auto-Hook", "AutoHookEnchantment", lambda t: t.kind == "FishingRod"),
    ("Preserving", "PreservingEnchantment", lambda t: t.kind == "FishingRod"),
    ("Efficient", "EfficientToolEnchantment",
     lambda t: t.kind in ("Axe", "Pickaxe", "Hoe", "WateringCan", "FishingRod")),
    ("Swift", "SwiftToolEnchantment", lambda t: t.kind in ("Axe", "Pickaxe", "Hoe")),
    ("Fisher", "FisherEnchantment", lambda t: t.kind == "Pan"),
)
BY_CLASS = {cls: name for name, cls, _ in ENCHANTMENTS}


@dataclass(frozen=True)
class Tool:
    kind: str  # the save's class name: Axe, Pickaxe, Hoe, WateringCan, FishingRod, Pan, MeleeWeapon…
    name: str = ""
    item_id: str = ""  # unqualified
    upgrade_level: int = 0
    enchantments: tuple[str, ...] = ()  # class names, all kinds (forges and innate ones included)
    previous: tuple[str, ...] = ()  # previousEnchantments, newest first
    forge_levels: int = 0  # gem forges on a weapon
    where: str = ""

    @property
    def enchantment(self) -> str | None:
        """Its Prismatic Shard enchantment, by name."""
        return next((BY_CLASS[c] for c in self.enchantments if c in BY_CLASS), None)


@dataclass(frozen=True)
class EnchantRoll:
    times_enchanted: int  # the stat when you forge
    enchantment: str | None  # None: nothing fits
    options: tuple[str, ...]  # what it was picked from
    sure: bool  # the first is sure; later ones need no other tool enchanted in between


def available(tool: Tool) -> list[str]:
    """GetAvailableEnchantmentsForItem: the names it can roll, in order."""
    have = set(tool.enchantments)
    out = [name for name, cls, fits in ENCHANTMENTS if fits(tool) and cls not in have]
    for prev in tool.previous:
        if len(out) <= 1:
            break
        out = [n for n in out if n != prev]
    return out


def roll(times_enchanted: int, game_id: int, farmer_id: int, tool: Tool, *, legacy: bool = False) -> str | None:
    options = available(tool)
    rng = NetRandom(random_seed(float(times_enchanted), float(game_id), float(farmer_id), legacy=legacy))
    return rng.choose(options)


def sequence(times_enchanted: int, game_id: int, farmer_id: int, tool: Tool, count: int = 5, *,
             legacy: bool = False) -> list[EnchantRoll]:
    """The next `count` Prismatic Shard results on this tool, forging each in turn."""
    out = []
    for i in range(count):
        options = tuple(available(tool))
        got = roll(times_enchanted, game_id, farmer_id, tool, legacy=legacy)
        out.append(EnchantRoll(times_enchanted, got, options, i == 0))
        if got is None:
            break
        cls = next(c for n, c, _ in ENCHANTMENTS if n == got)
        tool = replace(tool, enchantments=tuple(c for c in tool.enchantments if c not in BY_CLASS) + (cls,),
                       previous=(got, *tool.previous)[:2])
        times_enchanted += 1
    return out


def next_enchantments(save, data, tool: Tool, count: int = 5) -> list[EnchantRoll]:
    """What Prismatic Shards on `tool` give, in order, for this save. `data` is unused (kept for the facts API)."""
    del data
    return sequence(int(save.stats.get(STAT, 0)), int(save.unique_id), int(save.farmer_id), tool, count,
                    legacy=save.legacy_random)


def forge_cost(tool: Tool, item: str) -> int | None:
    """Cinder Shards to forge `item` (qualified id) into `tool`; None if it can't be forged."""
    if item == SHARD:
        return SHARD_COST if available(tool) else None
    if not _weapon(tool):
        return None
    if item == "(O)896":  # Galaxy weapons only (not checked here)
        return SHARD_COST
    if item == "(O)852":
        return 10
    if tool.forge_levels >= 3:
        return None
    if item == "(O)72":
        return 10
    return 10 + 5 * tool.forge_levels if item in GEMS else None


# --- the save ----------------------------------------------------------------------------


def _tag(el: ET.Element) -> str:
    return el.tag.rsplit("}", 1)[-1]


def _text(el: ET.Element, name: str) -> str:
    c = next((c for c in el if _tag(c) == name), None)
    return (c.text or "").strip() if c is not None and c.text else ""


def _tool(el: ET.Element, where: str) -> Tool:
    enchants, previous = [], []
    for c in el:
        tag = _tag(c)
        if tag == "enchantments":  # flattened list: one element per enchantment; or a wrapper
            kind = c.attrib.get(XSI + "type")
            enchants += [kind] if kind else [k.attrib.get(XSI + "type", "") for k in c]
        elif tag == "previousEnchantments":
            previous += [s.text.strip() for s in c if s.text] if len(c) else ([c.text.strip()] if c.text else [])
    gems = {"EmeraldEnchantment", "AquamarineEnchantment", "RubyEnchantment", "AmethystEnchantment",
            "TopazEnchantment", "JadeEnchantment"}  # a Diamond's own marker counts 0 (GetTotalForgeLevels)
    levels = 0
    for c in el:
        if _tag(c) == "enchantments":
            for k in ([c] if c.attrib.get(XSI + "type") else list(c)):
                if k.attrib.get(XSI + "type") in gems:
                    levels += int(_text(k, "level") or 1)
    return Tool(el.attrib.get(XSI + "type", ""), _text(el, "name") or _text(el, "Name"),
                _text(el, "itemId").removeprefix("(W)").removeprefix("(T)"),
                int(_text(el, "upgradeLevel") or 0), tuple(e for e in enchants if e), tuple(previous), levels, where)


def tools_in_save(save) -> list[Tool]:
    """Every tool and weapon the farmer has, backpack first (read from the save file; never written)."""
    root = ET.parse(save.path).getroot()  # noqa: S314 — the player's own local save
    player = next(c for c in root if _tag(c) == "player")
    items = next((c for c in player if _tag(c) == "items"), None)
    mine = set(items.iter()) if items is not None else set()
    found = [(0 if el in mine else 1, el) for el in root.iter() if el.attrib.get(XSI + "type") in TOOL_KINDS
             and _tag(el) in ("Item", "item", "Tool")]
    return [_tool(el, "Backpack" if rank == 0 else "Stored") for rank, el in sorted(found, key=lambda f: f[0])]

