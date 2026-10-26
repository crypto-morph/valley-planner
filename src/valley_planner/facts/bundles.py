"""Community Center bundles: what each asks for, what's been given, and what you hold that fits (1.6.15).

In our words:
- This farm's bundles are the save's bundleData (remixed or not), keyed
  "<Room>/<index>"; very old saves lack it and use Data/Bundles. A bundle is
  "name/reward/ingredients/colour/slots/sprite/display name"; ingredients are
  triples "id stack quality"; slots (if given) is how many must be filled.
- Matching (Bundle.IsValidItemForThisIngredientDescription): the item's
  quality must be at least the one asked; a negative id is a category (and a
  Dinosaur Egg counts as an egg, -5); otherwise the exact item id.
- Progress: the save keeps a true/false list per bundle, three times as long
  as its ingredients; entry i says ingredient i was given. A bundle shows as
  done once as many of those as its slots are true. Finishing it with items
  sets the whole list true; buying a Vault bundle sets only the first entry.
- Counting complete bundles (for which rooms' notes appear) needs the whole
  list true, so paid Vault bundles don't count. Notes appear: Crafts Room
  always; Pantry and Fish Tank after 1 complete bundle; Boiler Room after 2;
  Bulletin Board after 3; Vault after 4; the Joja "Missing" bundle after the
  Community Center ceremony; never once every bundle in the room is done.
- Vault bundles cost gold: the stack of their last ingredient.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from functools import cached_property

AREAS = {"Pantry": 0, "Crafts Room": 1, "CraftsRoom": 1, "Fish Tank": 2, "FishTank": 2, "Boiler Room": 3,
         "BoilerRoom": 3, "Vault": 4, "Bulletin": 5, "BulletinBoard": 5, "Bulletin Board": 5,
         "Abandoned Joja Mart": 6}
AREA_NAMES = ("Pantry", "Crafts Room", "Fish Tank", "Boiler Room", "Vault", "Bulletin Board", "Abandoned Joja Mart")
VAULT = 4
JOJA = 6
NOTE_AFTER = {1: 0, 0: 1, 2: 1, 3: 2, 5: 3, 4: 4}  # area -> complete bundles needed before its notes appear
CC_RESTORED_EVENT = "191393"
EGG_CATEGORY, DINOSAUR_EGG = -5, "(O)107"
REWARD_TYPES = {"O": "(O)", "BO": "(BC)", "F": "(F)", "R": "(O)", "B": "(B)", "W": "(W)", "H": "(H)"}


@dataclass(frozen=True)
class Ingredient:
    index: int
    item: str | None  # qualified id, or None for a category
    category: int | None
    stack: int
    quality: int
    given: bool

    def accepts(self, qualified_id: str, category: int | None, quality: int) -> bool:
        if quality < self.quality:
            return False
        if self.category is not None:
            return category == self.category or (self.category == EGG_CATEGORY and qualified_id == DINOSAUR_EGG)
        return qualified_id == self.item


@dataclass
class Bundle:
    key: str  # "Pantry/0"
    index: int
    room: str
    area: int
    name: str
    display: str
    reward: str | None  # qualified id
    reward_count: int
    ingredients: list[Ingredient]
    slots: int  # how many must be filled
    flags: list[bool]

    @property
    def done(self) -> bool:
        """As the bundle menu shows it."""
        return sum(i.given for i in self.ingredients) >= self.slots

    @property
    def counts_as_complete(self) -> bool:
        """For unlocking notes: every flag set (paid Vault bundles aren't)."""
        return bool(self.flags) and all(self.flags)

    @property
    def gold(self) -> int | None:
        return self.ingredients[-1].stack if self.area == VAULT and self.ingredients else None

    @property
    def still_needed(self) -> int:
        return 0 if self.done else self.slots - sum(i.given for i in self.ingredients)

    @property
    def open_ingredients(self) -> list[Ingredient]:
        return [] if self.done else [i for i in self.ingredients if not i.given]


def _qualify(token: str) -> str:
    return token if token.startswith("(") else f"(O){token}"


def parse_bundle(key: str, raw: str, flags: list[bool]) -> Bundle:
    room, _, idx = key.rpartition("/")
    f = raw.split("/")
    tokens = f[2].split() if len(f) > 2 else []
    ingredients = []
    for n, i in enumerate(range(0, len(tokens) - 2, 3)):
        tid, stack, quality = tokens[i], int(tokens[i + 1]), int(tokens[i + 2])
        cat = int(tid) if tid.lstrip("-").isdigit() and int(tid) < 0 else None
        ingredients.append(Ingredient(n, None if cat is not None else _qualify(tid), cat, stack, quality,
                                      n < len(flags) and flags[n]))
    reward = f[1].split() if len(f) > 1 and f[1] else []
    slots = int(f[4]) if len(f) > 4 and f[4].strip().lstrip("-").isdigit() else len(ingredients)
    return Bundle(
        key=key, index=int(idx), room=room, area=AREAS.get(room, -1), name=f[0],
        display=f[6] if len(f) > 6 and f[6] else f[0],
        reward=(REWARD_TYPES.get(reward[0], f"({reward[0]})") + reward[1]) if len(reward) >= 2 else None,
        reward_count=int(reward[2]) if len(reward) >= 3 and reward[2].isdigit() else 1,
        ingredients=ingredients, slots=slots, flags=list(flags))


@dataclass
class Fit:
    """Something you hold that a bundle can take."""
    bundle: Bundle
    ingredient: Ingredient


@dataclass
class Plan:
    """Held items set aside for open slots (a planning choice: quality slots first, uncontested items first)."""
    # (bundle key, ingredient index) -> [(item id, quality, count)]
    reserved: dict[tuple[str, int], list[tuple[str, int, int]]] = field(default_factory=dict)
    partial: dict[tuple[str, int], int] = field(default_factory=dict)  # some held, not enough yet


class Bundles:
    def __init__(self, bundles: list[Bundle], *, events_seen: set[str] = frozenset()):
        self.all = bundles
        self.events_seen = set(events_seen)

    @classmethod
    def from_save(cls, save, data=None) -> Bundles:
        raw = save.bundle_data or (data.asset("Data/Bundles") if data is not None else {})
        out = []
        for key, value in raw.items():
            idx = int(key.rpartition("/")[2])
            n = len(value.split("/")[2].split()) if len(value.split("/")) > 2 else 0
            flags = list(save.bundle_slots.get(idx, []))[:n] + [False] * max(0, n - len(save.bundle_slots.get(idx, [])))
            out.append(parse_bundle(key, value, flags))
        out.sort(key=lambda b: (b.area if b.area >= 0 else 99, b.index))
        return cls(out, events_seen=set(save.events_seen))

    @cached_property
    def by_key(self) -> dict[str, Bundle]:
        return {b.key: b for b in self.all}

    def in_area(self, area: int) -> list[Bundle]:
        return [b for b in self.all if b.area == area]

    def complete_count(self) -> int:
        return sum(b.counts_as_complete for b in self.all)

    def area_done(self, area: int) -> bool:
        """Every bundle in the area has each ingredient's flag set (how the game decides the note is gone)."""
        return all(all(b.flags[:len(b.ingredients)]) for b in self.in_area(area))

    def notes_shown(self, area: int) -> bool:
        """CommunityCenter.shouldNoteAppearInArea."""
        if self.area_done(area):
            return False
        if area == JOJA:
            return CC_RESTORED_EVENT in self.events_seen
        return area in NOTE_AFTER and self.complete_count() >= NOTE_AFTER[area]

    def fits(self, qualified_id: str, category: int | None, quality: int, *, shown_only: bool = True) -> list[Fit]:
        """Open slots this item could fill (by default only in rooms whose notes are up)."""
        out = []
        for b in self.all:
            if b.done or b.area == VAULT or (shown_only and not self.notes_shown(b.area)):
                continue
            out += [Fit(b, i) for i in b.open_ingredients if i.accepts(qualified_id, category, quality)]
        return out

    def plan(self, held) -> Plan:
        """Set held items (save Items) aside for open slots: whole stacks only; quality-gated slots first,
        then the slots fewest other bundles compete for. Leftover partial amounts are reported, not reserved."""
        stock: dict[tuple[str, int | None, int], int] = defaultdict(int)
        for it in held:
            if it.qualified_id:
                stock[(it.qualified_id, it.category, it.quality)] += it.stack
        open_ = [(b, i) for b in self.all if not b.done and b.area != VAULT for i in b.open_ingredients]
        demand: dict[str | int | None, int] = defaultdict(int)
        for _, i in open_:
            demand[i.item or i.category] += 1

        def have(i: Ingredient) -> int:
            return sum(n for (qid, cat, q), n in stock.items() if i.accepts(qid, cat, q))

        def take(i: Ingredient) -> list[tuple[str, int, int]]:
            need, got = i.stack, []
            for key in sorted((k for k in stock if i.accepts(*k) and stock[k] > 0), key=lambda k: k[2]):
                n = min(need, stock[key])
                stock[key] -= n
                need -= n
                got.append((key[0], key[2], n))
                if not need:
                    break
            return got

        plan = Plan()
        order = sorted({b.key: b for b, _ in open_}.values(),
                       key=lambda b: (not self.notes_shown(b.area), b.area, b.index))
        for quality_pass in (True, False):
            for b in order:
                taken = sum(1 for (bk, _) in plan.reserved if bk == b.key)
                cands = [i for i in b.open_ingredients if (b.key, i.index) not in plan.reserved
                         and (i.quality > 0) == quality_pass]
                cands.sort(key=lambda i: (have(i) < i.stack, demand[i.item or i.category], i.index))
                for i in cands:
                    if taken >= b.still_needed:
                        break
                    if have(i) < i.stack:
                        continue
                    plan.reserved[(b.key, i.index)] = take(i)
                    taken += 1
        for b, i in open_:
            if (b.key, i.index) not in plan.reserved and have(i):
                plan.partial[(b.key, i.index)] = min(i.stack, have(i))
        return plan
