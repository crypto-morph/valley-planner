# SMAPI mods that overlap with a save-driven planner

Method note: popularity figures (Nexus "downloads" and "endorsements") were pulled on 2026-10-26 from the public Nexus Mods v2 GraphQL API (`legacyModsByDomain`, field `downloads`). The API does not say whether `downloads` means unique or total downloads, so treat the numbers as relative. Compatibility status comes from the SMAPI update-check API (`POST https://smapi.io/api/v3.0/mods`, game version 1.6.15), which serves the SMAPI compatibility list data. Licences and last-push dates come from the GitHub API (`gh api repos/<repo>`). Nexus HTML pages returned HTTP 403 to the fetcher. The smapi.io/mods page warns that the list "is no longer comprehensively updated each month, and its future is in doubt" ([smapi.io/mods](https://smapi.io/mods)), so read a status of "Ok" as "last known good".

## Which mods overlap, and what is their 1.6 status, popularity, licence and maintenance?

### Takeaway
The info mods with the most players on 1.6 are NPC Map Locations (about 14.6M downloads), Lookup Anything (about 10.0M), CJB Show Item Sell Price (about 2.7M), UI Info Suite 2 (about 2.7M), Gift Taste Helper (about 2.4M, superseded by "Continued x2" at about 1.0M) and Chests Anywhere/Automate (about 4.4M/7.4M). Most are MIT-licensed and were updated in 2025–2026. Planning and to-do mods get one to two orders of magnitude fewer downloads: To-Dew has about 1.08M, Deluxe Journal about 177K and everything else is under 130K. That suggests players treat "information" as essential and "planning" as niche, at least in-game.

### Cited Findings

**Core information mods (all SMAPI status "Ok, use latest version" unless noted)**

| Mod (Nexus id) | Author | Nexus downloads / endorsements | Latest version, Nexus updated | Repo, licence, last push |
|---|---|---|---|---|
| Lookup Anything (541) | Pathoschild | 10,014,919 / 203,613 | 1.55.0, 2026-03-15 | Pathoschild/StardewMods, MIT, 2026-05-10 |
| NPC Map Locations (239) | Bouhm | 14,560,737 / 343,950 | 3.5.2, 2026-04-25 | Bouhm/stardew-valley-mods, MIT, 2026-04-25 |
| UI Info Suite 2 (7098) | Annosz / Abs0rbed | 2,724,477 / 49,813 | 2.3.7, 2024-11-12 | Annosz/UiInfoSuite2, **no repo licence detected** (only an asset licence file), last push 2024-11-12 |
| CJB Show Item Sell Price (5) | Pathoschild / CJBok | 2,674,353 / 70,121 | 1.11.0, 2026-04-20 | CJBok/SDV-Mods, MIT, 2026-05-02 |
| Gift Taste Helper (229) | tstaples | 2,427,917 / 90,052 | 2.9.1, 2019-03-24 | tstaples/GiftTasteHelper, GPL-3.0; SMAPI: "Workaround, use Gift Taste Helper Continued x2 instead" |
| Gift Taste Helper Continued x2 (21001) | JoXW | 1,029,651 / 19,026 | 1.2.5, 2025-02-15 | repo unknown (JoXW/GiftTasteHelper 404); not in SMAPI list metadata |
| Data Layers (1691) | Pathoschild | 439,785 / 9,919 | 1.23.0, 2026-03-15 | Pathoschild/StardewMods, MIT |
| Fishing Info Overlays (8970) | barteke22 | 350,651 / 8,234 | 1.3.2, 2025-11-14 | barteke22/StardewMods, MIT, 2025-11-14 |
| Automate (1063) | Pathoschild | 7,423,336 / 140,291 | 2.6.1, 2026-03-15 | Pathoschild/StardewMods, MIT |
| Chests Anywhere (518) | Pathoschild | 4,403,582 / 85,716 | 1.30.1, 2026-03-15 | Pathoschild/StardewMods, MIT |
| Better Crafting (11115) | KhloeLeclair | 1,738,594 / 17,700 | 2.18.0, 2025-03-26 | KhloeLeclair/StardewMods, **"All rights reserved"** (NOASSERTION on GitHub) |
| Community Bundle Item Tooltip (1329) | musbah | 64,513 / 2,347 | 1.4.2, 2024-09-02 | musbah/StardewValleyMods, no licence detected |
| Show Birthdays (7495) | Traktori | 814,538 / 18,754 | 1.3.0, 2022-05-10 | Traktori7/StardewValleyMods, MIT; SMAPI: **"Unofficial", broken, use unofficial 1.3.1-unofficial.2** |
| Simple Crop Label (314) | TheMusketeer | 854,088 / 26,626 | 6.0.2, 2024-10-14 | not in SMAPI list metadata; repo unknown |
| Add Berry Seasons to Calendar (10477) | inmognito | 526,989 / 4,193 | 1.1.0, 2022-04-06 | unknown; not updated since 2022 (likely a Content Patcher pack, unverified) |
| Calendar Crops (10586) | IanAkari | 55,808 / 1,384 | 2.0, 2022-01-12 | unknown; not updated for 1.6 by date |
| Harvest Calendar (25103) | LonerAxl | 16,690 / 344 | 1.2.1, 2024-08-18 | LonerAxl/Stardew_HarvestCalendar, MIT |
| Predict Reaction To Gift (28556) | YunHikari | 154,997 / 1,773 | 1.0.5, 2024-11-05 | repo unknown |

Sources: [Lookup Anything](https://www.nexusmods.com/stardewvalley/mods/541), [NPC Map Locations](https://www.nexusmods.com/stardewvalley/mods/239), [UI Info Suite 2](https://www.nexusmods.com/stardewvalley/mods/7098), [CJB Show Item Sell Price](https://www.nexusmods.com/stardewvalley/mods/5), [Gift Taste Helper](https://www.nexusmods.com/stardewvalley/mods/229), [Gift Taste Helper Continued x2](https://www.nexusmods.com/stardewvalley/mods/21001), [Data Layers](https://www.nexusmods.com/stardewvalley/mods/1691), [Fishing Info Overlays](https://www.nexusmods.com/stardewvalley/mods/8970), [Automate](https://www.nexusmods.com/stardewvalley/mods/1063), [Chests Anywhere](https://www.nexusmods.com/stardewvalley/mods/518), [Better Crafting](https://www.nexusmods.com/stardewvalley/mods/11115), [Community Bundle Item Tooltip](https://www.nexusmods.com/stardewvalley/mods/1329), [Show Birthdays](https://www.nexusmods.com/stardewvalley/mods/7495), [Simple Crop Label](https://www.nexusmods.com/stardewvalley/mods/314), [Add Berry Seasons to Calendar](https://www.nexusmods.com/stardewvalley/mods/10477), [Calendar Crops](https://www.nexusmods.com/stardewvalley/mods/10586), [Harvest Calendar](https://www.nexusmods.com/stardewvalley/mods/25103), [Predict Reaction To Gift](https://www.nexusmods.com/stardewvalley/mods/28556) (figures via the Nexus GraphQL API); compatibility via the [SMAPI API](https://smapi.io/mods); licences via GitHub ([Pathoschild/StardewMods](https://github.com/Pathoschild/StardewMods), [Bouhm](https://github.com/Bouhm/stardew-valley-mods), [UiInfoSuite2](https://github.com/Annosz/UiInfoSuite2), [CJBok/SDV-Mods](https://github.com/CJBok/SDV-Mods), [tstaples/GiftTasteHelper](https://github.com/tstaples/GiftTasteHelper), [barteke22/StardewMods](https://github.com/barteke22/StardewMods), [KhloeLeclair/StardewMods](https://github.com/KhloeLeclair/StardewMods), [musbah](https://github.com/musbah/StardewValleyMods), [Traktori7](https://github.com/Traktori7/StardewValleyMods), [LonerAxl](https://github.com/LonerAxl/Stardew_HarvestCalendar)).

**Luck and weather displays**

| Mod (Nexus id) | Downloads / endorsements | Version, updated | Notes |
|---|---|---|---|
| Forecaster Texts: TV Weather, Luck and Calendar reminders (7541) | 99,074 / 2,652 | 1.4.0, 2026-03-16 | Sends a chat message each morning with weather, daily luck and Queen of Sauce. Repo GStefanowich/SDV-Forecaster, MIT. SMAPI Ok |
| Daily Luck on HUD (JustLuckMod) (10386) | 33,753 / 1,212 | 1.2.1, 2026-01-18 | "See your exact luck score every day" |
| Daily Luck and Weather Predictions (6783) | 9,063 / 322 | 4.0.1, 2025-04-15 | Shows what RNG outcomes (daily luck, dish of the day and so on) will be "if the player was to sleep with the current step count" |
| Luck Skill (521) | 392,349 / 9,627 | 1.2.6, 2024-04-02 | SMAPI: Workaround, use Spacecore Luck Skill (28103, 133,681 downloads, updated 2026-06-13) |

Sources: [Forecaster Texts](https://www.nexusmods.com/stardewvalley/mods/7541), [JustLuckMod](https://www.nexusmods.com/stardewvalley/mods/10386), [Daily Luck and Weather Predictions](https://www.nexusmods.com/stardewvalley/mods/6783), [Luck Skill](https://www.nexusmods.com/stardewvalley/mods/521), [Spacecore Luck Skill](https://www.nexusmods.com/stardewvalley/mods/28103), [GStefanowich/SDV-Forecaster](https://github.com/GStefanowich/SDV-Forecaster).

**Planning, to-do and progress mods** (details in the planning-features question below)

| Mod (Nexus id) | Downloads / endorsements | Version, updated | Repo, licence | 1.6 status |
|---|---|---|---|---|
| To-Dew (7409) | 1,083,177 / 16,437 | 2.6.3, 2026-08-23 | jltaylor-us/StardewToDew, BSD-3-Clause | SMAPI Ok; README: "Requires Stardew Valley 1.6 / SMAPI 4.0 beginning with version 2.0" |
| Deluxe Journal (11436) | 176,723 / 2,090 | 1.4.0, 2024-11-29 | MolsonCAD/DeluxeJournal, MIT | SMAPI Ok; requires 1.6 / SMAPI 4.0 |
| Deluxe Journal Continued (43805) | 127,139 / 214 | 1.5.0, 2026-10-15 | kauf0/DeluxeJournal, MIT | community fork with bug fixes; not in SMAPI list metadata |
| Almanac (11022) | 84,096 / 2,382 | 0.18.1, 2022-11-14 | KhloeLeclair/StardewMods, all rights reserved | **SMAPI: Broken, "not updated yet"** |
| Automatic To-Do List (26008) | 34,628 / 819 | 1.5.0, 2024-07-31 | paulwrubel/stardew-mods, MIT | SMAPI Ok; tested on 1.6.8 |
| Farmer's Notebook (48121) | 25,495 / 255 | 3.11, 2026-10-13 | repo unknown | built for 1.6 (new in 2025–26) |
| Daily Tasks Report (1624) | 23,071 / 1,173 | 1.4.1, 2019-03-08 | unknown | **not updated for 1.6**; superseded by Plus |
| Daily Tasks Report Plus (20871) | 5,969 / 205 | 1.5.2, 2024-04-01 | "Source Code: Github" (URL not captured) | "Updated for SDV 1.6" |
| Perfection Handbook (45150) | 11,681 / 158 | 1.0.3, 2026-10-21 | Mushymato/PerfectionHandbook, MPL-2.0 | new; requires StardewUI Continued |
| Daily Planner (16704) | 7,659 / 207 | 1.2.1 on Nexus, 2023-06-12 | BuildABuddha/StardewDailyPlanner, no licence detected | SMAPI lists 1.2.2 "Ok" via GitHub, but Nexus has no update since 2023, so the two sources disagree |
| PerfectionStats (41495) | 6,759 / 122 | 1.6.0, 2026-02-25 | unknown | 1.6-era |
| Dynamic Checklist (1145) | 6,560 / 236 | 1.0.1, 2018-03-06 | unknown | **abandoned (2018)** |
| Stardew Dashboard: Live HUD and Info Tracker (43158) | 3,969 / 58 | 2.1.6, 2026-04-23 | unknown | SMAPI Ok |
| Fishing Perfection Helper (36032) | 3,608 / 109 | 1.0.1, 2026-06-29 | unknown | SMAPI Ok |
| Qi's Perfection and Completion Tracker (51900) | 3,525 / 40 | 1.7.15, 2026-10-03 | unknown | 1.6-era |
| Quest Journal (46966) | 3,285 / 82 | 1.7.0, 2026-07-06 | unknown | built on StardewUI |
| Community Center Checklist (51903) | 784 / 10 | 1.2, 2026-09-23 | unknown | new |
| Junimo Checklist: Community Bundle Helper (42904) | 663 / 16 | 1.0, 2026-03-06 | unknown | new |

Sources: [To-Dew](https://www.nexusmods.com/stardewvalley/mods/7409), [StardewToDew repo](https://github.com/jltaylor-us/StardewToDew), [Deluxe Journal](https://www.nexusmods.com/stardewvalley/mods/11436), [DeluxeJournal repo](https://github.com/MolsonCAD/DeluxeJournal), [Deluxe Journal Continued](https://www.nexusmods.com/stardewvalley/mods/43805), [Almanac](https://www.nexusmods.com/stardewvalley/mods/11022), [Automatic To-Do List](https://www.nexusmods.com/stardewvalley/mods/26008), [paulwrubel/stardew-mods](https://github.com/paulwrubel/stardew-mods), [Farmer's Notebook](https://www.nexusmods.com/stardewvalley/mods/48121), [Daily Tasks Report](https://www.nexusmods.com/stardewvalley/mods/1624), [Daily Tasks Report Plus](https://www.nexusmods.com/stardewvalley/mods/20871), [Perfection Handbook](https://www.nexusmods.com/stardewvalley/mods/45150), [PerfectionHandbook repo](https://github.com/Mushymato/PerfectionHandbook), [Daily Planner](https://www.nexusmods.com/stardewvalley/mods/16704), [PerfectionStats](https://www.nexusmods.com/stardewvalley/mods/41495), [Dynamic Checklist](https://www.nexusmods.com/stardewvalley/mods/1145), [Stardew Dashboard](https://www.nexusmods.com/stardewvalley/mods/43158), [Fishing Perfection Helper](https://www.nexusmods.com/stardewvalley/mods/36032), [Qi's Tracker](https://www.nexusmods.com/stardewvalley/mods/51900), [Quest Journal](https://www.nexusmods.com/stardewvalley/mods/46966), [Community Center Checklist](https://www.nexusmods.com/stardewvalley/mods/51903), [Junimo Checklist](https://www.nexusmods.com/stardewvalley/mods/42904).

**Feature sets of the main information mods**
- Lookup Anything: press F1 on anything, or Shift+F1 to search by name. It shows a villager's social data, friendship and liked gifts, highlighting gifts you carry or own. For an item it shows what the item is used for, who likes it as a gift and which recipes use it. For a fish it shows where to catch it and what it produces in a pond. It also covers crop harvest dates, machine readiness and recipes, fruit-tree fruit and quality timers, fence decay, animal happiness and problems, monster drops and eradication-goal progress, mine-node contents, building info and Ginger Island puzzle solutions. An optional "progression mode" hides gift tastes and puzzle solutions until the player discovers them in-game, and a "data mining mode" shows raw game values. README: "compatible with Stardew Valley 1.6+" — [README](https://github.com/Pathoschild/StardewMods/blob/develop/LookupAnything/docs/README.md)
- UI Info Suite 2: daily luck icon, XP gain and bar, more accurate heart levels, item tooltips including items still needed for bundles, calendar and quest billboard from anywhere, icons for animals needing petting or with produce, crop type and days until harvest, sprinkler/scarecrow/beehive/Junimo-hut ranges, NPC locations on the map, a Queen of Sauce icon when the recipe is unknown, Clint's tool upgrade timer, museum-donation and Full Shipment icons, and the next day's weather. Each feature can be toggled — [GitHub](https://github.com/Annosz/UiInfoSuite2); [Nexus](https://www.nexusmods.com/stardewvalley/mods/7098). The Nexus page says it is designed "to help you be aware of what's going on without feeling like you're cheating" — [Nexus](https://www.nexusmods.com/stardewvalley/mods/7098)
- Data Layers: overlays for accessibility, buildable and tillable tiles, bee house, bomb, Junimo hut, scarecrow and sprinkler coverage, crop fertilizer, crop harvest, crop water and paddy water, fishing depth and machines (from the `DataLayers/Layers/*.cs` source tree) — [repo](https://github.com/Pathoschild/StardewMods)
- NPC Map Locations: "See NPC and players on the map with live real-time positioning and an optional minimap"; requires Stardew Valley 1.6.9 or later — [Nexus](https://www.nexusmods.com/stardewvalley/mods/239)
- Fishing Info Overlays: shows the fish available in your current area while you hold a rod or crab pot, plus a preview during the minigame. It "Uses Data\\Fish + Fishing Simulation combo", meaning it repeatedly simulates the game's `getFish` method, which the author says should be "near 100% accurate" — [Nexus](https://www.nexusmods.com/stardewvalley/mods/8970)
- Gift Taste Helper Continued x2: shows a tooltip with an NPC's favourite gifts when you hover over their birthday on the calendar or on the social page — [Nexus](https://www.nexusmods.com/stardewvalley/mods/21001)
- Community Bundle Item Tooltip: adds a tooltip when an item is needed for a community bundle slot that has not been filled — [Nexus](https://www.nexusmods.com/stardewvalley/mods/1329)
- Daily Luck and Weather Predictions: predicts RNG results from the current step count — [Nexus](https://www.nexusmods.com/stardewvalley/mods/6783)

**Popularity context from guides and forums**
- QoL guides and forum threads keep recommending Lookup Anything (crop readiness, machine timers, gift tastes, "what an item can be used for"), UI Info Suite 2 (luck, weather, ranges), Chests Anywhere, Automate and CJB Show Item Sell Price — [Steam discussion](https://steamcommunity.com/app/413150/discussions/0/7204143288003702849); [Gameluster](https://gameluster.com/10-essential-stardew-valley-quality-of-life-mods/); [Stardew forums thread](https://forums.stardewvalley.net/threads/mod-recommendations.1026)
- Destructoid lists Lookup Anything among popular mods updated for 1.6 — [Destructoid](https://destructoid.com/?p=479674)

### Inferences
- Pathoschild's mods (Lookup Anything, Data Layers, Automate, Chests Anywhere, CJB Show Item Sell Price) are actively maintained. All were updated in March to May 2026 and are MIT-licensed, which makes them the safest code to read and cross-check against.
- UI Info Suite 2 has had no release since November 2024 and has no repo licence. Its source is readable, but without a licence it should be treated as all rights reserved. Use it for ideas, not code.
- KhloeLeclair's repo (Better Crafting, Almanac) is explicitly "All rights reserved". Almanac was the closest in-game analogue to a planner (long-term weather forecast and planting calendar) and is marked Broken on 1.6. The gap it leaves is one an out-of-game planner can fill.
- The large download gap between information mods (millions) and planning mods (tens to hundreds of thousands) suggests most players want answers at the point of need, not a separate planning surface. A companion should make lookups fast (as Ask search already does) and keep the to-do short and automatic.

### Gaps
- Nexus did not say whether the `downloads` field is unique or total downloads. Nexus HTML pages were blocked (HTTP 403), so the "unique downloads" figure shown on mod pages could not be confirmed.
- The licence and repo for Gift Taste Helper Continued x2, Farmer's Notebook, Qi's Tracker, Simple Crop Label and Daily Tasks Report Plus were not found.
- Exact Bundle Summary or Ginger Island "walnut helper" mods under those names did not turn up in Nexus name search. Walnut hints appear inside Qi's Tracker and Perfection Handbook, and Lookup Anything covers island puzzles.
- No Reddit threads were retrieved, so player sentiment comes from guides, Steam, the forums and mod descriptions.

## Which features would be worth replicating in an out-of-game planner, and which only make sense in-game?

### Takeaway
Anything computed from the save plus static game data is a good fit for a once-a-day planner. That covers gift tastes and "what is this item for", crop harvest dates, fish availability, tomorrow's weather and today's luck, birthdays, bundle needs, tool-upgrade and machine timers as of the morning, and Ginger Island puzzle and walnut hints. Live-position and live-cursor features fit only in-game: real-time NPC map pins, the fishing minigame preview, coverage overlays drawn on the world, hover tooltips, remote chest access and automation.

### Cited Findings
- Lookup Anything's most-cited uses (gift tastes, crop harvest date, "what an item is used for", where to catch a fish) are all derived from game data and per-save state — [README](https://github.com/Pathoschild/StardewMods/blob/develop/LookupAnything/docs/README.md); [Steam discussion](https://steamcommunity.com/app/413150/discussions/0/7204143288003702849)
- Lookup Anything's "progression mode" hides gift tastes and puzzle solutions until learned in-game, so spoiler control is something players want — [README](https://github.com/Pathoschild/StardewMods/blob/develop/LookupAnything/docs/README.md)
- UI Info Suite 2's once-a-day indicators (daily luck, next day's weather, an unknown Queen of Sauce recipe, Clint's upgrade timer, bundle-needed and museum/shipping-needed item markers) can all be computed at day start — [GitHub](https://github.com/Annosz/UiInfoSuite2)
- Fishing Info Overlays gets its accuracy from simulating `getFish` at the player's current tile while the rod is held, which ties it to live position — [Nexus](https://www.nexusmods.com/stardewvalley/mods/8970)
- NPC Map Locations provides "live real-time positioning" — [Nexus](https://www.nexusmods.com/stardewvalley/mods/239)
- Daily Luck and Weather Predictions depends on the current step count before sleeping, which changes during the day — [Nexus](https://www.nexusmods.com/stardewvalley/mods/6783)
- Farmer's Notebook (1.6, 2025–26) offers almost exactly the planner set: "Today: daily events, weather, luck, birthdays, crops and fishing information"; "Upcoming: the next three days"; a seasonal calendar; a guide to forageables, fish, CC bundles, museum donations and tailoring; goals; tasks; notes; and an automatic journal. It ranks crops into Tier A (multiple harvests possible before season end), Tier B (time-sensitive, plant now) and Tier C (won't mature before season end), and shows birthday gift suggestions with loved, liked and disliked gifts — [Nexus](https://www.nexusmods.com/stardewvalley/mods/48121)
- Qi's Perfection and Completion Tracker offers CC bundle details with acquisition help on hover, museum donation sources (artifact spots, geodes, troves, monster drops), Polyculture and Monoculture shipping counts, and Golden Walnut sources grouped by island area with click-to-reveal clues and solutions. It also has optional "remote bundle donations", which is an in-game-only action — [Nexus](https://www.nexusmods.com/stardewvalley/mods/51900)
- Perfection Handbook has a crop calendar, fruit-tree calendar, fish "where and when" panel, an "Ingredients" page totalling what is needed for remaining recipes, events per NPC and per location, and a HUD of reminders that clear themselves once done — [README](https://github.com/Mushymato/PerfectionHandbook)

### Inferences
Mapping against what the planner already has:

| Mod feature | Out-of-game fit | Planner status / idea |
|---|---|---|
| Item usage, gift tastes, fish locations (Lookup Anything) | High | Already in Ask search. Consider Lookup Anything's touch of highlighting gifts the player owns, from save inventory and chests |
| Spoiler-free "progression mode" | High | New idea: hide gift tastes and walnut or puzzle solutions until the save shows them learned (gift log / `giftsThisWeek` / friendship gift history, if present in the save) |
| Crop days-to-harvest (UIIS2, LA, Harvest Calendar) | High | Already covered by the season countdown and Speed-Gro. Could add Farmer's Notebook-style A/B/C planting tiers |
| Tomorrow's weather and today's luck (UIIS2, Forecaster Text, JustLuck) | High | Both are in the save (`dailyLuck`, `weatherForTomorrow`). A cheap headline for Today if not already shown |
| Queen of Sauce unknown recipe, Traveling Cart, Book Seller days (UIIS2, Automatic To-Do, Farmer's Notebook) | High | Calendar-driven reminders for the Today list |
| Clint upgrade timer and ready machines (UIIS2, Automatic To-Do, DTR Plus) | High at day start | Readable from the save (tool upgrade days left, machine `minutesUntilReady`) |
| Bundle-needed marker on items (UIIS2, Community Bundle Item Tooltip) | High | Already in bundles. Could cross-reference the sell/hold report so bundle items are held, not sold |
| Museum-donation and Full Shipment markers (UIIS2) | High | Add to the sell/hold report: "don't ship the only one, donate it" and "ship one for the collection" |
| Polyculture, Monoculture, perfection checklists (Qi, Perfection Handbook, PerfectionStats) | High | Possible future tab; all derivable from the save |
| Golden Walnut hints with tiered reveal (Qi) | High | Ginger Island helper idea with click-to-reveal, consistent with progression mode |
| End-of-month harvest warning (DTR Plus) | High | Overlaps with the season countdown; make sure it alerts on day 27–28 |
| Unwatered or dead crops, unpetted animals, unbaited crab pots, ready ponds (DTR Plus, Dynamic Checklist) | Partial, as morning state only | Missed-water detection exists. Unpetted/unbaited/ready status at save time can be shown as "yesterday you missed…" |
| Live NPC positions (NPC Map Locations) | Low live, fine as schedule | Schedule-based "where is X today" already exists. Real-time pins are in-game only |
| Fishing minigame preview, current-area fish overlay (FIO) | In-game only | Planner keeps season, weather, time and location rules |
| Coverage overlays: sprinkler, scarecrow, bee (Data Layers, UIIS2) | Low | Possible static farm-map render from the save, but players mostly want it while placing objects in-game |
| Remote chests, automation, bulk crafting (Chests Anywhere, Automate, Better Crafting) | In-game only | Leave to mods. Reading chest contents from the save for "do I own X" is still useful |
| Step-count luck manipulation (Daily Luck and Weather Predictions) | Low for a daily planner | Needs per-step simulation; leave to mods or web predictors |

### Gaps
- It was not checked whether the save stores "gift taste revealed" state in a form progression mode could use. That needs a look at the save schema (another researcher's area).

## Do any mods implement planning or to-do features, and how do players use them?

### Takeaway
Yes, in three styles. **Manual lists** (To-Dew, Daily Planner) are by far the most downloaded. **Auto-generated daily checklists** (Automatic To-Do List, Daily Tasks Report Plus, the abandoned Dynamic Checklist) build the list from game state. **Integrated planners and perfection dashboards** (Farmer's Notebook, Deluxe Journal, Perfection Handbook, Qi's Tracker, CC Checklist) are newer, mostly 2025–26 and still small. None provides a Community Center critical path or a multi-day plan ranked by deadline, which is the planner's strongest point of difference.

### Cited Findings
- To-Dew: a hotkey-opened list (L) shown as a top-left overlay. Items can repeat, with a number of days before they reappear, can be headers, and can be shown only for given weather, days of the week or seasons. The list is stored in the save, can be imported and exported through console commands, and is shared farm-wide in multiplayer — [README](https://github.com/jltaylor-us/StardewToDew). A Steam user describes using it to set reminders on certain days of the week, weeks of the month or seasons — [Steam](https://steamcommunity.com/app/413150/discussions/0/3762229314882036017)
- Deluxe Journal: a tasks page with "Smart Add" that parses task names such as "Collect 300 wood", "Buy 48 pumpkin seeds" and "Upgrade my axe" into auto-completing task types (Collect, Craft, Upgrade Tool, Build, Farm Animal, Buy, Sell). Completed tasks are removed at day end unless they have a renewal period (daily, weekly, monthly, annual or custom). A money box totals the cost or gain of pending tasks. It also has notes and on-screen overlays — [README](https://github.com/MolsonCAD/DeluxeJournal)
- Automatic To-Do List: tasks appear and tick themselves off for villager birthdays (cleared when gifted), harvestable crops, unwatered crops, ready machines, tools ready for pickup, the daily quest board, the Special Orders board, the Traveling Merchant, a new Queen of Sauce recipe and gifting chosen villagers. Each type can be toggled — [Nexus](https://www.nexusmods.com/stardewvalley/mods/26008)
- Daily Tasks Report Plus: a report (key P) covering a new Queen of Sauce recipe, birthdays, the Traveling Merchant, unwatered, ready and dead crops in all locations, unpetted pet and empty water bowl, unpetted animals, animal products, empty hay spots, farm-cave fruit or mushrooms, crab pots ready or unbaited, ready machines, ponds with items or requests, and an end-of-month harvest warning. The author notes animal-product and machine types "are hard coded … only check for items that are part of the non-modded game" — [Nexus](https://www.nexusmods.com/stardewvalley/mods/20871)
- Daily Planner: daily, weekly or one-day tasks on a HUD or in a menu, to "Plan out your entire year" — [Nexus](https://www.nexusmods.com/stardewvalley/mods/16704)
- Farmer's Notebook: Today, Upcoming (next three days), Calendar, Guide, Goals, Tasks (one-time, daily, weekly), Notes, and a Journal that automatically records completed tasks, goals and milestones. Clicking a recommended crop creates a planting task — [Nexus](https://www.nexusmods.com/stardewvalley/mods/48121)
- Community Center Checklist: "An interactive checklist to help you complete the Community Center quest by showing you what's needed, what you have in inventory, and how many you need" — [Nexus](https://www.nexusmods.com/stardewvalley/mods/51903)
- Junimo Checklist: when you hover a needed bundle item, shows the quantity and quality required — [Nexus](https://www.nexusmods.com/stardewvalley/mods/42904)
- Recipe Tracker (22378) tracks crafting recipes, blueprints, bundles and quests — [Nexus](https://www.nexusmods.com/stardewvalley/mods/22378)

### Inferences
- Players use these mods mainly as memory aids for recurring chores (birthdays, the Traveling Cart, Queen of Sauce, machines, watering), for repeating reminders keyed to weather, weekday or season, and for perfection or CC completion lists. Strategic sequencing (what to do first to finish the CC by a target date) does not appear in any mod found.
- Deluxe Journal's money box (the cost of pending buy tasks against current gold) and Smart Add parsing are ideas the planner could borrow. One example: "today's to-do needs 4,800g; you have 3,200g".
- To-Dew's weather and season-conditioned items suggest user-defined rules could layer on top of the generated to-do, for example "on rainy days, fish for catfish".
- Because in-game lists persist in the save (To-Dew) or in mod data, a vanilla planner cannot sync with them. That supports keeping the planner's to-do generated rather than user-edited, or storing user items outside the save.

### Gaps
- No usage statistics or survey data show how players actually use these mods beyond descriptions and one Steam comment.
- No mod with a CC "critical path" or a deadline-ranked plan was found. This is an absence of evidence in Nexus name search and guides, not proof none exists.

## Which open-source mod codebases are good references for game rules, and under what licences?

### Takeaway
The best reference is **Pathoschild/StardewMods (MIT)**. Lookup Anything's `DataParser.cs` and `GameHelper.cs` encode bundles, fish spawn rules, fish-pond gates and drops, friendship, monsters and recipe or machine outputs from 1.6 data. Data Layers encodes sprinkler, scarecrow, bee and Junimo coverage and crop water status, and Automate encodes machine behaviour. Secondary MIT references are Bouhm's NPC Map Locations (schedules and positions), barteke22's Fishing Info Overlays (fish availability through `getFish`), CJBok/SDV-Mods (sell prices), Automatic To-Do List and Deluxe Journal (task detection). Avoid copying code from KhloeLeclair (all rights reserved), UI Info Suite 2 (no licence) and tstaples' Gift Taste Helper (GPL-3.0, copyleft).

### Cited Findings
- Pathoschild/StardewMods: licensed under MIT, 14 active mods including Automate, Chests Anywhere, Content Patcher, Data Layers, Debug Mode and Lookup Anything; about 6,352 commits on `develop`, 957 stars; last push 2026-05-10 — [GitHub](https://github.com/Pathoschild/StardewMods)
- `LookupAnything/DataParser.cs` exposes `GetBundles`, `GetFishPondPopulationGates`, `GetFishPondDrops`, `GetFishSpawnRules(fish)`, `GetFishSpawnRules(location, tile, fishAreaId)`, `GetFriendshipForVillager/Pet/Animal`, `GetLocationDisplayName`, `GetMonsters` and `GetRecipes`. `Framework/Fields/` includes `CharacterGiftTastesField`, `ItemGiftTastesField`, `FishSpawnRulesField`, `ScheduleField`, `MovieTastesField` and `ItemRecipesField`. `Framework/Data/` includes `PuzzleSolutionsData` and `ShopData`. `assets/data.json` holds hand-maintained constants — [source tree](https://github.com/Pathoschild/StardewMods/tree/develop/LookupAnything)
- Lookup Anything warns that monster drops "may add special drops that are hardcoded and can't be detected by mods". The same caveat applies to any planner that reads only data files — [README](https://github.com/Pathoschild/StardewMods/blob/develop/LookupAnything/docs/README.md)
- Data Layers source has `Coverage/{BeeHouse,Bomb,JunimoHut,Scarecrow,Sprinkler}Layer.cs`, `Crops/{CropFertilizer,CropHarvest,CropPaddyWater,CropWater}Layer.cs`, `FishingDepthLayer.cs` and `MachineLayer.cs` — [source tree](https://github.com/Pathoschild/StardewMods/tree/develop/DataLayers)
- Bouhm/stardew-valley-mods (NPC Map Locations), MIT, pushed 2026-04-25 — [GitHub](https://github.com/Bouhm/stardew-valley-mods)
- barteke22/StardewMods (Fishing Info Overlays), MIT. The mod reads Data\\Fish and simulates the vanilla `getFish` method — [GitHub](https://github.com/barteke22/StardewMods); [Nexus](https://www.nexusmods.com/stardewvalley/mods/8970)
- CJBok/SDV-Mods (CJB Show Item Sell Price), MIT — [GitHub](https://github.com/CJBok/SDV-Mods)
- paulwrubel/stardew-mods (Automatic To-Do List), MIT; MolsonCAD/DeluxeJournal, MIT; kauf0/DeluxeJournal fork, MIT; jltaylor-us/StardewToDew, BSD-3-Clause; LonerAxl/Stardew_HarvestCalendar, MIT; GStefanowich/SDV-Forecaster, MIT; Traktori7/StardewValleyMods, MIT; Mushymato/PerfectionHandbook, MPL-2.0 (file-level copyleft) — GitHub API ([paulwrubel](https://github.com/paulwrubel/stardew-mods), [MolsonCAD](https://github.com/MolsonCAD/DeluxeJournal), [kauf0](https://github.com/kauf0/DeluxeJournal), [jltaylor-us](https://github.com/jltaylor-us/StardewToDew), [LonerAxl](https://github.com/LonerAxl/Stardew_HarvestCalendar), [GStefanowich](https://github.com/GStefanowich/SDV-Forecaster), [Traktori7](https://github.com/Traktori7/StardewValleyMods), [Mushymato](https://github.com/Mushymato/PerfectionHandbook))
- tstaples/GiftTasteHelper is GPL-3.0 — [GitHub](https://github.com/tstaples/GiftTasteHelper)
- The KhloeLeclair/StardewMods LICENSE reads "All rights reserved unless otherwise noted". The author explains they dropped MIT because CurseForge used it to redistribute the mods against their wishes — [GitHub](https://github.com/KhloeLeclair/StardewMods)
- Annosz/UiInfoSuite2 has no repository licence file (only `UIInfoSuite2/assets/LevelUp license.txt`). Latest release v2.3.7 on 2024-11-12; 1,761 stars — [GitHub](https://github.com/Annosz/UiInfoSuite2)
- Out-of-game references (not mods, MIT): mouseypounds/stardew-predictor ("Predictions of not very random events", pushed 2026-01-25) and mouseypounds/stardew-checkup ("Checks progress in a Stardew Valley save file", pushed 2024-05-09) — [stardew-predictor](https://github.com/mouseypounds/stardew-predictor); [stardew-checkup](https://github.com/mouseypounds/stardew-checkup)

### Inferences
- For cross-checking the planner's rules: compare fish availability against Lookup Anything's `GetFishSpawnRules`, gift tastes against `ItemGiftTastesField`/`CharacterGiftTastesField` (which resolve universal and per-NPC taste precedence), bundles against `GetBundles` (including remixed bundles), and crop readiness against `CropHarvestLayer` and Lookup Anything's crop subject. Data Layers' `CropWaterLayer` is the closest counterpart to missed-water detection. Automate's machine handling and `GetRecipes` cover the "run it through a machine first" logic in the sell report.
- MIT code can be read and ported with attribution: keep the copyright notice with any copied snippet. GPL-3.0 and MPL-2.0 code would bring copyleft obligations if copied, and all-rights-reserved or unlicensed repos should be read for ideas only.
- These mods run inside the game with SMAPI, so their logic calls the game's own methods (for example `getFish` and `Game1` state) instead of re-implementing them. Porting to a save-reading planner means re-implementing what those calls do, so mod code shows which game method to mirror more than it gives drop-in logic.

### Gaps
- Lookup Anything's `GameHelper.cs` and the Automate machine code were not read line by line. Specific rule details (for example the exact fish spawn weighting) still need checking in the source.
- The repo URL for Daily Tasks Report Plus (the source of its "hard coded" vanilla machine and animal lists) was not captured.
- 1.6 compatibility of stardew-predictor and stardew-checkup was not verified here (the latest push dates suggest predictor is maintained). The save-analyzer research notes may cover this.
