"""Farm animals: what they produce overnight, and the odds of better produce (FarmAnimal.dayUpdate, 1.6.15).

Overnight, in our words (each animal, in its home):
- Its home's door closed: happiness + 2 × its happiness drain.
- One more day since it last produced.
- Not petted today: friendship - (10 - friendship / 200), happiness - 50.
  (Petting: friendship +15, happiness + max(5, 30 + drain); with the
  animal's happiness profession — Coopmaster for coop animals, Shepherd for
  barn ones — friendship +15 and that happiness again.)
- Hungry (fullness under 200) and hay in the trough: it eats, fullness 255.
- A generator seeded (animal id / 2, days played — already the new day's).
  It grows a day if full (else with chance (fullness - 30) / 170); growing
  also adds 2 × drain happiness. Still hungry: happiness - 100, friendship - 20.
- It produces if enough days have passed (DaysToProduce, one fewer with the
  friendship or profession that speeds it up — Sheep with Shepherd), then
  rolls under fullness / 200 and under happiness / 70, and it's not a baby.
  The item is picked from its produce list (minimum friendship, condition).
- Then a roll under happiness / 150: only then can it be deluxe — the
  deluxe list, friendship at least the minimum, and a roll under
  (friendship + care) / divisor + luck × multiplier, where care is
  happiness × 1.5 above 200, (happiness - 100) at 100 or below, else 0 —
  and only then is the day count reset and a new quality rolled:
  q = friendship / 1000 - (1 - happiness / 225), +0.33 with the animal's
  quality profession; iridium if q ≥ 0.95 and a roll under q / 2, else gold
  under q / 2, else silver under q, else normal. Otherwise the last quality
  stays and it can produce again the next night.
- Eggs, wool from rabbits, feathers, feet drop on the floor (or into an
  auto-grabber); milk and wool from sheep wait for the pail or shears; pigs
  dig truffles outside. An animal cracker doubles the drop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

from .rng import NetRandom, random_seed
from .sell import f32


@dataclass(frozen=True)
class Kind:
    id: str
    house: str
    days_to_produce: int
    days_to_mature: int
    harvest: str  # DropOvernight / HarvestWithTool / DigUp
    produce: tuple[tuple[str, int, str | None], ...]  # (item id, minimum friendship, condition)
    deluxe: tuple[tuple[str, int, str | None], ...]
    deluxe_min_friendship: int
    care_divisor: float
    luck_multiplier: float
    drain: int
    faster_friendship: int
    faster_profession: int
    quality_profession: int
    happiness_profession: int
    produce_on_mature: bool
    sell_price: int
    purchase_price: int


@dataclass
class Animal:
    """An animal's state from the save (the morning)."""
    id: str
    type: str
    name: str = ""
    friendship: int = 0
    happiness: int = 255
    fullness: int = 0
    age: int = 0
    days_since_lay: int = 0
    produce_quality: int = 0
    cracker: bool = False

    @classmethod
    def from_save(cls, d: dict) -> Animal:
        return cls(d["id"], d["type"], d.get("name", ""), d.get("friendship", 0), d.get("happiness", 255),
                   d.get("fullness", 0), d.get("age", 0), d.get("days_since_lay", 0), d.get("produce_quality", 0),
                   d.get("cracker", False))


@dataclass
class Night:
    produce: str | None = None  # item id, if it produces
    deluxe: bool = False
    quality: int = 0
    stack: int = 1
    grows: bool = False
    friendship: int = 0  # after the night
    happiness: int = 0
    sure: bool = True  # False: the deluxe roll depends on tomorrow's luck
    notes: list[str] = field(default_factory=list)


def _clamp(v: int, lo: int = 0, hi: int = 255) -> int:
    return max(lo, min(hi, v))


