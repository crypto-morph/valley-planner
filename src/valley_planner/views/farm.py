"""One save, read once, with the game facts the views share."""

from __future__ import annotations

from functools import cached_property
from pathlib import Path

from ..facts.animals import Animals
from ..facts.bundles import Bundles
from ..facts.calendar import Calendar
from ..facts.cart import Cart
from ..facts.conditions import SEASONS, When
from ..facts.crops import Crops
from ..facts.fish import Fish
from ..facts.gifts import Gifts
from ..facts.hours import Hours
from ..facts.items import Items
from ..facts.machines import Machines
from ..facts.places import Places
from ..facts.schedules import Schedules
from ..facts.sell import Farmer
from ..facts.shops import Shops
from ..save import Save, read_save

REGULAR_SEED_SHOPS = ("SeedShop", "Joja", "Sandy")  # shops that are open most days (the cart is separate)


def date_label(season: str, day: int, year: int | None = None) -> str:
    return f"{season.capitalize()} {day}" + (f", Year {year}" if year else "")


class Farm:
    def __init__(self, data, save: Save, path: Path | None = None):
        self.data, self.save, self.path = data, save, path

    @classmethod
    def load(cls, data, path: Path) -> Farm:
        return cls(data, read_save(path, data), path)

    @cached_property
    def when(self) -> When:
        return When.from_save(self.save)

    @cached_property
    def farmer(self) -> Farmer:
        return Farmer.from_save(self.save)

    @cached_property
    def items(self) -> Items:
        return Items(self.data)

    @cached_property
    def crops(self) -> Crops:
        return Crops(self.data)

    @cached_property
    def shops(self) -> Shops:
        return Shops(self.data)

    @cached_property
    def cart(self) -> Cart:
        return Cart(self.data)

    @cached_property
    def calendar(self) -> Calendar:
        return Calendar(self.data)

    @cached_property
    def hours(self) -> Hours:
        return Hours(self.data)

    @cached_property
    def bundles(self) -> Bundles:
        return Bundles.from_save(self.save, self.data)

    @cached_property
    def machines(self) -> Machines:
        return Machines(self.data)

    @cached_property
    def animals(self) -> Animals:
        return Animals(self.data)

    @cached_property
    def gifts(self) -> Gifts:
        return Gifts(self.data)

    @cached_property
    def fish(self) -> Fish:
        return Fish(self.data, self.save.farm_type)

    @cached_property
    def schedules(self) -> Schedules:
        return Schedules(self.data)

    @cached_property
    def yesterday(self) -> Save | None:
        """Last night's save (the game keeps it as <save>_old), if it really is the day before."""
        if self.path is None:
            return None
        old = Path(str(self.path) + "_old")
        if not old.is_file():
            return None
        try:
            prev = read_save(old, self.data)
        except Exception:  # noqa: BLE001 — a damaged _old file just means no comparison
            return None
        return prev if prev.days_played == self.save.days_played - 1 else None

    @cached_property
    def places(self) -> Places:
        return Places(self.data, self.save.farm)

    def place(self, location: str) -> str:
        """A readable place name ("AnimalShop" -> "Marnie's Ranch")."""
        return self.places.name(location)

    def name(self, qid: str) -> str:
        info = self.items.get(qid.removeprefix("(O)"))
        return info.display if info else qid

    def held(self) -> dict[str, int]:
        """Qualified id -> how many you hold (everywhere the save keeps things)."""
        out: dict[str, int] = {}
        for it in self.save.items:
            if it.qualified_id:
                out[it.qualified_id] = out.get(it.qualified_id, 0) + it.stack
        return out

    def where_held(self, qid: str) -> list[str]:
        """Where you keep this, as you'd look for it: 'the green chest (the farm)', 'your backpack'."""
        return sorted({self.where_label(it.where, it.chest) for it in self.save.items if it.qualified_id == qid})

    def where_label(self, label: str, chest: str = "") -> str:
        """'FarmHouse fridge' -> 'the farmhouse (fridge)'; a chest by how it looks: 'the green chest (the farm)'."""
        if label == "Backpack":
            return "your backpack"
        if chest and label.endswith(" chest") and label != "Junimo chest":
            return f"the {chest} ({self.place(label[: -len(' chest')])})"
        for kind in (" chest", " fridge", " auto-grabber"):
            if label.endswith(kind) and label != "Junimo chest":
                return f"{self.place(label[: -len(kind)])} ({kind.strip()})"
        return label

    def hours_today(self) -> list[dict]:
        from .calendar import shop_hours
        return shop_hours(self)["shops"]

    def label(self, days_played: int) -> str:
        d = days_played - 1
        return date_label(SEASONS[d // 28 % 4], d % 28 + 1, d // 112 + 1)
