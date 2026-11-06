# Paths: goals you combine

The route started as "the Community Center by the end of Year 1". This is where it's going: each goal in the game
is its own ordered path, and the player combines them with options and priorities. There's no separate "maximum"
mode. Maximum is these paths plus a daily route that takes every extra it can fit in.

Planning runs to the end of Year 3. After that the player doesn't need the hand-holding.

## Decisions

- **No seed picking.** The player plays whatever seed they're dealt, and the planner uses everything that seed can
  tell it.
- **Each day is a timed route** with walking, fitted to the 6am to 2am clock, and the lowest-value extras drop first.
- **Goals are modules.** One file per goal in `engine/route/objectives/`, plus a line in `ORDER`. The Router doesn't
  change.
- **Goals can depend on goals.** A goal lists what must come first (`needs=`). Choosing it brings those in ahead of
  it, at its tier and within its deadline. If one can't be done in time, the goal says so.
- **The Mines run on a weekly target**, 10 floors by default, one trip a week, moved towards the pace the save shows
  (`engine/route/pace.py`).
- **The cart is a dated option, not luck.** With a real seed, every visit selling an item competes with the long
  way on gold (a Truffle at the cart beats a Barn and a pig). A visit you can't afford falls back to the next-best
  way, and one you've missed drops out when the plan is rebuilt from the next morning's save.
- **Travel is part of the plan**: minecarts and warp totems (`facts/travel.py`), with the horse, bus and boat to
  come. Totems are spent, so using one costs something and has to earn it.

## The interface

Five places, each answering one question, with Find on every screen: Today (what do I do now?), Farm (what do I grow,
sell and cook?), People (who do I see, and what do I give?), Goals (am I on track?), Ahead (what's coming up?). Each
opens with its answer in a sentence and has one main action. Green means fine, amber needs care, red will be missed,
blue is a forecast. Fonts stay local: the planner sends nothing off the computer. `static/ui.css` holds the look;
`styles.css` and `app.css` still style the route tree and tables.

`views/pack.py` turns the day's stops into a pack list, starting from the morning's backpack and its size: what to
leave, what to take for each stop, and what goes in the bin.

## Layout

| Where | What |
|---|---|
| `engine/route/objectives/` | One module per goal: what it needs, how it's planned, how to tell it's done |
| `engine/route/model.py` | Settings, requirements, steps and outcomes |
| `engine/route/plan.py` | Placing steps against cash, days, Robin and Clint |
| `engine/route/pace.py` | The Mines pace |
| `engine/route/present.py` | The tree and agenda the page shows |
| `facts/` | What's true in the game, checked against it (`garbage.py`, `travel.py`…) |

## Goals

In the planner now: the greenhouse, Seed Maker, kitchen, Community Center, horse, sprinklers, house upgrades,
marriage, Mr. Qi's notes, Deluxe Barn and Coop, Silo, Steel tools, the bottom of the Mines, the bus, the Skull
Cavern, Preserves Jars, Kegs.

To add, largely Year 2 and 3. Their steps still need checking against the game:

- Joja: the alternative to the Community Center. Choosing one rules out the other.
- Max a skill, each of the five, and the Masteries.
- The Galaxy Sword.
- Ginger Island: the boat, the walnuts, the Qi rooms, the island farm.
- Mr. Qi's challenges.
- The museum, Stardrops, Monster Eradication goals.
- Fishing, cooking and crafting collections.
- The Obelisks and the Golden Clock.

## The daily extras

Each one is a fact plus a value per minute, so the route can compare them.

| Extra | What can be known |
|---|---|
| Garbage cans | Exact today; odds on other days (`facts/garbage.py`) |
| Traveling Cart | Exact on any day (`facts/cart.py`) |
| Artifact spot digs | Seeded by day and tile; to build |
| Nightly farm events | Seeded by day; to build |
| Spring Onions, Salmonberries, Blackberries | Rules known; to surface in the day |
| Daily forage | Seeded by day, but shaped by what's on the map; to investigate |
| Geodes | Seeded by count and the farmer's id, so known once the save exists; to build |
| Help Wanted, special orders | The board is in the planner; to rank by value |
| Backpack room | The 12-slot pack fills on day one and the starter gift box is gone once opened, so the first 50 Wood goes on a Chest before the forage round. Leave 3 free slots before fishing: treasure needs room, and anything dropped while standing on a pier goes into the water; to plan |
| Fruit bats, day's luck | Unknowable ahead: rolled with the step count |

## The day plan

`views/today.py` gives a timed list limited by the clock, energy and what can be reached, with directions in words.
Read it and play, or press Recalculate with the time, energy and place you're at. It works from the morning save, so
tick what's done. The person you're courting is a timed stop, and spare energy becomes a suggestion for fishing or chopping. Recalculating with a time and ticked stops teaches it your walking pace. Bubbles and geodes are forecast. Still to come: cooking, and a better income model for the Community Center's Vault.

## Build order

1. Done: goals as modules, goal dependencies, Mines pace, travel facts.
2. Done: the day plan, walkable routes, Recalculate, learned walking pace, and forecasts for bins, the board,
   bubbles and geodes. All were checked against a real game, Spring 1 to 14 of one farm.
3. Next, from that play test:
   - Plan the watering load: 100+ dry tiles cost more than a day's energy, so it needs food and sprinklers.
   - Bundle reward stops, such as using Speed-Gro from Spring Crops on young crops.
   - Birthdays as stops, and fishing as a timed stop with a place.
   - A small map for bubble spots: "the lake" misled in play, because a tile can be in a river arm.
   - Income the route doesn't count yet, so the Vault estimate stops being too low.
4. The plan past Year 1: `Farmsim` and `Router` stop at the end of the save's year, and Clint's prices, `WEEKS` and
   default deadlines all assume one year.
5. New goals, Joja first since it tests either/or choices.
6. Ginger Island, then moving the Community Center's bundle logic out of the Router.
