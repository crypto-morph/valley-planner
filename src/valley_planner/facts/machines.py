"""What a machine makes from an item, for how much, and when it's ready — from Data/Machines (1.6.15).

How the game decides, in our words:
- A machine's output rules are tried in order; the first whose trigger
  matches wins (MachineDataUtility). A trigger matches when its condition
  holds for the item, the item has the required id, carries every required
  context tag ("!tag" = must not have it), and there are at least as many as
  it needs.
- The output: a plain item; DROP_IN (the item itself); "FLAVORED_ITEM <type>
  <ingredient>", priced from the ingredient's data price — wine ×3, juice
  ×2.25, jelly and pickles ×2 + 50, honey 100 + flower ×2, roe 30 + fish / 2,
  aged roe = roe ×2, dried fruit and mushrooms (×5 ×1.5) + 25, smoked fish
  ×2, bait a tenth; or a machine's own method (cask, seed maker…). Then the
  output's quality (or the input's, with CopyQuality), price copy and price
  modifiers, stack, and preserve fields apply.
- Time: MinutesUntilReady, or DaysUntilReady (ready at 6 AM that many
  mornings later), then the machine's ready-time modifiers (Coopmaster
  halves incubation; the Crystalarium has per-gem times).
- Machine clocks run 10 minutes per 10 game minutes while you're awake, and
  overnight jump to 6 AM: from bedtime that's what's left until 2 AM plus 400
  minutes, so every 6 AM-to-6 AM day is 1,600 machine minutes whenever you
  sleep.
- Some machines also use up other items per load (AdditionalConsumedItems):
  a coal for the Furnace and Fish Smoker, three for the Heavy Furnace.
- Seed Maker: the seed of the first crop (in Data/Crops order) that harvests
  this item; 1-3 of it, or 0.5% one Ancient Seed, then 2% 1-4 Mixed Seeds.
- Context tags an item has: its data tags, "id_(o)<id>", "id_o_<id>",
  "item_<name>", "item_type_<type>", a category tag, a quality tag, and for
  preserves "<type>_item" and "preserve_sheet_index_<id>".
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from .conditions import When, check, split

CATEGORY_TAGS = {
    -26: "artisan_goods", -21: "bait", -9: "big_craftable", -97: "boots", -100: "clothing", -7: "cooking",
    -8: "crafting", -5: "egg", -29: "equipment", -19: "fertilizer", -4: "fish", -80: "flowers", -79: "fruits",
    -24: "furniture", -2: "gem", -81: "greens", -95: "hat", -25: "ingredients", -20: "junk", -999: "litter",
    -14: "meat", -6: "milk", -12: "minerals", -28: "monster_loot", -96: "ring", -74: "seeds",
    -23: "sell_at_fish_shop", -27: "syrup", -22: "tackle", -99: "tool", -75: "vegetable", -98: "weapon",
    -17: "sell_at_pierres", -18: "sell_at_pierres_and_marnies", -15: "metal_resources", -16: "building_resources",
    -101: "trinket"}
QUALITY_TAGS = {0: "quality_none", 1: "quality_silver", 2: "quality_gold", 4: "quality_iridium"}
PRESERVE_TAGS = {"Honey": "honey_item", "Jelly": "jelly_item", "Juice": "juice_item", "Wine": "wine_item",
                 "Pickle": "pickle_item"}
FLAVOR_BASE = {"AgedRoe": "447", "Honey": "340", "Jelly": "344", "Juice": "350", "Pickle": "342", "Roe": "812",
               "Wine": "348", "Bait": "SpecificBait", "DriedFruit": "DriedFruit", "DriedMushroom": "DriedMushrooms",
               "SmokedFish": "SmokedFish"}
DAY_MINUTES = 1600
SEED_MAKER = "OutputSeedMaker"


def sanitize(tag: str) -> str:
    return tag.strip().lower().replace(" ", "_").replace("'", "")


def flavored_price(kind: str, ingredient_price: int, base_price: int = 0, roe_price: int = 30) -> int:
    """The price a flavored item gets from its ingredient's data price (honey and roe add to their own)."""
    p = ingredient_price
    return {
        "Wine": p * 3, "Juice": int(p * 2.25), "Jelly": p * 2 + 50, "Pickle": p * 2 + 50,
        "Honey": base_price + p * 2, "Roe": roe_price + p // 2, "AgedRoe": (roe_price + p // 2) * 2,
        "DriedFruit": int(p * 5 * 1.5) + 25, "DriedMushroom": int(p * 5 * 1.5) + 25,
        "SmokedFish": p * 2, "Bait": max(1, int(p * 0.1)),
    }[kind]


