"""What a Help Wanted delivery can ask for (Utility.getRandomItemFromSeason with forQuest, 1.6.15).

In our words: a base list of gems, minerals and fishing finds, plus more
gems once the mines' floor 40 (and 80) is passed or their bottom reached,
desert finds once the Vault is done (ccVault), bars once the Furnace recipe
is known (and Refined Quartz with the Quartz Globe), the season's forage and
fish, and the season's crops that are possible now (only the early ones in
the first week; some from Year 2 or with the Vault). For quests the game
also adds cooked dishes you know whose ingredients all come from that pool.
Egg (-5) and Milk (-6) requests become a plain Egg or Milk.
"""

from __future__ import annotations

BASE = ("68", "66", "78", "80", "86", "152", "167", "153", "420")
MINES_40 = ("62", "70", "72", "84", "422")
MINES_80 = ("64", "60", "82")
VAULT = ("88", "90", "164", "165")
FURNACE = ("334", "335", "336", "338")
QUARTZ_GLOBE = ("339",)
SEASON = {
    "spring": ("16", "18", "20", "22", "129", "131", "132", "136", "137", "142", "143", "145", "147", "148", "152",
               "167", "267"),
    "summer": ("128", "130", "132", "136", "138", "142", "144", "145", "146", "149", "150", "155", "396", "398",
               "402", "267"),
    "fall": ("404", "406", "408", "410", "129", "131", "132", "136", "137", "139", "140", "142", "143", "148",
             "150", "154", "155", "269"),
    "winter": ("412", "414", "416", "418", "130", "131", "132", "136", "140", "141", "144", "146", "147", "150",
               "151", "154", "269"),
}


def possible_crops(season: str, first_week: bool, year: int, vault: bool) -> list[str]:
    """Utility.possibleCropsAtThisTime: (early crops, all crops) — winter has none."""
    early: list[str]
    late: list[str]
    if season == "spring":
        early = ["24", "192"] + (["250"] if year > 1 else []) + (["248"] if vault else [])
        late = ["190", "188"] + (["252"] if vault else [])
    elif season == "summer":
        early = ["264", "262", "260"] + (["266"] if year > 1 else [])
        late = ["254", "256"] + (["258", "268"] if vault else [])
    elif season == "fall":
        early = ["272", "278"] + (["284"] if vault else [])
        late = ["270", "276", "280"] + (["274"] if year > 1 else []) + (["282"] if vault else [])
    else:
        return []
    return early if first_week else late + early


def raw_pool(season: str, day: int, year: int, *, mine_lowest: int = 0, mine_bottom: bool = False,
             vault: bool = False, crafting: set[str] = frozenset()) -> set[str]:
    """Object ids (unqualified) a Help Wanted delivery can ask for that aren't cooked dishes."""
    ids = set(BASE)
    if mine_lowest > 40 or mine_bottom:
        ids |= set(MINES_40)
    if mine_lowest > 80 or mine_bottom:
        ids |= set(MINES_80)
    if vault:
        ids |= set(VAULT)
    if "Furnace" in crafting:
        ids |= set(FURNACE)
    if "Quartz Globe" in crafting:
        ids |= set(QUARTZ_GLOBE)
    ids |= set(SEASON[season])
    ids |= set(possible_crops(season, day <= 7, year, vault))
    return ids
