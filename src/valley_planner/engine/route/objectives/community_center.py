"""The Community Center, and the greenhouse its Pantry repairs."""

from __future__ import annotations

from ....facts.bundles import VAULT
from ..model import VAULT_STEP, Req
from .base import objective


def _complete(r) -> bool:
    areas = r.farm.save.areas_complete
    return bool(areas) and all(areas)


@objective("greenhouse", "The greenhouse", 84, done=lambda r: "ccPantry" in r.farm.save.mail)
def greenhouse(r):
    return r.bundle_reqs({"Pantry"}), 0, []


@objective("cc", "The Community Center", 112, done=_complete)
def community_center(r):
    vault = sum(b.gold or 0 for b in r.farm.bundles.in_area(VAULT) if not b.done)
    if vault and r.vault_day is not None:  # another goal already pays it
        return r.bundle_reqs() + [Req(VAULT_STEP, r.vault_day, r.end, [], 0)], 0, []
    return r.bundle_reqs(), vault, []
