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


def quest_today(save, data, *, festival: bool = False) -> dict | None:
    """The board's request this morning (Utility.getQuestOfTheDay, ItemDeliveryQuest.loadQuestInfo). It isn't in the
    save, but it's a day-seeded roll: {"kind", "who", "item"} (who and item for deliveries), or None for no request."""
    from .conditions import When, check
    from .rng import NetRandom, day_save_random, random_seed
    gid, day = int(save.unique_id), save.days_played
    legacy = save.legacy_random
    if day <= 1 or festival:
        return None
    w = When.from_save(save)
    roll = day_save_random(day, gid, 100, day * 777, legacy=legacy).next_double()
    if roll < 0.08:
        return {"kind": "resource"}
    if roll < 0.2 and save.deepest_mine_level > 0 and day > 5:
        return {"kind": "slay", **slay(gid, day, save.deepest_mine_level, set(save.mail), legacy=legacy)}
    if roll < 0.5:
        return None
    if roll < 0.6:
        return {"kind": "fishing"}
    if roll < 0.66 and w.weekday == 1:
        return {"kind": "socialize"}
    people = [k for k, c in data.asset("Data/Characters").items()
              if check(c.get("CanSocialize"), w) is not False
              and (check(c["ItemDeliveryQuests"], w) if c.get("ItemDeliveryQuests") is not None
                   else c.get("HomeRegion") == "Town")
              and k in save.friends and str(c.get("Age")) != "Child" and save.friends[k].status != "Married"]
    if not people:
        return None
    r = NetRandom(random_seed(gid, day, legacy=legacy))
    who = people[r.next(len(people))]
    vault = "ccVault" in save.mail
    if who == "Wizard" and "wizardJunimoNote" not in save.mail and "JojaMember" not in save.mail:
        who = "Demetrius"
    if save.season != "winter" and r.next_double() < 0.15:
        return {"kind": "delivery", "who": who,
                "item": r.choose(possible_crops(save.season, save.day <= 7, save.year, vault))}
    pool = list(BASE)
    if save.deepest_mine_level > 40:
        pool += MINES_40
    if save.deepest_mine_level > 80:
        pool += MINES_80
    if vault:
        pool += VAULT
    if "Furnace" in save.crafting_recipes:
        pool += FURNACE
    if "Quartz Globe" in save.crafting_recipes:
        pool += QUARTZ_GLOBE
    pool += SEASON[save.season]
    rng = NetRandom(random_seed(gid, day, 1000, legacy=legacy))
    crops = possible_crops(save.season, save.day <= 7, save.year, vault)
    recipes = data.asset("Data/CookingRecipes")
    for name in save.cooking_order:
        if rng.next_double() < 0.4 or name not in recipes:
            continue
        fields = recipes[name].split("/")
        needs = fields[0].split()[::2]
        if all(n in pool or n in crops or (n.startswith("-") and n not in ("-5", "-6")) for n in needs):
            pool.append(fields[2].split()[0])
    item = rng.choose(pool)
    return {"kind": "delivery", "who": who, "item": {"-5": "176", "-6": "184"}.get(item, item)}


# (how many: Next(lo, hi), even only, gold each) per monster, from SlayMonsterQuest.loadQuestInfo
SLAY = {"Green Slime": (4, 11, True, 60), "Rock Crab": (2, 6, False, 75), "Duggy": (2, 4, False, 150),
        "Frost Jelly": (4, 11, True, 85), "Ghost": (2, 4, False, 250), "Sludge": (4, 11, True, 125),
        "Lava Crab": (2, 6, False, 180), "Squid Kid": (1, 3, False, 350), "Skeleton": (6, 12, False, 100),
        "Dust Spirit": (10, 21, False, 60)}
SLAY_OTHER = (3, 7, False, 120)
SLAY_WHERE = {"Green Slime": "the Mines, floors 1 to 29",
              "Rock Crab": "the Mines, floors 1 to 29 (they look like rocks)",
              "Duggy": "the Mines, floors 6 to 29 (they pop up from dirt)", "Frost Jelly": "the Mines, floors 40 to 79",
              "Dust Spirit": "the Mines, floors 40 to 79 (dark floors)", "Skeleton": "the Mines, floors 70 to 79",
              "Ghost": "the Mines, floors 80 to 119", "Sludge": "the Mines, floors 80 to 119",
              "Lava Crab": "the Mines, floors 80 to 119", "Squid Kid": "the Mines, floors 80 to 119"}


def slay(game_id: int, days_played: int, deepest: int, mail: set, *, legacy: bool = False) -> dict:
    """SlayMonsterQuest.loadQuestInfo: which monster, how many, the reward and who asks. Seeded by the game and the
    day; the monster list goes by the deepest Mines floor anyone has reached when the board is read."""
    from .rng import NetRandom, random_seed
    r = NetRandom(random_seed(game_id, days_played, legacy=legacy))
    i = 0
    while i < r.next(1, 100):  # the game draws a new limit on every pass
        r.next()
        i += 1
    if deepest < 39:
        pool = ["Green Slime"] + (["Rock Crab"] if deepest > 10 else []) + (["Duggy"] if deepest > 30 else [])
    elif deepest < 79:
        pool = ["Frost Jelly"] + (["Skeleton"] if deepest > 70 else []) + ["Dust Spirit"]
    else:
        pool = ["Sludge", "Ghost", "Lava Crab", "Squid Kid"]
    monster = pool[r.next(len(pool))]
    lo, hi, even, each = SLAY.get(monster, SLAY_OTHER)
    count = r.next(lo, hi)
    if even:
        count -= count % 2
    who = ("Lewis" if monster in ("Green Slime", "Frost Jelly", "Sludge") else
           "Demetrius" if monster in ("Rock Crab", "Lava Crab") else "Wizard")  # Duggy: Clint, then Wizard
    if who == "Wizard" and "wizardJunimoNote" not in mail and "JojaMember" not in mail:
        who = "Lewis"
    return {"monster": monster, "count": count, "reward": count * each, "who": who,
            "where": SLAY_WHERE.get(monster, "the Mines")}
