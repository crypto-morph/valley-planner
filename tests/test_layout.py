"""The Sprinkler pattern, level dates and what Wood costs you."""

from types import SimpleNamespace as NS

import pytest

from valley_planner.facts import layout
from valley_planner.facts.skills import harvest_xp, level_of
from valley_planner.views import today


def block(w, h):
    return {(x, y) for x in range(w) for y in range(h)}


def watered(plan):
    out = {}
    for x, y in plan.sprinklers:
        for dx, dy in layout.CROSS:
            t = (x + dx, y + dy)
            if t in plan.crops:
                out[t] = out.get(t, 0) + 1
    return out


def test_each_crop_is_watered_once_and_no_sprinkler_wets_another():
    plan = layout.plan(block(20, 20), {}, 120, lambda t: True)
    wet = watered(plan)
    assert set(wet) == plan.crops and set(wet.values()) == {1}
    assert not plan.crops & set(plan.sprinklers)


def test_four_crops_a_sprinkler_inside_a_big_field():
    plan = layout.plan(block(30, 30), {}, 80, lambda t: True)
    assert len(plan.sprinklers) <= 21 and len(plan.crops) >= 80


def test_nothing_is_planned_on_a_tile_that_is_taken():
    objects = {(5, 5): "Scarecrow", (6, 5): "a tree"}
    plan = layout.plan(block(12, 12), objects, 40, lambda t: True)
    assert not ({*plan.sprinklers, *plan.crops} & set(objects))


def test_the_quality_swap_leaves_nothing_dry():
    plan = layout.plan(block(20, 20), {}, 120, lambda t: True)
    wet = {(x + dx, y + dy) for x, y in plan.quality for dx, dy in layout.RING}
    wet |= {(x + dx, y + dy) for x, y in plan.keep for dx, dy in layout.CROSS}
    assert plan.crops <= wet
    assert len(plan.quality) + len(plan.keep) < len(plan.sprinklers)


def test_a_second_scarecrow_goes_where_the_crops_are_bare():
    crops = {(x, 0) for x in range(30)}
    assert layout.unguarded(crops, [(0, 0)]) == {(x, 0) for x in range(9, 30)}
    assert layout.next_scarecrow(crops, [(0, 0)])[0] >= 9
    assert layout.next_scarecrow({(1, 0)}, [(0, 0)]) is None


def test_harvest_xp_and_levels():
    assert harvest_xp(35) == 8  # a Parsnip
    assert level_of(3299) == 5 and level_of(3300) == 6


def wood_farm(held=0, year=1, bridge=False, house=0):
    return NS(save=NS(year=year, house_upgrade=house, flags={"beachBridgeFixed"} if bridge else set(),
                      tool_levels={}, skills={}),
              bundles=NS(all=[NS(open_ingredients=[NS(item="(O)388", stack=99)])]),
              held=lambda: {"(O)388": held})


def test_wood_counts_the_big_jobs():
    assert today.wood_wanted(wood_farm()) == 99 + 300 + 450
    assert today.wood_wanted(wood_farm(bridge=True, house=1)) == 99


def test_with_energy_chop_and_replant():
    note = today.wood_note(wood_farm(held=800), 5)
    assert "chop your 5" in note["text"] and "replant a seed" in note["text"] and "Robin" not in note["text"]
    assert note["lazy"] == "wood"  # opening it lists what your goals use Wood for


def test_short_of_trees_robin_has_the_rest():
    assert "That leaves" in today.wood_note(wood_farm(), 5)["why"]


@pytest.mark.parametrize(("year", "price"), [(1, 10), (2, 50)])
def test_no_energy_means_robin_at_the_going_price(year, price):
    note = today.wood_note(wood_farm(year=year), 0)
    assert f"from Robin at {price}g" in note["text"] and f"{price}g each" in note["why"]


def test_enough_wood_says_nothing():
    assert today.wood_note(wood_farm(held=900), 5) is None


def _wood_plan_farm(held, today=26):
    return NS(save=NS(year=1, days_played=today, tool_levels={}, skills={}), held=lambda: {"(O)388": held},
              label=lambda d: f"Day {d}, Year 1")


USES = [{"what": "build a Coop", "wood": 300, "on": 29, "by": "", "goal": "CC"},
        {"what": "build a Big Coop", "wood": 400, "on": 51, "by": "", "goal": "CC"}]


def test_wood_names_only_the_next_job_and_its_date():
    note = today.wood_plan(_wood_plan_farm(124), USES)
    assert note["text"].startswith("Wood: 176 more for a Coop (Day 29, in 3 days)") and note["level"] == "soon"
    assert [r["total"] for r in note["rows"]] == [300, 700]


def test_wood_stays_calm_until_a_week_before():
    later = today.wood_plan(_wood_plan_farm(124, today=10), USES)
    assert later["level"] == "later" and "plenty of time" in later["text"]
    covered = today.wood_plan(_wood_plan_farm(350), USES)  # the Coop is covered: the Big Coop is next
    assert "a Big Coop (Day 51, in 25 days). You're 350 short" in covered["text"] and covered["level"] == "later"
    assert today.wood_plan(_wood_plan_farm(700), USES) is None
