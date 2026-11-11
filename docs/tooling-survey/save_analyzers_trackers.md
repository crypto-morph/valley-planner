# Stardew Valley save analyzers, progress trackers, bundle checklists, layout planners and bots (survey as of Oct 2026)

Method: web search plus the GitHub API (`gh api repos/...`, `gh search repos`) on 2026-10-26. Star counts and "pushed" dates come from the GitHub API on that date. Where a claim rests only on a project's own homepage or README, the note says so.

## Which tools exist, and what each does (save reading, 1.6 support, maintenance, licence, repo, popularity)?

### Takeaway
There are five tools worth taking seriously. Three read the save and track completion: MouseyPounds' Stardew Checkup (with its sibling Predictor), stardew.app, and the newer closed-source stardewvalleyids.com Checkup. The other two are hpeinar's stardew.info farm planner and Thorinair's/exnil's crop calculators. upload.farm is effectively unmaintained: its last news post is from Jan 2021 and it does not support 1.5 or 1.6. Beyond these there is a long tail of 0–10★ hobby bundle checklists and trackers, a few mobile apps, and a growing set of SMAPI-based in-game to-do mods and AI agents. Those mods and agents fall outside a vanilla, no-mod planner.

### Cited Findings

**A. Save-driven progress and completion analyzers**