class Animals:
    def __init__(self, data):
        self.data = data

    @cached_property
    def kinds(self) -> dict[str, Kind]:
        out = {}
        for k, v in self.data.asset("Data/FarmAnimals").items():
            def lst(key, v=v):
                return tuple((p["ItemId"], p.get("MinimumFriendship") or 0, p.get("Condition"))
                             for p in v.get(key) or [])
            out[k] = Kind(k, v.get("House") or "", v.get("DaysToProduce") or 1, v.get("DaysToMature") or 0,
                          v.get("HarvestType") or "DropOvernight", lst("ProduceItemIds"), lst("DeluxeProduceItemIds"),
                          v.get("DeluxeProduceMinimumFriendship") or 0, v.get("DeluxeProduceCareDivisor") or -1.0,
                          v.get("DeluxeProduceLuckMultiplier") or 0.0, v.get("HappinessDrain") or 0,
                          v.get("FriendshipForFasterProduce", -1), v.get("ProfessionForFasterProduce", -1),
                          v.get("ProfessionForQualityBoost", -1), v.get("ProfessionForHappinessBoost", -1),
                          bool(v.get("ProduceOnMature")), v.get("SellPrice") or 0, v.get("PurchasePrice") or 0)
        return out

    def sell_price(self, a: Animal) -> int:
        """FarmAnimal.getSellPrice: price × (friendship / 1000 + 0.3)."""
        return int(self.kinds[a.type].sell_price * (a.friendship / 1000 + 0.3))

    def tonight(self, a: Animal, days_played_tomorrow: int, *, professions=frozenset(), petted: bool = True,
                fed: bool = True, door_closed: bool = True, luck: float | None = None) -> Night:
        """Replay tonight for an animal indoors from 6 PM. `fed`: it grazed or has hay waiting."""
        k = self.kinds[a.type]
        night = Night()
        friendship, happiness = a.friendship, a.happiness
        if petted:
            friendship = min(1000, friendship + 15)
            if k.happiness_profession >= 0 and k.happiness_profession in professions:
                friendship = min(1000, friendship + 15)
                happiness = _clamp(happiness + max(5, 30 + k.drain))
            happiness = _clamp(happiness + max(5, 30 + k.drain))
        fullness = 255 if fed else a.fullness
        faster = 1 if 0 <= k.faster_friendship <= friendship else 0  # decided before tonight's changes
        if door_closed:
            happiness = _clamp(happiness + k.drain * 2)
        since = a.days_since_lay + 1
        if not petted:
            friendship = max(0, friendship - (10 - friendship // 200))
            happiness = max(0, happiness - 50)
        r = NetRandom(random_seed(int(a.id) / 2.0, days_played_tomorrow))
        age = a.age
        if fullness > 200 or r.next_double() < (fullness - 30) / 170.0:
            if age == k.days_to_mature - 1:
                age = k.days_to_mature
                since = 99
                night.grows = True
                if k.produce_on_mature:
                    night.notes.append("grows up tonight (and has produce waiting)")
                    night.sure = False  # its produce pick uses the generator too
            else:
                age += 1
            happiness = _clamp(happiness + k.drain * 2)
        if fullness < 200:
            happiness = max(0, happiness - 100)
            friendship = max(0, friendship - 20)
        if k.faster_profession >= 0 and k.faster_profession in professions:
            faster += 1
        produces = since >= k.days_to_produce - faster and r.next_double() < fullness / 200.0 \
            and r.next_double() < happiness / 70.0
        quality = a.produce_quality
        item = None
        if produces and age >= k.days_to_mature:
            item = self._pick(k.produce, friendship, r)
            if r.next_double() < happiness / 150.0:
                care = f32(happiness * 1.5) if happiness > 200 else float(happiness - 100 if happiness <= 100 else 0)
                deluxe = self._pick(k.deluxe, friendship, r)
                if k.care_divisor >= 0 and deluxe is not None and friendship >= k.deluxe_min_friendship:
                    if k.luck_multiplier and luck is None:
                        night.sure = False
                        night.notes.append("the deluxe roll depends on tomorrow's luck")
                    if r.next_double() < f32(f32(friendship + care) / f32(k.care_divisor)) \
                            + (luck or 0.0) * f32(k.luck_multiplier):
                        item, night.deluxe = deluxe, True
                q = f32(f32(friendship / 1000) - f32(1 - f32(happiness / 225)))
                if k.quality_profession >= 0 and k.quality_profession in professions:
                    q += 0.33
                if q >= 0.95 and r.next_double() < q / 2:
                    quality = 4
                elif r.next_double() < q / 2:
                    quality = 2
                elif r.next_double() < q:
                    quality = 1
                else:
                    quality = 0
        night.produce, night.quality = item, quality
        night.stack = 2 if a.cracker and k.harvest == "DropOvernight" else 1
        night.friendship, night.happiness = friendship, happiness
        return night

    @staticmethod
    def _pick(options, friendship: int, r: NetRandom) -> str | None:
        valid = [o for o in options if not (o[1] > 0 and friendship < o[1])]  # (vanilla lists have no conditions)
        return r.choose([o[0] for o in valid])

    def deluxe_days(self, kind: str, confidence: float = 0.8, *, professions=frozenset(),
                    limit: int = 336) -> int | None:
        """Days from buying a newborn to `confidence` of at least one deluxe item: petted every day (+15
        friendship, +15 more with the animal's happiness profession), full happiness, average luck."""
        k = self.kinds[kind]
        if not k.deluxe or k.care_divisor < 0:
            return None
        step = 15 + (15 if k.happiness_profession in professions else 0)
        friendship, none, care = 0, 1.0, 255 * 1.5
        for day in range(1, limit + 1):
            friendship = min(1000, friendship + step)
            if day <= k.days_to_mature or (day - k.days_to_mature) % k.days_to_produce:
                continue
            if friendship >= k.deluxe_min_friendship:
                none *= 1 - min(1.0, (friendship + care) / k.care_divisor)
                if 1 - none >= confidence:
                    return day
        return None

    def odds(self, a: Animal, *, professions=frozenset(), petted: bool = True) -> dict[str, float]:
        """Chances for tonight from today's state, if fed and petted: produce, deluxe, and each quality."""
        k = self.kinds[a.type]
        friendship = min(1000, a.friendship + (15 if petted else 0) +
                         (15 if petted and k.happiness_profession in professions else 0))
        happiness = _clamp(a.happiness + (max(5, 30 + k.drain) if petted else -50) + k.drain * 4)
        produce = min(1.0, happiness / 70.0)
        branch = min(1.0, happiness / 150.0)
        care = happiness * 1.5 if happiness > 200 else (happiness - 100 if happiness <= 100 else 0)
        deluxe = 0.0
        if k.deluxe and k.care_divisor >= 0 and friendship >= k.deluxe_min_friendship:
            deluxe = branch * max(0.0, min(1.0, (friendship + care) / k.care_divisor))
        q = friendship / 1000 - (1 - happiness / 225) + (0.33 if k.quality_profession in professions else 0)
        half = max(0.0, min(1.0, q / 2))
        iri = half if q >= 0.95 else 0.0
        gold = (1 - iri) * half
        silver = (1 - iri) * (1 - half) * max(0.0, min(1.0, q))
        return {"produce": produce, "deluxe": produce * deluxe, "iridium": iri, "gold": gold, "silver": silver,
                "normal": max(0.0, 1 - iri - gold - silver), "new_quality": branch}
