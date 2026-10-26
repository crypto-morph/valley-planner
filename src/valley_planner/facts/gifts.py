"""Gift tastes from Data/NPCGiftTastes, resolved the way NPC.getGiftTasteForThisItem does (1.6.15).

For an object, in our words:
1. Universal tastes, in three passes that each override the last:
   categories (the item's category number, "0" included), then context
   tags, then specific items (love, hate, like, dislike, then neutral —
   the first list that names it wins).
2. Artifacts (type "Arch") become disliked — liked by Penny and the Dwarf.
3. Still neutral and not named by a universal list: hated if its edibility
   is negative (but not -300, "inedible"), else disliked if it's worth
   under 20g.
4. The villager's own lists then decide if they name the item: specific
   items first (love, hate, like, dislike, neutral), then context tags in
   the same order, then — only if no universal list named the item —
   categories (never category 0).
Non-object gifts (rings, tools…) are neutral. Stardrop Tea is special.
Item ids in the lists may be numbers ("24") or words ("Raisins").
"""

from __future__ import annotations

from functools import cached_property

LOVE, LIKE, NEUTRAL, DISLIKE, HATE = "love", "like", "neutral", "dislike", "hate"
ORDER = (LOVE, HATE, LIKE, DISLIKE, NEUTRAL)  # the order the game checks lists in
PERSONAL_SLOTS = {LOVE: 1, LIKE: 3, DISLIKE: 5, HATE: 7, NEUTRAL: 9}  # positions in a villager's entry
INEDIBLE = -300
STARDROP_TEA = "StardropTea"


def _tokens(raw: str) -> list[str]:
    return [t for t in raw.split() if t]


class Gifts:
    def __init__(self, data):
        self.data = data

    @cached_property
    def _objects(self) -> dict:
        return self.data.asset("Data/Objects")

    @cached_property
    def _universal(self) -> dict[str, list[str]]:
        raw = self.data.asset("Data/NPCGiftTastes")
        return {t: _tokens(raw.get(f"Universal_{t.capitalize()}", "")) for t in ORDER}

    @cached_property
    def villagers(self) -> dict[str, dict[str, list[str]]]:
        out = {}
        for name, raw in self.data.asset("Data/NPCGiftTastes").items():
            if name.startswith("Universal_"):
                continue
            parts = raw.split("/")
            out[name] = {t: _tokens(parts[i]) if i < len(parts) else [] for t, i in PERSONAL_SLOTS.items()}
        return out

    def _names_item(self, tokens: list[str], item_id: str) -> bool:
        """CheckTaste: a token that is an item id equal to this object (qualified or not)."""
        for t in tokens:
            if t.startswith("-"):
                continue
            if t.removeprefix("(O)") == item_id and t.removeprefix("(O)") in self._objects:
                return True
        return False

    @staticmethod
    def _names_tag(tokens: list[str], tags: set[str]) -> bool:
        """CheckTasteContextTags: a token that isn't a number or category and is one of the item's tags."""
        return any(t and not t[0].isdigit() and t[0] != "-" and t in tags for t in tokens)

    def taste(self, villager: str, item_id: str, *, price: int | None = None,
              edibility: int | None = None) -> str:
        """love / like / neutral / dislike / hate. `price`/`edibility` override the data (the save's own item)."""
        item_id = item_id.removeprefix("(O)")
        if item_id == STARDROP_TEA:
            return LOVE  # always loved (the game gives it a taste of its own)
        obj = self._objects.get(item_id)
        if obj is None:
            return NEUTRAL  # not an object: rings, tools, furniture…
        category = str(obj.get("Category") or 0)
        tags = set(obj.get("ContextTags") or ())
        price = int(obj.get("Price") or 0) if price is None else price
        edible = obj.get("Edibility") if edibility is None else edibility
        edible = INEDIBLE if edible is None else int(edible)
        uni = self._universal

        taste = NEUTRAL
        for t in (LOVE, HATE, LIKE, DISLIKE):  # categories (universal lists have no neutral category pass)
            if category in uni[t]:
                taste = t
                break
        for t in (LOVE, HATE, LIKE, DISLIKE):  # context tags override
            if self._names_tag(uni[t], tags):
                taste = t
                break
        named = False
        neutral_named = False
        for t in ORDER:  # specific items override again
            if self._names_item(uni[t], item_id):
                taste, named = t, True
                neutral_named = t == NEUTRAL
                break
        if obj.get("Type") == "Arch":
            taste = LIKE if villager in ("Penny", "Dwarf") else DISLIKE
        if taste == NEUTRAL and not neutral_named:
            if edible != INEDIBLE and edible < 0:
                taste = HATE
            elif price < 20:
                taste = DISLIKE

        own = self.villagers.get(villager)
        if own is None:
            return taste
        for t in ORDER:
            if self._names_item(own[t], item_id):
                return t
        for t in ORDER:
            if self._names_tag(own[t], tags):
                return t
        if not named and category != "0":
            for t in ORDER:
                if category in own[t]:
                    return t
        return taste

    def giftable(self, item_id: str) -> bool:
        """Data/Objects CanBeGivenAsGift (default yes)."""
        obj = self._objects.get(item_id.removeprefix("(O)"))
        return obj is not None and obj.get("CanBeGivenAsGift", True) is not False

    def lists(self, villager: str, *, include_universal: bool = True) -> dict[str, list[str]]:
        """Every object id this villager loves / likes / … (the full resolution, object by object)."""
        out: dict[str, list[str]] = {t: [] for t in ORDER}
        for oid in self._objects:
            out[self.taste(villager, oid)].append(oid)
        return out