- **Stardew Checkup (MouseyPounds)**: https://mouseypounds.github.io/stardew-checkup/ · repo https://github.com/MouseyPounds/stardew-checkup · **MIT** · 254★, 51 forks · last push 2024-05-09, last changelog entry v5.0.5 on 18 Apr 2024 (last commit "BigInt hotfix", 2024-04-27) — [GitHub](https://github.com/MouseyPounds/stardew-checkup), GitHub API.
  - What it checks: progress on the achievements, Grandpa's evaluation, Ginger Island upgrades, Perfection, social (friendship, heart events, the Introductions quest), Community Center bundles and the Joja route, the museum (including the Rusty Key counter), Monster Eradication goals, Special Orders, fish caught, cooking and crafting recipes, Secret Note rewards and quests. Results are framed as "what is missing" — [GitHub README](https://github.com/MouseyPounds/stardew-checkup).
  - 1.6: v5.0 (19 Mar 2024) added 1.6 support for "most changed and added content". 1.6 sections appear only when the save is detected as a 1.6 save, and there is a spoiler warning. Output Preferences can hide results but not section titles — [GitHub](https://github.com/MouseyPounds/stardew-checkup); the forum thread says "Fully updated for 1.6" — [Forum, 26 Mar 2024](https://forums.stardewvalley.net/threads/web-apps-stardew-checkup-predictor-and-fair-helper.28393).
  - Save handling: the user opens the save in the browser ("javascript required"). It is a static GitHub Pages app built on jQuery and pako, so parsing is client-side (inferred from the stack; the README does not say so outright) — [Forum](https://forums.stardewvalley.net/threads/web-apps-stardew-checkup-predictor-and-fair-helper.28393).
  - Known 1.6-era bugs from the forum: a `parseBundles` TypeError (unresolved in the thread); a re-opened Community Center not recognised (fix: refresh and reload); crafting showing 100% against 99% in game because of a mod recipe — [Forum](https://forums.stardewvalley.net/threads/web-apps-stardew-checkup-predictor-and-fair-helper.28393).
  - There is a mirror or fork at git.warze.org/Warze/stardew-checkup — [search result](https://git.warze.org/Warze/stardew-checkup/src/branch/master/index.html).
- **Stardew Predictor (MouseyPounds)**: repo https://github.com/MouseyPounds/stardew-predictor · **MIT** · 135★ · last push 2026-01-25 (community PRs: Bookseller days fix in May 2025, a wiki-link fix in Jan 2026), GitHub API. It simulates the game's RNG from the save's seed to "predict the future". 1.6 additions include the enchanting table, prize tickets, mystery boxes and CalicoJack. Users reported some prize-ticket, mystery-box and CalicoJack mismatches in 2024. Listed as "Fully updated for 1.6" — [Forum](https://forums.stardewvalley.net/threads/web-apps-stardew-checkup-predictor-and-fair-helper.28393).
- **Stardew Fair Helper (MouseyPounds)**: repo https://github.com/MouseyPounds/stardew-fair-helper · **MIT** · 25★ · last push 2020-12-28 (GitHub API). It picks a winning Grange display for the Fall Fair. The read-your-save path works with 1.6 saves, but manual entry has not been updated for 1.6 — [Forum](https://forums.stardewvalley.net/threads/web-apps-stardew-checkup-predictor-and-fair-helper.28393).
- **stardew.app ("community center" org)**: https://stardew.app · repo https://github.com/communitycenter/stardew.app (the `stardewapp/stardew.app` URL redirects here) · **MIT** · 213★, 43 forks, 1,150 commits · last push 2026-08-09. Recent commits: "feat: add next site access banner" (2026-08-09), "fix: auto-upload security issue" (2026-08-01), "feat(fishing): add toggle to exclude all-season fish from season filter" (2026-07-31), GitHub API.
  - Features (README table): 100% perfection tracking, "all 1.6 content", achievements, a fish tracker with locations, a shipping tracker with crop info, a villager tracker with gift info, cooking and crafting recipes, museum and artifacts, bundles, Golden Walnuts, Secret Notes, Journal Scraps, cross-platform use, Discord login — [GitHub](https://github.com/communitycenter/stardew.app). The homepage says it supports 1.6 through 1.6.9 — [stardew.app](https://stardew.app/).
  - Stack: Next.js on Cloudflare Workers (OpenNext/Wrangler) with a MySQL database — [GitHub](https://github.com/communitycenter/stardew.app).
  - Save handling: `src/components/dialogs/upload-dialog.tsx` calls `parseSaveFile(saveText)` from `src/lib/file.ts`, which uses `fast-xml-parser` with per-domain parsers for bundles, fishing, museum, shipping, social, perfection, raccoon, rarecrows, scraps, powers and so on. Parsing therefore runs in the browser; the parsed progress is then stored server-side and synced across devices through the Discord login. The storage half is inferred from the MySQL DB and Discord sync — GitHub API source read.
  - Console players can update progress by hand, and hearts are updated by hand. Multiple farmhands and saves are supported — [Forum announcement, 2023](https://forums.stardewvalley.net/threads/stardew-app-an-all-in-one-save-file-processor-perfection-tracker.25316/).
  - A rewrite is in progress: the "next site access banner" commit points to it. A third-party desktop app, **Stardrop Sync** (https://github.com/mooncakes-dev/stardrop-sync, **MIT**, 0★, pushed 2026-10-22), watches the save folder and picks up each new save, but does not upload yet "because the perfection tracker is undergoing a re-write" — [README](https://github.com/mooncakes-dev/stardrop-sync).
- **Stardew Valley IDs: Save File Checkup**: https://stardewvalleyids.com/checkup · **no repo or licence found (closed source)** · author not named. It parses the save in a Web Worker, and the site says "nothing is uploaded". It reports what is left across bundles, shipping, museum, walnuts, friendships, achievements and perfection, and a "Sync to my trackers" button copies progress into the site's own CC, shipping, museum and walnut trackers (additive only). The site says it is built and tested against 1.6; 1.5 saves parse only partially and mod content is ignored. Saves from PC, Mac, Linux and Steam Deck only. The same site has item-ID browsers, a save editor, and guides for gifts, CC, crops, fish, fish ponds, recipes, sprinklers, Green Rain, professions, museum, shipping and walnuts. The page mentions no recommendations or daily plans — [stardewvalleyids.com/checkup](https://stardewvalleyids.com/checkup).
- **upload.farm / SDV-Summary (Sketchy502 et al.)**: https://upload.farm · source https://github.com/Sketchy502/SDV-Summary · **no licence file** · 222★ · last push 2022-12-08 (GitHub API). It is a Flask and PIL server app: the save is **uploaded to the server** (`UPLOAD_FOLDER`), and it renders a farm image plus a player summary, with user accounts and imgur integration — [README](https://github.com/Sketchy502/SDV-Summary). Its newest blog post (12 Jan 2021) says it "does not support anything added in the v1.5 patch". There is nothing about 1.6. Recent uploads were still listed when fetched — [upload.farm](https://upload.farm/). A forum guide notes it was removed as an in-game sharing option on PC but is still the easiest way to get a farm image on mobile — [Forum guide](https://forums.stardewvalley.net/threads/how-to-share-your-farm-and-use-stardew-planner.152).
- **stardew.me (communitycenter)**: https://stardew-me.vercel.app · repo https://github.com/communitycenter/stardew.me · no licence · 16★ · pushed 2025-04-03. It generates a player sprite PNG from a save and credits upload.farm's `crop_image` — [GitHub](https://github.com/communitycenter/stardew.me).
- **Stardew Valley Item Finder (gucci-on-fleek / Max Chernoff)**: https://maxchernoff.ca/tools/Stardew-Valley-Item-Finder/ · repo https://github.com/gucci-on-fleek/Stardew-Valley-Item-Finder · licence NOASSERTION (custom or unclear) · 6★ · pushed 2024-11-16. It analyses the save to find where your items are stored (GitHub API description).
- **iGoodie stardew-save-analyzer**: https://stardew-save-analyzer.onrender.com · repo https://github.com/iGoodie/stardew-save-analyzer · no licence · 8★ · pushed 2025-07-19. The repo describes it as a "Save Analyzer & Tracker"; the README description is literally "TODO" (GitHub API).
- **Stardew Guide & Tracker (iOS and Android app)**: https://apps.apple.com/app/id6748267484 · closed source. It reads multiple save files on iOS and offers manual farm profiles. Its trackers cover farmer info, skills, relationships, perfection, shipping, fish, museum, cooking, crafting, CC bundles, stardrops, walnuts, secret notes and special orders. It added a predictor (weather, garbage-can loot, traveling-cart stock) in Nov 2025, villager map tracking in Nov 2025, a save editor and backup in Jan 2026, an Android release and a crop profit calculator in Apr 2026, and went free with a one-time IAP — [Forum thread](https://forums.stardewvalley.net/threads/stardew-guide-tracker-ios-app.43147/latest).
- A hobby-tier example: **IasminMoreira/stardew-perfection** (MIT, 0★, pushed 2026-08) is an API that reads saves and computes perfection % (GitHub search).

**B. Farm layout planners and viewers**

- **Stardew Planner (hpeinar) / stardew.info**: https://stardew.info/planner/ (v2 at https://v2.stardew.info/planner/, v3 at https://v3.stardew.info/planner/) · repo https://github.com/hpeinar/stardewplanner · **Apache-2.0** · 267★ · last push 2024-03-19. The v3 repo https://github.com/hpeinar/planner_v3 has **no licence**, 26★ and a last push of 2024-07-05 (GitHub API). It is an interactive grid planner for farm layouts that can import a save. V3 has replaced the older planner — [search summary of stardew.info](https://v3.stardew.info/planner/). Open community requests in the README: counts of placed items, image export, more trees and tappers, depth rendering, save exporting — [README](https://github.com/hpeinar/stardewplanner). upload.farm integrated with the stardew.info planner — [upload.farm blog](https://upload.farm/blog?p=2).
- **Stardew Valley Designer (AzimMuradov)**: https://stardewdesigner.com · repo https://github.com/AzimMuradov/stardew-valley-designer · **Apache-2.0** · 21★ · pushed 2024-06-29. A free and open-source farm editor that can save designs as images (GitHub API; [README](https://github.com/AzimMuradov/stardew-valley-designer/blob/master/README.md)).
- **stardewvalleyplanner.art (wsir78933-rgb)**: repo https://github.com/wsir78933-rgb/stardew-planner · licence NOASSERTION · 0★ · pushed 2026-10-26. A bilingual browser farm planner with local storage, save import, layout editing and image export (GitHub search description).
- **stardewplanner.xyz ("Valley Ledger")**: no repo or licence found. It is a small MVP: a 12×8 layout grid, a sample bundle checklist, a gift lookup for 34 villagers and a crop-margin calculator. It states "No save file upload…" and that the calculator shows "arithmetic … not a hidden recommendation". Its data was verified against 1.6.15 on 2026-08-11 — [stardewplanner.xyz](https://stardewplanner.xyz/).

**C. Crop and profit planners (manual input, no save reading)**

- **Stardew Profits (Thorinair)**: https://thorinair.github.io/Stardew-Profits/ · **MIT** · 220★ · pushed 2026-04-15 (GitHub API). A crop profit calculator and visualiser.
- **Crop Planner (exnil)**: repo https://github.com/exnil/crop_planner · **MIT** · 117★ · pushed 2024-03-26 (GitHub API). A season planting calendar.
- **mschult2/stardew-planner**: no licence, 5★, pushed 2025-12-13. A crop planting scheduler built in Blazor WebAssembly (GitHub API).
- **Duct Tape Solutions tools**: crop profit, bundles and gift planner; the bundle checklist tracks by room, season, source and reward with no day scheduling — [duct-tape-solutions.com](https://www.duct-tape-solutions.com/en/tools/games/stardew-valley/).

**D. Bundle and completion checklists (manual, local storage)**

- **Destructive Burn checklists**: https://destructiveburn.com/StardewValley/bundles.html and the completion checklist https://destructiveburn.com/StardewValley/ · no repo found. Progress is saved locally with no login — [search summary](https://destructiveburn.com/StardewValley/bundles.html).
- Other bundle and completion checklists: an interactive Steam guide checklist (https://steamcommunity.com/sharedfiles/filedetails/?id=2855536638) and the mgaud.com CC checklist (https://mgaud.com/stardew-valley-community-center-checklist/) — [search results](https://steamcommunity.com/sharedfiles/filedetails/?id=2855536638).
- GitHub long tail, all ≤3★ (GitHub search, 2026-10-26):
  - TheOddler/stardew-bundles (pabloproductions.be/stardew-bundles), plus a printable variant
  - mrsperry/stardew-trackers
  - anokimoto/stardew_checklist (MIT)
  - SaltHash/stardew-checklist (GPL-3.0)
  - holmera1/stardew-bundle-tracker, a desktop app last pushed 2022
  - Willow-Zero/StardewChecklist ("tells you what materials you still need")
  - Mabi19/stardew-perfection-randomizer (MIT)
  - many personal student projects
- **Online save editors** (adjacent; they also parse saves):
  - colecrouter/stardew-save-editor, https://colecrouter.github.io/stardew-save-editor/ · licence NOASSERTION · 105★ · pushed 2026-10-26 · in-browser editing of character, skills, money, relationships, inventory and recipes — [README](https://github.com/colecrouter/stardew-save-editor)
  - windwild/stardew-save-editor-zh (front-end only, 1.6)

**E. Discord bots**

- **Krobot (Warze)**: https://git.warze.org/Warze/Krobot · licence unknown. A Discord bot or webhook pointed at a local `SAVE_FILE` that posts upcoming events (birthdays, festivals) from the save — [Krobot README](https://git.warze.org/Warze/Krobot/raw/branch/master/README.md).
- No Discord bot doing progress tracking or planning was found — [search](https://git.warze.org/Warze/Krobot).

**F. Mod-based or in-game tools (not vanilla; listed for contrast)**

- **Automatic To-Do List** (Nexus 26008): reminders for birthdays, ready crops and machines, unwatered crops and the traveling cart. Tested on 1.6.8 — [Nexus](https://www.nexusmods.com/stardewvalley/mods/26008).
- **Dynamic Checklist** (Nexus 1145): a daily in-game task list — [Nexus](https://www.nexusmods.com/stardewvalley/mods/1145).
- **SDV Tracker**: a SMAPI mod that sends end-of-day checklist completions to a web tracker account — [Forum resource](https://forums.stardewvalley.net/resources/sdv-tracker.190/).
- **stardew-together** (Zsh123456-BOOP): 190★, no licence, pushed 2026-09-23. A SMAPI and DeepSeek AI agent that runs the farm autonomously or suggests "what can I progress next" (quest, collection and unlock prerequisites) — [README](https://github.com/Zsh123456-BOOP/stardew-together).
- **stardew-mcp** (Hunter-Thompson): 173★, no licence, pushed 2026-02-05. A repo containing `mod/` and `mcp-server/` directories, so it is a SMAPI mod exposing the game to LLMs over MCP (GitHub API directory listing; no README description).
- **Stardew Valley Assistant** (Ayndpa): **MIT**, 65★, pushed 2026-09-14. A Tauri desktop app in Chinese with a mod manager, save editor, farm calendar (festivals, birthdays, daily luck), profit calculator and live villager locations — [README](https://github.com/Ayndpa/stardew-valley-assistant).

### Inferences
- The only actively maintained, open-source, save-driven *completion* trackers with real usage are stardew.app (MIT, mid-rewrite as of Aug 2026) and MouseyPounds' Checkup. Checkup has been frozen since Apr–May 2024, so 1.6.9 and later additions may be missing. That is unverified: there is no changelog entry after 5.0.5.
- MouseyPounds' tools (MIT, client-side JS) and stardew.app (MIT, TypeScript parsers) are the most reusable code: licence-compatible parsers and reference data. Checkup's MIT JS is a good cross-check for bundle and perfection parsing. stardew.app's `src/lib/parsers/*` are modular TypeScript and could be consulted or vendored with attribution.
- For "Valley Planner": link out to stardew.info or Stardew Valley Designer for layouts and to Stardew Predictor for RNG forecasts. Do not compete on perfection checklists, where stardew.app and Checkup are entrenched. Overlap is unavoidable on Bundles, Fish, Villagers gifts and shipping, but those are table stakes.
- upload.farm (server upload, no licence, stuck before 1.5) is a historical reference only.

### Gaps
- Exact traffic or usage numbers for any of these sites: not published.
- Reddit mention counts: Reddit was not reachable through search in this session, so popularity rests on GitHub stars and forum threads.
- stardew.app's privacy policy (whether the raw save, or only parsed results, reaches the server) was not read directly; the client-side parsing comes from source.
- Krobot's licence and maintenance date were not verified.
- stardew.info v3's current 1.6 support and its exact save-import behaviour were not confirmed from primary text.
- The licence status of hpeinar/planner_v3 is "none" (all rights reserved by default).

## Does any tool generate daily recommendations, a dated plan or route to finish the Community Center, or sell/hold advice?

### Takeaway
Among vanilla, save-driven web tools, the claim holds: none produces a dated CC route to a deadline, a "do this today" list verified against the next save, or sell/hold advice. The near-misses are listed below.

### Cited Findings
- A search for day-by-day CC route tools found only bundle trackers (Duct Tape Solutions, Destructive Burn), the stardew.info planner and save editors. "I didn't find a tool that builds a day-by-day Community Center route from a save file" — [search: Duct Tape](https://www.duct-tape-solutions.com/en/tools/games/stardew-valley/), [Destructive Burn](https://destructiveburn.com/StardewValley/bundles.html).
- Checkup reports "what is missing" and makes no recommendations — [GitHub](https://github.com/MouseyPounds/stardew-checkup). stardewvalleyids Checkup is read-only and mentions no next-step guidance — [stardewvalleyids.com](https://stardewvalleyids.com/checkup). stardewplanner.xyz explicitly avoids "hidden recommendation[s]" — [stardewplanner.xyz](https://stardewplanner.xyz/).
- Closest to daily guidance:
  - **Stardew Predictor** forecasts RNG outcomes (cart, mines, geodes, night events and so on), which players use to plan days — [Forum](https://forums.stardewvalley.net/threads/web-apps-stardew-checkup-predictor-and-fair-helper.28393).
  - The **Stardew Guide & Tracker** app's predictor (weather, trash loot, cart stock) is "positioned to help players plan their days" — [Forum](https://forums.stardewvalley.net/threads/stardew-guide-tracker-ios-app.43147/latest).
  - **Krobot** posts upcoming birthdays and festivals from the save to Discord — [Krobot](https://git.warze.org/Warze/Krobot/raw/branch/master/README.md).
  - The **Fair Helper** recommends a Grange display from the save — [Forum](https://forums.stardewvalley.net/threads/web-apps-stardew-checkup-predictor-and-fair-helper.28393).
- Daily to-do lists exist only as **SMAPI mods** (Automatic To-Do List, Dynamic Checklist, SDV Tracker) — [Nexus 26008](https://www.nexusmods.com/stardewvalley/mods/26008), [Nexus 1145](https://www.nexusmods.com/stardewvalley/mods/1145), [SDV Tracker](https://forums.stardewvalley.net/resources/sdv-tracker.190/). LLM "next step" suggestions also exist only as SMAPI agents — [stardew-together](https://github.com/Zsh123456-BOOP/stardew-together).
- Profit and sell maths exists only as manual crop-profit calculators (Stardew Profits, Guide & Tracker's calculator, Duct Tape). None reads your inventory to say ship, process or hold — [Stardew Profits](https://thorinair.github.io/Stardew-Profits/), [Guide & Tracker thread](https://forums.stardewvalley.net/threads/stardew-guide-tracker-ios-app.43147/latest).

### Inferences
- Valley Planner's differentiators look genuinely new for vanilla web tools. They are the dated CC critical path with luck odds and gold pace, save-verified to-dos, and sell/hold advice from inventory. The closest prior art is either mod-based (needs SMAPI) or forecast-only (Predictor).
- Integrating Predictor-style RNG forecasts (cart stock, geode contents, mine floors, night events) into the Morning summary would close the most obvious "planning" gap. Predictor is MIT and its logic can be consulted.

### Gaps
- Small or private tools may exist that this search did not surface, such as Discord servers' private bots or non-English sites (Chinese tools are numerous). Absence is "not found", not proven.
- The iGoodie analyzer's live site was not inspected; its README is empty.

## Which features do these tools have that players praise and that our planner lacks?

### Takeaway
Players value these tools for breadth of completion tracking (perfection, museum, walnuts, secret notes, journal scraps, recipes, achievements), multi-farm and multi-farmhand support with cross-device sync, manual entry for console and mobile players, RNG prediction, and farm images. Valley Planner has none of these today.

### Cited Findings
- Forum users thanked MouseyPounds for updating "so quickly" for 1.6 and for "continuing to support prior versions" — [Forum](https://forums.stardewvalley.net/threads/web-apps-stardew-checkup-predictor-and-fair-helper.28393). Players value fast updates and older-version compatibility.
- The Predictor is used for the enchanting table, prize tickets, mystery boxes and CalicoJack. Users are invested enough to report mismatches — [Forum](https://forums.stardewvalley.net/threads/web-apps-stardew-checkup-predictor-and-fair-helper.28393).
- stardew.app's feature set:
  - Discord login for sync across devices — [Forum](https://forums.stardewvalley.net/threads/stardew-app-an-all-in-one-save-file-processor-perfection-tracker.25316/)
  - multiple farmhands and saves — same forum thread
  - manual updates for console players — same forum thread
  - fish locations, shipping with crop info, Golden Walnuts, Secret Notes, Journal Scraps, museum, achievements and recipes — [GitHub](https://github.com/communitycenter/stardew.app)
  - a fishing toggle that excludes all-season fish from the season filter, added Jul 2026 — GitHub API commit log
- Guide & Tracker users praised syncing multiple farm profiles. The app also offers offline use, dark mode, 12 languages, real-time villager map tracking, and backup and restore — [Forum](https://forums.stardewvalley.net/threads/stardew-guide-tracker-ios-app.43147/latest).
- stardewvalleyids lets the save fill in its trackers while keeping manual ticks ("additive, never removes"), and says plainly "nothing is uploaded" (verifiable in DevTools) — [stardewvalleyids.com](https://stardewvalleyids.com/checkup).
- Requests on the farm planner: placed-item counts, image export, save export — [hpeinar README](https://github.com/hpeinar/stardewplanner). upload.farm's value was a shareable rendered farm image and stats, especially on mobile — [Forum guide](https://forums.stardewvalley.net/threads/how-to-share-your-farm-and-use-stardew-planner.152).
- Spoiler control is a design concern: Checkup warns about spoilers and offers Output Preferences to hide sections — [GitHub](https://github.com/MouseyPounds/stardew-checkup).
- An auto-pickup desktop watcher (Stardrop Sync) is wanted enough that someone is building one, so the player does not have to re-upload every day — [Stardrop Sync](https://github.com/mooncakes-dev/stardrop-sync). stardew.app also has an "auto-upload" feature (commit "fix: auto-upload security issue", 2026-08-01) — GitHub API.

### Inferences
Candidate gaps in Valley Planner, roughly in priority order:
1. Full-perfection coverage: museum, walnuts, secret notes and journal scraps, recipes, achievements, monster goals, special orders. These could link out to stardew.app or Checkup rather than be rebuilt.
2. RNG forecasts in the morning view (Predictor-style cart, geode and night-event predictions).
3. Multiplayer and farmhand selection, and multiple saves.
4. Spoiler toggles.
5. An explicit "nothing leaves your device" privacy statement.
6. Automatic save pickup (a folder watcher), which matches the "reads the save once a day" model.
7. Farm image or render (lower priority; link to stardew.info).
8. Manual-entry fallback for console players (likely out of scope for a save-driven tool).

### Gaps
- Direct Reddit praise quotes could not be gathered (no Reddit results surfaced). Praise evidence is limited to the official forums and READMEs.
- stardew.app's forum thread was not read past the summary; there may be more requests there.
