# Stardew Valley 1.6: game data, save parsers and licensing norms

Researched 2026-10-26. These notes report what the policies and norms say. They are not legal advice. The official wiki (stardewvalleywiki.com, mirrored at wiki.stardewvalley.net) blocked direct fetches with a Cloudflare challenge and a 503, so the wiki's statements below come from search-result snippets of those pages, not from full-page reads. GitHub metadata comes from `gh api` on the research date.

## Game-data extraction tools a user can run on their own install

### Takeaway
StardewXnbHack (MIT, by Pathoschild, the SMAPI author) is the tool the community recommends for 1.6. The user runs it inside their own game folder, and it writes every `Data/*` asset as Content Patcher-compatible JSON. xnbcli (LeonBlade, JavaScript) is older and cannot unpack the data-model assets that 1.6 relies on.

### Cited Findings
- **StardewXnbHack.** MIT licence. It is a one-way unpacker: you unzip it into the Stardew Valley folder next to `Stardew Valley.dll` and run it, and it unpacks `Content` into `Content (unpacked)`. It needs Stardew Valley and SMAPI installed. It "reads files through a temporary game instance, unlike other unpackers which read them directly." Data comes out as `.json`, images as `.png`, maps as `.tmx`/`.tbin`. It "supports every Stardew Valley asset type." — [GitHub: Pathoschild/StardewXnbHack](https://github.com/Pathoschild/StardewXnbHack)
- StardewXnbHack's latest release is 1.1.2, published 2024-11-06, and the repo was last pushed the same day. The release notes list a March 2024 update for SDV 1.6 and an April 2024 update for SMAPI 4.0.6. — `gh api repos/Pathoschild/StardewXnbHack/releases/latest`; [release notes](https://github.com/Pathoschild/StardewXnbHack/blob/develop/release-notes.md)
- Setup pitfall: the executable must sit in the same folder as the game executable. — [Stardew forums: Trouble Unpacking XNB files](https://forums.stardewvalley.net/threads/trouble-unpacking-xnb-files.30080/latest)
- **xnbcli.** A JavaScript/Node CLI that packs and unpacks, "purpose built for Stardew Valley." Its latest release is v1.0.7 from 2021-01-25. The GitHub licence field says GPL-3.0 but the README says "GNU LGPL v3.0", so the licence is unclear. The repo was last pushed 2025-05-12. — [GitHub: LeonBlade/xnbcli](https://github.com/LeonBlade/xnbcli)
- The official wiki's Modding:Editing XNB files page (snippets) says xnbcli "can't handle some files specific to Stardew Valley. StardewXnbHack is recommended instead," and that it "can't unpack XNB files containing data models (like Data\FishPondData or Data\Movies); use StardewXnbHack if you need those." — [Wiki: Modding:Editing XNB files](https://stardewvalleywiki.com/Modding:Editing_XNB_files)
- **SMAPI** is licensed LGPL-3.0. Its latest release is 4.5.2 (2026-03-22) and the repo is actively pushed (2026-09-28). Its `SMAPI.Toolkit` has JSON serialization helpers aimed at mod manifests (`src/SMAPI.Toolkit/Serialization/*`). I found no general save-file reader in the Toolkit. — [GitHub: Pathoschild/SMAPI](https://github.com/Pathoschild/SMAPI); repo tree via `gh api`
- **Proof the pattern works in production.** stardew.app's data pipeline expects the user or maintainer to drop the game's unpacked `Data/` JSON (from StardewXnbHack) into `scripts/content/`. Python scripts (`fish.py`, `villagers.py`, `crops`…) then build derived JSON that is committed to `src/data/*.json`. The `fish.py` header says its logic is "ported from the game's source code" and that it also scrapes wiki pages. — [GitHub: communitycenter/stardew.app scripts/content/README.md](https://github.com/communitycenter/stardew.app/tree/main/scripts/content); [scripts/fish.py](https://github.com/communitycenter/stardew.app/blob/main/scripts/fish.py)

### Inferences
- For a vanilla planner, the clean route is to tell the user to run StardewXnbHack once per game patch against their own install and point the planner at `Content (unpacked)/Data`. The repo then never holds game files. StardewXnbHack needs SMAPI installed only for the extraction step, not at play time, which fits a "no mods at play time" design, though it is a one-off dependency worth stating.
- XNB readers in Python, Rust or C# outside the SMAPI ecosystem don't look maintained for 1.6 data models. I found none that matter, which is itself a finding: everyone funnels through StardewXnbHack.

### Gaps
- I couldn't confirm whether a newer StardewXnbHack release exists for 1.6.15+ or a 1.7 beta. The latest tagged release is November 2024.
- I didn't find a standalone, maintained XNB-to-JSON reader for 1.6 data models in Python or Rust.

## Existing open data sets (1.6 JSON) and how they handle game files

### Takeaway
Most open projects publish *derived* JSON (curated fields, ids and numbers) under MIT, with the raw extraction step kept out of the repo. Some go further and bundle sprites or verbatim wiki text, and justify it by "fair use" or third-party licence notices. A few repos openly redistribute raw assets or decompiled code, and those are where the only known takedowns happened.

### Cited Findings
- **stardew.app** (communitycenter). MIT, 213 stars, last pushed 2026-08-09, claims "All 1.6 content." It commits derived JSON (`src/data/achievements.json`, `fish.json`, `bundles.json`, etc.) and a small number of `.png` files (12 in the tree). — [GitHub: communitycenter/stardew.app](https://github.com/communitycenter/stardew.app); tree via `gh api`
- **stardew-valley-data** (npm, chiefpansancolt). MIT, last pushed 2026-10-17, 5 stars. It covers items, crops, fish, 34 villagers with gifts and schedules, universal gift preferences, events, quests, shops, monsters and recipes, and includes a `parseSaveFile(xml)` save parser. The README names no game version and no data source. The repo bundles many game sprites under `images/` (achievements, animals…) with no copyright notice for them. — [GitHub: chiefpansancolt/stardew-valley-data](https://github.com/chiefpansancolt/stardew-valley-data)
- **Stardew Save Editor** (colecrouter). Its `LICENSE.md` is MIT-style plus a clarification: the licence excludes "any copyrighted assets and materials from *Stardew Valley* used under fair use provisions," and lists third-party data. `src/lib/wiki/villagers.json` is credited as "© Stardew Valley Wiki contributors, licensed under CC BY-NC-SA 3.0," and `src/lib/wiki/events.json` as "© Stardew Modding Wiki contributors, licensed under CC BY-SA 4.0." The repo has `codegen`/`generated` folders, lists 1.6.x as fully supported, and was last pushed 2026-10-26. — [GitHub: colecrouter/stardew-save-editor LICENSE.md](https://github.com/colecrouter/stardew-save-editor/blob/main/LICENSE.md)
- Other small data repos: kronosta/stardew-data ("a modding resource… for modders to write Content Patcher…", no licence); rbolt13/StardewData (R package, MIT, last pushed 2024); polarstoat/stardew-crop-data ("Parses Stardew Valley data files, extracting crop and seed data as JSON"). — `gh search repos "stardew data"`; [polarstoat/stardew-crop-data](https://github.com/polarstoat/stardew-crop-data)
- **Openly redistributed raw content and code.** Huu-Yuu/StardewValley-Assets says it collects "all the image resources in the game" under an MIT label. Dannode36/StardewValleyDecompiled ("Stardew Valley 1.6 decompiled to .NET 6", 82 stars, no licence) and veywrn/StardewValley ("Decompiled Stardew Valley", 339 stars) are both public. — `gh search repos stardew`; [Dannode36/StardewValleyDecompiled](https://github.com/Dannode36/StardewValleyDecompiled)
- **Known takedowns.** GitHub's public DMCA repo has two Stardew notices from July 2016. Both target repositories of "decompiled source code for Stardew Valley" (klukule/stardew-valley-sourcecode and a fork, kazuyabr/stardew-valley-sourcecode). The notice reads: "They've gone ahead and decompiled a commercial game's source code and made it public via Github. It should definitely be removed." The sender's name is redacted. — [github/dmca 2016-07-11-StardewValley.md](https://github.com/github/dmca/blob/master/2016/2016-07-11-StardewValley.md); [github/dmca 2016-07-20-Stardew.md](https://github.com/github/dmca/blob/master/2016/2016-07-20-Stardew.md)

### Inferences
- "Tolerated" seems to mean "not enforced". The only takedowns found target *decompiled source code*, not data JSON or sprites. Decompiled-code repos still exist today, so enforcement looks rare and sporadic, not absent. Copying that risk would be imprudent.
- Derived, fact-level JSON under MIT (stardew.app's model) is the most common pattern and has no takedown history that I could find. Bundling sprites under a "fair use" claim (the save editor) is common but legally weaker.

### Gaps
- I found no DMCA notices after 2016, and none against data-JSON or sprite repos. Absence in the GitHub DMCA repo doesn't rule out takedowns on other hosts.
- I couldn't tell who sent the 2016 notices (ConcernedApe or the then-publisher Chucklefish), because the name is redacted.

## Save-file parsers and libraries

### Takeaway
No widely adopted, versioned 1.6 save-parsing *library* exists in Python, Rust or C#. Mature parsers live inside apps (Stardew Checkup and Stardew Predictor in JS, the Stardew Save Editor in TS) or in a single small npm package. The 1.6 save is plain .NET `XmlSerializer` XML, compressed on Switch, so most projects write their own reader.

### Cited Findings
- **Stardew Checkup** (MouseyPounds). JavaScript plus jQuery and pako, MIT, 254 stars. v5.0 (2024-03-19) added "Support for Stardew Valley 1.6," and v5.0.5 (2024-04-18) added compressed Switch saves and 1.6.4 fixes. The last push was 2024-05-09, so it is dormant. "Most changed & added content from version 1.6 is supported." — [GitHub: MouseyPounds/stardew-checkup](https://github.com/MouseyPounds/stardew-checkup)
- **Stardew Predictor** (MouseyPounds). MIT, uses BigInteger.js and xxHash to reproduce the game's RNG. v5.0.0 (2024-03-26) supports 1.6 ("All changed & added content from version 1.6 should be supported"). Last pushed 2026-01-25. — [GitHub: MouseyPounds/stardew-predictor](https://github.com/MouseyPounds/stardew-predictor)
- **Stardew Save Editor** (colecrouter). TypeScript/Svelte, in-browser, 1.6.x "fully supported," 1.5.x dropped, actively maintained (pushed 2026-10-26). — [GitHub: colecrouter/stardew-save-editor](https://github.com/colecrouter/stardew-save-editor)
- **stardew-valley-data** (npm). MIT, `parseSaveFile(xml)` returns player data, inventory, friendships and progress. 1.6 coverage isn't stated. — [GitHub: chiefpansancolt/stardew-valley-data](https://github.com/chiefpansancolt/stardew-valley-data)
- **stardewsavestructures** (scriptsforweirdos). GPL-3.0, a reference for the save's structure, not a parser. It includes a 1.6 multiplayer save layout taken from a fresh vanilla save on v1.6.8. — [GitHub: scriptsforweirdos/stardewsavestructures](https://github.com/scriptsforweirdos/stardewsavestructures)
- Other repos, mostly old or proof-of-concept: Sketchy502/SDV-Summary (Python, no licence); nictuku/stardew-rocks (Go, Apache-2.0); cheshire137/svtools (Go, MIT, WIP); beeradmoore/StardewValleySaveEditor (C#, MIT); LeifT/StardewValleySave (C#, last pushed 2017); gucci-on-fleek/Stardew-Valley-Item-Finder (JS, converts any save "into a more basic XML file," last pushed 2024-11). — `gh search repos "stardew valley save"`; [Item Finder](https://github.com/gucci-on-fleek/Stardew-Valley-Item-Finder)

### Inferences
- A save-driven planner should keep its own tolerant XML reader that ignores unknown elements, versioned against the save's `gameVersion` field. Stardew Checkup and Predictor take this approach, gating 1.6 features on detected version, and it has survived several patches. Checkup's MIT JS code is a good reference for field paths.
- There is no maintained PyPI or crates.io library worth depending on, so a dependency on any of these adds risk without much benefit.

### Gaps
- I didn't check PyPI or crates.io directly. GitHub search found no Python or Rust 1.6 save library of note.
- SMAPI uses the game's own `SaveGame` serializer at runtime, and I found no standalone SMAPI Toolkit save reader to reuse outside the game.

## Official Stardew Valley Wiki content licence

### Takeaway
Wiki text is CC BY-NC-SA 3.0 Unported, except developer-owned images, art and lore, which remain ConcernedApe's. Bare facts such as numbers, ids and prices are generally not copyrightable, but copying wiki *text or tables wholesale* brings in attribution, non-commercial and share-alike duties. Those duties clash with permissive licences like MIT unless the material is kept separate and labelled, as the save editor does.

### Cited Findings
- The Copyrights page says: "This sites content is protected under Creative Commons license - Attribution-NonCommercial-ShareAlike 3.0 Unported (CC BY-NC-SA 3.0)." This is a search-snippet quote; the page itself was blocked. — [Wiki: Stardew Valley Wiki:Copyrights](https://stardewvalleywiki.com/Stardew_Valley_Wiki:Copyrights)
- The About page says the licence covers all wiki content "with the exception of developer-owned images, art and lore," and that Stardew Valley content and materials are trademarks and copyrights of ConcernedApe. — [Wiki: About](https://www.stardewvalleywiki.com/Stardew_Valley_Wiki%3AAbout)
- A wiki file page says game screenshots, textures and audio do "not fall under the Stardew Valley Wiki's Terms of Service but is freely usable on this wiki." So the CC licence does not extend to game art. — [Wiki: File:Stardewbackground.png](https://stardewvalleywiki.com/File:Stardewbackground.png)
- The wiki also appears at wiki.stardewvalley.net, ConcernedApe's domain, which hosts ConcernedApe's privacy policy. — [wiki.stardewvalley.net Privacy policy](https://wiki.stardewvalley.net/Stardew_Valley_Wiki:Privacy_policy)
- Precedent: the save editor keeps wiki-derived text in separate files with a per-file notice, "villager descriptions © Stardew Valley Wiki contributors, licensed under CC BY-NC-SA 3.0," and the Stardew Modding Wiki (stardewmodding.wiki.gg) material as CC BY-SA 4.0. — [colecrouter/stardew-save-editor LICENSE.md](https://github.com/colecrouter/stardew-save-editor/blob/main/LICENSE.md)
- Stardew Checkup's changelog shows it *links* to the wiki ("Wiki links for social summary," "Added wiki links for needed item lists") rather than copying from it. — [MouseyPounds/stardew-checkup README](https://github.com/MouseyPounds/stardew-checkup)

### Inferences
- Linking to wiki pages is the safest pattern. Using facts (prices, days to grow, gift-taste ids) re-derived from the user's own extracted data avoids the wiki licence entirely.
- If wiki prose or curated tables are copied, keep them in a separate data file under CC BY-NC-SA 3.0 with attribution. NC blocks commercial use of that file, and share-alike may extend to adaptations of it. Under CC 3.0, whether a database of facts is covered is murkier than under 4.0 (sui generis database rights are mostly a 4.0 matter). This is legal uncertainty worth flagging.

### Gaps
- I couldn't read the full Copyrights page (Cloudflare), so attribution wording and any exceptions beyond the snippets are unconfirmed.
- The Stardew Modding Wiki's (wiki.gg) licence is confirmed only second-hand, as CC BY-SA 4.0 via the save editor's notice. I couldn't fetch the site.

## ConcernedApe's official stance on fan content, mods and tools

### Takeaway
There is no published fan-content policy and no game EULA clause that I could find covering mods or decompiling. ConcernedApe's published Terms of Use cover only his websites and services, and they assert trademark rights in "ConcernedApe™" and "Stardew Valley®". In practice he tolerates and accommodates modding (1.6 was largely a modding-framework update), and the community tools named above (SMAPI, Checkup, Predictor, stardew.app) have run openly for years. The only documented enforcement is the 2016 takedowns of decompiled source code.

### Cited Findings
- The Terms of Use (effective 2018-12-14) "govern your use of our websites, including stardewvalley.net and its subdomains." They say "ConcernedApe™, Stardew Valley®, and related design and composite marks are trademarks of ConcernedApe LLC. You must not use such marks without the prior written permission of the Company." Site material is for "personal, non-commercial use only," and you must not link "in such a way as to suggest any form of association, approval, or endorsement." They don't mention mods, reverse engineering or fan creations. — [stardewvalley.net/terms](https://www.stardewvalley.net/terms/)
- The stardewvalleypc.com "Terms of Use / EULA" that bans decompiling belongs to an *unaffiliated fan website*, not ConcernedApe. Don't cite it as official. — [stardewvalleypc.com](https://stardewvalleypc.com/terms-use-eula)
- ConcernedApe publicly took the blame for a patch that broke mods and said he would "release fewer, large patches" in future. This shows he is mindful of mod compatibility; I saw only the headline. — [GamesRadar](https://www.gamesradar.com/games/simulation/i-accept-the-blame-stardew-valley-creator-concernedape-address-broken-mods-after-recent-patch-says-he-will-release-fewer-large-patches-in-future/)
- A primary aim of 1.6 was to support adding new objects through a single unified data format, which is moddability. — [Fanlore: Stardew Valley](https://fanlore.org/wiki/Stardew_Valley)
- Community tools are promoted on the *official* forums. Stardew Predictor asks users to report bugs at forums.stardewvalley.net ("Web Apps: Stardew Checkup, Predictor and Fair Helper" thread). — [MouseyPounds/stardew-predictor README](https://github.com/MouseyPounds/stardew-predictor); [forum thread](https://forums.stardewvalley.net/threads/web-apps-stardew-checkup-predictor-and-fair-helper.28393/)
- A fan Tumblr post claims ConcernedApe has not permitted fan *merchandise*. It is second-hand and unverified. — [Tumblr: joja-hotline](https://www.tumblr.com/joja-hotline/149713143100/fanmerch-of-stardew-valley)
- DMCA takedowns of decompiled source: see the earlier section. — [github/dmca 2016](https://github.com/github/dmca/blob/master/2016/2016-07-11-StardewValley.md)

### Inferences
- "Stardew Valley" is a registered trademark, so the app shouldn't use it as the product name or logo. Use descriptive phrasing such as "a planner for Stardew Valley" with a "not affiliated with or endorsed by ConcernedApe" disclaimer. That is the standard nominative-use norm and matches the Terms' warning against implied endorsement.
- Absent a fan-content policy, the safe norm comes from what has never drawn action: tools that read the user's own save and data, link to the wiki, and publish their own code and fact-level derived data.

### Gaps
- I didn't find the game's own EULA as shown on Steam or GOG, if one exists, so I can't say whether it has a reverse-engineering clause.
- I found no direct ConcernedApe statement (tweet or interview) explicitly blessing third-party tools or datasets. The Nexus Mods policies weren't reviewed (out of call budget).

## Practical guidance: commonly safe vs not

### Takeaway
The working consensus, inferred from practice rather than any official policy, ranks options from safe to risky:
1. Your own code, plus reading the user's own save and their locally extracted game data. Safest.
2. Facts, ids and numbers republished as derived JSON. Widely done under MIT with no enforcement seen.
3. Wiki text or tables. Allowed with CC BY-NC-SA attribution and kept separate.
4. Game sprites and verbatim game strings. Common but resting on fair-use claims.
5. Raw `Content/*.xnb` or unpacked files, or decompiled C#. Clearly not OK to redistribute. Decompiled code is the only category with documented takedowns.

### Cited Findings
- The derived-JSON-from-locally-extracted-content workflow is used by stardew.app (MIT). — [stardew.app scripts/content README](https://github.com/communitycenter/stardew.app/tree/main/scripts/content)
- Explicit carve-outs for game assets ("used under fair use… remain the property of their respective owners") and for wiki text under its CC licence. — [colecrouter/stardew-save-editor LICENSE.md](https://github.com/colecrouter/stardew-save-editor/blob/main/LICENSE.md)
- Decompiled code drew DMCA takedowns. — [github/dmca](https://github.com/github/dmca/blob/master/2016/2016-07-20-Stardew.md)
- Game art isn't covered by the wiki's CC licence. — [Wiki: About](https://www.stardewvalleywiki.com/Stardew_Valley_Wiki%3AAbout)
- Trademark use needs permission, and you must not imply endorsement. — [stardewvalley.net/terms](https://www.stardewvalley.net/terms/)

### Inferences
- For this planner:
  - Ship no game files, sprites or decompiled code.
  - Read `Data/*.json` from the user's own StardewXnbHack output, or ship only a minimal hand-written table of facts such as ids, prices and days, with code comments citing where each number came from.
  - Show item names read from the user's extracted `Strings`/`Data` at runtime, not hard-coded game text.
  - Link to wiki pages instead of copying prose.
  - Add a non-affiliation disclaimer and avoid the logo.
- Where game logic has to be re-implemented (RNG, growth rules), describing behaviour in your own code is the norm, as Stardew Predictor does. Pasting decompiled code is not.
- Short game strings (item names) are in a grey area. They are probably not protectable individually, but a full verbatim dump of `Strings/*` is closer to redistributing game files.

### Gaps
- No court ruling or official ConcernedApe guidance draws these lines. They are community practice, and outcomes depend on jurisdiction: US fair use differs from UK fair dealing, and the user is UK-based.
