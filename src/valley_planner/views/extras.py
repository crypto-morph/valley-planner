"""Worth knowing: the Stable, the spa, the next forge enchantment, and animal care, each only when it applies."""

from __future__ import annotations

from ..facts import comforts, forge
from .farm import Farm

DAY_TILES = 600  # a day with a trip to Town and the beach, in tiles walked, roughly
FORGE_KINDS = ("Axe", "Pickaxe", "Hoe", "WateringCan", "FishingRod", "Pan")


def _stable(farm: Farm) -> dict | None:
    if farm.save.buildings.get("Stable"):
        return None
    st = comforts.stable(farm.data)
    saved = comforts.horse_minutes_saved(DAY_TILES)
    mats = ", ".join(f"{n} {farm.name(q if q.startswith('(') else '(O)' + q)}" for q, n in st.materials)
    return {"title": "A Stable",
            "text": f"{st.gold:,}g with {mats}, built in {st.days} days by Robin. Riding is about "
                    f"{comforts.horse_speed_ratio():.1f} times walking speed: around {round(saved / 10) * 10} "
                    f"game minutes saved on a day out to Town and the beach. {comforts.HORSE_ADVICE.split('. ', 1)[1]}"}


def _spa(farm: Farm) -> dict:
    when = "" if comforts.spa_open(farm.save.days_played) else " It opens on Summer 3."
    return {"title": "The spa refills energy for free",
            "text": f"Up the mountain past the Railroad. Stand still in the pool: about "
                    f"{comforts.SPA_ENERGY_PER_MINUTE:.0f} energy a game minute, so an empty bar of "
                    f"{farm.save.max_stamina} takes {comforts.spa_minutes(0, farm.save.max_stamina)} minutes.{when}"}


def _forge(farm: Farm) -> dict | None:
    if farm.save.deepest_mine_level < 120 and "(O)74" not in farm.held():
        return None  # the forge is in the Volcano and needs a Prismatic Shard: nothing to plan yet
    rows = []
    for tool in forge.tools_in_save(farm.save):
        if tool.kind not in FORGE_KINDS:
            continue
        nxt = forge.next_enchantments(farm.save, farm.data, tool, count=1)
        if nxt and nxt[0].enchantment:
            rows.append(f"{tool.name or tool.kind}: {nxt[0].enchantment}")
    if not rows:
        return None
    return {"title": "Your next forge enchantment",
            "text": "A Prismatic Shard and 20 Cinder Shards at the Volcano forge gives: " + "; ".join(rows)
                    + ". Each enchant changes the next, so this is for the next one only."}


def _animals(farm: Farm) -> list[dict]:
    kinds = {a["type"] for a in farm.save.animals}
    out = []
    if kinds:
        out.append({"title": "Heaters", "text": comforts.HEATER_ADVICE})
    if any("Pig" in k for k in kinds):
        out.append({"title": "Truffles", "text": comforts.TRUFFLE_ADVICE})
    return out


def view(farm: Farm) -> list[dict]:
    return [x for x in (_stable(farm), _spa(farm), _forge(farm)) if x] + _animals(farm)