def _minutes(t: int) -> int:
    return t // 100 * 60 + t % 100


def _time(m: int) -> int:
    return m // 60 * 100 + m % 60


def minutes_until_morning(now: int, days: int = 1) -> int:
    """Utility.CalculateMinutesUntilMorning."""
    return 0 if days < 1 else _minutes(2600) - _minutes(now) + 400 + (days - 1) * DAY_MINUTES


def ready_at(load_time: int, minutes: int, *, overnight_only: bool = False) -> tuple[int, int]:
    """(days later, time) a machine loaded at `load_time` with `minutes` is ready; time 600 = by the morning."""
    left, day, now = minutes, 0, load_time
    while True:
        awake = _minutes(2600) - _minutes(now)  # until 2 AM
        if left <= awake and not overnight_only:
            t = _minutes(now) + left
            return day, _time(-(-t // 10) * 10)  # machines are checked every 10 minutes
        night = minutes_until_morning(now)
        if left <= night or (overnight_only and left <= awake):
            return day + 1, 600
        left -= night
        day, now = day + 1, 600


@dataclass(frozen=True)
class Input:
    """An item going into a machine."""
    item: str  # qualified id
    stack: int = 1
    quality: int = 0
    preserve: str | None = None
    preserved_id: str | None = None


@dataclass(frozen=True)
class Output:
    machine: str
    rule: str
    item: str  # qualified id ("" when the machine's own method decides and we don't model it)
    name: str
    price: int  # the output's own price (sell price is worked out from this)
    quality: int
    stack: tuple[int, int]  # min, max
    minutes: int | None
    days: int | None  # DaysUntilReady
    preserve: str | None = None
    preserved_id: str | None = None
    uses: int = 1  # input items it takes
    sure: bool = True  # False: random, or a condition we can't decide
    note: str = ""
    overnight_only: bool = False  # finishes only overnight (incubators)
    also: tuple[tuple[str, int], ...] = ()  # other items each load uses up (coal for the furnace)


class Machines:
    def __init__(self, data):
        self.data = data

    @cached_property
    def machines(self) -> dict:
        return self.data.asset("Data/Machines")

    @cached_property
    def objects(self) -> dict:
        return self.data.asset("Data/Objects")

    @cached_property
    def crops(self) -> dict:
        return self.data.asset("Data/Crops")

    def tags(self, inp: Input) -> set[str]:
        kind, _, iid = inp.item[1:].partition(")")
        out = {sanitize(f"id_({kind}){iid}")}
        if kind == "O":
            out.add(sanitize(f"id_o_{iid}"))
            o = self.objects.get(iid) or {}
            out |= set(o.get("ContextTags") or ())
            if o.get("Name"):
                out.add("item_" + sanitize(o["Name"]))
            if o.get("Type"):
                out.add("item_type_" + sanitize(o["Type"]))
            cat = int(o.get("Category") or 0)
            if cat in CATEGORY_TAGS:
                out.add("category_" + CATEGORY_TAGS[cat])
            if o.get("CanBeGivenAsGift") is False:
                out.add("not_giftable")
            if o.get("GeodeDropsDefaultItems") or o.get("GeodeDrops"):
                out.add("geode")
        if inp.quality in QUALITY_TAGS:
            out.add(QUALITY_TAGS[inp.quality])
        if inp.preserve in PRESERVE_TAGS:
            out.add(PRESERVE_TAGS[inp.preserve])
        if inp.preserved_id:
            out.add("preserve_sheet_index_" + sanitize(inp.preserved_id))
        return {t.lower() for t in out}

    def _item_query(self, tokens: list[str], inp: Input, tags: set[str]) -> bool | None:
        key = tokens[0].lstrip("!").upper()
        args = tokens[2:] if len(tokens) > 1 and tokens[1] in ("Input", "Target") else tokens[1:]
        o = self.objects.get(inp.item[3:]) if inp.item.startswith("(O)") else None
        if key == "ITEM_CONTEXT_TAG":
            return all(t.lower() in tags for t in args)
        if key == "ITEM_ID":
            return inp.item in {a if a.startswith("(") else f"(O){a}" for a in args}
        if key == "ITEM_EDIBILITY":
            if o is None:
                return False
            lo = int(args[0]) if args else -299
            hi = int(args[1]) if len(args) > 1 else 2**31 - 1
            return lo <= int(o.get("Edibility") if o.get("Edibility") is not None else -300) <= hi
        if key == "ITEM_CATEGORY":
            return o is not None and str(int(o.get("Category") or 0)) in args
        if key == "ITEM_QUALITY":
            return inp.quality >= int(args[0]) and inp.quality <= (int(args[1]) if len(args) > 1 else 4)
        return None

    def _condition(self, condition: str | None, inp: Input, when: When | None) -> bool | None:
        """Item queries are answered from the item; the rest by the condition language (None = can't tell)."""
        if not condition:
            return True
        tags, unknown = self.tags(inp), False
        for tokens in split(condition):
            result = self._item_query(tokens, inp, tags)
            if result is None:
                result = check(" ".join(tokens).lstrip("!"), when) if when is not None else None
            if result is None:
                unknown = True
                continue
            if result == tokens[0].startswith("!"):
                return False
        return None if unknown else True

    def _matches(self, trigger: dict, inp: Input, tags: set[str], when: When | None) -> bool | None:
        if "ItemPlacedInMachine" not in (trigger.get("Trigger") or ""):
            return False
        cond = self._condition(trigger.get("Condition"), inp, when)
        if cond is False:
            return False
        req = trigger.get("RequiredItemId")
        if req and inp.item != (req if req.startswith("(") else f"(O){req}"):
            return False
        for t in trigger.get("RequiredTags") or ():
            t = t.strip()
            negated = t.startswith("!")
            name = (t[1:].strip() if negated else t).lower()
            if (name in tags) == negated:
                return False
        if (trigger.get("RequiredCount") or 1) > inp.stack:
            return False
        return cond

    def output(self, machine: str, inp: Input, when: When | None = None, professions=None) -> Output | None:
        """What `machine` makes from `inp` (None if it won't take it)."""
        data = self.machines.get(machine)
        if not data:
            return None
        tags = self.tags(inp)
        for rule in data.get("OutputRules") or []:
            hit = None
            for trig in rule.get("Triggers") or []:
                m = self._matches(trig, inp, tags, when)
                if m is not False:
                    hit = (trig, m)
                    break
            if hit is None:
                continue
            outs = [o for o in rule.get("OutputItem") or []
                    if self._condition(o.get("Condition"), inp, when) is not False]
            if not outs:
                continue
            # several valid outputs: the first if the rule says so, else a random one (we show the first)
            sure = hit[1] is True and (len(outs) == 1 or bool(rule.get("UseFirstValidOutput")))
            made = self._make(machine, rule, outs[0], inp, hit[0], sure)
            if made is not None:
                return self._timed(data, made, professions)
        return None

    def _timed(self, data: dict, out: Output, professions) -> Output:
        """Apply the machine's ready-time modifiers (Coopmaster, per-gem Crystalarium times)."""
        extra = tuple((a["ItemId"], a.get("RequiredCount") or 1) for a in data.get("AdditionalConsumedItems") or [])
        if extra:
            out = Output(**{**out.__dict__, "also": extra})
        if data.get("OnlyCompleteOvernight"):
            out = Output(**{**out.__dict__, "overnight_only": True})
        mods = data.get("ReadyTimeModifiers") or []
        if not mods or out.minutes is None:
            return out
        minutes, sure = float(out.minutes), out.sure
        for m in mods:
            ok = True
            for tokens in split(m.get("Condition") or ""):
                key = tokens[0].upper()
                if key == "ITEM_ID":
                    ok = ok and out.item in {a if a.startswith("(") else f"(O){a}" for a in tokens[2:]}
                elif key == "PLAYER_HAS_PROFESSION":
                    if professions is None:
                        sure = False
                        ok = False
                    else:
                        ok = ok and int(tokens[2]) in professions
                else:
                    sure, ok = False, False
            if ok:
                minutes = {"Multiply": minutes * m["Amount"], "Set": m["Amount"], "Add": minutes + m["Amount"]}.get(
                    m.get("Modification"), minutes)
        return Output(**{**out.__dict__, "minutes": int(minutes), "sure": sure})

    def _make(self, machine: str, rule: dict, out: dict, inp: Input, trigger: dict, sure: bool) -> Output:
        item_id, preserve, preserved, price, note = out.get("ItemId") or "", None, None, None, ""
        method = out.get("OutputMethod") or ""
        stack = (max(out.get("MinStack") or 1, 1), max(out.get("MaxStack") or 1, out.get("MinStack") or 1, 1))
        quality = out.get("Quality") if (out.get("Quality") or -1) >= 0 else 0
        if method.endswith(SEED_MAKER):
            seed = next((k for k, c in self.crops.items()
                         if (c.get("HarvestItemId") or "") in (inp.item, inp.item.removeprefix("(O)"))), None)
            if seed is None:
                return None
            item_id, stack, sure, note = f"(O){seed}", (1, 3), False, "0.5% an Ancient Seed, 2% 1-4 Mixed Seeds"
        elif method:
            item_id, sure, note = "", False, method.rsplit(":", 1)[-1].strip()
        elif item_id == "DROP_IN":
            item_id, preserve, preserved = inp.item, inp.preserve, inp.preserved_id
        elif item_id.startswith("FLAVORED_ITEM"):
            parts = item_id.replace("DROP_IN_ID", inp.item).replace("DROP_IN_PRESERVE", inp.preserved_id or "0").split()
            preserve = parts[1]
            ingredient = parts[2] if len(parts) > 2 else ""
            if preserve == "AgedRoe" and ingredient == "(O)812":
                ingredient = f"(O){inp.preserved_id}" if inp.preserved_id else ""
            preserved = ingredient.removeprefix("(O)") or None
            ing_price = int((self.objects.get(preserved or "") or {}).get("Price") or 0)
            item_id = f"(O){FLAVOR_BASE[preserve]}"
            own = int((self.objects.get(FLAVOR_BASE[preserve]) or {}).get("Price") or 0)
            price = flavored_price(preserve, ing_price, own, int((self.objects.get("812") or {}).get("Price") or 30))
            if preserve == "Honey" and ingredient in ("", "-1", "(O)-1", "(O)NEARBY_FLOWER_ID"):
                preserved, price, sure, note = None, own, False, "flavoured by a flower nearby, if any"
        if out.get("CopyQuality"):
            quality = inp.quality
        base = self.objects.get(item_id.removeprefix("(O)")) if item_id.startswith("(O)") else None
        if price is None:
            price = int((base or {}).get("Price") or 0)
        if out.get("CopyPrice"):
            price = int((self.objects.get(inp.item.removeprefix("(O)")) or {}).get("Price") or 0)
        for m in out.get("PriceModifiers") or []:  # Stack mode (the vanilla data's)
            price = int({"Add": price + m["Amount"], "Multiply": price * m["Amount"], "Set": m["Amount"]}
                        .get(m.get("Modification"), price))
        if out.get("PreserveType"):
            preserve = out["PreserveType"]
        if out.get("PreserveId"):
            preserved = inp.item.removeprefix("(O)") if out["PreserveId"] == "DROP_IN" else (
                inp.preserved_id if out["PreserveId"] == "DROP_IN_PRESERVE" else out["PreserveId"])
        days = rule.get("DaysUntilReady") if (rule.get("DaysUntilReady") or -1) >= 0 else None
        minutes = rule.get("MinutesUntilReady") if days is None and (rule.get("MinutesUntilReady") or -1) >= 0 else None
        name = (base or {}).get("Name") or item_id
        if preserve and preserved:
            name = f"{(self.objects.get(preserved) or {}).get('Name', preserved)} {name}"
        return Output(machine, rule.get("Id") or "", item_id, name, price, quality, stack, minutes, days, preserve,
                      preserved, trigger.get("RequiredCount") or 1, sure, note)
