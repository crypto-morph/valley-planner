"""What an unlock costs, how long it takes, and what has to come before it (1.6.15).

From the game:
- Buildings (Data/Buildings): Robin's price, materials and build days; an
  upgrade needs the building it upgrades first.
- Animals: Marnie's price is twice the data's PurchasePrice; they need
  their building, then grow up (DaysToMature) and produce (DaysToProduce).
- Tool upgrades (Clint): 2,000 / 5,000 / 10,000 / 25,000g and 5 copper /
  iron / gold / iridium bars for levels 1-4, two days, one level at a time.
- The kitchen: the first house upgrade, 10,000g and 450 Wood, three days.
- Crafted machines: their recipe's materials, once the recipe is known
  (Data/CraftingRecipes: "s <Skill> <level>" means that skill level).
- Cooking recipes: "f <villager> <hearts>" (a letter), "s <skill> <level>",
  "l <level>" (farmer level, not modelled); others come from the Queen of
  Sauce or events.
- The Desert: the Vault bundles (gold) bring the bus; the beach bridge: 300
  Wood; the Secret Woods: a Steel Axe.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..facts.access import place_open
from ..views.farm import Farm

TOOL_PRICES = {1: 2000, 2: 5000, 3: 10000, 4: 25000}
TOOL_BARS = {1: "334", 2: "335", 3: "336", 4: "337"}
TOOL_DAYS = 2
KITCHEN = (10000, (("388", 450),), 3)
BRIDGE_WOOD = 300
SKILLS = ("farming", "fishing", "foraging", "mining", "combat")


@dataclass
class Unlock:
    key: str
    label: str
    gold: int = 0
    materials: list[tuple[str, int]] = field(default_factory=list)
    days: int = 0  # from paying to having it
    after: list[str] = field(default_factory=list)  # unlocks this needs first
    how: str = ""  # anything not bought (a skill level, a friendship, a quest)
    done: bool = False


def _alternates(animal: dict) -> set[str]:
    """The animals Marnie may hand over when you buy this one (white or brown chickens and cows)."""
    return {x for alt in animal.get("AlternatePurchaseTypes") or [] for x in alt.get("AnimalIds") or []}


class Unlocks:
    def __init__(self, farm: Farm):
        self.farm = farm
        self.data = farm.data
        self.save = farm.save

    def get(self, key: str) -> Unlock:
        kind, _, what = key.partition(":")
        f, s = self.farm, self.save
        if kind == "building":
            b = self.data.asset("Data/Buildings").get(what) or {}
            prev = b.get("BuildingToUpgrade")
            return Unlock(key, f"build a {what}", int(b.get("BuildCost") or 0),
                          [(m["ItemId"].removeprefix("(O)"), m["Amount"]) for m in b.get("BuildMaterials") or []],
                          int(b.get("BuildDays") or 0), [f"building:{prev}"] if prev else [],
                          done=bool(s.buildings.get(what)) or self._has_upgrade_of(what))
        if kind == "animal":
            animals = self.data.asset("Data/FarmAnimals")
            a = animals.get(what) or {}
            how = ""
            if int(a.get("PurchasePrice") or -1) < 0:  # Brown Chicken, Brown Cow: bought as the other colour
                seller = next((k for k, v in animals.items() if what in _alternates(v)), None)
                if seller:
                    a = {**animals[seller], "DaysToMature": a.get("DaysToMature"),
                         "DaysToProduce": a.get("DaysToProduce")}
                    how = f"Marnie sells it as a {seller.split()[-1]}; the colour is random"
            house = a.get("RequiredBuilding") or a.get("House") or ""
            return Unlock(key, f"buy a {what}", max(0, int(a.get("PurchasePrice") or 0)) * 2, [],
                          int(a.get("DaysToMature") or 0) + int(a.get("DaysToProduce") or 1),
                          [f"building:{house}"] if house else [], how=how,
                          done=any(x["type"] == what for x in s.animals))
        if kind == "tool":
            tool, _, level = what.partition("@")
            lvl, have = int(level), self._tool_level(tool)
            return Unlock(key, f"a {('', 'Copper', 'Steel', 'Gold', 'Iridium')[lvl]} {tool} from Clint",
                          TOOL_PRICES[lvl], [(TOOL_BARS[lvl], 5)], TOOL_DAYS,
                          [f"tool:{tool}@{lvl - 1}"] if lvl > 1 else [], done=have >= lvl)
        if kind == "kitchen":
            gold, mats, days = KITCHEN
            return Unlock(key, "the kitchen (house upgrade)", gold, list(mats), days, done=s.house_upgrade >= 1)
        if kind == "machine":
            bc = self.data.asset("Data/BigCraftables").get(what.removeprefix("(BC)")) or {}
            name = bc.get("Name") or what
            recipe = self.data.asset("Data/CraftingRecipes").get(name)
            mats = []
            if recipe:
                parts = recipe.split("/")[0].split()
                mats = [(parts[i], int(parts[i + 1])) for i in range(0, len(parts) - 1, 2)]
            return Unlock(key, f"craft a {f.data.text(bc.get('DisplayName')) or name}", 0, mats, 0,
                          [f"recipe:{name}"] if recipe else [], how="" if recipe else "buy one",
                          done=bool(s.machines.get(name)))
        if kind == "recipe":
            return self._recipe(key, what)
        if kind == "place":
            ok, why = place_open("IslandSouth" if what == "Island" else what, f.when)
            if what in ("Desert", "SandyHouse"):
                gold = sum(b.gold or 0 for b in f.bundles.in_area(4) if not b.done)
                return Unlock(key, "the bus to the Desert (finish the Vault)", gold, [], 1, done=ok)
            if what == "Woods":
                return Unlock(key, "the Secret Woods", after=["tool:Axe@2"], done=ok)
            if what == "BeachTidePools":
                return Unlock(key, "repair the beach bridge", 0, [("388", BRIDGE_WOOD)], 0, done=ok)
            return Unlock(key, f"open {what}", how=why, done=ok)
        if kind == "input":
            return Unlock(key, f"get {f.name('(O)' + what)}", how="see its own sources",
                          done=f.held().get(f"(O){what}", 0) > 0)
        return Unlock(key, key, how="not modelled")

    def _recipe(self, key: str, name: str) -> Unlock:
        s = self.save
        known = name in s.crafting_recipes or name in s.cooking_recipes
        raw = self.data.asset("Data/CraftingRecipes").get(name) or self.data.asset("Data/CookingRecipes").get(name)
        field4 = (raw.split("/")[4 if name in self.data.asset("Data/CraftingRecipes") else 3]
                  if raw and len(raw.split("/")) > 3 else "")
        parts = field4.split()
        how = "the Queen of Sauce, a letter or an event"
        if parts[:1] == ["s"] and len(parts) >= 3:
            skill, level = parts[1].lower(), int(parts[2])
            have = s.skills.get(skill, 0)
            how = f"{parts[1]} level {level}" + (f" (you're {have})" if have < level else "")
            known = known or have >= level
        elif parts[:1] == ["f"] and len(parts) >= 3:
            how = f"{parts[2]} hearts with {parts[1]} (a letter)"
        elif parts[:1] == ["default"]:
            known = True
        bought = self._recipe_shop(raw.split("/")[2].split()[0] if raw and len(raw.split("/")) > 2 else "")
        if bought and not known:
            shop, price = bought
            return Unlock(key, f"the {name} recipe", price, how=f"buy it from {shop}", done=False)
        return Unlock(key, f"the {name} recipe", how=how, done=known)

    def _recipe_shop(self, output_id: str) -> tuple[str, int] | None:
        """A shop entry that sells this recipe: (shop, price)."""
        from ..facts.sources import _shop_label
        for sid, shop in self.data.asset("Data/Shops").items():
            for e in shop.get("Items") or []:
                if e.get("IsRecipe") and (e.get("ItemId") or "").removeprefix("(O)") == output_id \
                        and not e.get("Condition"):
                    return _shop_label(sid), int(e.get("Price") or 0)
        return None

    def _tool_level(self, tool: str) -> int:
        return self.save.axe_level if tool == "Axe" else 0

    def _has_upgrade_of(self, building: str) -> bool:
        """A Big Coop also counts as having a Coop."""
        for name in self.save.buildings:
            b = self.data.asset("Data/Buildings").get(name) or {}
            seen = 0
            while b.get("BuildingToUpgrade") and seen < 4:
                if b["BuildingToUpgrade"] == building:
                    return True
                b = self.data.asset("Data/Buildings").get(b["BuildingToUpgrade"]) or {}
                seen += 1
        return False

    def chain(self, key: str) -> list[Unlock]:
        """This unlock and everything it needs first that isn't done, earliest first."""
        out: list[Unlock] = []
        seen = set()

        def walk(k: str) -> None:
            if k in seen:
                return
            seen.add(k)
            u = self.get(k)
            if u.done:
                return
            for a in u.after:
                walk(a)
            out.append(u)

        walk(key)
        return out
